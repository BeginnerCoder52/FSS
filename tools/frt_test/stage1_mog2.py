#!/usr/bin/env python3
"""
Stage 1: MOG2 frame selection for FRTApp offline/live testing.

This tool intentionally uses the production MotionDetector class from
frt_app/py_ai_core/src and only adds file/CSV/JSON debug output around it.
"""

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
FRT_SRC = REPO_ROOT / "frt_app" / "py_ai_core" / "src"
DEFAULT_TARGET_FPS = 5.0


def import_motion_detector():
    """Import the real FRTApp MotionDetector with a clear failure message."""
    if not FRT_SRC.exists():
        raise RuntimeError(f"FRT_IMPORT_ERROR: FRT source directory not found: {FRT_SRC}")
    if str(FRT_SRC) not in sys.path:
        sys.path.insert(0, str(FRT_SRC))
    try:
        from MotionDetector import MotionDetector
    except Exception as exc:  # noqa: BLE001 - report exact import problem to user
        raise RuntimeError(
            "FRT_IMPORT_ERROR: cannot import MotionDetector from "
            f"{FRT_SRC}: {exc}"
        ) from exc
    return MotionDetector


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dirs(output_dir: Path) -> Dict[str, Path]:
    dirs = {
        "frames": output_dir / "frames",
        "background": output_dir / "background",
        "masks": output_dir / "masks",
        "compare": output_dir / "compare",
        "selected_frames": output_dir / "selected_frames",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def write_image(path: Path, image: np.ndarray, jpeg_quality: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        ok = cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    else:
        ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"Failed to write image: {path}")


def normalize_panel(image: Optional[np.ndarray], size: Tuple[int, int]) -> np.ndarray:
    width, height = size
    if image is None:
        panel = np.zeros((height, width, 3), dtype=np.uint8)
    elif len(image.shape) == 2:
        panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        panel = image.copy()
    if panel.shape[:2] != (height, width):
        panel = cv2.resize(panel, (width, height), interpolation=cv2.INTER_LINEAR)
    return panel


def label_panel(panel: np.ndarray, label: str) -> np.ndarray:
    out = panel.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 28), (0, 0, 0), -1)
    cv2.putText(
        out,
        label,
        (8, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return out


def build_compare_image(
    frame: np.ndarray,
    background_before: Optional[np.ndarray],
    mask: np.ndarray,
    decision: str,
    motion_ratio: float,
) -> np.ndarray:
    height, width = frame.shape[:2]
    size = (width, height)

    frame_panel = label_panel(normalize_panel(frame, size), "frame(t)")
    bg_panel = label_panel(
        normalize_panel(background_before, size),
        "background_model(t-1)",
    )

    mask_panel = normalize_panel(mask, size)
    mask_panel = cv2.applyColorMap(mask_panel, cv2.COLORMAP_JET)
    mask_panel = label_panel(mask_panel, "foreground_mask")

    overlay = frame.copy()
    overlay_mask = mask > 0
    overlay[overlay_mask] = (0.35 * overlay[overlay_mask] + np.array([0, 0, 180])).astype(
        np.uint8
    )
    overlay_label = f"{decision} motion_ratio={motion_ratio:.6f}"
    overlay_panel = label_panel(overlay, overlay_label)

    top = np.hstack([frame_panel, bg_panel])
    bottom = np.hstack([mask_panel, overlay_panel])
    return np.vstack([top, bottom])


def open_capture(source_type: str, source: str) -> cv2.VideoCapture:
    capture_source = int(source) if source_type == "camera" and source.isdigit() else source
    cap = cv2.VideoCapture(capture_source)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open {source_type} source: {source}")
    return cap


def run_stage1(
    source_type: str,
    source: str,
    output_dir: Path,
    max_frames: int = 0,
    frame_stride: int = 1,
    target_fps: float = DEFAULT_TARGET_FPS,
    motion_threshold: float = 1.0,
    jpeg_quality: int = 90,
) -> Dict:
    MotionDetector = import_motion_detector()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dirs = ensure_dirs(output_dir)

    detector = MotionDetector(threshold_percent=motion_threshold)
    detector.init_mog2()
    if detector.mog2_subtractor is None:
        raise RuntimeError("MotionDetector.init_mog2() did not create a subtractor")

    cap = open_capture(source_type, source)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    csv_path = output_dir / "mog2_decision.csv"
    start_time = time.time()
    started_at = utc_now_iso()
    processed = 0
    selected = 0
    skipped = 0
    fps_skipped = 0
    source_frame_index = 0
    motion_ratios = []
    target_interval_ms = 1000.0 / target_fps if target_fps and target_fps > 0 else 0.0
    next_video_timestamp_ms = None
    last_live_process_time = 0.0
    processed_timestamps_ms = []

    logging.info(
        "Stage 1 MOG2 started: source=%s output=%s target_fps=%.2f",
        source,
        output_dir,
        target_fps,
    )

    fieldnames = [
        "frame_id",
        "source_frame_index",
        "timestamp_ms",
        "frame_path",
        "background_path",
        "mask_path",
        "compare_path",
        "selected_path",
        "background_available",
        "motion_pixels",
        "total_pixels",
        "motion_ratio",
        "motion_threshold_percent",
        "decision",
    ]

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break

                source_frame_index += 1
                raw_stamp_ms = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                if raw_stamp_ms > 0:
                    stamp_ms = raw_stamp_ms
                elif fps > 0:
                    stamp_ms = (source_frame_index - 1) * 1000.0 / fps
                elif target_interval_ms > 0:
                    stamp_ms = (source_frame_index - 1) * target_interval_ms
                else:
                    stamp_ms = 0.0

                if source_type == "video" and target_interval_ms > 0:
                    if next_video_timestamp_ms is None:
                        next_video_timestamp_ms = stamp_ms
                    if stamp_ms + 1e-6 < next_video_timestamp_ms:
                        fps_skipped += 1
                        continue
                    next_video_timestamp_ms = stamp_ms + target_interval_ms

                if frame_stride > 1 and (source_frame_index - 1) % frame_stride != 0:
                    continue
                if max_frames > 0 and processed >= max_frames:
                    break

                if source_type == "camera" and target_interval_ms > 0:
                    target_interval_sec = target_interval_ms / 1000.0
                    now = time.monotonic()
                    if last_live_process_time > 0:
                        sleep_sec = target_interval_sec - (now - last_live_process_time)
                        if sleep_sec > 0:
                            time.sleep(sleep_sec)
                    last_live_process_time = time.monotonic()

                processed += 1
                frame_id = processed
                processed_timestamps_ms.append(stamp_ms)

                background_before = detector.mog2_subtractor.getBackgroundImage()
                background_available = background_before is not None
                mask = detector.apply_background_subtraction(frame)
                if mask is None:
                    mask = np.zeros(frame.shape[:2], dtype=np.uint8)

                motion_pixels = int(cv2.countNonZero(mask))
                total_pixels = int(mask.shape[0] * mask.shape[1])
                motion_ratio = float(motion_pixels / total_pixels) if total_pixels else 0.0
                motion_ratios.append(motion_ratio)
                motion_detected = detector.is_motion_detected(mask)
                decision = "SEND_TO_MODEL" if motion_detected else "SKIP_FRAME"

                name = f"frame_{frame_id:06d}"
                frame_path = dirs["frames"] / f"{name}.jpg"
                bg_path = dirs["background"] / f"background_{frame_id:06d}.jpg"
                mask_path = dirs["masks"] / f"mask_{frame_id:06d}.png"
                compare_path = dirs["compare"] / f"compare_{frame_id:06d}.jpg"
                selected_path = dirs["selected_frames"] / f"{name}.jpg"

                background_to_write = (
                    background_before
                    if background_before is not None
                    else np.zeros_like(frame)
                )
                compare = build_compare_image(
                    frame, background_before, mask, decision, motion_ratio
                )

                write_image(frame_path, frame, jpeg_quality)
                write_image(bg_path, background_to_write, jpeg_quality)
                write_image(mask_path, mask)
                write_image(compare_path, compare, jpeg_quality)

                selected_path_text = ""
                if motion_detected:
                    write_image(selected_path, frame, jpeg_quality)
                    selected += 1
                    selected_path_text = str(selected_path)
                else:
                    skipped += 1

                writer.writerow(
                    {
                        "frame_id": frame_id,
                        "source_frame_index": source_frame_index,
                        "timestamp_ms": round(stamp_ms, 3),
                        "frame_path": str(frame_path),
                        "background_path": str(bg_path),
                        "mask_path": str(mask_path),
                        "compare_path": str(compare_path),
                        "selected_path": selected_path_text,
                        "background_available": background_available,
                        "motion_pixels": motion_pixels,
                        "total_pixels": total_pixels,
                        "motion_ratio": f"{motion_ratio:.8f}",
                        "motion_threshold_percent": motion_threshold,
                        "decision": decision,
                    }
                )

                if processed % 50 == 0:
                    logging.info(
                        "Stage 1 processed=%d selected=%d skipped=%d",
                        processed,
                        selected,
                        skipped,
                    )
    except KeyboardInterrupt:
        logging.warning("Stage 1 interrupted by user; writing partial summary")
    finally:
        cap.release()

    elapsed = time.time() - start_time
    source_duration_sec = 0.0
    if processed_timestamps_ms:
        span_ms = processed_timestamps_ms[-1] - processed_timestamps_ms[0]
        if target_interval_ms > 0:
            source_duration_sec = (span_ms + target_interval_ms) / 1000.0
        elif len(processed_timestamps_ms) > 1:
            source_duration_sec = span_ms / 1000.0
        elif fps > 0:
            source_duration_sec = 1.0 / fps

    summary = {
        "stage": "stage1_mog2",
        "source_type": source_type,
        "source": source,
        "output_dir": str(output_dir),
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "elapsed_sec": round(elapsed, 3),
        "input_fps": fps,
        "target_fps": target_fps,
        "fps_limited": bool(target_interval_ms > 0),
        "fps_skipped_frames": fps_skipped,
        "effective_processed_fps": float(processed / source_duration_sec)
        if source_duration_sec > 0
        else 0.0,
        "processing_throughput_fps": float(processed / elapsed) if elapsed > 0 else 0.0,
        "processed_source_duration_sec": source_duration_sec,
        "input_width": frame_width,
        "input_height": frame_height,
        "frame_stride": frame_stride,
        "max_frames": max_frames,
        "motion_threshold_percent": motion_threshold,
        "total_processed_frames": processed,
        "selected_frames": selected,
        "skipped_frames": skipped,
        "selection_rate": float(selected / processed) if processed else 0.0,
        "motion_ratio_min": min(motion_ratios) if motion_ratios else 0.0,
        "motion_ratio_max": max(motion_ratios) if motion_ratios else 0.0,
        "motion_ratio_avg": float(sum(motion_ratios) / len(motion_ratios))
        if motion_ratios
        else 0.0,
        "outputs": {
            "frames": str(dirs["frames"]),
            "background": str(dirs["background"]),
            "masks": str(dirs["masks"]),
            "compare": str(dirs["compare"]),
            "selected_frames": str(dirs["selected_frames"]),
            "decisions_csv": str(csv_path),
        },
    }

    summary_path = output_dir / "mog2_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logging.info("Stage 1 complete: %s", summary_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRT test stage 1: MOG2 frame selection")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Input video file")
    source.add_argument("--camera", help="Camera device path or numeric index")
    parser.add_argument("--output-dir", type=Path, required=True, help="Stage output directory")
    parser.add_argument("--max-frames", type=int, default=0, help="0 means no limit")
    parser.add_argument("--frame-stride", type=int, default=1, help="Process every Nth frame")
    parser.add_argument(
        "--target-fps",
        type=float,
        default=DEFAULT_TARGET_FPS,
        help="Limit stage 1 processing rate. Default matches FRTApp: 5 FPS. Use 0 to disable.",
    )
    parser.add_argument(
        "--motion-threshold",
        type=float,
        default=1.0,
        help="Motion threshold in percent, passed to MotionDetector",
    )
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    try:
        if args.input:
            run_stage1(
                source_type="video",
                source=str(args.input),
                output_dir=args.output_dir,
                max_frames=args.max_frames,
                frame_stride=max(1, args.frame_stride),
                target_fps=args.target_fps,
                motion_threshold=args.motion_threshold,
                jpeg_quality=args.jpeg_quality,
            )
        else:
            run_stage1(
                source_type="camera",
                source=str(args.camera),
                output_dir=args.output_dir,
                max_frames=args.max_frames,
                frame_stride=max(1, args.frame_stride),
                target_fps=args.target_fps,
                motion_threshold=args.motion_threshold,
                jpeg_quality=args.jpeg_quality,
            )
    except Exception as exc:  # noqa: BLE001 - CLI should print clear terminal error
        logging.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
