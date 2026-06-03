#!/usr/bin/env python3
"""
user_scenario_pipeline.py — FRTApp User Scenario Pipeline (CHECK-IN / CHECK-OUT)
=================================================================================

Real hardware test: live camera → MOG2 → YOLOv11 (C backend) → state machine.

Scenarios:
  S1 (CHECK-IN) : Hand with fruit enters frame → YOLO detects → "<food> has added"
  S2 (CHECK-OUT): Hand enters empty, fruit appears then leaves → "<food> has removed"

Output (in OUTPUT_DIR/):
  1. full_log.txt              — Complete timestamped pipeline log
  2. annotated_result.jpg      — Best frame with bbox + COCO class labels
  3. mog2_foreground_mask.jpg  — MOG2 foreground mask (green)
  4. mog2_heatmap.jpg          — MOG2 heatmap visualization
  5. preprocess_rgb.jpg        — BGR→RGB conversion result
  6. preprocess_letterbox.jpg  — Letterboxed 640×640 frame
  7. inference_table.csv       — Full detection CSV with labels
  8. inference_table.md        — Formatted markdown inference table
  9. pipeline_report.json      — Structured metrics + scenario summary
  10. scenario_report.json     — Check-in/check-out state transitions

Usage:
    python3 user_scenario_pipeline.py --scenario check-in --duration 15
    python3 user_scenario_pipeline.py --scenario check-out --duration 15 --debug

Dependencies:
    OpenCV, NumPy, loguru, tflite-runtime (or libtflite_reader.so for C backend)
"""

import os
import sys
import time
import json
import argparse
import datetime
import csv
import io
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from enum import Enum

import cv2
import numpy as np

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

FRT_SRC = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if FRT_SRC not in sys.path:
    sys.path.insert(0, FRT_SRC)

CLASS_YAML_PATH = "/opt/fss/models/class.yaml"

FOOD_CLASS_NAMES = {}

def load_class_yaml(path: str = CLASS_YAML_PATH) -> list:
    global FOOD_CLASS_NAMES
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        names = data.get("names", {})
        FOOD_CLASS_NAMES = {int(k): v for k, v in names.items()}
        max_id = max(FOOD_CLASS_NAMES.keys()) if FOOD_CLASS_NAMES else 0
        labels = [FOOD_CLASS_NAMES.get(i, f"class_{i}") for i in range(max_id + 1)]
        return labels
    except Exception:
        pass
    return ["apple", "carrot", "egg", "lemon", "tomato"]

CLASS_LABELS = load_class_yaml()

STABLE_CONFIRM_FRAMES = 5
COOLDOWN_FRAMES = 30

SCAN_TIMEOUT_SEC = 10
ACTION_TIMEOUT_SEC = 5


