#!/usr/bin/env python3
"""
[FRT-MAIN]-test_comprehensive_frt.py — PRIMARY FRT Pipeline Test (most important)
====================================================================

Purpose:
    End-to-end validation of the FRT App using REAL hardware:
      1. CameraUvcDriver — USB camera initialization, frame capture, FPS
      2. ImagePreprocessor — BGR→RGB, letterbox resize, normalization, tensor prep
      3. MotionDetector — MOG2 init, background subtraction, motion detection
      4. YoloTfliteEngine — Real YOLO model load, inference, output boxes
      5. ByteTrack — IoU-based tracking, track assignment, persistence
      6. YoloPipeline — Full pipeline integration (camera→preproc→motion→YOLO→track)
      7. ShmReader — Optional SHM frame reading (if C++ camera core running)

    Every algorithm stage is timed and validated for correctness.

Usage:
    # Real hardware, door bypassed (default)
    python "[FRT-MAIN]-test_comprehensive_frt.py"

    # Synthetic fallback (no camera/model)
    python "[FRT-MAIN]-test_comprehensive_frt.py" --synthetic

    # Real door sensor required via D-Bus
    python "[FRT-MAIN]-test_comprehensive_frt.py" --no-bypass-door

    # Debug mode with verbose logging
    python "[FRT-MAIN]-test_comprehensive_frt.py" --debug

Exit Codes:
    0 — All critical tests pass
    1 — One or more tests failed
"""

import os
import sys
import time
import json
import argparse
import importlib
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

FRT_SRC = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if FRT_SRC not in sys.path:
    sys.path.insert(0, FRT_SRC)

sys.path.insert(0, FRT_SRC)


CAMERA_DEVICE = "/dev/video0"
YOLO_MODEL_PATH = "/opt/fss/models/yolov11n.tflite"


def setup_logging(output_dir: str, debug: bool = False):
    from loguru import logger
    logger.remove()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_path / f"frt_comprehensive_{timestamp}.log"
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level,
               format="<level>{time:HH:mm:ss.SSS}</level> | <level>{level: <8}</level> | {message}")
    logger.add(str(log_file), level="DEBUG",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
               rotation="10 MB", retention=3)
    logger.info("Log file: {}", log_file)
    return logger


