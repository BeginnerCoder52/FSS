#!/usr/bin/env python3
"""
live_camera_pipeline.py - Live Camera YOLO Pipeline for FRTApp Bash Test
=======================================================================

Called by: run_live_camera_test.sh

Captures ~3-5 seconds of live camera feed, runs the full FRTApp pipeline:
  USB Camera -> MOG2 Motion Detection -> Preprocess -> YOLO Inference -> ByteTrack

Outputs (all saved to OUTPUT_DIR):
  1. full_log.txt            - Complete timestamped pipeline log
  2. annotated_result.jpg    - Final frame with bounding boxes + food class labels
  3. mog2_foreground_mask.jpg - MOG2 foreground mask visualization
  4. letterbox_preview.jpg   - Letterboxed RGB frame before normalization
  5. inference_table.csv     - All detections with class_id, confidence, bbox
  6. pipeline_report.json    - Structured metrics + detection summary

Usage:
    python3 live_camera_pipeline.py [--camera /dev/video0]
                                     [--model /opt/fss/models/yolov11n.tflite]
                                     [--duration 5]
                                     [--output-dir /tmp/frt_live_test]
                                     [--debug]

Author: FSS Project Team
License: Proprietary
"""

import os
import sys
import time
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

SRC_DIR = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# ==============================================================================
# Live Camera Pipeline Runner
# ==============================================================================

