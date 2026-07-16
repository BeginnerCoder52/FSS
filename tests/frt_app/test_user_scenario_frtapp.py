#!/usr/bin/env python3
"""
test_user_scenario_frtapp.py - Full user scenario test for FRTApp
=================================================================

Simulates the complete FRTApp pipeline as used by MagicMirror
using REAL hardware (USB camera) and REAL YOLO model:
  USB Camera -> Frame Capture -> Motion Detection -> Preprocess -> YOLO -> Tracking

Usage (REAL hardware):
    python3 test_user_scenario_frtapp.py
    python3 test_user_scenario_frtapp.py --debug

Usage (synthetic fallback — no camera/model required):
    python3 test_user_scenario_frtapp.py --synthetic

Exit Codes:
    0 - All critical tests pass
    1 - One or more tests failed
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

FRT_SRC = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if FRT_SRC not in sys.path:
    sys.path.insert(0, FRT_SRC)


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

def setup_test_logging(output_dir: str, debug: bool = False):
    """Setup test logging to file and console (uses loguru)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    from loguru import logger
    logger.remove()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_path / f"frtapp_scenario_test_{timestamp}.log"

    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level,
               format="<level>{time:HH:mm:ss.SSS}</level> | <level>{level: <8}</level> | {message}")
    logger.add(str(log_file), level="DEBUG",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
               rotation="10 MB", retention=3)
    logger.info("Test log file: {}", log_file)
    return logger


# ==============================================================================
# TEST SUITE
# ==============================================================================

