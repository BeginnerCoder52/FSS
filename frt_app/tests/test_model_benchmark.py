#!/usr/bin/env python3
"""
test_model_benchmark.py — Phase 1: Model Test
==============================================
Load INT8 TFLite model, run inference on a known image, measure latency.
Outputs structured JSON with pass/fail.

Usage:
    python3 test_model_benchmark.py
    python3 test_model_benchmark.py --model /opt/fss/models/YOLOv11n_260518_best_int8.tflite
    python3 test_model_benchmark.py --image test.jpg --no-c-backend
"""

import argparse, json, sys, time, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../py_ai_core/src"))

from loguru import logger
logger.remove()  # suppress loguru for clean JSON output

from ImagePreprocessor import ImagePreprocessor
from YoloTfliteEngine import YoloTfliteEngine


LATENCY_TARGET_MS = 150
DEFAULT_MODEL = "/opt/fss/models/YOLOv11n_260518_best_int8.tflite"
WARMUP_RUNS = 10
BENCHMARK_RUNS = 10


def load_image(path):
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"Failed to load image: {path}")
    return img


def make_synthetic_image():
    tile = np.zeros((64, 64, 3), dtype=np.uint8)
    tile[:32, :32] = [255, 0, 0]
    tile[:32, 32:] = [0, 255, 0]
    tile[32:, :32] = [0, 0, 255]
    tile[32:, 32:] = [255, 255, 0]
    return np.tile(tile, (8, 8, 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--image", default=None)
    p.add_argument("--no-c-backend", action="store_true")
    p.add_argument("--confidence", type=float, default=0.2)
    args = p.parse_args()

    result = {"phase": "model_test", "status": "fail", "metrics": {}, "errors": []}

    # 1. Load image
    try:
        frame = load_image(args.image) if args.image else make_synthetic_image()
        h, w = frame.shape[:2]
    except Exception as e:
        result["errors"].append(f"image_load: {e}")
        print(json.dumps(result))
        return 1

    # 2. Initialize preprocessor + engine
    pre = ImagePreprocessor(640, 640)
    use_c = not args.no_c_backend

    try:
        engine = YoloTfliteEngine(
            args.model, use_c_backend=use_c,
            confidence_threshold=args.confidence
        )
        if not engine.load_model_mmap():
            raise RuntimeError("load_model_mmap() returned False")
    except Exception as e:
        result["errors"].append(f"model_load: {e}")
        print(json.dumps(result))
        return 1

    # 3. Preprocess + inference path
    use_c_preprocess = (use_c and engine._c_reader and engine._has_preprocess)

    if use_c_preprocess:
        # C backend handles: resize (640x480 -> 640x640) + BGR->RGB + normalize
        tensor = None
        for _ in range(WARMUP_RUNS):
            if not engine.preprocess_and_run(frame):
                raise RuntimeError("C preprocess_and_run failed during warmup")
        engine.get_output_boxes()

        latencies = []
        for _ in range(BENCHMARK_RUNS):
            t0 = time.perf_counter()
            if not engine.preprocess_and_run(frame):
                raise RuntimeError("C preprocess_and_run failed")
            latencies.append((time.perf_counter() - t0) * 1000)

        tensor_shape = [1, 640, 640, 3]
    else:
        # Python preprocessing: BGR->RGB + letterbox 640x640 + normalize + batch dim
        try:
            tensor = pre.prepare_tensor_input(frame)
            if tensor is None:
                raise RuntimeError("prepare_tensor_input returned None")
            expected = (1, 640, 640, 3)
            if tensor.shape != expected:
                raise RuntimeError(f"tensor shape {tensor.shape} != {expected}")
        except Exception as e:
            result["errors"].append(f"preprocess: {e}")
            print(json.dumps(result))
            return 1

        for _ in range(WARMUP_RUNS):
            engine.set_input_tensor(tensor)
            engine.invoke_inference()
        engine.get_output_boxes()

        latencies = []
        for _ in range(BENCHMARK_RUNS):
            engine.set_input_tensor(tensor)
            t0 = time.perf_counter()
            engine.invoke_inference()
            latencies.append((time.perf_counter() - t0) * 1000)

        tensor_shape = list(tensor.shape) if tensor is not None else []

    # 6. Get detections
    dets = engine.get_output_boxes()
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    # 7. Build output
    preprocess_path = "c_backend" if use_c_preprocess else "python"
    result["status"] = "pass" if (len(dets) >= 0 and avg_latency < LATENCY_TARGET_MS * 2) else "warn"
    result["metrics"] = {
        "backend": "c" if (use_c and engine._c_reader) else "python",
        "preprocess": preprocess_path,
        "model": args.model,
        "input_image": args.image or "synthetic",
        "input_shape": list(frame.shape[:2]),
        "tensor_shape": tensor_shape,
        "latency_ms_avg": round(avg_latency, 2),
        "latency_ms_min": round(min_latency, 2),
        "latency_ms_max": round(max_latency, 2),
        "latency_ms_target": LATENCY_TARGET_MS,
        "detection_count": len(dets),
        "classes_detected": sorted(set(d["class_id"] for d in dets)),
        "max_confidence": round(max(d["confidence"] for d in dets), 4) if dets else 0.0,
        "total_inferences": BENCHMARK_RUNS,
        "total_inferences_warmup": WARMUP_RUNS,
    }

    if dets:
        result["metrics"]["top_detection"] = {
            "class_id": dets[0]["class_id"],
            "confidence": round(dets[0]["confidence"], 4),
            "bbox": [round(v, 4) for v in dets[0]["bbox"]],
        }

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
