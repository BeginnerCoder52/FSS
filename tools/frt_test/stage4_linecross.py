#!/usr/bin/env python3
"""
Stage 4: virtual line crossing replay for FRTApp tracks.

This stage uses the production LineCrossDetector class and reconstructs Track
objects from stage3 trajectories. It emits IN/OUT events equivalent to the
FoodDetected boundary logic used by FRTApp.
"""

import argparse
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


def import_linecross_classes():
    """Import real FRTApp LineCrossDetector and Track classes."""
    if not FRT_SRC.exists():
        raise RuntimeError(f"FRT_IMPORT_ERROR: FRT source directory not found: {FRT_SRC}")
    if str(FRT_SRC) not in sys.path:
        sys.path.insert(0, str(FRT_SRC))
    try:
        from ByteTracker import LineCrossDetector, Track
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "FRT_IMPORT_ERROR: cannot import LineCrossDetector/Track from "
            f"{FRT_SRC}: {exc}"
        ) from exc
    try:
        from ByteTracker import _get_food_name
    except Exception:  # noqa: BLE001
        _get_food_name = lambda class_id: f"class_{class_id}"  # noqa: E731
    return LineCrossDetector, Track, _get_food_name


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


def read_canvas_from_tracks(tracks_payload: Dict) -> Tuple[np.ndarray, int, int]:
    for frame in reversed(tracks_payload.get("frames", [])):
        for key in ("source_path", "tracked_frame_path"):
            path = frame.get(key)
            if not path:
                continue
            image = cv2.imread(str(path))
            if image is not None:
                height, width = image.shape[:2]
                return image, width, height
    width, height = 640, 480
    return np.full((height, width, 3), 28, dtype=np.uint8), width, height


def load_line_config(
    line_config: Optional[Path],
    line_type: str,
    line_pos: float,
    width: int,
    height: int,
) -> Dict:
    config = {"type": line_type, "pos": float(line_pos)}
    if line_config:
        raw = json.loads(Path(line_config).read_text(encoding="utf-8"))
        if "line" in raw and isinstance(raw["line"], dict):
            raw = raw["line"]
        config["type"] = raw.get("type", config["type"])
        config["pos"] = float(raw.get("pos", config["pos"]))

    if config["type"] not in {"horizontal", "vertical"}:
        raise RuntimeError(f"Invalid line type: {config['type']}")

    # Tracks are stored in normalized coordinates. Accept pixel pos for CLI
    # convenience and normalize it here.
    if config["pos"] > 1.0:
        if config["type"] == "horizontal":
            config["pos"] = config["pos"] / float(height)
        else:
            config["pos"] = config["pos"] / float(width)
    config["pos"] = clamp01(config["pos"])
    return config


def build_track_object(Track, track_id: int, class_id: int, point: Dict):
    cx = clamp01(point["cx_norm"])
    cy = clamp01(point["cy_norm"])
    bbox = [max(0.0, cx - 0.001), max(0.0, cy - 0.001), 0.002, 0.002]
    track = Track(bbox, float(point.get("confidence", 1.0)), class_id, track_id)
    track.centroid_x_history = [cx]
    track.centroid_y_history = [cy]
    return track


def append_point_to_track(track, point: Dict) -> None:
    track.centroid_x_history.append(clamp01(point["cx_norm"]))
    track.centroid_y_history.append(clamp01(point["cy_norm"]))
    if len(track.centroid_x_history) > 10:
        track.centroid_x_history.pop(0)
        track.centroid_y_history.pop(0)