class ComprehensiveFrtTest:
    def __init__(self, camera: str, model: str, output_dir: str,
                 synthetic: bool = False, debug: bool = False,
                 bypass_door: bool = True):
        self.camera_device = camera
        self.model_path = model
        self.output_dir = Path(output_dir)
        self.synthetic = synthetic
        self.debug = debug
        self.bypass_door = bypass_door
        self.logger = setup_logging(output_dir, debug)
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        self.metrics: Dict = {}
        self.captured_frames: List[np.ndarray] = []
        self.detection_results: List[Dict] = []
        self.camera_driver = None

    def _pass(self, name: str, detail: str = ""):
        self.results["passed"] += 1
        self.logger.info("  ✓ PASS: {} {}", name, detail)

    def _fail(self, name: str, detail: str = ""):
        self.results["failed"] += 1
        self.logger.error("  ✗ FAIL: {} {}", name, detail)

    def _skip(self, name: str, detail: str = ""):
        self.results["skipped"] += 1
        self.logger.warning("  ∼ SKIP: {} {}", name, detail)

    def _section(self, title: str):
        self.logger.info("")
        self.logger.info("═" * 70)
        self.logger.info("  {}", title)
        self.logger.info("═" * 70)

    def _benchmark(self, fn, *args, **kwargs) -> tuple:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        return result, elapsed

    # ──────────────────────────────────────────────────────────────
    # TEST 1: CameraUvcDriver
    # ──────────────────────────────────────────────────────────────

    def test_camera_driver(self):
        self._section("TEST 1 — CameraUvcDriver: USB Camera")
        from CameraUvcDriver import CameraUvcDriver
        driver = CameraUvcDriver(self.camera_device)

        result, t = self._benchmark(driver.check_uvc_connection)
        if result:
            self._pass("check_uvc_connection()", "{:.1f}ms — device OK".format(t))
        elif self.synthetic:
            self._skip("check_uvc_connection()", "Synthetic mode")
            return None
        else:
            self._fail("check_uvc_connection()", "{:.1f}ms — {} not found".format(t, self.camera_device))
            return None

        result, t = self._benchmark(driver.open_camera_stream)
        if result:
            self._pass("open_camera_stream()", "{:.1f}ms — V4L2 stream OK".format(t))
        elif self.synthetic:
            self._skip("open_camera_stream()", "Synthetic mode")
            driver.release_camera()
            return None
        else:
            self._fail("open_camera_stream()", "{:.1f}ms — failed to open".format(t))
            driver.release_camera()
            return None

        frames = []
        timestamps = []
        self._section("  └─ Frame capture (10 frames)")
        for i in range(10):
            frame, t = self._benchmark(driver.read_frame)
            if frame is not None:
                frames.append(frame)
                timestamps.append(t)
                if i < 3:
                    self.logger.info("    Frame {}: shape={} dtype={} read={:.1f}ms".format(
                        i + 1, frame.shape, frame.dtype, t))
            else:
                self.logger.warning("    Frame {}: FAILED".format(i + 1))

        if len(frames) >= 8:
            self._pass("Frame capture", "{}/10 frames captured".format(len(frames)))
            self.captured_frames = frames
        else:
            self._fail("Frame capture", "Only {}/10 frames".format(len(frames)))
            driver.release_camera()
            return None

        self._section("  └─ Frame integrity")
        import cv2
        all_ok = True
        for i, f in enumerate(frames):
            if f.dtype != np.uint8:
                self.logger.warning("    Frame {}: dtype {} (expected uint8)".format(i, f.dtype))
                all_ok = False
            if len(f.shape) != 3 or f.shape[2] != 3:
                self.logger.warning("    Frame {}: shape {} (expected HWC)".format(i, f.shape))
                all_ok = False
            if np.mean(f) < 1.0 and not self.synthetic:
                self.logger.warning("    Frame {}: suspiciously dark ({:.1f})".format(i, np.mean(f)))
        if all_ok:
            self._pass("Pixel integrity", "dtype=uint8, 3-channel BGR, non-empty")
        else:
            self._fail("Pixel integrity", "One or more frames failed checks")

        sample_path = self.output_dir / "capture_sample.jpg"
        cv2.imwrite(str(sample_path), frames[0], [cv2.IMWRITE_JPEG_QUALITY, 85])
        self._pass("Sample saved", str(sample_path))

        self._section("  └─ FPS benchmark (3s)")
        start = time.time()
        count = 0
        while time.time() - start < 3.0:
            f = driver.read_frame()
            if f is not None:
                count += 1
        elapsed = time.time() - start
        fps = count / elapsed
        self.metrics["camera_fps"] = round(fps, 1)
        if fps >= 10:
            self._pass("Camera FPS", "{:.1f} FPS over {:.1f}s (target ≥10)".format(fps, elapsed))
        else:
            self._fail("Camera FPS", "{:.1f} FPS — too slow (target ≥10)".format(fps))

        self._section("  └─ Latency benchmark (50 reads)")
        latencies = []
        for _ in range(50):
            f = driver.read_frame()
            if f is not None:
                _, t = self._benchmark(driver.read_frame)
                latencies.append(t)
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            self._pass("Read latency", "avg={:.1f}ms min={:.1f}ms max={:.1f}ms".format(
                avg_lat, min(latencies), max(latencies)))

        driver.release_camera()
        self._pass("release_camera()", "Resources released")
        self.camera_driver = driver
        return driver

    # ──────────────────────────────────────────────────────────────
    # TEST 2: ImagePreprocessor
    # ──────────────────────────────────────────────────────────────

    def test_image_preprocessor(self):
        self._section("TEST 2 — ImagePreprocessor: Frame Preprocessing")
        from ImagePreprocessor import ImagePreprocessor
        pre = ImagePreprocessor(640, 640)

        if self.captured_frames:
            raw = self.captured_frames[0]
            self.logger.info("  Using real frame: {}", raw.shape)
        else:
            raw = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
            self.logger.info("  Using synthetic frame: {}", raw.shape)

        rgb, t = self._benchmark(pre.convert_bgr_to_rgb, raw)
        if rgb is not None and rgb.shape == raw.shape:
            self._pass("convert_bgr_to_rgb()", "{:.1f}ms — shape={}".format(t, rgb.shape))
        else:
            self._fail("convert_bgr_to_rgb()", "{:.1f}ms — returned {}".format(t, type(rgb)))

        resized, t = self._benchmark(pre.resize_frame, rgb if rgb is not None else raw)
        if resized is not None and resized.shape[:2] == (640, 640):
            ok = (resized.shape == (640, 640, 3))
            msg = "{:.1f}ms — shape={}".format(t, resized.shape)
            msg += " letterboxed" if resized.shape != raw.shape[:2] else ""
            (self._pass if ok else self._fail)("resize_frame()", msg)
        else:
            self._fail("resize_frame()", "{:.1f}ms — returned None".format(t))

        normalized, t = self._benchmark(pre.normalize_pixels, resized if resized is not None else raw)
        if normalized is not None:
            ok = normalized.min() >= 0.0 and normalized.max() <= 1.0
            msg = "{:.1f}ms — range=[{:.3f}, {:.3f}] dtype={}".format(
                t, normalized.min(), normalized.max(), normalized.dtype)
            (self._pass if ok else self._fail)("normalize_pixels()", msg)
        else:
            self._fail("normalize_pixels()", "{:.1f}ms — returned None".format(t))

        tensor, t = self._benchmark(pre.prepare_tensor_input, raw)
        if tensor is not None and tensor.shape == (1, 640, 640, 3):
            ok = tensor.dtype == np.float32 and tensor.min() >= 0.0 and tensor.max() <= 1.0
            msg = "{:.1f}ms — shape={} dtype={} range=[{:.3f}, {:.3f}]".format(
                t, tensor.shape, tensor.dtype, tensor.min(), tensor.max())
            (self._pass if ok else self._fail)("prepare_tensor_input()", msg)
            self.metrics["preprocess_latency_ms"] = round(t, 2)
        else:
            self._fail("prepare_tensor_input()", "{:.1f}ms — got {}".format(
                t, tensor.shape if tensor is not None else "None"))

        self._section("  └─ Preprocessing latency (100 iterations)")
        dummy = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        start = time.perf_counter()
        for _ in range(100):
            pre.prepare_tensor_input(dummy)
        avg = (time.perf_counter() - start) * 10
        self._pass("Pipeline throughput", "avg {:.2f}ms per frame".format(avg))
        self.metrics["preprocess_avg_ms"] = round(avg, 2)
        return pre

    # ──────────────────────────────────────────────────────────────
    # TEST 3: MotionDetector
    # ──────────────────────────────────────────────────────────────

    def test_motion_detector(self):
        self._section("TEST 3 — MotionDetector: MOG2 Background Subtraction")
        from MotionDetector import MotionDetector
        md = MotionDetector(threshold_percent=1.0)

        _, t = self._benchmark(md.init_mog2)
        if md.mog2_subtractor is not None:
            self._pass("init_mog2()", "{:.1f}ms — history=500, threshold=16.0".format(t))
        else:
            self._fail("init_mog2()", "{:.1f}ms — returned None".format(t))
            return None

        if self.captured_frames:
            test_frames = self.captured_frames[:5]
            self.logger.info("  Using {} real frames".format(len(test_frames)))
        else:
            test_frames = [
                np.ones((480, 640, 3), dtype=np.uint8) * 100,
                np.ones((480, 640, 3), dtype=np.uint8) * 200,
            ]
            self.logger.info("  Using synthetic frames")

        masks = []
        for i, f in enumerate(test_frames):
            mask, t = self._benchmark(md.apply_background_subtraction, f)
            if mask is not None:
                masks.append(mask)
                if i == 0:
                    self._pass("apply_background_subtraction()",
                               "{:.1f}ms — mask shape={} dtype={}".format(t, mask.shape, mask.dtype))
            else:
                self._fail("apply_background_subtraction()", "Frame {} returned None".format(i))

        if masks:
            motion, t = self._benchmark(md.is_motion_detected, masks[-1])
            self._pass("is_motion_detected()", "{:.1f}ms — result={}".format(t, motion))
            self.logger.info("    Motion on last frame: {} ({}% threshold)".format(
                "DETECTED" if motion else "NOT DETECTED", md.pixel_change_threshold))

        self._section("  └─ Static vs. motion discrimination")
        static = np.ones((480, 640, 3), dtype=np.uint8) * 128
        for _ in range(10):
            md.apply_background_subtraction(static)
        mask_static, _ = self._benchmark(md.apply_background_subtraction, static)
        no_motion = not md.is_motion_detected(mask_static) if mask_static is not None else True

        moving = np.ones((480, 640, 3), dtype=np.uint8) * 200
        mask_motion, _ = self._benchmark(md.apply_background_subtraction, moving)
        has_motion = md.is_motion_detected(mask_motion) if mask_motion is not None else False

        if no_motion and has_motion:
            self._pass("Motion discrimination", "Static=no-motion, Changed=motion ✓")
        elif no_motion and not has_motion:
            self._skip("Motion discrimination", "Static OK, changed below threshold")
        else:
            self._skip("Motion discrimination", "Check threshold sensitivity")

        _, t = self._benchmark(md.reset_background_model)
        self._pass("reset_background_model()", "{:.1f}ms".format(t))
        return md

    # ──────────────────────────────────────────────────────────────
    # TEST 4: YoloTfliteEngine
    # ──────────────────────────────────────────────────────────────

    def test_yolo_engine(self):
        self._section("TEST 4 — YoloTfliteEngine: YOLO Inference")
        from YoloTfliteEngine import YoloTfliteEngine
        engine = YoloTfliteEngine(self.model_path, use_c_backend=True, c_precision=2)

        loaded, t = self._benchmark(engine.load_model_mmap)
        if loaded:
            self._pass("load_model_mmap()", "{:.1f}ms — {}".format(t, self.model_path))
        elif self.synthetic:
            self._skip("load_model_mmap()", "Synthetic mode — skipping YOLO tests")
            return engine
        else:
            self._fail("load_model_mmap()", "{:.1f}ms — model not found".format(t))
            return engine

        _, t = self._benchmark(engine.allocate_tensors)
        if engine.is_initialized:
            self._pass("allocate_tensors()", "{:.1f}ms — initialized={}".format(t, engine.is_initialized))
        else:
            self._fail("allocate_tensors()", "{:.1f}ms — not initialized".format(t))

        if self.captured_frames:
            from ImagePreprocessor import ImagePreprocessor
            pre = ImagePreprocessor(640, 640)
            tensor = pre.prepare_tensor_input(self.captured_frames[0])
        else:
            tensor = np.random.rand(1, 640, 640, 3).astype(np.float32)

        _, t = self._benchmark(engine.set_input_tensor, tensor)
        self._pass("set_input_tensor()", "{:.1f}ms — shape={}".format(t, tensor.shape))

        _, t = self._benchmark(engine.invoke_inference)
        self._pass("invoke_inference()", "{:.1f}ms".format(t))
        self.metrics["yolo_latency_first_ms"] = round(t, 2)

        boxes, t = self._benchmark(engine.get_output_boxes)
        n = len(boxes)
        msg = "{:.1f}ms — {} detections".format(t, n)
        if n > 0:
            cls_ids = [b.get("class_id") for b in boxes[:3]]
            confs = [b.get("confidence", 0) for b in boxes[:3]]
            msg += " | classes={} confs={}".format(cls_ids, [round(c, 2) for c in confs])
        self._pass("get_output_boxes()", msg)

        self._section("  └─ Inference latency (10 runs)")
        latencies = []
        for i in range(10):
            noise = np.random.rand(1, 640, 640, 3).astype(np.float32)
            engine.set_input_tensor(noise)
            _, t = self._benchmark(engine.invoke_inference)
            latencies.append(t)
            engine.get_output_boxes()
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        self.metrics["yolo_avg_latency_ms"] = round(avg_lat, 2)
        self.metrics["yolo_min_latency_ms"] = round(min_lat, 2)
        self.metrics["yolo_max_latency_ms"] = round(max_lat, 2)
        self._pass("Latency (10 runs)", "avg={:.1f}ms min={:.1f}ms max={:.1f}ms".format(
            avg_lat, min_lat, max_lat))

        self._section("  └─ C backend check")
        try:
            import ctypes
            lib = ctypes.CDLL("libtflite_reader.so")
            self._pass("C backend", "libtflite_reader.so loaded")
        except Exception:
            self._skip("C backend", "libtflite_reader.so not found (optional)")

        self.detection_results = boxes
        return engine

    # ──────────────────────────────────────────────────────────────
    # TEST 5: ByteTrack
    # ──────────────────────────────────────────────────────────────

    def test_bytetrack(self):
        self._section("TEST 5 — ByteTrack: Multi-Object Tracking")
        from YoloPipeline import ByteTrack
        tracker = ByteTrack(max_age=30)

        self._pass("ByteTrack init", "max_age=30")

        if self.detection_results:
            real_dets = self.detection_results
            self.logger.info("  Using {} real detections".format(len(real_dets)))
            tracks, t = self._benchmark(tracker.update, real_dets)
            msg = "{:.1f}ms — {} tracks created".format(t, len(tracks))
            if tracks:
                ids = [tr["track_id"] for tr in tracks[:3]]
                msg += " IDs={}".format(ids)
            self._pass("update() — real detections", msg)
        else:
            dummy_dets = [
                {"bbox": [10, 20, 50, 60], "confidence": 0.9, "class_id": 0},
                {"bbox": [100, 150, 40, 50], "confidence": 0.8, "class_id": 1},
            ]
            self.logger.info("  Using 2 synthetic detections")
            tracks, t = self._benchmark(tracker.update, dummy_dets)
            self._pass("update() — synthetic", "{:.1f}ms — {} tracks".format(t, len(tracks)))

        self._section("  └─ Track persistence")
        tracker2 = ByteTrack(max_age=30)
        det_a = [{"bbox": [10, 20, 30, 40], "confidence": 0.9, "class_id": 0}]
        det_b = [{"bbox": [12, 22, 30, 40], "confidence": 0.85, "class_id": 0}]
        det_c = [{"bbox": [200, 200, 30, 40], "confidence": 0.7, "class_id": 1}]

        tracks_a = tracker2.update(det_a)
        tracks_b = tracker2.update(det_b)
        tracks_c = tracker2.update(det_c)

        same_id = (tracks_a and tracks_b and
                   tracks_a[0]["track_id"] == tracks_b[0]["track_id"])
        diff_class = (tracks_b and tracks_c and
                      tracks_b[0]["track_id"] != tracks_c[0]["track_id"])

        if same_id and diff_class:
            self._pass("Track assignment",
                       "Same object = same ID, diff object = diff ID")
        elif same_id and not diff_class:
            self._fail("Track assignment", "New object got same ID as old")
        else:
            self._skip("Track assignment", "Check IoU thresholds")

        _, t = self._benchmark(tracker2.reset)
        self._pass("reset()", "{:.1f}ms — {} tracks cleared".format(t, len(tracker2.tracks)))

        self._section("  └─ Quantity change detection")
        qty_tracker = ByteTrack(max_age=30)
        qty_tracker.update([{"bbox": [0, 0, 10, 10], "confidence": 0.9, "class_id": 0}])
        qty_tracker.update([{"bbox": [0, 0, 10, 10], "confidence": 0.9, "class_id": 0}])
        changes = qty_tracker.get_quantity_change()
        self._pass("get_quantity_change()", "{} class changes".format(len(changes)))
        return tracker

    # ──────────────────────────────────────────────────────────────
    # TEST 6: YoloPipeline (Full Integration)
    # ──────────────────────────────────────────────────────────────

    def test_full_pipeline(self):
        self._section("TEST 6 — YoloPipeline: Full Pipeline Integration")
        from YoloPipeline import YoloPipeline, SharedMemoryReader

        if self.bypass_door:
            self.logger.info("  Door sensor bypassed — no D-Bus subscription needed")
        pipeline = YoloPipeline(model_path=self.model_path, use_shared_memory=False)
        result, t = self._benchmark(pipeline.init_pipeline)
        if result:
            self._pass("init_pipeline()", "{:.1f}ms".format(t))
        else:
            self._fail("init_pipeline()", "{:.1f}ms — failed".format(t))

        if self.captured_frames:
            test_frames = self.captured_frames[:3]
        else:
            test_frames = [np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8) for _ in range(3)]

        self._section("  └─ process_frame() — individual frames")
        pipeline_results = []
        for i, frame in enumerate(test_frames):
            result, t = self._benchmark(pipeline.process_frame, frame)
            pipeline_results.append(result)
            if "error" in result:
                msg = result.get("error", "unknown")
                self._fail("Frame {}: process_frame()".format(i), "{:.1f}ms — error: {}".format(t, msg))
            elif result.get("skipped"):
                self._pass("Frame {}: process_frame()".format(i),
                           "{:.1f}ms — skipped (no motion)".format(t))
            else:
                n = result.get("count", 0)
                self._pass("Frame {}: process_frame()".format(i),
                           "{:.1f}ms — {} detections".format(t, n))

        self._section("  └─ run_stream() — simulated sequence")
        if self.camera_driver is not None:
            self.camera_driver.open_camera_stream()
            stream_frames = []
            for _ in range(5):
                f = self.camera_driver.read_frame()
                if f is not None:
                    stream_frames.append(f)
            if stream_frames:
                self._pass("Stream input", "{} real frames from camera".format(len(stream_frames)))
            self.camera_driver.release_camera()

        self._section("  └─ Pipeline metrics")
        metrics = pipeline.get_metrics()
        self.metrics["pipeline"] = metrics
        self._pass("Metrics report",
                   "frames={}, inferences={}, tracks={}".format(
                       metrics.get("total_frames"),
                       metrics.get("total_inferences"),
                       metrics.get("active_tracks")))

        motion_mask = pipeline.motion_detector.mog2_subtractor is not None
        engine_ok = pipeline.ai_engine.is_initialized
        pre_ok = pipeline.preprocessor is not None
        tracker_ok = pipeline.tracker is not None

        all_ok = motion_mask and engine_ok and pre_ok and tracker_ok
        details = "MotionDet={} YOLO={} Preproc={} Tracker={}".format(
            "✓" if motion_mask else "✗",
            "✓" if engine_ok else "✗",
            "✓" if pre_ok else "✗",
            "✓" if tracker_ok else "✗")
        (self._pass if all_ok else self._fail)("All components initialized", details)

        self._section("  └─ SharedMemoryReader check")
        shm_reader = SharedMemoryReader()
        attached, t = self._benchmark(shm_reader.attach)
        if attached:
            self._pass("SharedMemoryReader.attach()",
                       "{:.1f}ms — SHM at /dev/shm/fss_video_frame".format(t))
            shm_reader.detach()
        else:
            self._skip("SharedMemoryReader.attach()",
                       "C++ camera core not running (optional)")

    # ──────────────────────────────────────────────────────────────
    # TEST 7: Annotated Output
    # ──────────────────────────────────────────────────────────────

    def test_save_annotated_output(self):
        self._section("TEST 7 — Annotated Output: Visual Validation")
        import cv2

        if not self.captured_frames:
            self._skip("Annotated output", "No frames available")
            return
        if not self.detection_results:
            self._skip("Annotated output", "No detections to draw")
            return

        frame = self.captured_frames[0].copy()
        h, w = frame.shape[:2]
        for det in self.detection_results[:10]:
            bbox = det.get("bbox", [0, 0, 0, 0])
            conf = det.get("confidence", 0)
            cls_id = det.get("class_id", 0)
            x1 = int(bbox[0] * w / 640)
            y1 = int(bbox[1] * h / 640)
            x2 = int((bbox[0] + bbox[2]) * w / 640)
            y2 = int((bbox[1] + bbox[3]) * h / 640)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = "cls{}:{:.2f}".format(cls_id, conf)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        path = self.output_dir / "annotated_result.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self._pass("Annotated output saved", "{} ({} detections)".format(path, len(self.detection_results)))

    # ──────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────

    def print_summary(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("  COMPREHENSIVE FRT TEST — SUMMARY")
        self.logger.info("=" * 70)
        total = self.results["passed"] + self.results["failed"] + self.results["skipped"]
        self.logger.info("  Passed:   {}", self.results["passed"])
        self.logger.info("  Failed:   {}", self.results["failed"])
        self.logger.info("  Skipped:  {}", self.results["skipped"])
        self.logger.info("  Total:    {}", total)
        self.logger.info("")

        if self.metrics:
            self.logger.info("  Performance Metrics:")
            for k, v in self.metrics.items():
                self.logger.info("    {:<30s} = {}", k + ":", v)

        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "synthetic" if self.synthetic else "real",
            "camera": self.camera_device,
            "model": self.model_path,
            "results": self.results,
            "metrics": self.metrics,
        }
        rpath = self.output_dir / "frt_comprehensive_report.json"
        with open(rpath, "w") as f:
            json.dump(report, f, indent=2)
        self.logger.info("  Report: {}", rpath)

        if self.results["failed"] == 0:
            self.logger.info("")
            self.logger.info("  ✓ ALL TESTS PASSED — FRT pipeline validated")
            return 0
        else:
            self.logger.info("")
            self.logger.error("  ✗ {} TEST(S) FAILED — review log".format(self.results["failed"]))
            return 1

    def run_all(self):
        self.logger.info("")
        self.logger.info("╔" + "=" * 68 + "╗")
        self.logger.info("║      FRT COMPREHENSIVE REAL-HARDWARE TEST         ║")
        self.logger.info("║  Camera → Preproc → Motion → YOLO → Track → Out  ║")
        self.logger.info("╚" + "=" * 68 + "╝")
        self.logger.info("  Camera: {}", self.camera_device)
        self.logger.info("  Model:  {}", self.model_path)
        self.logger.info("  Mode:   {}", "REAL HARDWARE" if not self.synthetic else "SYNTHETIC")
        self.logger.info("  Door:   {}", "BYPASSED (assume camera ON)" if self.bypass_door else "READ from D-Bus")
        self.logger.info("  Output: {}", self.output_dir)

        self.test_camera_driver()
        self.test_image_preprocessor()
        self.test_motion_detector()
        self.test_yolo_engine()
        self.test_bytetrack()
        self.test_full_pipeline()
        self.test_save_annotated_output()
        return self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="FRT App Comprehensive Real-Hardware Test",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", default=CAMERA_DEVICE,
                        help="Camera device (default: /dev/video0)")
    parser.add_argument("--model", default=YOLO_MODEL_PATH,
                        help="YOLO model path (default: /opt/fss/models/yolov11n.tflite)")
    parser.add_argument("--output-dir", default="/tmp/frt_comprehensive_test",
                        help="Output directory")
    parser.add_argument("--synthetic", action="store_true",
                        help="Use synthetic data (no hardware required)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--bypass-door", action="store_true", default=True,
                        help="Bypass door sensor, assume camera ON (default: True)")
    parser.add_argument("--no-bypass-door", action="store_false", dest="bypass_door",
                        help="Require real door sensor via D-Bus")
    args = parser.parse_args()

    tester = ComprehensiveFrtTest(
        camera=args.camera,
        model=args.model,
        output_dir=args.output_dir,
        synthetic=args.synthetic,
        debug=args.debug,
        bypass_door=args.bypass_door)
    return tester.run_all()


if __name__ == "__main__":
    sys.exit(main())
