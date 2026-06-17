#!/usr/bin/env python3
"""
Quantization Trade-off Analysis: FP32 vs INT8 for FSS YOLO Models
=================================================================
Compares file size, inference latency, and accuracy (mAP@0.5) between
a full-precision FP32 TFLite model and its quantized INT8 counterpart.

Designed for Raspberry Pi 4B — uses `tflite_runtime.interpreter`
(minimal footprint), hardware warm-up, and optional CPU temp monitoring.

Quantization Theory Background
------------------------------
Post-training integer quantization maps FP32 values to INT8 (256 levels):
    q = clamp(round(r / S) + Z)
where r is the real value, S = (max - min) / 255 is the scale factor, and Z
is the zero-point offset.

Accuracy degradation stems from:
1. **Range clipping**: Activations/weights outside the learned min/max range
   are clipped, discarding outlier information.
2. **Rounding error**: The round() operation introduces ±0.5 LSB noise per
   element (~0.4% relative error per quantized value).
3. **Channel vs per-tensor quantization**: Per-tensor uses a single S/Z for
   an entire tensor; per-channel (per-axis) preserves more fidelity for
   convolutional weights but is not always supported by all hardware.
4. **BatchNorm folding**: During quantization, BatchNorm layers are folded
   into preceding Conv2D weights, which can amplify quantization error near
   the decision boundary.

Reference: TensorFlow Lite quantization spec
https://www.tensorflow.org/lite/performance/model_optimization
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import csv
from collections import OrderedDict

import cv2
import numpy as np

from tflite_runtime.interpreter import Interpreter


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WARMUP_ITERATIONS = 10
BENCHMARK_ITERATIONS = 100
MAP50_IOU_THRESH = 0.5
ACCURACY_DEGRADATION_THRESHOLD_PCT = 4.0
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
RPI_THERMAL_CMD = "vcgencmd measure_temp"


# ---------------------------------------------------------------------------
# Thermal monitoring helpers (Raspberry Pi)
# ---------------------------------------------------------------------------
def get_cpu_temperature_celsius():
    """Return CPU temp in °C via vcgencmd, or None if unavailable."""
    try:
        result = subprocess.run(
            RPI_THERMAL_CMD.split(),
            capture_output=True,
            text=True,
            timeout=2,
        )
        match = re.search(r"temp=([\d.]+)'C", result.stdout)
        if match:
            return float(match.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def log_temperature(label=""):
    temp = get_cpu_temperature_celsius()
    if temp is not None:
        print(f"    [THERMAL] {label} CPU temperature: {temp:.1f} °C")


# ---------------------------------------------------------------------------
# Model Size Analysis
# ---------------------------------------------------------------------------
def analyze_model_size(fp32_path, int8_path):
    """Measure file sizes and compute the compression ratio."""
    size_fp32 = os.path.getsize(fp32_path) / (1024 * 1024)
    size_int8 = os.path.getsize(int8_path) / (1024 * 1024)
    reduction_pct = (size_fp32 - size_int8) / size_fp32 * 100.0
    return {
        "fp32_mb": size_fp32,
        "int8_mb": size_int8,
        "reduction_pct": reduction_pct,
    }


# ---------------------------------------------------------------------------
# TFLite Inference Engine (lightweight, no full TF dependency)
# ---------------------------------------------------------------------------
class TfliteBenchmarkEngine:
    """Minimal TFLite wrapper for latency & accuracy benchmarking."""

    def __init__(self, model_path, num_threads=2):
        self.model_path = model_path
        self.interpreter = Interpreter(
            model_path=model_path,
            num_threads=num_threads,
        )
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        in_d = self.input_details[0]
        self.input_shape = in_d["shape"]
        self.input_height = in_d["shape"][1]
        self.input_width = in_d["shape"][2]
        self.is_quantized_input = in_d["dtype"] == np.int8
        self.input_scale, self.input_zero_point = in_d["quantization"]

        out_d = self.output_details[0]
        out_shape = out_d["shape"]
        self.num_attrs = min(out_shape[1], out_shape[2])
        self.num_classes = self.num_attrs - 4
        self.output_scale, self.output_zero_point = out_d["quantization"]

        self.precision_label = "INT8" if self.is_quantized_input else "FP32"

    def letterbox(self, img, target_size, color=(114, 114, 114)):
        h, w = img.shape[:2]
        r = min(target_size[0] / h, target_size[1] / w)
        new_unpad = (int(round(w * r)), int(round(h * r)))
        dw = (target_size[1] - new_unpad[0]) / 2
        dh = (target_size[0] - new_unpad[1]) / 2

        if (w, h) != new_unpad:
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right,
                                 cv2.BORDER_CONSTANT, value=color)
        return img, r, (dw, dh)

    def preprocess(self, img_path):
        img0 = cv2.imread(img_path)
        if img0 is None:
            raise ValueError(f"Cannot read image: {img_path}")

        img_rgb = cv2.cvtColor(img0, cv2.COLOR_BGR2RGB)
        img_pad, ratio, pad = self.letterbox(
            img_rgb, (self.input_height, self.input_width)
        )

        img_input = img_pad.astype(np.float32) / 255.0

        if self.is_quantized_input and self.input_scale != 0:
            img_input = (img_input / self.input_scale) + self.input_zero_point
            img_input = img_input.astype(np.int8)

        img_input = np.expand_dims(img_input, axis=0)
        return img_input, img0, ratio, pad

    def run_inference(self, img_path):
        """Single inference; returns (latency_ms, detections_list)."""
        input_data, original_img, ratio, pad = self.preprocess(img_path)
        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)

        t0 = time.perf_counter()
        self.interpreter.invoke()
        latency_ms = (time.perf_counter() - t0) * 1000.0

        out = self.interpreter.get_tensor(self.output_details[0]["index"])
        if self.is_quantized_input and self.output_scale != 0:
            out = (out.astype(np.float32) - self.output_zero_point) * self.output_scale

        squeezed = np.squeeze(out)
        predictions = squeezed.T if squeezed.shape[0] < squeezed.shape[1] else squeezed

        detections = []
        boxes, scores, class_ids = [], [], []
        for pred in predictions:
            cls_scores = pred[4:]
            cls_id = int(np.argmax(cls_scores))
            confidence = float(cls_scores[cls_id])
            if confidence > 0.5:
                xc, yc, w, h = pred[0], pred[1], pred[2], pred[3]
                if xc <= 1.0 and yc <= 1.0:
                    xc *= self.input_width
                    yc *= self.input_height
                    w *= self.input_width
                    h *= self.input_height

                x1 = int(((xc - w / 2) - pad[0]) / ratio)
                y1 = int(((yc - h / 2) - pad[1]) / ratio)
                x2 = int(((xc + w / 2) - pad[0]) / ratio)
                y2 = int(((yc + h / 2) - pad[1]) / ratio)

                h_img, w_img = original_img.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)

                boxes.append([x1, y1, x2 - x1, y2 - y1])
                scores.append(confidence)
                class_ids.append(cls_id)

        if boxes:
            indices = cv2.dnn.NMSBoxes(boxes, scores, 0.5, 0.45)
            for i in indices:
                i = int(i)
                x, y, w, h = boxes[i]
                detections.append({
                    "class_id": class_ids[i],
                    "confidence": round(scores[i], 4),
                    "bbox": [x, y, x + w, y + h],
                })

        return latency_ms, detections


# ---------------------------------------------------------------------------
# Latency Benchmark
# ---------------------------------------------------------------------------
def benchmark_latency(engine, image_paths, warmup=WARMUP_ITERATIONS,
                      iterations=BENCHMARK_ITERATIONS):
    """
    Returns (avg_latency_ms, fps_equivalent, all_latencies).
    warmup runs are discarded (no caching bias).
    """
    if not image_paths:
        return 0.0, 0.0, []

    # Phase 1: Warm-up (stabilize CPU freq, caches, TFLite arena)
    print(f"    Warming up: {warmup} iterations ...")
    for i in range(warmup):
        img = image_paths[i % len(image_paths)]
        engine.run_inference(img)
    log_temperature("after warm-up")

    # Phase 2: Measured runs
    print(f"    Benchmarking: {iterations} iterations ...")
    latencies = []
    for i in range(iterations):
        img = image_paths[i % len(image_paths)]
        lat_ms, _ = engine.run_inference(img)
        latencies.append(lat_ms)

    avg_ms = float(np.mean(latencies))
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    return avg_ms, fps, latencies


# ---------------------------------------------------------------------------
# YOLO Label Loading & mAP Evaluation (copied from test-inference.py)
# ---------------------------------------------------------------------------
def compute_iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def yolo_to_xyxy(x_center, y_center, width, height, img_w, img_h):
    x1 = (x_center - width / 2.0) * img_w
    y1 = (y_center - height / 2.0) * img_h
    x2 = (x_center + width / 2.0) * img_w
    y2 = (y_center + height / 2.0) * img_h
    return [
        min(max(0.0, x1), float(img_w)),
        min(max(0.0, y1), float(img_h)),
        min(max(0.0, x2), float(img_w)),
        min(max(0.0, y2), float(img_h)),
    ]


def load_yolo_labels(label_path, img_w, img_h):
    gt_boxes = []
    if not os.path.isfile(label_path):
        return gt_boxes
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                cls_id = int(float(parts[0]))
                xc = float(parts[1])
                yc = float(parts[2])
                w = float(parts[3])
                h = float(parts[4])
            except ValueError:
                continue
            bbox = yolo_to_xyxy(xc, yc, w, h, img_w, img_h)
            gt_boxes.append({"class_id": cls_id, "bbox": bbox})
    return gt_boxes


def compute_ap(recalls, precisions):
    if len(recalls) == 0:
        return 0.0
    mrec = np.concatenate(([0.0], recalls, [1.0]))
    mpre = np.concatenate(([0.0], precisions, [0.0]))
    for i in range(mpre.size - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def evaluate_map50(predictions_by_image, gt_by_image, iou_thresh=0.5):
    per_class = {}
    for image_name, gt_items in gt_by_image.items():
        for gt in gt_items:
            cls = gt["class_id"]
            per_class.setdefault(cls, {
                "num_gt": 0, "scores": [], "tp": [], "fp": [], "num_pred": 0,
            })
            per_class[cls]["num_gt"] += 1

    gt_index = {}
    for image_name, gt_items in gt_by_image.items():
        gt_index[image_name] = {}
        for gt in gt_items:
            cls = gt["class_id"]
            gt_index[image_name].setdefault(cls, []).append({
                "bbox": gt["bbox"], "matched": False,
            })

    all_preds = []
    for image_name, pred_items in predictions_by_image.items():
        for pred in pred_items:
            cls = int(pred["class_id"])
            conf = float(pred["confidence"])
            bbox = [float(v) for v in pred["bbox"]]
            all_preds.append((conf, image_name, cls, bbox))
            per_class.setdefault(cls, {
                "num_gt": 0, "scores": [], "tp": [], "fp": [], "num_pred": 0,
            })
            per_class[cls]["num_pred"] += 1

    all_preds.sort(key=lambda x: x[0], reverse=True)

    for conf, img_name, cls, pred_bbox in all_preds:
        stats = per_class[cls]
        stats["scores"].append(conf)
        best_iou, best_idx = 0.0, -1
        candidates = gt_index.get(img_name, {}).get(cls, [])
        for gi, gt in enumerate(candidates):
            if gt["matched"]:
                continue
            iou = compute_iou(pred_bbox, gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_idx = gi
        if best_idx >= 0 and best_iou >= iou_thresh:
            candidates[best_idx]["matched"] = True
            stats["tp"].append(1)
            stats["fp"].append(0)
        else:
            stats["tp"].append(0)
            stats["fp"].append(1)

    total_gt = sum(s["num_gt"] for s in per_class.values())
    total_tp = sum(sum(s["tp"]) for s in per_class.values())
    total_fp = sum(sum(s["fp"]) for s in per_class.values())
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / total_gt if total_gt else 0.0

    ap_values = []
    for cls in sorted(per_class.keys()):
        s = per_class[cls]
        tp_arr = np.array(s["tp"], dtype=np.float32)
        fp_arr = np.array(s["fp"], dtype=np.float32)
        if len(tp_arr) > 0:
            cum_tp = np.cumsum(tp_arr)
            cum_fp = np.cumsum(fp_arr)
            prec_arr = cum_tp / np.maximum(cum_tp + cum_fp, 1e-12)
            rec_arr = cum_tp / max(float(s["num_gt"]), 1e-12)
        else:
            prec_arr = np.array([], dtype=np.float32)
            rec_arr = np.array([], dtype=np.float32)
        ap50 = compute_ap(rec_arr, prec_arr) if s["num_gt"] > 0 else 0.0
        if s["num_gt"] > 0:
            ap_values.append(ap50)

    map50 = float(np.mean(ap_values)) if ap_values else 0.0
    return {"map50": map50, "precision": precision, "recall": recall}


# ---------------------------------------------------------------------------
# Accuracy Evaluation on Validation Dataset
# ---------------------------------------------------------------------------
def evaluate_accuracy(engine, image_paths, labels_dir):
    """Run inference on all images, compute mAP@0.5 against ground-truth."""
    predictions_by_image = {}
    gt_by_image = {}

    for img_path in image_paths:
        filename = os.path.basename(img_path)
        _, detections = engine.run_inference(img_path)
        predictions_by_image[filename] = detections

        img = cv2.imread(img_path)
        if img is None:
            gt_by_image[filename] = []
        else:
            h, w = img.shape[:2]
            label_file = os.path.splitext(filename)[0] + ".txt"
            label_path = os.path.join(labels_dir, label_file)
            gt_by_image[filename] = load_yolo_labels(label_path, w, h)

    result = evaluate_map50(
        predictions_by_image, gt_by_image, iou_thresh=MAP50_IOU_THRESH
    )
    return result


# ---------------------------------------------------------------------------
# ASCII Table Rendering
# ---------------------------------------------------------------------------
def print_separator(width):
    print("+-" + "-" * (width - 3) + "-+")


def print_table_row(columns, widths):
    parts = []
    for col, w in zip(columns, widths):
        parts.append(f" {str(col):{w}} ")
    print("|" + "|".join(parts) + "|")


def print_summary_table(size_result, fp32_latency, int8_latency,
                        fp32_map, int8_map):
    """Pretty-print the final ASCII comparison table."""
    widths = [38, 22, 22, 28]
    sep = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"

    print("\n" + "=" * 60)
    print("   QUANTIZATION TRADE-OFF ANALYSIS SUMMARY")
    print("   FP32 (baseline) vs INT8 (quantized)")
    print("=" * 60)

    # Model Size
    print("\n  [1] Model Size Analysis")
    print(sep)
    print_table_row(["Metric", "FP32 Model", "INT8 Model", "Difference/Status"], widths)
    print(sep)
    pct_str = f"{size_result['reduction_pct']:.1f}% smaller"
    print_table_row([
        "File Size (MB)",
        f"{size_result['fp32_mb']:.2f} MB",
        f"{size_result['int8_mb']:.2f} MB",
        pct_str,
    ], widths)
    print(sep)

    # Inference Latency
    fp32_delta = int8_latency["avg_ms"] - fp32_latency["avg_ms"]
    print("\n  [2] Inference Latency ({} warm-up + {} measured)".format(
        WARMUP_ITERATIONS, BENCHMARK_ITERATIONS))
    print(sep)
    print_table_row(["Metric", "FP32 Model", "INT8 Model", "Difference/Status"], widths)
    print(sep)
    print_table_row([
        "Avg Latency (ms)",
        f"{fp32_latency['avg_ms']:.2f} ms",
        f"{int8_latency['avg_ms']:.2f} ms",
        f"{fp32_delta:+.2f} ms",
    ], widths)
    print_table_row([
        "Throughput (FPS)",
        f"{fp32_latency['fps']:.1f} FPS",
        f"{int8_latency['fps']:.1f} FPS",
        f"{int8_latency['fps'] - fp32_latency['fps']:+.1f} FPS",
    ], widths)
    speedup_x = fp32_latency["avg_ms"] / int8_latency["avg_ms"] \
        if int8_latency["avg_ms"] > 0 else 0
    print_table_row([
        "Speedup Factor",
        "1.00x (baseline)",
        f"{speedup_x:.2f}x",
        f"{(speedup_x - 1) * 100:+.0f}%",
    ], widths)
    print(sep)

    # Accuracy (mAP@0.5)
    map_delta_pct = int8_map["map50"] - fp32_map["map50"]
    exceeds_threshold = abs(map_delta_pct * 100) > ACCURACY_DEGRADATION_THRESHOLD_PCT

    map_delta_str = f"{map_delta_pct:+.4f}"
    if map_delta_pct < 0 and exceeds_threshold:
        diff_status = (
            f"\033[91m{map_delta_str}  WARNING: Degradation > "
            f"{ACCURACY_DEGRADATION_THRESHOLD_PCT}%!\033[0m"
        )
    elif map_delta_pct < 0:
        diff_status = f"\033[93m{map_delta_str}\033[0m (within threshold)"
    else:
        diff_status = f"\033[92m{map_delta_str}\033[0m (no degradation)"

    print("\n  [3] Accuracy (mAP@0.5)")
    print(sep)
    print_table_row(["Metric", "FP32 Model", "INT8 Model", "Difference/Status"], widths)
    print(sep)
    print_table_row([
        "mAP@0.5",
        f"{fp32_map['map50']:.4f}",
        f"{int8_map['map50']:.4f}",
        diff_status,
    ], widths)
    print_table_row([
        "Precision",
        f"{fp32_map['precision']:.4f}",
        f"{int8_map['precision']:.4f}",
        f"{int8_map['precision'] - fp32_map['precision']:+.4f}",
    ], widths)
    print_table_row([
        "Recall",
        f"{fp32_map['recall']:.4f}",
        f"{int8_map['recall']:.4f}",
        f"{int8_map['recall'] - fp32_map['recall']:+.4f}",
    ], widths)
    print(sep)

    # Degradation warning
    if map_delta_pct < 0 and exceeds_threshold:
        print(
            f"\n\033[91m  [!!] ALERT: INT8 mAP degradation ({abs(map_delta_pct)*100:.1f}% drop)"
            f" exceeds {ACCURACY_DEGRADATION_THRESHOLD_PCT}% threshold!\033[0m"
        )
        print("  Quantization may be too aggressive for this model.")
        print("  Consider: per-channel quantization, representative dataset")
        print("  calibration with more samples, or partial quantization.\n")
    else:
        print(
            f"\n  INT8 mAP delta: {map_delta_pct:+.4f}"
            f" (threshold: {ACCURACY_DEGRADATION_THRESHOLD_PCT}%) — \033[92mOK\033[0m\n"
        )


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Quantization Trade-off Analysis: FP32 vs INT8",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python quantization_tradeoff_analysis.py \\\n"
            "    --fp32-model models/model_fp32.tflite \\\n"
            "    --int8-model models/model_int8.tflite \\\n"
            "    --image-dir test-images/ \\\n"
            "    --labels-dir test-labels/ \\\n"
            "    --num-threads 2\n"
        ),
    )
    parser.add_argument(
        "--fp32-model", required=True,
        help="Path to the FP32 baseline TFLite model",
    )
    parser.add_argument(
        "--int8-model", required=True,
        help="Path to the INT8 quantized TFLite model",
    )
    parser.add_argument(
        "--image-dir", required=True,
        help="Directory containing evaluation images",
    )
    parser.add_argument(
        "--labels-dir", default="",
        help="Directory containing YOLO-format .txt labels (for mAP eval)",
    )
    parser.add_argument(
        "--num-threads", type=int, default=2,
        help="Number of TFLite inference threads (default: 2, RPi4 optimal)",
    )
    parser.add_argument(
        "--warmup", type=int, default=WARMUP_ITERATIONS,
        help=f"Warm-up iterations before measured runs (default: {WARMUP_ITERATIONS})",
    )
    parser.add_argument(
        "--iterations", type=int, default=BENCHMARK_ITERATIONS,
        help=f"Measured inference iterations (default: {BENCHMARK_ITERATIONS})",
    )
    parser.add_argument(
        "--degradation-threshold", type=float,
        default=ACCURACY_DEGRADATION_THRESHOLD_PCT,
        help=f"mAP degradation warning threshold %% (default: {ACCURACY_DEGRADATION_THRESHOLD_PCT}%%)",
    )
    parser.add_argument(
        "--output-csv", default="",
        help="Optional path to save results as CSV",
    )
    args = parser.parse_args()

    # Validate model files
    for p, label in [(args.fp32_model, "FP32"), (args.int8_model, "INT8")]:
        if not os.path.isfile(p):
            print(f"[ERROR] {label} model not found: {p}")
            sys.exit(1)

    # Collect image paths
    image_dir = args.image_dir
    if not os.path.isdir(image_dir):
        # Try nested images/ subdirectory
        nested = os.path.join(args.image_dir, "images")
        if os.path.isdir(nested):
            image_dir = nested
        else:
            print(f"[ERROR] Image directory not found: {args.image_dir}")
            sys.exit(1)

    image_paths = sorted([
        os.path.join(image_dir, f)
        for f in os.listdir(image_dir)
        if os.path.splitext(f)[1].lower() in SUPPORTED_IMAGE_EXTS
    ])
    if not image_paths:
        print(f"[ERROR] No valid images found in {image_dir}")
        sys.exit(1)
    print(f"[INFO] Found {len(image_paths)} images in '{image_dir}'")

    # Resolve labels directory
    labels_dir = args.labels_dir.strip()
    if not labels_dir:
        candidates = [
            os.path.join(args.image_dir, "labels"),
            os.path.join(os.path.dirname(image_dir), "labels"),  # sibling
        ]
        for c in candidates:
            if os.path.isdir(c):
                labels_dir = c
                break
    eval_enabled = bool(labels_dir) and os.path.isdir(labels_dir)
    if not eval_enabled:
        print("[WARN] No labels directory found — accuracy evaluation skipped.")
        print("       Only model size + latency will be reported.\n")
    else:
        print(f"[INFO] Labels directory: '{labels_dir}' — mAP evaluation enabled")

    # --- Phase 1: Model Size Analysis ---
    print("\n" + "=" * 60)
    print("  PHASE 1: Model Size Analysis")
    print("=" * 60)
    size_result = analyze_model_size(args.fp32_model, args.int8_model)
    print(f"  FP32: {size_result['fp32_mb']:.2f} MB")
    print(f"  INT8: {size_result['int8_mb']:.2f} MB")
    print(f"  Reduction: {size_result['reduction_pct']:.1f}%")
    print(f"  Expected range: 70-75%")

    # --- Phase 2: Latency Benchmark ---
    print("\n" + "=" * 60)
    print("  PHASE 2: Inference Latency Benchmark")
    print("=" * 60)

    log_temperature("before loading FP32")
    fp32_engine = TfliteBenchmarkEngine(args.fp32_model, args.num_threads)
    log_temperature("after loading FP32")
    print(f"  FP32 Engine ready ({fp32_engine.precision_label})")

    log_temperature("before loading INT8")
    int8_engine = TfliteBenchmarkEngine(args.int8_model, args.num_threads)
    log_temperature("after loading INT8")
    print(f"  INT8 Engine ready ({int8_engine.precision_label})")

    print(f"\n  FP32 Benchmark:")
    fp32_lat = {}
    fp32_lat["avg_ms"], fp32_lat["fps"], fp32_raw = benchmark_latency(
        fp32_engine, image_paths, args.warmup, args.iterations,
    )
    log_temperature("after FP32 benchmark")
    print(f"    Avg: {fp32_lat['avg_ms']:.2f} ms ({fp32_lat['fps']:.1f} FPS)")

    print(f"\n  INT8 Benchmark:")
    int8_lat = {}
    int8_lat["avg_ms"], int8_lat["fps"], int8_raw = benchmark_latency(
        int8_engine, image_paths, args.warmup, args.iterations,
    )
    log_temperature("after INT8 benchmark")
    print(f"    Avg: {int8_lat['avg_ms']:.2f} ms ({int8_lat['fps']:.1f} FPS)")

    # --- Phase 3: Accuracy Evaluation ---
    fp32_map = {"map50": 0.0, "precision": 0.0, "recall": 0.0}
    int8_map = {"map50": 0.0, "precision": 0.0, "recall": 0.0}

    if eval_enabled:
        print("\n" + "=" * 60)
        print("  PHASE 3: Accuracy Evaluation (mAP@0.5)")
        print("=" * 60)
        print("  Evaluating FP32 ...")
        fp32_map = evaluate_accuracy(fp32_engine, image_paths, labels_dir)
        print(f"    mAP@0.5: {fp32_map['map50']:.4f}")
        print(f"    Precision: {fp32_map['precision']:.4f}, Recall: {fp32_map['recall']:.4f}")

        print("  Evaluating INT8 ...")
        int8_map = evaluate_accuracy(int8_engine, image_paths, labels_dir)
        print(f"    mAP@0.5: {int8_map['map50']:.4f}")
        print(f"    Precision: {int8_map['precision']:.4f}, Recall: {int8_map['recall']:.4f}")
    else:
        print("\n[SKIP] Accuracy evaluation skipped (no labels).")

    # --- Summary Table ---
    print_summary_table(size_result, fp32_lat, int8_lat, fp32_map, int8_map)

    # --- Optional CSV Output ---
    if args.output_csv:
        map_delta = int8_map["map50"] - fp32_map["map50"]
        rows = [
            ["Metric", "FP32", "INT8", "Difference"],
            ["Model File Size (MB)",
             f"{size_result['fp32_mb']:.2f}", f"{size_result['int8_mb']:.2f}",
             f"{size_result['reduction_pct']:.1f}% reduction"],
            ["Avg Latency (ms)",
             f"{fp32_lat['avg_ms']:.2f}", f"{int8_lat['avg_ms']:.2f}",
             f"{int8_lat['avg_ms'] - fp32_lat['avg_ms']:+.2f}"],
            ["Throughput (FPS)",
             f"{fp32_lat['fps']:.1f}", f"{int8_lat['fps']:.1f}",
             f"{int8_lat['fps'] - fp32_lat['fps']:+.1f}"],
            ["mAP@0.5",
             f"{fp32_map['map50']:.4f}", f"{int8_map['map50']:.4f}",
             f"{map_delta:+.4f}"],
        ]
        with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"[INFO] Results saved to {args.output_csv}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