class LiveCameraPipelineRunner:
    """
    Captures live camera feed, runs full FRTApp pipeline for N seconds,
    saves all algorithm visualizations and inference results.
    """

    def __init__(self, camera_device: str, model_path: str,
                 duration_sec: int, output_dir: str, debug: bool = False):
        self.camera_device = camera_device
        self.model_path = model_path
        self.duration_sec = duration_sec
        self.output_dir = Path(output_dir)
        self.debug = debug

        self.log_lines: List[str] = []
        self.detection_history: List[Dict] = []
        self.frame_count = 0
        self.inference_count = 0
        self.fps_values: List[float] = []
        self.inference_latencies: List[float] = []
        self.best_frame = None
        self.best_detections: List[Dict] = []
        self.best_confidence = 0.0
        self.all_masks: List[np.ndarray] = []
        self.all_preprocessed: List[np.ndarray] = []

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def log(self, msg: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
        line = f"[{ts}] [{level:8s}] {msg}"
        self.log_lines.append(line)
        print(line, file=sys.stderr if level == "ERROR" else sys.stdout)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def run(self) -> int:
        self.log("╔══════════════════════════════════════════════════════════╗")
        self.log("║      FRTApp LIVE CAMERA PIPELINE TEST                   ║")
        self.log("║  Camera → MOG2 → Preprocess → YOLOv11 → ByteTrack       ║")
        self.log("╚══════════════════════════════════════════════════════════╝")
        self.log(f"  Camera:   {self.camera_device}")
        self.log(f"  Model:    {self.model_path}")
        self.log(f"  Duration: {self.duration_sec}s")
        self.log(f"  Output:   {self.output_dir}")

        from CameraUvcDriver import CameraUvcDriver
        from MotionDetector import MotionDetector
        from ImagePreprocessor import ImagePreprocessor
        from YoloTfliteEngine import YoloTfliteEngine
        from YoloPipeline import ByteTrack

        # ---- STEP 1: Initialize components ----
        self.log("─── STEP 1: Component Initialization ───")

        camera = CameraUvcDriver(self.camera_device)
        if not camera.check_uvc_connection():
            self.log(f"ERROR: Camera {self.camera_device} not found", "ERROR")
            self._save_log()
            return 1

        if not camera.open_camera_stream():
            self.log(f"ERROR: Failed to open camera stream", "ERROR")
            self._save_log()
            return 1
        self.log(f"  Camera stream opened: 640x480 @ 30 FPS")

        detector = MotionDetector(threshold_percent=1.0)
        detector.init_mog2()
        self.log(f"  MOG2 initialized: history=500, threshold=16.0")

        preprocessor = ImagePreprocessor(640, 640)
        self.log(f"  Preprocessor initialized: target=640x640")

        engine = YoloTfliteEngine(self.model_path, use_c_backend=True, c_precision=2)
        if not engine.load_model_mmap():
            self.log("WARNING: YOLO model not loaded — running degraded", "WARN")
        else:
            self.log(f"  YOLO engine initialized: C_backend={engine.use_c_backend}")

        tracker = ByteTrack(max_age=30)
        self.log(f"  ByteTrack tracker initialized: max_age=30")

        # ---- STEP 2: Capture + Process loop ----
        self.log("")
        self.log("─── STEP 2: Live Capture + Inference Loop ───")
        self.log(f"  Target: ~10 FPS for {self.duration_sec}s")

        start_time = time.time()
        warmup_frames = 5
        capture_count = 0
        first_inference = True

        while True:
            elapsed = time.time() - start_time
            if elapsed >= self.duration_sec:
                break

            frame = camera.read_frame()
            if frame is None:
                time.sleep(0.03)
                continue

            capture_count += 1
            self.frame_count += 1

            # Skip first few frames for MOG2 warmup
            if capture_count <= warmup_frames:
                _ = detector.apply_background_subtraction(frame)
                continue

            fps_start = time.time()

            # STEP 2a: MOG2 Motion Detection
            mog2_start = time.time()
            motion_mask = detector.apply_background_subtraction(frame)
            mog2_time = (time.time() - mog2_start) * 1000
            has_motion = detector.is_motion_detected(motion_mask) if motion_mask is not None else True
            self.all_masks.append(motion_mask)

            if not has_motion:
                continue

            # STEP 2b: Preprocess
            pre_start = time.time()
            tensor = preprocessor.prepare_tensor_input(frame)
            pre_time = (time.time() - pre_start) * 1000
            if tensor is None:
                continue
            self.all_preprocessed.append(tensor)

            # STEP 2c: YOLO Inference
            yolo_start = time.time()
            engine.set_input_tensor(tensor)
            engine.invoke_inference()
            boxes = engine.get_output_boxes()
            yolo_time = (time.time() - yolo_start) * 1000
            self.inference_latencies.append(yolo_time)
            self.inference_count += 1

            # STEP 2d: ByteTrack
            tracked = tracker.update(boxes)

            fps_time = (time.time() - fps_start) * 1000
            self.fps_values.append(1000.0 / fps_time if fps_time > 0 else 0)

            if first_inference:
                self.log(f"  First inference: {len(boxes)} detections | "
                         f"MOG2={mog2_time:.1f}ms Pre={pre_time:.1f}ms "
                         f"YOLO={yolo_time:.1f}ms")
                first_inference = False

            # Collect detection results
            for det in boxes:
                det["frame_id"] = self.frame_count
                det["timestamp"] = time.time()
                det["mog2_time_ms"] = round(mog2_time, 1)
                det["preprocess_time_ms"] = round(pre_time, 1)
                det["yolo_time_ms"] = round(yolo_time, 1)
                self.detection_history.append(det)

            # Track best-confidence frame
            for det in boxes:
                conf = det.get("confidence", 0)
                if conf > self.best_confidence:
                    self.best_confidence = conf
                    self.best_frame = frame.copy()
                    self.best_detections = boxes

            if self.frame_count % 10 == 0:
                self.log(f"  Frame {self.frame_count}: {len(boxes)} det, "
                         f"best_conf={self.best_confidence:.3f}, "
                         f"YOLO={yolo_time:.1f}ms")

        # ---- STEP 3: Cleanup ----
        camera.release_camera()
        self.log("")
        self.log("─── STEP 3: Cleanup ───")
        self.log("  Camera released")

        # ---- STEP 4: Generate output artifacts ----
        self.log("")
        self.log("─── STEP 4: Generating Output Artifacts ───")
        self._save_log()
        self._save_annotated_image()
        self._save_mog2_viz()
        self._save_preprocess_viz()
        self._save_inference_table()
        self._save_pipeline_report()

        self._print_summary()
        return 0

    # ------------------------------------------------------------------
    # Output generators
    # ------------------------------------------------------------------

    def _save_log(self):
        path = self.output_dir / "full_log.txt"
        with open(path, "w") as f:
            f.write("\n".join(self.log_lines) + "\n")
        self.log(f"  ✓ Full log saved: {path}")

    def _save_annotated_image(self):
        if self.best_frame is None:
            self.log("  WARNING: No frame with confident detections", "WARN")
            return

        import cv2
        frame = self.best_frame.copy()
        h, w = frame.shape[:2]

        for det in self.best_detections[:20]:
            bbox = det.get("bbox", [0, 0, 0, 0])
            conf = det.get("confidence", 0)
            cls_id = det.get("class_id", 0)
            category = det.get("category", "unknown")

            x1 = int(bbox[0] * w / 640)
            y1 = int(bbox[1] * h / 640)
            x2 = int((bbox[0] + bbox[2]) * w / 640)
            y2 = int((bbox[1] + bbox[3]) * h / 640)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{category} #{cls_id}: {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), (0, 255, 0), -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        info = (f"Frames: {self.frame_count} | Inferences: {self.inference_count} | "
                f"Detections: {len(self.best_detections)} | Best conf: {self.best_confidence:.3f}")
        cv2.putText(frame, info, (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(frame, f"Duration: {self.duration_sec}s | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        path = self.output_dir / "annotated_result.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.log(f"  ✓ Annotated image saved: {path} ({len(self.best_detections)} detections)")

    def _save_mog2_viz(self):
        if not self.all_masks:
            self.log("  WARNING: No MOG2 masks captured", "WARN")
            return

        import cv2
        last_mask = self.all_masks[-1]
        if last_mask is None:
            return

        mask_colored = cv2.cvtColor(last_mask, cv2.COLOR_GRAY2BGR)
        mask_colored[last_mask > 0] = [0, 255, 0]

        path = self.output_dir / "mog2_foreground_mask.jpg"
        cv2.imwrite(str(path), mask_colored, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.log(f"  ✓ MOG2 mask saved: {path}")

        mask_heatmap = cv2.applyColorMap(last_mask.astype(np.uint8), cv2.COLORMAP_JET)
        path2 = self.output_dir / "mog2_heatmap.jpg"
        cv2.imwrite(str(path2), mask_heatmap, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.log(f"  ✓ MOG2 heatmap saved: {path2}")

    def _save_preprocess_viz(self):
        if self.best_frame is None:
            return

        import cv2
        from ImagePreprocessor import ImagePreprocessor

        pre = ImagePreprocessor(640, 640)

        rgb = pre.convert_bgr_to_rgb(self.best_frame)
        if rgb is not None:
            path = self.output_dir / "preprocess_rgb.jpg"
            cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.log(f"  ✓ RGB conversion saved: {path}")

        letterboxed = pre.resize_frame(rgb if rgb is not None else self.best_frame)
        if letterboxed is not None:
            path = self.output_dir / "preprocess_letterbox.jpg"
            cv2.imwrite(str(path), letterboxed, [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.log(f"  ✓ Letterboxed frame saved: {path}")

    def _save_inference_table(self):
        if not self.detection_history:
            self.log("  WARNING: No detections to write", "WARN")
            empty_path = self.output_dir / "inference_table.csv"
            with open(empty_path, "w") as f:
                f.write("frame_id,class_id,category,confidence,bbox_x1,bbox_x2,bbox_y1,bbox_y2,"
                        "mog2_time_ms,preprocess_time_ms,yolo_time_ms\n")
            self.log(f"  ✓ Empty inference table saved: {empty_path}")
            return

        fieldnames = [
            "frame_id", "class_id", "category", "confidence",
            "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
            "mog2_time_ms", "preprocess_time_ms", "yolo_time_ms"
        ]

        path = self.output_dir / "inference_table.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for det in self.detection_history:
                bbox = det.get("bbox", [0, 0, 0, 0])
                writer.writerow({
                    "frame_id": det.get("frame_id", 0),
                    "class_id": det.get("class_id", -1),
                    "category": det.get("category", "unknown"),
                    "confidence": round(det.get("confidence", 0), 4),
                    "bbox_x1": round(bbox[0], 2),
                    "bbox_y1": round(bbox[1], 2),
                    "bbox_x2": round(bbox[2], 2),
                    "bbox_y2": round(bbox[3], 2),
                    "mog2_time_ms": det.get("mog2_time_ms", 0),
                    "preprocess_time_ms": det.get("preprocess_time_ms", 0),
                    "yolo_time_ms": det.get("yolo_time_ms", 0),
                })

        self.log(f"  ✓ Inference table saved: {path} ({len(self.detection_history)} rows)")

        markdown_path = self.output_dir / "inference_table.md"
        with open(markdown_path, "w") as f:
            f.write("# FRTApp Live Camera Inference Table\n\n")
            f.write(f"**Test run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Camera:** {self.camera_device}\n")
            f.write(f"**Model:** {self.model_path}\n")
            f.write(f"**Duration:** {self.duration_sec}s\n")
            f.write(f"**Frames processed:** {self.frame_count}\n")
            f.write(f"**Inferences run:** {self.inference_count}\n")
            f.write(f"**Total detections:** {len(self.detection_history)}\n")
            f.write(f"**Best confidence:** {self.best_confidence:.4f}\n\n")
            f.write("| Frame | Class ID | Category | Confidence | BBox (x1,y1,x2,y2) | MOG2(ms) | Pre(ms) | YOLO(ms) |\n")
            f.write("|-------|----------|----------|------------|--------------------|----------|---------|----------|\n")
            for det in self.detection_history:
                bbox = det.get("bbox", [0, 0, 0, 0])
                f.write(f"| {det.get('frame_id',0)} | {det.get('class_id',-1)} | "
                        f"{det.get('category','unknown')} | {det.get('confidence',0):.4f} | "
                        f"({bbox[0]:.1f},{bbox[1]:.1f},{bbox[2]:.1f},{bbox[3]:.1f}) | "
                        f"{det.get('mog2_time_ms',0):.1f} | {det.get('preprocess_time_ms',0):.1f} | "
                        f"{det.get('yolo_time_ms',0):.1f} |\n")

        self.log(f"  ✓ Markdown inference table saved: {markdown_path}")

    def _save_pipeline_report(self):
        avg_yolo = (sum(self.inference_latencies) / len(self.inference_latencies)
                    if self.inference_latencies else 0)
        min_yolo = min(self.inference_latencies) if self.inference_latencies else 0
        max_yolo = max(self.inference_latencies) if self.inference_latencies else 0

        report = {
            "timestamp": datetime.now().isoformat(),
            "camera_device": self.camera_device,
            "model_path": self.model_path,
            "duration_sec": self.duration_sec,
            "frames_captured": self.frame_count,
            "inferences_run": self.inference_count,
            "total_detections": len(self.detection_history),
            "best_confidence": round(self.best_confidence, 4),
            "detections_by_class": self._count_by_class(),
            "performance": {
                "yolo_avg_ms": round(avg_yolo, 2),
                "yolo_min_ms": round(min_yolo, 2),
                "yolo_max_ms": round(max_yolo, 2),
            },
            "output_files": {
                "full_log": "full_log.txt",
                "annotated_image": "annotated_result.jpg",
                "mog2_mask": "mog2_foreground_mask.jpg",
                "mog2_heatmap": "mog2_heatmap.jpg",
                "rgb_preview": "preprocess_rgb.jpg",
                "letterbox_preview": "preprocess_letterbox.jpg",
                "inference_csv": "inference_table.csv",
                "inference_md": "inference_table.md",
            }
        }

        path = self.output_dir / "pipeline_report.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        self.log(f"  ✓ Pipeline report saved: {path}")

    def _count_by_class(self) -> Dict:
        counts = {}
        for det in self.detection_history:
            cid = det.get("class_id", -1)
            counts[cid] = counts.get(cid, 0) + 1
        return counts

    def _print_summary(self):
        avg_yolo = (sum(self.inference_latencies) / len(self.inference_latencies)
                    if self.inference_latencies else 0)
        self.log("")
        self.log("╔══════════════════════════════════════════╗")
        self.log("║       LIVE CAMERA TEST — SUMMARY         ║")
        self.log("╚══════════════════════════════════════════╝")
        self.log(f"  Total frames:        {self.frame_count}")
        self.log(f"  Inferences run:      {self.inference_count}")
        self.log(f"  Total detections:    {len(self.detection_history)}")
        self.log(f"  Best confidence:     {self.best_confidence:.4f}")
        self.log(f"  Avg YOLO latency:    {avg_yolo:.1f}ms")
        if self.fps_values:
            self.log(f"  Pipeline throughput: {len(self.fps_values)/self.duration_sec:.1f} FPS")
        self.log(f"  Output directory:    {self.output_dir}")
        self.log("")
        self.log("  ── Output Files ──")
        self.log(f"    1. full_log.txt              — Complete pipeline log")
        self.log(f"    2. annotated_result.jpg      — BBox + class labels on best frame")
        self.log(f"    3. mog2_foreground_mask.jpg  — MOG2 foreground (green)")
        self.log(f"    4. mog2_heatmap.jpg          — MOG2 heatmap visualization")
        self.log(f"    5. preprocess_rgb.jpg        — BGR→RGB conversion result")
        self.log(f"    6. preprocess_letterbox.jpg  — Letterboxed 640x640 frame")
        self.log(f"    7. inference_table.csv       — Full detection CSV")
        self.log(f"    8. inference_table.md        — Formatted markdown table")
        self.log(f"    9. pipeline_report.json      — Structured metrics")
        self.log("")


# ==============================================================================
# CLI Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FRTApp Live Camera Pipeline — Real-time YOLO + Algorithm Visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", default="/dev/video0",
                        help="Camera device (default: /dev/video0)")
    parser.add_argument("--model", default="/opt/fss/models/yolov11n.tflite",
                        help="YOLO model path")
    parser.add_argument("--duration", type=int, default=5,
                        help="Capture duration in seconds (default: 5)")
    parser.add_argument("--output-dir", default="",
                        help="Output directory (default: /tmp/frt_live_test_<timestamp>)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose debug output")
    args = parser.parse_args()

    if not args.output_dir:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = f"/tmp/frt_live_test_{ts}"

    runner = LiveCameraPipelineRunner(
        camera_device=args.camera,
        model_path=args.model,
        duration_sec=args.duration,
        output_dir=args.output_dir,
        debug=args.debug,
    )
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
