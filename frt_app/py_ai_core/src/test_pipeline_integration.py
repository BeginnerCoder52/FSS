#!/usr/bin/env python3
"""
test_pipeline_integration.py — Phase 2: FRTApp Pipeline Integration Test

Tests the complete inference pipeline with synthetic frames:
  A. Motion Gating — MOG2 skips static frames, runs on motion
  B. Line Crossing — ByteTrack detects CHECK_IN/CHECK_OUT over virtual boundary
  C. Full Pipeline — End-to-end latency through YoloPipeline (if model exists)

Usage:
    python test_pipeline_integration.py
    python test_pipeline_integration.py --model /path/to/model.tflite
    python test_pipeline_integration.py --output-dir /tmp/results --debug
"""

import os
import sys
import json
import time
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from MotionDetector import MotionDetector
from ByteTracker import ByteTracker
from YoloPipeline import YoloPipeline


def make_frame(h=480, w=640, value=64):
    return np.full((h, w, 3), value, dtype=np.uint8)


def make_noise_frame(h=480, w=640):
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


def make_detection(x, y, w, h, conf=0.9, class_id=5):
    return {"bbox": [x, y, w, h], "confidence": conf, "class_id": class_id}


def test_motion_gating():
    detector = MotionDetector(threshold_percent=1.0)
    detector.init_mog2()

    bg = make_frame(value=64)
    for _ in range(20):
        detector.apply_background_subtraction(bg)

    mask = detector.apply_background_subtraction(bg)
    motion = detector.is_motion_detected(mask)
    if motion:
        return {"name": "MOG2 static", "status": "FAIL",
                "detail": "Detected motion on identical frame"}
    yield {"name": "MOG2 static", "status": "PASS"}

    mask = detector.apply_background_subtraction(make_frame(value=128))
    motion = detector.is_motion_detected(mask)
    if not motion:
        yield {"name": "MOG2 motion", "status": "FAIL",
               "detail": "No motion on changed frame"}
    else:
        yield {"name": "MOG2 motion", "status": "PASS"}


def test_line_crossing():
    tracker = ByteTracker()
    # Set 2 fixed lines: A=160, B=320 (for 480-height frame)
    tracker.line_detector.set_virtual_lines(160, 320)

    # CHECK_IN: start in zone 1 (y<160), cross A then B → enter
    for y in range(50, 420, 30):
        tracker.update([make_detection(200, y - 40, 80, 80, class_id=5)])
    changes = tracker.get_quantity_change()
    if changes.get(5) != 1:
        yield {"name": "CHECK_IN 2-line entry", "status": "FAIL",
               "detail": f"Expected +1 for class 5, got {changes}"}
    else:
        yield {"name": "CHECK_IN 2-line entry", "status": "PASS"}

    tracker.reset()
    tracker.line_detector.set_virtual_lines(160, 320)

    # CHECK_OUT: start in zone 3 (y>320), cross B then A → exit
    for y in range(420, 50, -30):
        tracker.update([make_detection(200, y - 40, 80, 80, class_id=2)])
    changes = tracker.get_quantity_change()
    if changes.get(2) != -1:
        yield {"name": "CHECK_OUT 2-line exit", "status": "FAIL",
               "detail": f"Expected -1 for class 2, got {changes}"}
    else:
        yield {"name": "CHECK_OUT 2-line exit", "status": "PASS"}


def test_full_pipeline(model_path):
    if not os.path.exists(model_path):
        yield {"name": "Full pipeline", "status": "SKIP",
               "detail": f"Model not found: {model_path}"}
        return

    pipeline = YoloPipeline(model_path=model_path, use_shared_memory=False)
    pipeline.init_pipeline()
    if not pipeline.is_initialized:
        yield {"name": "Full pipeline init", "status": "FAIL",
               "detail": "Pipeline not initialized"}
        return

    latencies = []
    inference_runs = 0

    for i in range(20):
        frame = make_noise_frame()
        t0 = time.perf_counter()
        result = pipeline.process_frame(frame)
        elapsed = (time.perf_counter() - t0) * 1000

        if "error" not in result:
            latencies.append(elapsed)
            if not result.get("skipped", False):
                inference_runs += 1

    if len(latencies) == 0:
        yield {"name": "Full pipeline timing", "status": "FAIL",
               "detail": "All frames returned error"}
        return

    avg_ms = sum(latencies) / len(latencies)
    metrics = {
        "avg_ms": round(avg_ms, 1),
        "max_ms": round(max(latencies), 1),
        "min_ms": round(min(latencies), 1),
        "frames": len(latencies),
        "inferences": inference_runs,
        "active_tracks": len(pipeline.tracker.tracks)
    }

    status = "PASS" if avg_ms < 300 else "FAIL"
    detail = (f"avg {avg_ms:.0f}ms, {inference_runs}/{len(latencies)} "
              f"inferences, {len(pipeline.tracker.tracks)} tracks")
    yield {"name": "Full pipeline latency", "status": status,
           "detail": detail, "metrics": metrics}

    if inference_runs == 0:
        yield {"name": "Pipeline motion trigger", "status": "FAIL",
               "detail": "MOG2 gated all frames"}
    else:
        yield {"name": "Pipeline motion trigger", "status": "PASS",
               "detail": f"{inference_runs}/{len(latencies)} frames triggered"}


def main():
    parser = argparse.ArgumentParser(description="FRTApp Phase 2 pipeline test")
    parser.add_argument("--model",
                        default="/opt/fss/models/YOLOv11n_260518_best_int8.tflite")
    parser.add_argument("--output-dir", default="/tmp/frt_pipeline_test")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if args.debug else "INFO",
               format="<level>{level: <8}</level> | {message}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("FRTApp Phase 2: Pipeline Integration Test")
    logger.info(f"Model: {args.model}")
    logger.info(f"Output: {output_dir}")

    all_tests = []
    all_tests.extend(test_motion_gating())
    all_tests.extend(test_line_crossing())
    all_tests.extend(test_full_pipeline(args.model))

    counts = {"pass": 0, "fail": 0, "skip": 0}
    for t in all_tests:
        s = t["status"].lower()
        if s == "passed" or s == "pass":
            counts["pass"] += 1
        elif s == "failed" or s == "fail":
            counts["fail"] += 1
        elif s == "skipped" or s == "skip":
            counts["skip"] += 1

    logger.info("")
    icon = "✓" if counts["fail"] == 0 else "✗"
    logger.info(f"{icon}  {counts['pass']} passed, {counts['fail']} failed, "
                f"{counts['skip']} skipped of {len(all_tests)} tests")

    report = {
        "test": "FRTApp Phase 2: Pipeline Integration",
        "timestamp": datetime.now().isoformat(),
        "summary": counts,
        "tests": all_tests
    }
    report_path = output_dir / "pipeline_test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report: {report_path}")

    return 1 if counts["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