def draw_visualization(
    output_path: Path,
    base: np.ndarray,
    line: Dict,
    trajectories: List[Dict],
    events: List[Dict],
    jpeg_quality: int,
) -> None:
    canvas = base.copy()
    height, width = canvas.shape[:2]

    if line["type"] == "horizontal":
        y = int(round(line["pos"] * (height - 1)))
        cv2.line(canvas, (0, y), (width - 1, y), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(
            canvas,
            f"line y={line['pos']:.3f}",
            (8, max(18, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    else:
        x = int(round(line["pos"] * (width - 1)))
        cv2.line(canvas, (x, 0), (x, height - 1), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(
            canvas,
            f"line x={line['pos']:.3f}",
            (min(width - 150, x + 8), 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    for trajectory in trajectories:
        track_id = int(trajectory["track_id"])
        points = trajectory.get("points", [])
        if not points:
            continue
        color = color_for_id(track_id)
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
        cv2.circle(canvas, tuple(pts[-1]), 4, color, -1, cv2.LINE_AA)
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

    for event in events:
        x = int(round(clamp01(event["centroid_norm"][0]) * (width - 1)))
        y = int(round(clamp01(event["centroid_norm"][1]) * (height - 1)))
        color = (0, 180, 0) if event["direction"] == "IN" else (0, 0, 255)
        cv2.circle(canvas, (x, y), 8, color, -1, cv2.LINE_AA)
        cv2.putText(
            canvas,
            event["direction"],
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(output_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])


def run_stage4(
    tracks_json: Path,
    output_dir: Path,
    line_config: Optional[Path] = None,
    line_type: str = "horizontal",
    line_pos: float = 0.66,
    jpeg_quality: int = 90,
) -> Dict:
    LineCrossDetector, Track, get_food_name = import_linecross_classes()
    tracks_json = Path(tracks_json)
    output_dir = Path(output_dir)
    if not tracks_json.exists():
        raise RuntimeError(f"tracks.json not found: {tracks_json}")
    output_dir.mkdir(parents=True, exist_ok=True)

    tracks_payload = json.loads(tracks_json.read_text(encoding="utf-8"))
    base, width, height = read_canvas_from_tracks(tracks_payload)
    line = load_line_config(line_config, line_type, line_pos, width, height)

    detector = LineCrossDetector(boundary_y=line["pos"])
    detector.set_virtual_line(line)

    trajectories = sorted(
        tracks_payload.get("trajectories", []),
        key=lambda item: int(item.get("track_id", 0)),
    )
    active_track_objects = {}
    timeline = []
    for trajectory in trajectories:
        track_id = int(trajectory["track_id"])
        class_id = int(trajectory["class_id"])
        for point in trajectory.get("points", []):
            timeline.append(
                {
                    "frame_id": int(point["frame_id"]),
                    "track_id": track_id,
                    "class_id": class_id,
                    "point": point,
                }
            )
    timeline.sort(key=lambda item: (item["frame_id"], item["track_id"]))

    events = []
    net_by_class: Dict[int, int] = {}
    started_at = utc_now_iso()

    logging.info(
        "Stage 4 line crossing started: points=%d line=%s %.3f",
        len(timeline),
        line["type"],
        line["pos"],
    )

    for item in timeline:
        track_id = item["track_id"]
        class_id = item["class_id"]
        point = item["point"]
        if track_id not in active_track_objects:
            active_track_objects[track_id] = build_track_object(
                Track, track_id, class_id, point
            )
            continue

        track = active_track_objects[track_id]
        append_point_to_track(track, point)
        detector.check_crossing(track)
        changes = detector.get_and_clear_changes()
        if not changes:
            continue

        for changed_class_id, delta in changes.items():
            direction = "IN" if delta > 0 else "OUT"
            net_by_class[changed_class_id] = net_by_class.get(changed_class_id, 0) + delta
            event = {
                "event_id": len(events) + 1,
                "frame_id": item["frame_id"],
                "track_id": track_id,
                "class_id": int(changed_class_id),
                "food_name": get_food_name(int(changed_class_id)),
                "direction": direction,
                "event_type": "CHECK_IN" if delta > 0 else "CHECK_OUT",
                "delta": int(delta),
                "line": dict(line),
                "centroid_norm": [
                    clamp01(track.centroid_x_history[-1]),
                    clamp01(track.centroid_y_history[-1]),
                ],
                "food_detected_equivalent": {
                    "signal": "FoodDetected",
                    "food_items": [{"id": int(changed_class_id), "qty": int(delta)}],
                    "event": "line_cross",
                },
            }
            events.append(event)

    events_json_path = output_dir / "linecross_events.json"
    events_csv_path = output_dir / "linecross_events.csv"
    visualization_path = output_dir / "linecross_visualization.jpg"
    summary_path = output_dir / "event_summary.json"

    events_json_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    with events_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "event_id",
            "frame_id",
            "track_id",
            "class_id",
            "food_name",
            "direction",
            "event_type",
            "delta",
            "line_type",
            "line_pos_norm",
            "cx_norm",
            "cy_norm",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "event_id": event["event_id"],
                    "frame_id": event["frame_id"],
                    "track_id": event["track_id"],
                    "class_id": event["class_id"],
                    "food_name": event["food_name"],
                    "direction": event["direction"],
                    "event_type": event["event_type"],
                    "delta": event["delta"],
                    "line_type": event["line"]["type"],
                    "line_pos_norm": f"{event['line']['pos']:.8f}",
                    "cx_norm": f"{event['centroid_norm'][0]:.8f}",
                    "cy_norm": f"{event['centroid_norm'][1]:.8f}",
                }
            )

    draw_visualization(
        visualization_path,
        base,
        line,
        trajectories,
        events,
        jpeg_quality,
    )

    in_count = sum(1 for event in events if event["direction"] == "IN")
    out_count = sum(1 for event in events if event["direction"] == "OUT")
    summary = {
        "stage": "stage4_linecross",
        "input_tracks_json": str(tracks_json),
        "output_dir": str(output_dir),
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "line": line,
        "total_events": len(events),
        "in_events": in_count,
        "out_events": out_count,
        "net_by_class": {str(k): v for k, v in sorted(net_by_class.items())},
        "events_by_class": {
            str(class_id): {
                "food_name": get_food_name(int(class_id)),
                "in": sum(
                    1
                    for event in events
                    if event["class_id"] == class_id and event["direction"] == "IN"
                ),
                "out": sum(
                    1
                    for event in events
                    if event["class_id"] == class_id and event["direction"] == "OUT"
                ),
                "net": net_by_class[class_id],
            }
            for class_id in sorted(net_by_class)
        },
        "outputs": {
            "linecross_events_json": str(events_json_path),
            "linecross_events_csv": str(events_csv_path),
            "linecross_visualization_jpg": str(visualization_path),
            "event_summary_json": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logging.info("Stage 4 complete: %s", summary_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRT test stage 4: virtual line crossing")
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--line-config", type=Path)
    parser.add_argument("--line-type", choices=["horizontal", "vertical"], default="horizontal")
    parser.add_argument("--line-pos", type=float, default=0.66)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    try:
        run_stage4(
            tracks_json=args.tracks,
            output_dir=args.output_dir,
            line_config=args.line_config,
            line_type=args.line_type,
            line_pos=args.line_pos,
            jpeg_quality=args.jpeg_quality,
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
