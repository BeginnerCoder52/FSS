#!/usr/bin/env python3
"""
Stage 2: standalone YOLOv11 TFLite inference for selected FRT frames.

This tool uses the production ImagePreprocessor and YoloTfliteEngine classes.
It prefers ai_edge_litert through YoloTfliteEngine(use_c_backend=False), then
falls back to the existing C TFLite reader backend when available.
"""

import argparse
import csv
import ctypes
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
FRT_SRC = REPO_ROOT / "frt_app" / "py_ai_core" / "src"
DEFAULT_MODEL = (
    REPO_ROOT
    / "frt_app"
    / "py_ai_core"
    / "models"
    / "YOLOv11n"
    / "YOLOv11n_260518_best_int8.tflite"
)


def import_frt_classes():
    """Import the real FRTApp classes with clear error messages."""
    if not FRT_SRC.exists():
        raise RuntimeError(f"FRT_IMPORT_ERROR: FRT source directory not found: {FRT_SRC}")
    if str(FRT_SRC) not in sys.path:
        sys.path.insert(0, str(FRT_SRC))
    try:
        from ImagePreprocessor import ImagePreprocessor
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "FRT_IMPORT_ERROR: cannot import ImagePreprocessor from "
            f"{FRT_SRC}: {exc}"
        ) from exc
    try:
        from YoloTfliteEngine import YoloTfliteEngine
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "FRT_IMPORT_ERROR: cannot import YoloTfliteEngine from "
            f"{FRT_SRC}: {exc}"
        ) from exc
    return ImagePreprocessor, YoloTfliteEngine


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def image_files(input_dir: Path) -> List[Path]:
    extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted(p for p in input_dir.iterdir() if p.suffix.lower() in extensions)


def ensure_dirs(output_dir: Path) -> Dict[str, Path]:
    dirs = {
        "annotated": output_dir / "annotated",
        "raw_outputs": output_dir / "raw_outputs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def runtime_name(engine) -> str:
    if getattr(engine, "use_c_backend", False) and getattr(engine, "_c_reader", None):
        return "c_tflite_reader"
    if getattr(engine, "interpreter", None) is not None:
        return "ai_edge_litert"
    return "unknown"


def load_engine(model_path: Path, confidence_threshold: float, allow_c_fallback: bool):
    ImagePreprocessor, YoloTfliteEngine = import_frt_classes()
    attempts = []

    logging.info("Trying YOLO runtime: ai_edge_litert")
    engine = YoloTfliteEngine(
        str(model_path),
        use_c_backend=False,
        confidence_threshold=confidence_threshold,
    )
    ok = engine.load_model_mmap()
    attempts.append({"runtime": "ai_edge_litert", "ok": bool(ok)})
    if ok:
        return ImagePreprocessor(640, 640), engine, "ai_edge_litert", attempts

    if allow_c_fallback:
        logging.warning("ai_edge_litert load failed; trying C TFLite reader fallback")
        engine = YoloTfliteEngine(
            str(model_path),
            use_c_backend=True,
            c_precision=2,
            confidence_threshold=confidence_threshold,
        )
        ok = engine.load_model_mmap()
        used = runtime_name(engine)
        attempts.append({"runtime": "c_tflite_reader", "ok": bool(ok and used == "c_tflite_reader")})
        if ok:
            return ImagePreprocessor(640, 640), engine, used, attempts

    raise RuntimeError(
        "YOLO_RUNTIME_ERROR: failed to load model with ai_edge_litert"
        + (" or C TFLite reader fallback" if allow_c_fallback else "")
        + f". model={model_path}"
    )


def input_output_details(engine) -> Dict:
    details = {"input_details": None, "output_details": None}
    if getattr(engine, "input_details", None) is not None:
        details["input_details"] = [
            {k: str(v) for k, v in item.items()} for item in engine.input_details
        ]
    if getattr(engine, "output_details", None) is not None:
        details["output_details"] = [
            {k: str(v) for k, v in item.items()} for item in engine.output_details
        ]
    if getattr(engine, "_c_input_size", 0):
        details["c_input_size_bytes"] = int(engine._c_input_size)
    return details


def save_raw_outputs(engine, raw_dir: Path, frame_name: str) -> List[str]:
    saved = []
    raw_dir.mkdir(parents=True, exist_ok=True)

    if getattr(engine, "use_c_backend", False) and getattr(engine, "_c_reader", None):
        try:
            num_out = ctypes.c_int(0)
            out_ptr = engine._c_lib.tflite_reader_get_output(  # noqa: SLF001
                engine._c_reader, ctypes.byref(num_out)  # noqa: SLF001
            )
            if out_ptr and num_out.value > 0:
                out_array = np.ctypeslib.as_array(out_ptr, shape=(num_out.value,)).copy()
                path = raw_dir / f"{frame_name}_output0.npy"
                np.save(path, out_array)
                saved.append(str(path))
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to save C backend raw output for %s: %s", frame_name, exc)
        return saved

    if getattr(engine, "interpreter", None) is not None and engine.output_details:
        for idx, detail in enumerate(engine.output_details):
            try:
                output = engine.interpreter.get_tensor(detail["index"])
                path = raw_dir / f"{frame_name}_output{idx}.npy"
                np.save(path, output)
                saved.append(str(path))
            except Exception as exc:  # noqa: BLE001
                logging.warning("Failed to save raw output %d for %s: %s", idx, frame_name, exc)
    return saved


def letterbox_params(frame_shape: Tuple[int, int], target_size: int = 640) -> Dict[str, float]:
    height, width = frame_shape
    scale = min(target_size / float(height), target_size / float(width))
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))
    pad_x = (target_size - new_width) / 2.0
    pad_y = (target_size - new_height) / 2.0
    return {
        "scale": scale,
        "new_width": new_width,
        "new_height": new_height,
        "pad_x": pad_x,
        "pad_y": pad_y,
    }


