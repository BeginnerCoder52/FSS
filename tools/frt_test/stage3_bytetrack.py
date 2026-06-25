#!/usr/bin/env python3
"""
Stage 3: ByteTrack replay for FRTApp detections.

This stage does not call YOLO. It reads stage2 detections.json, feeds copied
detections into the production ByteTracker class, and writes tracking artifacts.
"""

import argparse
import copy
import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
FRT_SRC = REPO_ROOT / "frt_app" / "py_ai_core" / "src"


def import_byte_tracker():
    """Import the real FRTApp ByteTracker with a clear failure message."""
    if not FRT_SRC.exists():
        raise RuntimeError(f"FRT_IMPORT_ERROR: FRT source directory not found: {FRT_SRC}")
    if str(FRT_SRC) not in sys.path:
        sys.path.insert(0, str(FRT_SRC))
    try:
        from ByteTracker import ByteTracker
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "FRT_IMPORT_ERROR: cannot import ByteTracker from "
            f"{FRT_SRC}: {exc}"
        ) from exc
    return ByteTracker


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def color_for_id(track_id: int) -> Tuple[int, int, int]:
    rng = np.random.default_rng(track_id * 9973)
    color = rng.integers(64, 255, size=3)
    return int(color[0]), int(color[1]), int(color[2])


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def xywh_to_xyxy_norm(bbox_xywh: List[float]) -> List[float]:
    x, y, w, h = [float(v) for v in bbox_xywh]
    return [clamp01(x), clamp01(y), clamp01(x + w), clamp01(y + h)]