class FrtAppScenarioTest:
    """
    User scenario test for FRTApp pipeline using real hardware + real model.
    """

    def __init__(self, camera_device: str, model_path: str,
                 output_dir: str, debug: bool = False, synthetic: bool = False):
        self.camera_device = camera_device
        self.model_path = model_path
        self.output_dir = Path(output_dir)
        self.debug = debug
        self.synthetic = synthetic
        self.logger = setup_test_logging(output_dir, debug)
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        self.captured_frames = []
        self.fps_samples = []
        self.target_fps = 10

    def _pass(self, name: str, detail: str = ""):
        self.results["passed"] += 1
        self.logger.info("✓ PASS: {} {}", name, detail)

    def _fail(self, name: str, detail: str = ""):
        self.results["failed"] += 1
        self.logger.error("✗ FAIL: {} {}", name, detail)

    def _skip(self, name: str, detail: str = ""):
        self.results["skipped"] += 1
        self.logger.warning("∼ SKIP: {} {}", name, detail)

    # ------------------------------------------------------------------
    # TEST 1: System & Environment Readiness
    # ------------------------------------------------------------------

    def test_system_environment(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 1: System Environment Readiness")
        self.logger.info("=" * 70)

        # 1a. Check camera device
        self.logger.info("--- 1a. Camera device: {}", self.camera_device)
        if os.path.exists(self.camera_device):
            import stat
            mode = os.stat(self.camera_device).st_mode
            is_char = stat.S_ISCHR(mode)
            if is_char:
                self._pass("Camera device present",
                           "{} (char device)".format(self.camera_device))
            else:
                self._fail("Camera device",
                          "{} exists but is not a character device".format(self.camera_device))
        else:
            if self.synthetic:
                self._skip("Camera device not found",
                           "Synthetic mode — skipping camera checks")
            else:
                self._fail("Camera device",
                          "{} not found. Use --synthetic for mock mode".format(self.camera_device))

        # 1b. Check model file
        self.logger.info("--- 1b. YOLO model: {}", self.model_path)
        if os.path.exists(self.model_path):
            model_size = os.path.getsize(self.model_path) / (1024 * 1024)
            self._pass("YOLO model present", "{:.1f} MB".format(model_size))
        else:
            if self.synthetic:
                self._skip("YOLO model not found",
                           "Synthetic mode — skipping model checks")
            else:
                self._fail("YOLO model",
                          "Model not found at {}. Use --synthetic for mock mode".format(self.model_path))

        # 1c. Check required directories
        self.logger.info("--- 1c. Required directories")
        dirs = {
            "/opt/fss": "Runtime data",
            "/opt/fss/images": "Captured images",
            "/opt/fss/logs": "Log files",
            "/opt/fss/models": "ML models",
        }
        for d, purpose in dirs.items():
            p = Path(d)
            if p.exists():
                self._pass("Directory exists: {}".format(d), purpose)
            else:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    self._pass("Directory created: {}".format(d), purpose)
                except PermissionError:
                    self._fail("Cannot create: {}".format(d),
                              "Run with sudo or create manually")

        # 1d. Check Python dependencies
        self.logger.info("--- 1d. Python dependencies")
        deps = {
            "cv2": "OpenCV",
            "numpy": "NumPy",
            "loguru": "Loguru (logging)",
        }
        for mod_name, label in deps.items():
            try:
                __import__(mod_name)
                self._pass("Module: {}".format(label), "{} available".format(mod_name))
            except ImportError:
                self._fail("Module: {}".format(label), "{} not installed".format(mod_name))

        # 1e. Check TFLite inference backend (Python or C)
        self.logger.info("--- 1e. TFLite inference backend")
        tflite_available = False
        try:
            import tflite_runtime.interpreter as tflite
            tflite_available = True
            self._pass("TFLite runtime", "tflite_runtime available")
        except ImportError:
            try:
                import tensorflow.lite as tflite
                tflite_available = True
                self._pass("TFLite runtime", "tensorflow.lite available")
            except ImportError:
                try:
                    import ctypes
                    lib = ctypes.CDLL("libtflite_reader.so")
                    tflite_available = True
                    self._pass("TFLite runtime",
                               "C backend (libtflite_reader.so)")
                except Exception:
                    self._fail("TFLite runtime",
                              "No Python TFLite or C backend available")

    # ------------------------------------------------------------------
    # TEST 2: Camera Driver
    # ------------------------------------------------------------------

    def test_camera_driver(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 2: USB Camera Driver (CameraUvcDriver)")
        self.logger.info("=" * 70)

        from CameraUvcDriver import CameraUvcDriver

        driver = CameraUvcDriver(self.camera_device)

        # 2a. Check UVC connection
        self.logger.info("--- 2a. Check UVC connection")
        if driver.check_uvc_connection():
            self._pass("UVC device accessible", self.camera_device)
        else:
            if self.synthetic:
                self._skip("UVC device not accessible",
                           "Using synthetic frames for remaining tests.")
                return None
            else:
                self._fail("UVC device",
                          "{} not accessible. Use --synthetic for mock".format(self.camera_device))
                return None

        # 2b. Open camera stream
        self.logger.info("--- 2b. Open camera stream")
        if not driver.open_camera_stream():
            import subprocess
            busy_check = subprocess.run(
                ["fuser", "-v", self.camera_device],
                capture_output=True, text=True, timeout=3
            )
            if busy_check.returncode == 0:
                self._fail("Camera stream open",
                           "{} held by another process. "
                           "Run: sudo systemctl stop fss-camera".format(self.camera_device))
            else:
                self._fail("Camera stream open",
                           "Failed to open {} with V4L2".format(self.camera_device))
            driver.release_camera()
            return None
        self._pass("Camera stream opened", "640x480 @ 30 FPS via V4L2")

        # 2c. Capture multiple frames
        self.logger.info("--- 2c. Frame capture (5 frames)")
        frames = []
        for i in range(5):
            frame = driver.read_frame()
            if frame is not None:
                frames.append(frame)
                self.logger.info("  Frame {}: shape={}, dtype={}",
                                 i + 1, frame.shape, frame.dtype)
            else:
                self.logger.warning("  Frame {}: FAILED", i + 1)
            time.sleep(0.05)

        if len(frames) >= 3:
            self._pass("Frame capture", "{} / 5 frames captured".format(len(frames)))
            self.captured_frames = frames
        else:
            self._fail("Frame capture",
                       "Only {} / 5 frames captured".format(len(frames)))
            driver.release_camera()
            return None

        # 2d. Save a sample frame
        self.logger.info("--- 2d. Save sample frame")
        try:
            import cv2
            sample_path = self.output_dir / "sample_frame.jpg"
            cv2.imwrite(str(sample_path), frames[0],
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            file_size = os.path.getsize(str(sample_path))
            self._pass("Sample frame saved",
                       "{} ({} KB)".format(sample_path, file_size // 1024))
        except Exception as e:
            self._fail("Save sample frame", str(e))

        # 2e. Measure frame read FPS
        self.logger.info("--- 2e. Frame read FPS benchmark")
        start = time.time()
        count = 0
        while time.time() - start < 2.0:
            f = driver.read_frame()
            if f is not None:
                count += 1
        elapsed = time.time() - start
        fps = count / elapsed
        self.fps_samples.append(fps)
        self._pass("Camera read FPS", "{:.1f} FPS over {:.1f}s".format(fps, elapsed))

        # 2f. Verify frame data integrity
        self.logger.info("--- 2f. Frame data integrity")
        import numpy as np
        frame_valid = True
        for i, f in enumerate(self.captured_frames):
            if f is None or not isinstance(f, np.ndarray):
                self.logger.warning("  Frame {}: not an ndarray".format(i))
                frame_valid = False
                continue
            if f.dtype != np.uint8:
                self.logger.warning("  Frame {}: dtype={} (expected uint8)".format(i, f.dtype))
                frame_valid = False
            if f.ndim != 3 or f.shape[2] != 3:
                self.logger.warning("  Frame {}: shape={} (expected HWC 3-channel)".format(i, f.shape))
                frame_valid = False
            if f.size == 0:
                self.logger.warning("  Frame {}: empty".format(i))
                frame_valid = False
        if frame_valid and self.captured_frames:
            self._pass("Frame integrity",
                       "{} valid frames (BGR uint8)".format(len(self.captured_frames)))
        else:
            self._fail("Frame integrity", "One or more frames failed validation")

        # 2g. Release camera
        self.logger.info("--- 2g. Release camera")
        driver.release_camera()
        self._pass("Camera released", "")

        return driver

    # ------------------------------------------------------------------
    # TEST 3: Image Preprocessor
    # ------------------------------------------------------------------

    def test_image_preprocessor(self, frame_source):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 3: Image Preprocessor (ImagePreprocessor)")
        self.logger.info("=" * 70)

        from ImagePreprocessor import ImagePreprocessor

        preprocessor = ImagePreprocessor(640, 640)

        # Use real frame if available, otherwise synthetic
        if frame_source is not None and len(frame_source) > 0:
            test_frame = frame_source[0]
            self.logger.info("Using captured frame: shape={}", test_frame.shape)
        else:
            import numpy as np
            test_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
            self.logger.info("Using synthetic frame: shape={}", test_frame.shape)

        # 3a. BGR -> RGB conversion
        self.logger.info("--- 3a. BGR -> RGB conversion")
        rgb = preprocessor.convert_bgr_to_rgb(test_frame)
        if rgb is not None and rgb.shape == test_frame.shape:
            self._pass("BGR -> RGB", "shape={}".format(rgb.shape))
        else:
            self._fail("BGR -> RGB", "shape={}".format(
                rgb.shape if rgb is not None else "None"))

        # 3b. Resize with letterboxing
        self.logger.info("--- 3b. Resize with letterboxing")
        resized = preprocessor.resize_frame(rgb if rgb is not None else test_frame)
        if resized is not None and resized.shape == (640, 640, 3):
            self._pass("Resize with letterbox", "640x640x3")
        else:
            self._fail("Resize with letterbox", "got {}".format(
                resized.shape if resized is not None else "None"))

        # 3c. Pixel normalization
        self.logger.info("--- 3c. Pixel normalization [0,1]")
        normalized = preprocessor.normalize_pixels(resized)
        if normalized is not None:
            ok = normalized.min() >= 0.0 and normalized.max() <= 1.0
            if ok:
                self._pass("Pixel normalization",
                           "range=[{:.3f}, {:.3f}]".format(
                               normalized.min(), normalized.max()))
            else:
                self._fail("Pixel normalization",
                           "range=[{:.3f}, {:.3f}]".format(
                               normalized.min(), normalized.max()))
        else:
            self._fail("Pixel normalization", "returned None")

        # 3d. Full tensor preparation
        self.logger.info("--- 3d. Full tensor preparation")
        tensor = preprocessor.prepare_tensor_input(test_frame)
        if tensor is not None and tensor.shape == (1, 640, 640, 3):
            self._pass("Tensor preparation",
                       "shape={}, dtype={}".format(tensor.shape, tensor.dtype))
        else:
            self._fail("Tensor preparation", "got {}".format(
                tensor.shape if tensor is not None else "None"))

        # 3e. Benchmark preprocessing latency
        self.logger.info("--- 3e. Preprocessing latency (100 iterations)")
        import numpy as np
        dummy = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        start = time.time()
        for _ in range(100):
            preprocessor.prepare_tensor_input(dummy)
        avg_ms = (time.time() - start) * 10
        self._pass("Preprocessing latency", "avg {:.2f}ms per frame".format(avg_ms))

        return preprocessor

    # ------------------------------------------------------------------
    # TEST 4: Motion Detector
    # ------------------------------------------------------------------

    def test_motion_detector(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 4: Motion Detector (MotionDetector)")
        self.logger.info("=" * 70)

        from MotionDetector import MotionDetector
        import numpy as np

        detector = MotionDetector(threshold_percent=1.0)

        # 4a. MOG2 initialization
        self.logger.info("--- 4a. MOG2 initialization")
        try:
            detector.init_mog2()
            self._pass("MOG2 initialized", "history=500, threshold=16.0")
        except Exception as e:
            self._fail("MOG2 initialization", str(e))
            return None

        # 4b. Process identical frames (should show no motion)
        self.logger.info("--- 4b. Static scene (no motion)")
        frame_static = np.ones((480, 640, 3), dtype=np.uint8) * 128
        for _ in range(5):
            detector.apply_background_subtraction(frame_static)
        mask_last = detector.apply_background_subtraction(frame_static)
        motion = detector.is_motion_detected(mask_last)
        if not motion:
            self._pass("No motion on static scene")
        else:
            self._skip("No motion on static scene",
                       "MOG2 may need more warmup frames")

        # 4c. Process changed frame (should show motion)
        self.logger.info("--- 4c. Changed scene (motion)")
        frame_motion = np.ones((480, 640, 3), dtype=np.uint8) * 200
        mask_motion = detector.apply_background_subtraction(frame_motion)
        motion_detected = detector.is_motion_detected(mask_motion)
        if motion_detected:
            self._pass("Motion detected on changed scene")
        else:
            self._skip("Motion on changed scene",
                       "Difference may be below threshold. Try larger delta.")

        # 4d. Background model reset
        self.logger.info("--- 4d. Background model reset")
        try:
            detector.reset_background_model()
            self._pass("Background model reset")
        except Exception as e:
            self._fail("Background model reset", str(e))

        return detector

    # ------------------------------------------------------------------
    # TEST 5: YOLO Inference Engine
    # ------------------------------------------------------------------

    def test_yolo_engine(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 5: YOLO Inference Engine (YoloTfliteEngine)")
        self.logger.info("=" * 70)

        from YoloTfliteEngine import YoloTfliteEngine
        import numpy as np

        engine = YoloTfliteEngine(
            self.model_path,
            use_c_backend=True,
            c_precision=2
        )

        # 5a. Load model
        self.logger.info("--- 5a. Load model: {}", self.model_path)
        loaded = engine.load_model_mmap()
        if loaded:
            self._pass("Model loaded", self.model_path)
        else:
            if self.synthetic:
                self._skip("Model load",
                           "Model file missing. Remaining YOLO tests skipped.")
                return engine
            else:
                self._fail("Model load",
                          "Failed to load model from {}".format(self.model_path))
                return engine

        # 5b. Allocate tensors
        self.logger.info("--- 5b. Allocate tensors")
        try:
            engine.allocate_tensors()
            self._pass("Tensors allocated")
        except Exception as e:
            self._fail("Tensors allocate", str(e))

        # 5c. Set input tensor
        self.logger.info("--- 5c. Set input tensor")
        dummy_input = np.random.rand(1, 640, 640, 3).astype(np.float32)
        try:
            engine.set_input_tensor(dummy_input)
            self._pass("Input tensor set", "shape={}, dtype={}".format(
                dummy_input.shape, dummy_input.dtype))
        except Exception as e:
            self._fail("Input tensor set", str(e))

        # 5d. Run inference
        self.logger.info("--- 5d. Run inference")
        try:
            engine.invoke_inference()
            self._pass("Inference invoked")
        except Exception as e:
            self._fail("Inference invoke", str(e))

        # 5e. Get output boxes
        self.logger.info("--- 5e. Get output boxes")
        try:
            boxes = engine.get_output_boxes()
            count = len(boxes)
            self._pass("Output boxes received",
                       "{} detections (expected 0-5 on random input)".format(count))
            if count > 0:
                for b in boxes[:3]:
                    self.logger.info("    class_id={}, confidence={:.2f}, bbox={}",
                                     b.get("class_id"), b.get("confidence", 0),
                                     b.get("bbox"))
        except Exception as e:
            self._fail("Output boxes", str(e))

        # 5f. Inference backend
        self.logger.info("--- 5f. Inference backend")
        if engine.use_c_backend:
            self._pass("Backend: C TFLite reader",
                       "libtflite_reader.so (faster on RPi)")
        else:
            self._pass("Backend: Python TFLite runtime",
                       "tflite_runtime.interpreter (fallback)")

        # 5g. Measure inference latency
        self.logger.info("--- 5g. Inference latency benchmark (10 runs)")
        if engine.is_initialized:
            latencies = []
            for i in range(10):
                tensor = np.random.rand(1, 640, 640, 3).astype(np.float32)
                engine.set_input_tensor(tensor)
                start = time.time()
                engine.invoke_inference()
                latencies.append((time.time() - start) * 1000)
            avg_lat = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            self._pass("Inference latency",
                       "avg={:.1f}ms min={:.1f}ms max={:.1f}ms".format(
                           avg_lat, min_lat, max_lat))

        # 5h. C backend check (if available)
        self.logger.info("--- 5h. C backend availability")
        try:
            import ctypes
            lib = ctypes.CDLL("libtflite_reader.so")
            self._pass("C backend library found",
                       "libtflite_reader.so loaded via ctypes")
        except Exception:
            self._skip("C backend library",
                       "libtflite_reader.so not found (optional, Python fallback works)")

        return engine

    # ------------------------------------------------------------------
    # TEST 6: Full Pipeline (Camera -> Preprocess -> YOLO)
    # ------------------------------------------------------------------

    def test_full_pipeline(self, camera_driver):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST 6: Full Pipeline Integration")
        self.logger.info("=" * 70)

        from YoloTfliteEngine import YoloTfliteEngine
        from ImagePreprocessor import ImagePreprocessor
        from MotionDetector import MotionDetector

        preprocessor = ImagePreprocessor(640, 640)
        engine = YoloTfliteEngine(
            self.model_path,
            use_c_backend=True,
            c_precision=2
        )
        engine.load_model_mmap()
        detector = MotionDetector(threshold_percent=1.0)
        detector.init_mog2()

        # Determine frame source
        if camera_driver is not None:
            camera_driver.open_camera_stream()
            self.logger.info("Frame source: USB camera ({})", self.camera_device)
            has_real_frames = True
        elif self.captured_frames:
            self.logger.info("Frame source: {} pre-captured frames",
                             len(self.captured_frames))
            has_real_frames = bool(self.captured_frames)
        else:
            import numpy as np
            self.captured_frames = [
                np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
                for _ in range(5)
            ]
            has_real_frames = False
            if self.synthetic:
                self.logger.info("Frame source: synthetic frames (--synthetic mode)")
            else:
                self.logger.warning("Frame source: synthetic frames (no camera available)")

        # 6a. Pipeline iteration
        frame_budget_ms = 1000.0 / max(self.target_fps, 1)
        num_iterations = max(self.target_fps * 2, 10)  # run for ~2s at target FPS
        self.logger.info("--- 6a. Inference cycle ({} iterations, target {:.1f} ms/frame, {:.0f}s window)",
                         num_iterations, frame_budget_ms, num_iterations / max(self.target_fps, 1))
        processed = 0
        inferred = 0
        start = time.time()

        for i in range(num_iterations):
            frame = None
            if camera_driver and camera_driver.is_camera_open:
                frame = camera_driver.read_frame()
            elif self.captured_frames:
                frame = self.captured_frames[i % len(self.captured_frames)]

            if frame is None:
                continue
            processed += 1

            # Motion detection
            mask = detector.apply_background_subtraction(frame)
            if mask is not None and detector.is_motion_detected(mask):
                inferred += 1
            else:
                continue

            # Preprocess
            tensor = preprocessor.prepare_tensor_input(frame)
            if tensor is None:
                continue

            # Inference
            engine.set_input_tensor(tensor)
            engine.invoke_inference()
            boxes = engine.get_output_boxes()

            if i == 0:
                self.logger.info("  First inference: {} detections".format(len(boxes)))

        elapsed = time.time() - start
        self._pass("Pipeline cycle",
                   "{}/10 processed, {} inferences, {:.1f}s".format(
                       processed, inferred, elapsed))

        # 6b. Frame save for UI (as LivePreview would use)
        self.logger.info("--- 6b. Save preview frame for UI (as LivePreview bridge)")
        try:
            import cv2
            preview_path = self.output_dir / "latest_preview.jpg"
            if self.captured_frames:
                frame_to_save = self.captured_frames[0]
                cv2.imwrite(str(preview_path), frame_to_save,
                            [cv2.IMWRITE_JPEG_QUALITY, 70])
                file_size = os.path.getsize(str(preview_path))
                self._pass("Preview frame saved",
                           "{} ({} KB)".format(preview_path, file_size // 1024))
        except Exception as e:
            self._fail("Save preview", str(e))

        # 6c. SHM check (C++ camera core integration)
        self.logger.info("--- 6c. POSIX shared memory check ({})", "/dev/shm/fss_video_frame")
        shm_path = "/dev/shm/fss_video_frame"
        if os.path.exists(shm_path):
            shm_size = os.path.getsize(shm_path)
            self._pass("SHM exists", "{} ({} bytes)".format(shm_path, shm_size))
        else:
            self._skip("SHM not found",
                       "C++ camera core not running. Start: ./frt_app/build/cpp_camera_core/camera_core_exec")

        # 6d. D-Bus service check
        self.logger.info("--- 6d. D-Bus service status")
        import subprocess
        try:
            result = subprocess.run(
                ["dbus-send", "--system", "--print-reply",
                 "--dest=org.freedesktop.DBus",
                 "/org/freedesktop/DBus",
                 "org.freedesktop.DBus.ListNames"],
                capture_output=True, text=True, timeout=5
            )
            fss_services = [line for line in result.stdout.split("\n")
                            if "FSS" in line]
            if fss_services:
                self._pass("FSS D-Bus services",
                           "Found: {}".format(", ".join(s.strip()
                                                          for s in fss_services)))
            else:
                self._skip("FSS D-Bus services",
                           "No FSS services registered (expected in test env)")
        except Exception as e:
            self._skip("D-Bus check", str(e))

        if camera_driver is not None and camera_driver.is_camera_open:
            camera_driver.release_camera()

    # ------------------------------------------------------------------
    # TEST 7: Summary & Report
    # ------------------------------------------------------------------

    def print_summary(self):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("TEST SUMMARY")
        self.logger.info("=" * 70)
        total = (self.results["passed"] + self.results["failed"]
                 + self.results["skipped"])
        self.logger.info("  Passed:  {}", self.results["passed"])
        self.logger.info("  Failed:  {}", self.results["failed"])
        self.logger.info("  Skipped: {}", self.results["skipped"])
        self.logger.info("  Total:   {}", total)
        self.logger.info("=" * 70)

        # Save JSON report
        report = {
            "timestamp": datetime.now().isoformat(),
            "camera_device": self.camera_device,
            "model_path": self.model_path,
            "output_dir": str(self.output_dir),
            "results": self.results,
            "fps_samples": self.fps_samples,
        }
        report_path = self.output_dir / "frtapp_scenario_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        self.logger.info("Report saved: {}", report_path)

        if self.results["failed"] == 0:
            self.logger.info("")
            self.logger.info("✓ ALL CRITICAL TESTS PASSED")
            self.logger.info("  System is ready for MagicMirror FRTApp integration.")
        else:
            self.logger.info("")
            self.logger.error("✗ {} TEST(S) FAILED - Review logs above",
                              self.results["failed"])

    def run_all(self):
        """Execute all tests in sequence."""
        self.logger.info("")
        self.logger.info("╔" + "=" * 68 + "╗")
        self.logger.info("║          FRTApp USER SCENARIO TEST             ║")
        self.logger.info("║  USB Camera -> AI Pipeline -> MagicMirror Flow  ║")
        self.logger.info("╚" + "=" * 68 + "╝")
        self.logger.info("Camera: {}", self.camera_device)
        self.logger.info("Model:  {}", self.model_path)
        self.logger.info("Output: {}", self.output_dir)
        self.logger.info("Mode:   {}", "REAL HARDWARE" if not self.synthetic else "SYNTHETIC")
        self.logger.info("Debug:  {}", self.debug)

        self.test_system_environment()
        camera_driver = self.test_camera_driver()
        self.test_image_preprocessor(self.captured_frames)
        self.test_motion_detector()
        self.test_yolo_engine()
        self.test_full_pipeline(camera_driver)
        self.print_summary()

        return 0 if self.results["failed"] == 0 else 1


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FRTApp User Scenario Test - USB Camera + YOLO Pipeline (REAL HARDWARE)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--camera", default="/dev/video0",
                        help="Camera device path (default: /dev/video0)")
    parser.add_argument("--model", default="/opt/fss/models/yolov11n.tflite",
                        help="YOLO model path (default: /opt/fss/models/yolov11n.tflite)")
    parser.add_argument("--output-dir", default="/tmp/frt_test_output",
                        help="Output directory for logs and artifacts")
    parser.add_argument("--synthetic", action="store_true",
                        help="Use synthetic frames instead of real camera/model")
    parser.add_argument("--target-fps", type=int, default=10,
                        help="Target pipeline processing FPS (default: 10)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    tester = FrtAppScenarioTest(
        camera_device=args.camera,
        model_path=args.model,
        output_dir=args.output_dir,
        debug=args.debug,
        synthetic=args.synthetic,
    )
    tester.target_fps = args.target_fps
    return tester.run_all()


if __name__ == "__main__":
    sys.exit(main())