def bbox_norm_to_pixels(
    bbox: List[float],
    frame_shape: Tuple[int, int],
    target_size: int = 640,
) -> Tuple[List[int], List[int]]:
    height, width = frame_shape
    x1, y1, x2, y2 = bbox
    lb = letterbox_params(frame_shape, target_size)
    letterbox_px = [
        int(round(x1 * target_size)),
        int(round(y1 * target_size)),
        int(round(x2 * target_size)),
        int(round(y2 * target_size)),
    ]
    px = [
        int(round((letterbox_px[0] - lb["pad_x"]) / lb["scale"])),
        int(round((letterbox_px[1] - lb["pad_y"]) / lb["scale"])),
        int(round((letterbox_px[2] - lb["pad_x"]) / lb["scale"])),
        int(round((letterbox_px[3] - lb["pad_y"]) / lb["scale"])),
    ]
    px[0] = max(0, min(width - 1, px[0]))
    px[1] = max(0, min(height - 1, px[1]))
    px[2] = max(0, min(width - 1, px[2]))
    px[3] = max(0, min(height - 1, px[3]))
    return px, letterbox_px


def annotate_frame(frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
    out = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox_xyxy_pixels"]
        color = (0, 220, 0)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = "{} {:.2f}".format(det.get("category", det["class_id"]), det["confidence"])
        cv2.rectangle(out, (x1, max(0, y1 - 24)), (min(out.shape[1] - 1, x1 + 180), y1), color, -1)
        cv2.putText(
            out,
            label,
            (x1 + 4, max(16, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
    return out


def resolve_labels_dir(image_dir: Path, labels_dir: Optional[Path]) -> Optional[Path]:
    if labels_dir:
        return Path(labels_dir)
    if any(image_dir.glob("*.txt")):
        return image_dir
    if "images" in image_dir.parts:
        parts = list(image_dir.parts)
        idx = len(parts) - 1 - parts[::-1].index("images")
        candidate = Path(*parts[:idx], "labels", *parts[idx + 1:])
        if candidate.exists():
            return candidate
    if image_dir.name == "images" and (image_dir.parent / "labels").exists():
        return image_dir.parent / "labels"
    if (image_dir.parent / "labels").exists():
        return image_dir.parent / "labels"
    return None


def load_yolo_labels(labels_dir: Optional[Path], frame_stem: str) -> List[Dict]:
    if labels_dir is None:
        return []
    label_path = Path(labels_dir) / f"{frame_stem}.txt"
    if not label_path.exists():
        return []
    labels = []
    for line_no, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) < 5:
            logging.warning("Skipping invalid YOLO label %s:%d", label_path, line_no)
            continue
        try:
            class_id = int(float(parts[0]))
            cx, cy, w, h = [float(v) for v in parts[1:5]]
        except ValueError:
            logging.warning("Skipping non-numeric YOLO label %s:%d", label_path, line_no)
            continue
        labels.append(
            {
                "class_id": class_id,
                "bbox_xywh_norm": [cx, cy, w, h],
                "bbox_xyxy_norm": [
                    max(0.0, cx - w / 2.0),
                    max(0.0, cy - h / 2.0),
                    min(1.0, cx + w / 2.0),
                    min(1.0, cy + h / 2.0),
                ],
                "label_path": str(label_path),
            }
        )
    return labels


def bbox_iou(box_a: List[float], box_b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def detection_eval_box(det: Dict, frame_shape: Tuple[int, int]) -> List[float]:
    height, width = frame_shape
    x1, y1, x2, y2 = det["bbox_xyxy_pixels"]
    return [
        max(0.0, min(1.0, x1 / float(width))),
        max(0.0, min(1.0, y1 / float(height))),
        max(0.0, min(1.0, x2 / float(width))),
        max(0.0, min(1.0, y2 / float(height))),
    ]


def evaluate_frame(
    detections: List[Dict],
    labels: List[Dict],
    frame_shape: Tuple[int, int],
    iou_threshold: float,
) -> Dict:
    matches = []
    used_det = set()
    used_gt = set()
    candidates = []

    for det_idx, det in enumerate(detections):
        det_box = detection_eval_box(det, frame_shape)
        det["bbox_eval_xyxy_norm"] = det_box
        for gt_idx, gt in enumerate(labels):
            if det["class_id"] != gt["class_id"]:
                continue
            candidates.append((bbox_iou(det_box, gt["bbox_xyxy_norm"]), det_idx, gt_idx))

    for iou, det_idx, gt_idx in sorted(candidates, reverse=True):
        if iou < iou_threshold:
            break
        if det_idx in used_det or gt_idx in used_gt:
            continue
        used_det.add(det_idx)
        used_gt.add(gt_idx)
        matches.append({"detection_index": det_idx, "gt_index": gt_idx, "iou": iou})

    tp = len(matches)
    fp = len(detections) - tp
    fn = len(labels) - tp
    precision = tp / float(tp + fp) if tp + fp > 0 else 0.0
    recall = tp / float(tp + fn) if tp + fn > 0 else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    detection_accuracy = tp / float(tp + fp + fn) if tp + fp + fn > 0 else 0.0
    return {
        "gt_count": len(labels),
        "prediction_count": len(detections),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "detection_accuracy": detection_accuracy,
        "mean_iou": sum(m["iou"] for m in matches) / tp if tp else 0.0,
        "matches": matches,
        "unmatched_detection_indices": [idx for idx in range(len(detections)) if idx not in used_det],
        "unmatched_gt_indices": [idx for idx in range(len(labels)) if idx not in used_gt],
    }


def aggregate_evaluation(frame_evals: List[Dict], iou_threshold: float) -> Dict:
    tp = sum(item["evaluation"]["tp"] for item in frame_evals)
    fp = sum(item["evaluation"]["fp"] for item in frame_evals)
    fn = sum(item["evaluation"]["fn"] for item in frame_evals)
    gt_count = sum(item["evaluation"]["gt_count"] for item in frame_evals)
    pred_count = sum(item["evaluation"]["prediction_count"] for item in frame_evals)
    ious = [m["iou"] for item in frame_evals for m in item["evaluation"]["matches"]]
    precision = tp / float(tp + fp) if tp + fp > 0 else 0.0
    recall = tp / float(tp + fn) if tp + fn > 0 else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    detection_accuracy = tp / float(tp + fp + fn) if tp + fp + fn > 0 else 0.0
    return {
        "iou_threshold": iou_threshold,
        "frames_evaluated": len(frame_evals),
        "ground_truth_count": gt_count,
        "prediction_count": pred_count,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "detection_accuracy": detection_accuracy,
        "mean_iou": sum(ious) / len(ious) if ious else 0.0,
    }


def run_stage2(
    selected_frames_dir: Path,
    output_dir: Path,
    model_path: Path,
    labels_dir: Optional[Path] = None,
    eval_iou_threshold: float = 0.5,
    confidence_threshold: float = 0.2,
    allow_c_fallback: bool = True,
    jpeg_quality: int = 90,
) -> Dict:
    selected_frames_dir = Path(selected_frames_dir)
    output_dir = Path(output_dir)
    model_path = Path(model_path)
    if not selected_frames_dir.exists():
        raise RuntimeError(f"Selected frames directory not found: {selected_frames_dir}")
    if not model_path.exists():
        raise RuntimeError(f"YOLO model not found: {model_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dirs = ensure_dirs(output_dir)
    resolved_labels_dir = resolve_labels_dir(selected_frames_dir, labels_dir)
    if labels_dir is not None and (resolved_labels_dir is None or not resolved_labels_dir.exists()):
        raise RuntimeError(f"YOLO labels directory not found: {labels_dir}")
    preprocessor, engine, used_runtime, attempts = load_engine(
        model_path, confidence_threshold, allow_c_fallback
    )

    frames = image_files(selected_frames_dir)
    detections_json_path = output_dir / "detections.json"
    detections_csv_path = output_dir / "detections.csv"
    latency_csv_path = output_dir / "latency.csv"
    eval_summary_path = output_dir / "eval_summary.json"
    eval_matches_csv_path = output_dir / "eval_matches.csv"
    model_summary_path = output_dir / "model_summary.json"

    started_at = utc_now_iso()
    start_time = time.time()
    frame_results = []
    detection_rows = []
    latency_rows = []
    frame_evals = []
    eval_rows = []
    raw_output_files = []

    logging.info(
        "Stage 2 YOLO started: frames=%d model=%s runtime=%s labels=%s",
        len(frames),
        model_path,
        used_runtime,
        resolved_labels_dir,
    )

    for frame_idx, frame_path in enumerate(frames, start=1):
        frame = cv2.imread(str(frame_path))
        if frame is None:
            logging.warning("Skipping unreadable image: %s", frame_path)
            continue

        frame_name = frame_path.stem
        pre_start = time.time()
        tensor = preprocessor.prepare_tensor_input(frame)
        pre_ms = (time.time() - pre_start) * 1000.0
        if tensor is None:
            logging.warning("Preprocessor returned None for %s", frame_path)
            continue

        infer_start = time.time()
        engine.set_input_tensor(tensor)
        engine.invoke_inference()
        infer_ms = (time.time() - infer_start) * 1000.0

        post_start = time.time()
        detections = engine.get_output_boxes()
        post_ms = (time.time() - post_start) * 1000.0

        saved_raw = save_raw_outputs(engine, dirs["raw_outputs"], frame_name)
        raw_output_files.extend(saved_raw)

        enriched = []
        for det_idx, det in enumerate(detections):
            bbox_norm = [float(v) for v in det["bbox"]]
            px, lb_px = bbox_norm_to_pixels(bbox_norm, frame.shape[:2], 640)
            item = {
                "detection_index": det_idx,
                "class_id": int(det["class_id"]),
                "category": str(det.get("category", f"class_{det['class_id']}")),
                "confidence": float(det["confidence"]),
                "bbox": bbox_norm,
                "bbox_xyxy_norm": bbox_norm,
                "bbox_xyxy_pixels": px,
                "bbox_letterbox_pixels": lb_px,
            }
            enriched.append(item)
            detection_rows.append(
                {
                    "frame_id": frame_idx,
                    "frame_name": frame_name,
                    "detection_index": det_idx,
                    "class_id": item["class_id"],
                    "category": item["category"],
                    "confidence": f"{item['confidence']:.6f}",
                    "x1_norm": f"{bbox_norm[0]:.8f}",
                    "y1_norm": f"{bbox_norm[1]:.8f}",
                    "x2_norm": f"{bbox_norm[2]:.8f}",
                    "y2_norm": f"{bbox_norm[3]:.8f}",
                    "x1_px": px[0],
                    "y1_px": px[1],
                    "x2_px": px[2],
                    "y2_px": px[3],
                }
            )

        ground_truth = load_yolo_labels(resolved_labels_dir, frame_name)
        evaluation = None
        if resolved_labels_dir is not None:
            evaluation = evaluate_frame(
                enriched, ground_truth, frame.shape[:2], eval_iou_threshold
            )
            frame_evals.append(
                {
                    "frame_id": frame_idx,
                    "frame_name": frame_name,
                    "ground_truth": ground_truth,
                    "detections": enriched,
                    "evaluation": evaluation,
                }
            )
            for match in evaluation["matches"]:
                gt = ground_truth[match["gt_index"]]
                det = enriched[match["detection_index"]]
                eval_rows.append(
                    {
                        "frame_id": frame_idx,
                        "frame_name": frame_name,
                        "match_type": "TP",
                        "class_id": gt["class_id"],
                        "gt_index": match["gt_index"],
                        "detection_index": match["detection_index"],
                        "confidence": f"{det['confidence']:.6f}",
                        "iou": f"{match['iou']:.6f}",
                    }
                )
            for det_idx in evaluation["unmatched_detection_indices"]:
                det = enriched[det_idx]
                eval_rows.append(
                    {
                        "frame_id": frame_idx,
                        "frame_name": frame_name,
                        "match_type": "FP",
                        "class_id": det["class_id"],
                        "gt_index": "",
                        "detection_index": det_idx,
                        "confidence": f"{det['confidence']:.6f}",
                        "iou": "",
                    }
                )
            for gt_idx in evaluation["unmatched_gt_indices"]:
                gt = ground_truth[gt_idx]
                eval_rows.append(
                    {
                        "frame_id": frame_idx,
                        "frame_name": frame_name,
                        "match_type": "FN",
                        "class_id": gt["class_id"],
                        "gt_index": gt_idx,
                        "detection_index": "",
                        "confidence": "",
                        "iou": "",
                    }
                )

        annotated = annotate_frame(frame, enriched)
        annotated_path = dirs["annotated"] / f"{frame_name}_annotated.jpg"
        cv2.imwrite(str(annotated_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

        total_ms = pre_ms + infer_ms + post_ms
        latency_rows.append(
            {
                "frame_id": frame_idx,
                "frame_name": frame_name,
                "preprocess_ms": f"{pre_ms:.3f}",
                "inference_ms": f"{infer_ms:.3f}",
                "postprocess_ms": f"{post_ms:.3f}",
                "total_ms": f"{total_ms:.3f}",
                "detection_count": len(enriched),
            }
        )
        frame_results.append(
            {
                "frame_id": frame_idx,
                "frame_name": frame_name,
                "source_path": str(frame_path),
                "annotated_path": str(annotated_path),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "letterbox": letterbox_params(frame.shape[:2], 640),
                "raw_output_files": saved_raw,
                "ground_truth": ground_truth,
                "evaluation": evaluation,
                "latency_ms": {
                    "preprocess": round(pre_ms, 3),
                    "inference": round(infer_ms, 3),
                    "postprocess": round(post_ms, 3),
                    "total": round(total_ms, 3),
                },
                "detections": enriched,
            }
        )

        if frame_idx % 25 == 0:
            logging.info("Stage 2 processed=%d detections=%d", frame_idx, len(detection_rows))

    with detections_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "frame_id",
            "frame_name",
            "detection_index",
            "class_id",
            "category",
            "confidence",
            "x1_norm",
            "y1_norm",
            "x2_norm",
            "y2_norm",
            "x1_px",
            "y1_px",
            "x2_px",
            "y2_px",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detection_rows)

    with latency_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "frame_id",
            "frame_name",
            "preprocess_ms",
            "inference_ms",
            "postprocess_ms",
            "total_ms",
            "detection_count",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(latency_rows)

    evaluation_summary = None
    if resolved_labels_dir is not None:
        evaluation_summary = aggregate_evaluation(frame_evals, eval_iou_threshold)
        with eval_matches_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            fieldnames = [
                "frame_id",
                "frame_name",
                "match_type",
                "class_id",
                "gt_index",
                "detection_index",
                "confidence",
                "iou",
            ]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(eval_rows)
        eval_summary_path.write_text(
            json.dumps(evaluation_summary, indent=2), encoding="utf-8"
        )

    latencies = [float(row["total_ms"]) for row in latency_rows]
    infer_latencies = [float(row["inference_ms"]) for row in latency_rows]
    elapsed = time.time() - start_time
    detections_payload = {
        "stage": "stage2_yolo",
        "image_dir": str(selected_frames_dir),
        "selected_frames_dir": str(selected_frames_dir),
        "model_path": str(model_path),
        "runtime_used": used_runtime,
        "runtime_attempts": attempts,
        "confidence_threshold": confidence_threshold,
        "labels_dir": str(resolved_labels_dir) if resolved_labels_dir else None,
        "eval_iou_threshold": eval_iou_threshold,
        "evaluation": evaluation_summary,
        "frames": frame_results,
    }
    detections_json_path.write_text(
        json.dumps(detections_payload, indent=2), encoding="utf-8"
    )

    summary = {
        "stage": "stage2_yolo",
        "image_dir": str(selected_frames_dir),
        "selected_frames_dir": str(selected_frames_dir),
        "output_dir": str(output_dir),
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "elapsed_sec": round(elapsed, 3),
        "model_path": str(model_path),
        "runtime_preference": "ai_edge_litert",
        "runtime_used": used_runtime,
        "runtime_attempts": attempts,
        "fallback_runtime_used": used_runtime != "ai_edge_litert",
        "confidence_threshold": confidence_threshold,
        "labels_dir": str(resolved_labels_dir) if resolved_labels_dir else None,
        "eval_iou_threshold": eval_iou_threshold,
        "evaluation": evaluation_summary,
        "frames_seen": len(frames),
        "frames_processed": len(frame_results),
        "total_detections": len(detection_rows),
        "latency_ms": {
            "total_avg": float(sum(latencies) / len(latencies)) if latencies else 0.0,
            "total_min": min(latencies) if latencies else 0.0,
            "total_max": max(latencies) if latencies else 0.0,
            "inference_avg": float(sum(infer_latencies) / len(infer_latencies))
            if infer_latencies
            else 0.0,
        },
        "engine_details": input_output_details(engine),
        "outputs": {
            "annotated": str(dirs["annotated"]),
            "raw_outputs": str(dirs["raw_outputs"]),
            "detections_json": str(detections_json_path),
            "detections_csv": str(detections_csv_path),
            "latency_csv": str(latency_csv_path),
            "eval_summary_json": str(eval_summary_path) if evaluation_summary else "",
            "eval_matches_csv": str(eval_matches_csv_path) if evaluation_summary else "",
            "model_summary_json": str(model_summary_path),
        },
        "raw_output_file_count": len(raw_output_files),
    }
    model_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logging.info("Stage 2 complete: %s", model_summary_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRT test stage 2: YOLO TFLite inference")
    parser.add_argument("--image-dir", type=Path, help="Dataset image directory")
    parser.add_argument("--selected-frames", type=Path, help="Alias for --image-dir")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--labels-dir", type=Path, help="YOLO .txt label directory")
    parser.add_argument("--eval-iou-threshold", type=float, default=0.5)
    parser.add_argument("--confidence-threshold", type=float, default=0.2)
    parser.add_argument("--no-c-fallback", action="store_true")
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    try:
        image_dir = args.image_dir or args.selected_frames
        if image_dir is None:
            raise RuntimeError("Stage 2 requires --image-dir (or legacy --selected-frames)")
        run_stage2(
            selected_frames_dir=image_dir,
            output_dir=args.output_dir,
            model_path=args.model,
            labels_dir=args.labels_dir,
            eval_iou_threshold=args.eval_iou_threshold,
            confidence_threshold=args.confidence_threshold,
            allow_c_fallback=not args.no_c_fallback,
            jpeg_quality=args.jpeg_quality,
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