class ScenarioState(Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    FRUIT_DETECTED = "FRUIT_DETECTED"
    CHECKING_IN = "CHECKING_IN"
    CHECKING_OUT = "CHECKING_OUT"
    CONFIRMED = "CONFIRMED"


class UserScenarioPipeline:
    def __init__(
        self,
        camera_device: str,
        model_path: str,
        scenario: str,
        output_dir: str,
        duration: int = 15,
        debug: bool = False,
    ):
        self.camera_device = camera_device
        self.model_path = model_path
        self.scenario = scenario.lower()
        assert self.scenario in ("check-in", "check-out"), \
            f"Scenario must be 'check-in' or 'check-out', got {scenario}"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.duration = duration
        self.debug = debug

        self.log_lines = []
        self.frame_count = 0
        self.inferences_run = 0
        self.total_detections = 0
        self.best_confidence = 0.0
        self.best_frame = None
        self.best_detections = []
        self.best_frame_idx = 0
        self.best_mask = None
        self.best_preprocessed_rgb = None
        self.best_preprocessed_letterbox = None
        self.detection_history = []
        self.all_masks = []
        self.yolo_latencies = []
        self.mog2_latencies = []
        self.preprocess_latencies = []

        self.state = ScenarioState.IDLE
        self.state_log = []
        self.stable_count = 0
        self.cooldown_counter = 0
        self.current_detected = {}
        self.last_notification = ""
        self.notification_log = []

        self.scan_start_time = 0.0
        self.action_start_time = 0.0
        self.alarm_scan_triggered = False
        self.alarm_action_triggered = False

        self.latest_masks = []
        self.latest_frames = []
        self.latest_detections = []
        self.MAX_LATEST_FRAMES = 5

        self._setup_logger()

    def _setup_logger(self):
        from loguru import logger
        self.logger = logger
        self.logger.remove()
        level = "DEBUG" if self.debug else "INFO"
        self.logger.add(sys.stderr, level=level,
                        format="<level>{time:HH:mm:ss.SSS}</level> | <level>{level: <8}</level> | {message}")
        log_file = self.output_dir / "full_log.txt"
        self.logger.add(str(log_file), level="DEBUG",
                        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
                        rotation="10 MB", retention=3)
        self._log("UserScenarioPipeline initialized")
        self._log(f"  Camera:   {self.camera_device}")
        self._log(f"  Model:    {self.model_path}")
        self._log(f"  Scenario: {self.scenario}")
        self._log(f"  Duration: {self.duration}s")
        self._log(f"  Output:   {self.output_dir}")

    def _log(self, msg: str):
        self.logger.info(msg)
        self.log_lines.append(f"[{datetime.datetime.now():%H:%M:%S.%f}] {msg}")

    def _get_food_name(self, class_id: int) -> str:
        if 0 <= class_id < len(CLASS_LABELS):
            return CLASS_LABELS[class_id]
        return f"class_{class_id}"

    def _is_food(self, class_id: int) -> bool:
        return 0 <= class_id < len(CLASS_LABELS)

    def _annotate_frame(self, frame: np.ndarray, detections: List[Dict],
                        state: str, notification: str) -> np.ndarray:
        h, w = frame.shape[:2]
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            sx1 = int(x1 * w)
            sy1 = int(y1 * h)
            sx2 = int(x2 * w)
            sy2 = int(y2 * h)
            sx1 = max(0, min(sx1, w - 1))
            sy1 = max(0, min(sy1, h - 1))
            sx2 = max(0, min(sx2, w - 1))
            sy2 = max(0, min(sy2, h - 1))
            sx1, sx2 = sorted([sx1, sx2])
            sy1, sy2 = sorted([sy1, sy2])

            class_name = self._get_food_name(det["class_id"])
            conf = det["confidence"]
            label = f"{class_name} ({conf:.2f})"

            color = (0, 255, 0) if self._is_food(det["class_id"]) else (255, 255, 0)
            cv2.rectangle(annotated, (sx1, sy1), (sx2, sy2), color, 2)

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (sx1, sy1 - th - 4),
                          (sx1 + tw + 4, sy1), color, -1)
            cv2.putText(annotated, label, (sx1 + 2, sy1 - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        cv2.putText(annotated, f"State: {state}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        if notification:
            cv2.putText(annotated, notification, (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(annotated, f"Frame {self.frame_count}", (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        return annotated

    def _update_state(self, food_items: Dict[int, List[Dict]], now: float):
        prev_state = self.state
        notification = ""

        if self.state == ScenarioState.IDLE:
            if food_items:
                self.state = ScenarioState.FRUIT_DETECTED
                self.stable_count = 0
                self.scan_start_time = 0.0
                self.alarm_scan_triggered = False
                self.current_detected = food_items
                names = [self._get_food_name(cid) for cid in food_items]
                notification = f"{', '.join(names)} detected! Ready for {self.scenario}"
            elif self.frame_count == 1:
                notification = "Waiting for item..."
            elif self.frame_count % 30 == 0:
                notification = "Waiting for item..."

        elif self.state == ScenarioState.SCANNING:
            scan_elapsed = now - self.scan_start_time if self.scan_start_time > 0 else 0
            if food_items:
                self.state = ScenarioState.FRUIT_DETECTED
                self.stable_count = 0
                self.alarm_scan_triggered = False
                self.current_detected = food_items
                names = [self._get_food_name(cid) for cid in food_items]
                notification = f"{', '.join(names)} detected! Ready for {self.scenario}"
            elif scan_elapsed >= SCAN_TIMEOUT_SEC and not self.alarm_scan_triggered:
                self.alarm_scan_triggered = True
                notification = f"⚠ SCAN TIMEOUT: No item detected for {SCAN_TIMEOUT_SEC}s"
                self._log(f"[ALARM] {notification}")
            else:
                remaining = max(0, SCAN_TIMEOUT_SEC - scan_elapsed)
                notification = f"Scanning... ({remaining:.0f}s)"

        elif self.state == ScenarioState.FRUIT_DETECTED:
            if food_items:
                self.stable_count += 1
                self.current_detected = food_items
                names = [self._get_food_name(cid) for cid in food_items]
                notification = f"{', '.join(names)} detected! Ready for {self.scenario}"

                if self.stable_count >= STABLE_CONFIRM_FRAMES:
                    self.action_start_time = now
                    self.alarm_action_triggered = False
                    if self.scenario == "check-in":
                        self.state = ScenarioState.CHECKING_IN
                    else:
                        self.state = ScenarioState.CHECKING_OUT
            else:
                if self.scenario == "check-out":
                    self.action_start_time = now
                    self.alarm_action_triggered = False
                    self.state = ScenarioState.CHECKING_OUT
                    self.stable_count = STABLE_CONFIRM_FRAMES
                else:
                    self.state = ScenarioState.SCANNING
                    self.scan_start_time = now
                    self.alarm_scan_triggered = False
                    self.stable_count = 0
                    notification = "Item lost — scanning again..."

        elif self.state == ScenarioState.CHECKING_IN:
            action_elapsed = now - self.action_start_time
            if action_elapsed >= ACTION_TIMEOUT_SEC and not self.alarm_action_triggered:
                self.alarm_action_triggered = True
                notification = f"⚠ ACTION TIMEOUT: Check-in took >{ACTION_TIMEOUT_SEC}s"
                self._log(f"[ALARM] {notification}")
            self.state = ScenarioState.CONFIRMED
            self.cooldown_counter = COOLDOWN_FRAMES
            counts = defaultdict(int)
            for cid, dets in self.current_detected.items():
                name = self._get_food_name(cid)
                counts[name] += len(dets)
            for name, count in counts.items():
                notification = f"{count} {name} has added"
            self._log(f"[CHECK-IN] {notification}")

        elif self.state == ScenarioState.CHECKING_OUT:
            action_elapsed = now - self.action_start_time
            if action_elapsed >= ACTION_TIMEOUT_SEC and not self.alarm_action_triggered:
                self.alarm_action_triggered = True
                notification = f"⚠ ACTION TIMEOUT: Check-out took >{ACTION_TIMEOUT_SEC}s"
                self._log(f"[ALARM] {notification}")
            self.state = ScenarioState.CONFIRMED
            self.cooldown_counter = COOLDOWN_FRAMES
            counts = defaultdict(int)
            for cid, dets in self.current_detected.items():
                name = self._get_food_name(cid)
                counts[name] += len(dets)
            for name, count in counts.items():
                notification = f"{count} {name} has removed"
            self._log(f"[CHECK-OUT] {notification}")

        elif self.state == ScenarioState.CONFIRMED:
            self.cooldown_counter -= 1
            notification = self.last_notification
            if self.cooldown_counter <= 0:
                self.state = ScenarioState.IDLE
                self.current_detected = {}
                notification = "Ready for next item"

        if self.state != prev_state:
            self._log(f"State: {prev_state.value} → {self.state.value}")
            self.state_log.append({
                "timestamp": now,
                "from": prev_state.value,
                "to": self.state.value,
                "notification": notification,
            })

        if notification and notification != self.last_notification:
            self.notification_log.append({
                "timestamp": now,
                "state": self.state.value,
                "message": notification,
            })
            self._log(f"[NOTIFY] {notification}")

        self.last_notification = notification
        return notification

    def run(self) -> int:
        from CameraUvcDriver import CameraUvcDriver
        from ImagePreprocessor import ImagePreprocessor
        from MotionDetector import MotionDetector
        from YoloTfliteEngine import YoloTfliteEngine

        self._log("")
        self._log("=" * 60)
        self._log(f"USER SCENARIO: {self.scenario.upper()}")
        self._log("=" * 60)
        self._log(f"  Food labels ({len(CLASS_LABELS)}): {CLASS_LABELS}")
        self._log("")

        if getattr(self, 'image_mode', False):
            class ImageFileDriver:
                def __init__(self, path):
                    self.path = path
                    self.frame = None
                def check_uvc_connection(self): return True
                def open_camera_stream(self):
                    img = cv2.imread(self.path)
                    if img is None:
                        return False
                    self.frame = cv2.resize(img, (640, 480))
                    return True
                def read_frame(self):
                    return self.frame.copy() if self.frame is not None else None
                def release_camera(self): pass
                def close_camera_stream(self): pass
                def stop_camera_stream(self): pass
            camera = ImageFileDriver(self.camera_device)
            if not camera.open_camera_stream():
                self._log(f"ERROR: Could not load image {self.camera_device}")
                return 1
            self._log(f"Image mode: {self.camera_device} ({camera.frame.shape[1]}x{camera.frame.shape[0]})")
        else:
            camera = CameraUvcDriver(self.camera_device)
            if not camera.check_uvc_connection():
                self._log("ERROR: Camera not accessible")
                return 1
            if not camera.open_camera_stream():
                self._log("ERROR: Could not open camera stream")
                return 1
            self._log(f"Camera opened: 640x480 @ 30 FPS")

        preprocessor = ImagePreprocessor(640, 640)
        detector = MotionDetector(threshold_percent=0.5)
        detector.MOG2_HISTORY = 100
        detector.MOG2_THRESHOLD = 8.0
        detector.init_mog2()

        engine = YoloTfliteEngine(
            self.model_path,
            use_c_backend=True,
            c_precision=2,
        )
        engine.load_model_mmap()
        self._log(f"YOLO engine loaded: C backend={engine.use_c_backend}")

        self._log("")
        self._log("─" * 60)
        self._log("Pipeline running — scanning for items...")
        self._log("─" * 60)

        start_time = time.time()
        end_time = start_time + self.duration

        while time.time() < end_time:
            now = time.time()
            self.frame_count += 1

            frame = camera.read_frame()
            if frame is None:
                continue

            t_mog2_start = now
            mask = detector.apply_background_subtraction(frame)
            t_mog2 = (time.time() - t_mog2_start) * 1000
            if mask is not None:
                self.all_masks.append(mask)

            has_motion = False
            if mask is not None:
                has_motion = detector.is_motion_detected(mask)

            food_items = {}
            detections = []

            if has_motion or self.state in (
                ScenarioState.FRUIT_DETECTED,
                ScenarioState.CHECKING_IN,
                ScenarioState.CHECKING_OUT,
            ):
                self.inferences_run += 1

                t_pre_start = time.time()
                rgb = preprocessor.convert_bgr_to_rgb(frame)
                letterbox = preprocessor.resize_frame(rgb)
                tensor = preprocessor.normalize_pixels(letterbox)
                input_tensor = np.expand_dims(tensor, axis=0).astype(np.float32)
                t_pre = (time.time() - t_pre_start) * 1000

                if self.best_preprocessed_rgb is None:
                    self.best_preprocessed_rgb = rgb
                if self.best_preprocessed_letterbox is None:
                    self.best_preprocessed_letterbox = letterbox

                t_yolo_start = time.time()
                engine.set_input_tensor(input_tensor)
                engine.invoke_inference()
                boxes = engine.get_output_boxes()
                t_yolo = (time.time() - t_yolo_start) * 1000

                self.yolo_latencies.append(t_yolo)
                self.mog2_latencies.append(t_mog2)
                self.preprocess_latencies.append(t_pre)
                self.total_detections += len(boxes)

                for det in boxes:
                    det["frame_id"] = self.frame_count
                    det["mog2_time_ms"] = round(t_mog2, 1)
                    det["preprocess_time_ms"] = round(t_pre, 1)
                    det["yolo_time_ms"] = round(t_yolo, 1)
                    det["actual_label"] = self._get_food_name(det["class_id"])
                    det["is_food"] = self._is_food(det["class_id"])
                    self.detection_history.append(det)

                for det in boxes:
                    if self._is_food(det["class_id"]):
                        cid = det["class_id"]
                        if cid not in food_items:
                            food_items[cid] = []
                        food_items[cid].append(det)

                detections = boxes

                for det in boxes:
                    conf = det["confidence"]
                    if conf > self.best_confidence:
                        self.best_confidence = conf
                        self.best_frame = frame.copy()
                        self.best_detections = boxes
                        self.best_frame_idx = self.frame_count
                        self.best_mask = mask
                        self.best_preprocessed_rgb = rgb
                        self.best_preprocessed_letterbox = letterbox

            if mask is not None:
                self.latest_masks.append(mask.copy())
                self.latest_frames.append(frame.copy())
                self.latest_detections.append(detections.copy() if detections else [])
                if len(self.latest_masks) > self.MAX_LATEST_FRAMES:
                    self.latest_masks.pop(0)
                    self.latest_frames.pop(0)
                    self.latest_detections.pop(0)

            if not has_motion and not food_items and self.state == ScenarioState.IDLE and self.scan_start_time == 0:
                self.scan_start_time = now

            notification = self._update_state(food_items, now)

            if self.debug and detections:
                for det in detections[:3]:
                    label = self._get_food_name(det["class_id"])
                    self.logger.debug(f"  Det: {label} ({det['confidence']:.2f}) "
                                      f"bbox={det['bbox']}")

            if self.frame_count % 10 == 0:
                delta = now - start_time
                fps = self.frame_count / delta if delta > 0 else 0
                self.logger.info(f"  [{self.state.value}] Frame {self.frame_count} "
                                 f"| {fps:.1f} FPS | {len(detections)} dets | "
                                 f"YOLO {t_yolo:.0f}ms | {notification[:40] if notification else ''}")

        self._log("")
        self._log("─" * 60)
        self._log("Capture complete — generating output artifacts...")
        self._log("─" * 60)

        camera.release_camera()
        self._save_artifacts()

        elapsed = time.time() - start_time
        self._log("")
        self._log("=" * 60)
        self._log(f"SCENARIO {self.scenario.upper()} COMPLETE")
        self._log(f"  Frames:     {self.frame_count}")
        self._log(f"  Inferences: {self.inferences_run}")
        self._log(f"  Detections: {self.total_detections}")
        self._log(f"  Best conf:  {self.best_confidence:.4f}")
        self._log(f"  Elapsed:    {elapsed:.1f}s")
        self._log(f"  Output:     {self.output_dir}/")
        self._log("=" * 60)

        return 0

    def _save_artifacts(self):
        self._save_log()
        self._save_annotated_image()
        self._save_mog2_viz()
        self._save_preprocess_viz()
        self._save_inference_table()
        self._save_pipeline_report()
        self._save_scenario_report()

    def _save_log(self):
        path = self.output_dir / "full_log.txt"
        with open(path, "w") as f:
            f.write("\n".join(self.log_lines))
        self._log(f"Log saved: {path}")

    def _save_annotated_image(self):
        path = self.output_dir / "annotated_result.jpg"
        if self.best_frame is not None:
            annotated = self._annotate_frame(
                self.best_frame, self.best_detections,
                self.state.value, self.last_notification
            )
            cv2.imwrite(str(path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
            size_kb = os.path.getsize(path) // 1024
            self._log(f"Annotated image saved: {path} ({size_kb} KB)")
        else:
            self._log("WARN: No best frame to annotate")

    def _save_mog2_viz(self):
        if self.best_mask is not None:
            mask_colored = cv2.cvtColor(self.best_mask, cv2.COLOR_GRAY2BGR)
            mask_green = np.zeros_like(mask_colored)
            mask_green[:, :, 1] = self.best_mask
            path_fg = self.output_dir / "mog2_foreground_mask.jpg"
            cv2.imwrite(str(path_fg), mask_green, [cv2.IMWRITE_JPEG_QUALITY, 85])
            self._log(f"MOG2 mask saved: {path_fg}")

            mask_heat = cv2.applyColorMap(self.best_mask, cv2.COLORMAP_JET)
            path_hm = self.output_dir / "mog2_heatmap.jpg"
            cv2.imwrite(str(path_hm), mask_heat, [cv2.IMWRITE_JPEG_QUALITY, 85])
            self._log(f"MOG2 heatmap saved: {path_hm}")

        latest_dir = self.output_dir / "latest_frames"
        latest_dir.mkdir(exist_ok=True)
        for i, (lmask, lframe, ldet) in enumerate(zip(
            self.latest_masks, self.latest_frames, self.latest_detections
        )):
            annotated = self._annotate_frame(
                lframe, ldet, self.state.value, self.last_notification
            )
            cv2.imwrite(str(latest_dir / f"frame_{i}_annotated.jpg"), annotated,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])

            mask_g = np.zeros((lframe.shape[0], lframe.shape[1], 3), dtype=np.uint8)
            mask_g[:, :, 1] = lmask
            cv2.imwrite(str(latest_dir / f"frame_{i}_mog2_mask.jpg"), mask_g,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])

            heat = cv2.applyColorMap(lmask, cv2.COLORMAP_JET)
            cv2.imwrite(str(latest_dir / f"frame_{i}_mog2_heatmap.jpg"), heat,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])

            if ldet:
                first_conf = ldet[0]["confidence"] if ldet else 0
                self._log(f"  Latest frame {i}: {len(ldet)} dets, "
                          f"top: {ldet[0].get('actual_label','?')} ({first_conf:.2f})")
        self._log(f"Latest {len(self.latest_masks)} frame visualizations saved to {latest_dir}/")

    def _save_preprocess_viz(self):
        if self.best_preprocessed_rgb is not None:
            path_rgb = self.output_dir / "preprocess_rgb.jpg"
            cv2.imwrite(str(path_rgb), self.best_preprocessed_rgb,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            self._log(f"RGB preview saved: {path_rgb}")
        if self.best_preprocessed_letterbox is not None:
            path_lb = self.output_dir / "preprocess_letterbox.jpg"
            cv2.imwrite(str(path_lb), self.best_preprocessed_letterbox,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            self._log(f"Letterbox preview saved: {path_lb}")

    def _save_inference_table(self):
        csv_path = self.output_dir / "inference_table.csv"
        md_path = self.output_dir / "inference_table.md"

        fieldnames = [
            "frame_id", "class_id", "actual_label", "is_food",
            "confidence", "mog2_time_ms", "preprocess_time_ms", "yolo_time_ms"
        ]
        extra_fields = ["bbox"]

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames + ["bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"])
            writer.writeheader()
            for det in self.detection_history:
                row = {k: det.get(k, "") for k in fieldnames}
                bbox = det.get("bbox", [0, 0, 0, 0])
                row["bbox_x1"] = round(bbox[0], 2)
                row["bbox_y1"] = round(bbox[1], 2)
                row["bbox_x2"] = round(bbox[2], 2)
                row["bbox_y2"] = round(bbox[3], 2)
                writer.writerow(row)
        self._log(f"Inference CSV saved: {csv_path} ({len(self.detection_history)} rows)")

        with open(md_path, "w") as f:
            f.write(f"# User Scenario Inference Table ({self.scenario})\n\n")
            f.write(f"**Run:** {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"**Scenario:** {self.scenario}\n")
            f.write(f"**Duration:** {self.duration}s\n")
            f.write(f"**Frames:** {self.frame_count} | **Inferences:** {self.inferences_run}\n")
            f.write(f"**Detections:** {self.total_detections}\n\n")
            f.write("| Frame | Class ID | Label | Food? | Confidence | BBox | MOG2(ms) | Pre(ms) | YOLO(ms) |\n")
            f.write("|-------|----------|-------|-------|------------|------|----------|---------|----------|\n")
            for det in self.detection_history[:100]:
                bbox = det.get("bbox", [0, 0, 0, 0])
                f.write(f"| {det.get('frame_id','')} ")
                f.write(f"| {det.get('class_id','')} ")
                f.write(f"| {det.get('actual_label','')} ")
                f.write(f"| {'Y' if det.get('is_food') else 'N'} ")
                f.write(f"| {det.get('confidence',0):.2f} ")
                f.write(f"| ({bbox[0]:.1f},{bbox[1]:.1f},{bbox[2]:.1f},{bbox[3]:.1f}) ")
                f.write(f"| {det.get('mog2_time_ms','')} ")
                f.write(f"| {det.get('preprocess_time_ms','')} ")
                f.write(f"| {det.get('yolo_time_ms','')} |\n")
            if len(self.detection_history) > 100:
                f.write(f"| ... | ({len(self.detection_history) - 100} more rows truncated) |\n")
        self._log(f"Inference MD saved: {md_path}")

    def _save_pipeline_report(self):
        by_class = defaultdict(int)
        for det in self.detection_history:
            cid = det.get("class_id", -1)
            by_class[str(cid)] += 1

        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "scenario": self.scenario,
            "camera_device": self.camera_device,
            "model_path": self.model_path,
            "duration_sec": self.duration,
            "frames_captured": self.frame_count,
            "inferences_run": self.inferences_run,
            "total_detections": self.total_detections,
            "best_confidence": round(self.best_confidence, 4),
            "class_labels": CLASS_LABELS,
            "detections_by_class": dict(by_class),
            "performance": {
                "yolo_avg_ms": round(np.mean(self.yolo_latencies), 2) if self.yolo_latencies else 0,
                "yolo_min_ms": round(min(self.yolo_latencies), 2) if self.yolo_latencies else 0,
                "yolo_max_ms": round(max(self.yolo_latencies), 2) if self.yolo_latencies else 0,
                "mog2_avg_ms": round(np.mean(self.mog2_latencies), 2) if self.mog2_latencies else 0,
            },
            "state_transitions": len(self.state_log),
            "notifications": len(self.notification_log),
            "output_files": {
                "full_log": "full_log.txt",
                "annotated_image": "annotated_result.jpg",
                "mog2_mask": "mog2_foreground_mask.jpg",
                "mog2_heatmap": "mog2_heatmap.jpg",
                "rgb_preview": "preprocess_rgb.jpg",
                "letterbox_preview": "preprocess_letterbox.jpg",
                "inference_csv": "inference_table.csv",
                "inference_md": "inference_table.md",
                "scenario_report": "scenario_report.json",
            },
        }

        path = self.output_dir / "pipeline_report.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        self._log(f"Pipeline report saved: {path}")

    def _save_scenario_report(self):
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "scenario": self.scenario,
            "duration_sec": self.duration,
            "state_transitions": self.state_log,
            "notifications": self.notification_log,
            "inferences_run": self.inferences_run,
            "total_detections": self.total_detections,
            "class_labels": CLASS_LABELS,
            "alarms": {
                "scan_timeout_sec": SCAN_TIMEOUT_SEC,
                "action_timeout_sec": ACTION_TIMEOUT_SEC,
                "scan_alarm_triggered": self.alarm_scan_triggered,
                "action_alarm_triggered": self.alarm_action_triggered,
            },
            "detection_summary": {},
        }

        for det in self.detection_history:
            label = det.get("actual_label", "unknown")
            if label not in report["detection_summary"]:
                report["detection_summary"][label] = {
                    "count": 0, "class_ids": set(), "max_conf": 0
                }
            report["detection_summary"][label]["count"] += 1
            report["detection_summary"][label]["class_ids"].add(det.get("class_id", -1))
            report["detection_summary"][label]["max_conf"] = max(
                report["detection_summary"][label]["max_conf"],
                det.get("confidence", 0)
            )

        for label in report["detection_summary"]:
            report["detection_summary"][label]["class_ids"] = \
                list(report["detection_summary"][label]["class_ids"])

        path = self.output_dir / "scenario_report.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        self._log(f"Scenario report saved: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="FRTApp User Scenario Pipeline (CHECK-IN / CHECK-OUT)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--camera", default="/dev/video0",
                        help="Camera device (default: /dev/video0)")
    parser.add_argument("--model", default="/opt/fss/models/yolov11n_fp32.tflite",
                        help="YOLO model path")
    parser.add_argument("--scenario", required=True,
                        choices=["check-in", "check-out"],
                        help="Scenario mode")
    parser.add_argument("--duration", type=int, default=15,
                        help="Capture duration in seconds (default: 15)")
    parser.add_argument("--output-dir", default="",
                        help="Output directory (default: /tmp/fss_scenario_<timestamp>)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--image", default="",
                        help="Single image file for static testing (no camera needed)")
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"/tmp/fss_scenario_{args.scenario}_{ts}"

    pipeline = UserScenarioPipeline(
        camera_device=args.camera if not args.image else args.image,
        model_path=args.model,
        scenario=args.scenario,
        output_dir=output_dir,
        duration=args.duration,
        debug=args.debug,
    )

    pipeline.image_mode = bool(args.image)
    return pipeline.run()


if __name__ == "__main__":
    sys.exit(main())