def xywh_iou(box_a: List[float], box_b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = xywh_to_xyxy_norm(box_a)
    bx1, by1, bx2, by2 = xywh_to_xyxy_norm(box_b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def norm_xyxy_to_pixels(
    bbox_xyxy: List[float],
    width: int,
    height: int,
    letterbox: Optional[Dict] = None,
) -> List[int]:
    x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
    if letterbox and letterbox.get("scale"):
        target_size = 640.0
        lb_px = [x1 * target_size, y1 * target_size, x2 * target_size, y2 * target_size]
        scale = float(letterbox["scale"])
        pad_x = float(letterbox.get("pad_x", 0.0))
        pad_y = float(letterbox.get("pad_y", 0.0))
        px = [
            int(round((lb_px[0] - pad_x) / scale)),
            int(round((lb_px[1] - pad_y) / scale)),
            int(round((lb_px[2] - pad_x) / scale)),
            int(round((lb_px[3] - pad_y) / scale)),
        ]
    else:
        px = [
            int(round(x1 * width)),
            int(round(y1 * height)),
            int(round(x2 * width)),
            int(round(y2 * height)),
        ]
    px[0] = max(0, min(width - 1, px[0]))
    px[1] = max(0, min(height - 1, px[1]))
    px[2] = max(0, min(width - 1, px[2]))
    px[3] = max(0, min(height - 1, px[3]))
    return px


def annotate_tracks(frame: np.ndarray, tracks: List[Dict], letterbox: Optional[Dict]) -> np.ndarray:
    out = frame.copy()
    height, width = out.shape[:2]
    for track in tracks:
        x1, y1, x2, y2 = norm_xyxy_to_pixels(
            track["bbox_xyxy_norm"], width, height, letterbox
        )
        color = color_for_id(int(track["track_id"]))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = "ID {} C{} {:.2f}".format(
            track["track_id"], track["class_id"], track["confidence"]
        )
        cv2.rectangle(out, (x1, max(0, y1 - 24)), (min(width - 1, x1 + 150), y1), color, -1)
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


def detection_copy_for_tracker(detections: List[Dict]) -> List[Dict]:
    copied = []
    for det in detections:
        bbox = det.get("bbox") or det.get("bbox_xyxy_norm")
        if not bbox or len(bbox) != 4:
            continue
        copied.append(
            {
                "bbox": [float(v) for v in bbox],
                "confidence": float(det.get("confidence", 0.0)),
                "class_id": int(det.get("class_id", 0)),
                "category": det.get("category", f"class_{det.get('class_id', 0)}"),
            }
        )
    return copied


def draw_trajectory_plot(
    output_path: Path,
    trajectories: Dict[int, Dict],
    width: int,
    height: int,
) -> None:
    canvas = np.full((height, width, 3), 28, dtype=np.uint8)
    for track_id, info in trajectories.items():
        points = info.get("points", [])
        if len(points) < 1:
            continue
        color = color_for_id(int(track_id))
        pts = np.array(
            [
                [
                    int(round(clamp01(p["cx_norm"]) * (width - 1))),
                    int(round(clamp01(p["cy_norm"]) * (height - 1))),
                ]
                for p in points
            ],
            dtype=np.int32,
        )
        if len(pts) >= 2:
            cv2.polylines(canvas, [pts], False, color, 2, cv2.LINE_AA)
        for point in pts:
            cv2.circle(canvas, tuple(point), 3, color, -1, cv2.LINE_AA)
        cv2.putText(
            canvas,
            f"ID {track_id}",
            tuple(pts[-1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(output_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])


def run_stage3(
    detections_json: Path,
    output_dir: Path,
    max_age: int = 30,
    high_thresh: float = 0.85,
    match_thresh: float = 0.8,
    id_switch_iou: float = 0.8,
    jpeg_quality: int = 90,
) -> Dict:
    ByteTracker = import_byte_tracker()
    detections_json = Path(detections_json)
    output_dir = Path(output_dir)
    if not detections_json.exists():
        raise RuntimeError(f"detections.json not found: {detections_json}")
    output_dir.mkdir(parents=True, exist_ok=True)
    tracked_dir = output_dir / "tracked_frames"
    tracked_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(detections_json.read_text(encoding="utf-8"))
    frames = sorted(payload.get("frames", []), key=lambda item: int(item.get("frame_id", 0)))

    tracker = ByteTracker(max_age=max_age, high_thresh=high_thresh, match_thresh=match_thresh)
    started_at = utc_now_iso()
    frame_outputs = []
    track_rows = []
    lifecycles: Dict[int, Dict] = {}
    trajectories: Dict[int, Dict] = {}
    previous_states: Dict[int, str] = {}
    previous_active: List[Dict] = []
    lost_events = []
    class_changes = []
    high_iou_id_changes = []
    plot_width = 640
    plot_height = 480

    logging.info("Stage 3 ByteTrack started: frames=%d", len(frames))

    for frame_data in frames:
        frame_id = int(frame_data["frame_id"])
        detections = detection_copy_for_tracker(frame_data.get("detections", []))
        tracked = tracker.update(copy.deepcopy(detections))
        normalized_tracks = []

        for track in tracked:
            track_id = int(track["track_id"])
            bbox_xywh = [float(v) for v in track["bbox"]]
            bbox_xyxy = xywh_to_xyxy_norm(bbox_xywh)
            cx = clamp01(bbox_xywh[0] + bbox_xywh[2] / 2.0)
            cy = clamp01(bbox_xywh[1] + bbox_xywh[3] / 2.0)
            class_id = int(track["class_id"])
            confidence = float(track["confidence"])

            lifecycle = lifecycles.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "class_id": class_id,
                    "first_frame": frame_id,
                    "last_active_frame": frame_id,
                    "active_frames": 0,
                    "lost_observations": 0,
                    "lost_events": 0,
                    "status": "ACTIVE",
                },
            )
            if lifecycle["class_id"] != class_id:
                class_changes.append(
                    {
                        "track_id": track_id,
                        "frame_id": frame_id,
                        "previous_class_id": lifecycle["class_id"],
                        "new_class_id": class_id,
                    }
                )
            lifecycle["last_active_frame"] = frame_id
            lifecycle["active_frames"] += 1
            lifecycle["status"] = "ACTIVE"

            trajectory = trajectories.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "class_id": class_id,
                    "points": [],
                    "first_frame": frame_id,
                    "last_frame": frame_id,
                },
            )
            trajectory["last_frame"] = frame_id
            trajectory["points"].append(
                {
                    "frame_id": frame_id,
                    "cx_norm": cx,
                    "cy_norm": cy,
                    "confidence": confidence,
                }
            )

            item = {
                "track_id": track_id,
                "class_id": class_id,
                "confidence": confidence,
                "bbox_xywh_norm": bbox_xywh,
                "bbox_xyxy_norm": bbox_xyxy,
                "centroid_norm": [cx, cy],
                "state": "ACTIVE",
            }
            normalized_tracks.append(item)
            track_rows.append(
                {
                    "frame_id": frame_id,
                    "frame_name": frame_data.get("frame_name", ""),
                    "track_id": track_id,
                    "class_id": class_id,
                    "confidence": f"{confidence:.6f}",
                    "x_norm": f"{bbox_xywh[0]:.8f}",
                    "y_norm": f"{bbox_xywh[1]:.8f}",
                    "w_norm": f"{bbox_xywh[2]:.8f}",
                    "h_norm": f"{bbox_xywh[3]:.8f}",
                    "cx_norm": f"{cx:.8f}",
                    "cy_norm": f"{cy:.8f}",
                    "state": "ACTIVE",
                }
            )

        for internal_track in tracker.tracks:
            track_id = int(internal_track.track_id)
            state = str(internal_track.state)
            lifecycle = lifecycles.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "class_id": int(internal_track.class_id),
                    "first_frame": frame_id,
                    "last_active_frame": None,
                    "active_frames": 0,
                    "lost_observations": 0,
                    "lost_events": 0,
                    "status": state,
                },
            )
            if state == "LOST":
                lifecycle["lost_observations"] += 1
                lifecycle["status"] = "LOST"
                if previous_states.get(track_id) != "LOST":
                    lifecycle["lost_events"] += 1
                    lost_events.append({"track_id": track_id, "frame_id": frame_id})
            previous_states[track_id] = state

        for prev in previous_active:
            for cur in normalized_tracks:
                if prev["track_id"] == cur["track_id"]:
                    continue
                if prev["class_id"] != cur["class_id"]:
                    continue
                iou = xywh_iou(prev["bbox_xywh_norm"], cur["bbox_xywh_norm"])
                if iou >= id_switch_iou:
                    high_iou_id_changes.append(
                        {
                            "previous_frame_id": prev["frame_id"],
                            "current_frame_id": frame_id,
                            "previous_track_id": prev["track_id"],
                            "current_track_id": cur["track_id"],
                            "class_id": cur["class_id"],
                            "iou": round(iou, 6),
                        }
                    )

        current_active = []
        for item in normalized_tracks:
            item_for_prev = dict(item)
            item_for_prev["frame_id"] = frame_id
            current_active.append(item_for_prev)
        previous_active = current_active

        tracked_path = ""
        source_path = frame_data.get("source_path")
        if source_path:
            frame = cv2.imread(str(source_path))
            if frame is not None:
                plot_height, plot_width = frame.shape[:2]
                annotated = annotate_tracks(frame, normalized_tracks, frame_data.get("letterbox"))
                tracked_path_obj = tracked_dir / f"{frame_data.get('frame_name', frame_id)}_tracked.jpg"
                cv2.imwrite(
                    str(tracked_path_obj),
                    annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
                )
                tracked_path = str(tracked_path_obj)

        frame_outputs.append(
            {
                "frame_id": frame_id,
                "frame_name": frame_data.get("frame_name", ""),
                "source_path": source_path,
                "tracked_frame_path": tracked_path,
                "detections_count": len(detections),
                "tracks": normalized_tracks,
            }
        )

    tracks_json_path = output_dir / "tracks.json"
    tracks_csv_path = output_dir / "tracks.csv"
    lifecycle_csv_path = output_dir / "track_lifecycle.csv"
    id_switch_path = output_dir / "id_switch_report.json"
    trajectory_plot_path = output_dir / "trajectory_plot.jpg"

    with tracks_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "frame_id",
            "frame_name",
            "track_id",
            "class_id",
            "confidence",
            "x_norm",
            "y_norm",
            "w_norm",
            "h_norm",
            "cx_norm",
            "cy_norm",
            "state",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(track_rows)

    lifecycle_rows = []
    for lifecycle in sorted(lifecycles.values(), key=lambda item: item["track_id"]):
        lifecycle_rows.append(
            {
                "track_id": lifecycle["track_id"],
                "class_id": lifecycle["class_id"],
                "first_frame": lifecycle["first_frame"],
                "last_active_frame": lifecycle.get("last_active_frame") or "",
                "active_frames": lifecycle["active_frames"],
                "lost_observations": lifecycle["lost_observations"],
                "lost_events": lifecycle["lost_events"],
                "status": lifecycle["status"],
            }
        )
    with lifecycle_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "track_id",
            "class_id",
            "first_frame",
            "last_active_frame",
            "active_frames",
            "lost_observations",
            "lost_events",
            "status",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lifecycle_rows)

    draw_trajectory_plot(trajectory_plot_path, trajectories, plot_width, plot_height)

    id_switch_report = {
        "stage": "stage3_bytetrack",
        "note": "No ground truth is available; id_switch_candidates are high-IoU adjacent-frame track-id changes.",
        "lost_event_count": len(lost_events),
        "lost_events": lost_events,
        "class_change_count": len(class_changes),
        "class_changes": class_changes,
        "id_switch_candidate_count": len(high_iou_id_changes),
        "id_switch_candidates": high_iou_id_changes,
    }
    id_switch_path.write_text(json.dumps(id_switch_report, indent=2), encoding="utf-8")

    summary = {
        "stage": "stage3_bytetrack",
        "input_detections_json": str(detections_json),
        "output_dir": str(output_dir),
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "tracker_config": {
            "max_age": max_age,
            "high_thresh": high_thresh,
            "match_thresh": match_thresh,
        },
        "frames_processed": len(frames),
        "total_tracks_created": len(lifecycles),
        "active_track_rows": len(track_rows),
        "lost_event_count": len(lost_events),
        "id_switch_candidate_count": len(high_iou_id_changes),
        "outputs": {
            "tracked_frames": str(tracked_dir),
            "tracks_json": str(tracks_json_path),
            "tracks_csv": str(tracks_csv_path),
            "track_lifecycle_csv": str(lifecycle_csv_path),
            "id_switch_report_json": str(id_switch_path),
            "trajectory_plot_jpg": str(trajectory_plot_path),
        },
    }

    tracks_payload = {
        "stage": "stage3_bytetrack",
        "input_detections_json": str(detections_json),
        "tracker_config": summary["tracker_config"],
        "frames": frame_outputs,
        "trajectories": sorted(trajectories.values(), key=lambda item: item["track_id"]),
        "lifecycles": lifecycle_rows,
        "summary": summary,
    }
    tracks_json_path.write_text(json.dumps(tracks_payload, indent=2), encoding="utf-8")

    logging.info("Stage 3 complete: %s", tracks_json_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRT test stage 3: ByteTrack replay")
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-age", type=int, default=30)
    parser.add_argument("--high-thresh", type=float, default=0.85)
    parser.add_argument("--match-thresh", type=float, default=0.8)
    parser.add_argument("--id-switch-iou", type=float, default=0.8)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    try:
        run_stage3(
            detections_json=args.detections,
            output_dir=args.output_dir,
            max_age=args.max_age,
            high_thresh=args.high_thresh,
            match_thresh=args.match_thresh,
            id_switch_iou=args.id_switch_iou,
            jpeg_quality=args.jpeg_quality,
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
