#!/usr/bin/env python3
"""
Main runner for FRTApp offline/live staged testing.

Session layout:
  frt_test_runs/YYYYMMDD_HHMMSS/
    stage1_mog2/
    stage2_yolo/
    stage3_bytetrack/
    stage4_linecross/
    final_report.json
    final_summary.md
"""

import argparse
import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from stage1_mog2 import run_stage1
from stage2_yolo_infer import DEFAULT_MODEL, run_stage2
from stage3_bytetrack import run_stage3
from stage4_linecross import run_stage4


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "frt_test_runs"


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def create_session_dir(output_root: Path, session_dir: Optional[Path]) -> Path:
    if session_dir:
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_root / stamp
    path.mkdir(parents=True, exist_ok=False)
    return path


def stage_sequence(stage: str) -> List[int]:
    if stage == "all":
        return [1, 2, 3, 4]
    return [int(stage)]


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise RuntimeError(f"{label} not found: {path}")
    return path


def write_final_artifacts(session_dir: Path, report: Dict) -> None:
    final_report_path = session_dir / "final_report.json"
    final_summary_path = session_dir / "final_summary.md"
    stage_status_path = session_dir / "final_stage_status.csv"

    report["outputs"]["final_report_json"] = str(final_report_path)
    report["outputs"]["final_summary_md"] = str(final_summary_path)
    report["outputs"]["final_stage_status_csv"] = str(stage_status_path)
    final_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with stage_status_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["stage", "status", "output_dir", "summary_path"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for name, info in report.get("stages", {}).items():
            writer.writerow(
                {
                    "stage": name,
                    "status": info.get("status", ""),
                    "output_dir": info.get("output_dir", ""),
                    "summary_path": info.get("summary_path", ""),
                }
            )

    lines = [
        "# FRT Test Summary",
        "",
        f"- Status: {report['status']}",
        f"- Session: `{session_dir}`",
        f"- Mode: `{report['mode']}`",
        f"- Stage request: `{report['stage_request']}`",
    ]
    if report.get("source"):
        lines.append(f"- Source: `{report['source']}`")
    if report.get("error"):
        lines.extend(["", "## Error", "", f"```text\n{report['error']}\n```"])

    lines.extend(["", "## Stages", ""])
    for name, info in report.get("stages", {}).items():
        summary = info.get("summary", {})
        lines.append(f"- `{name}`: {info.get('status', 'unknown')}")
        if name == "stage1_mog2" and summary:
            lines.append(
                "  target_fps={target_fps} processed={total_processed_frames} selected={selected_frames} skipped={skipped_frames}".format(
                    **summary
                )
            )
        elif name == "stage2_yolo" and summary:
            lines.append(
                "  frames={frames_processed} detections={total_detections} runtime={runtime_used}".format(
                    **summary
                )
            )
        elif name == "stage3_bytetrack" and summary:
            lines.append(
                "  tracks={total_tracks_created} lost_events={lost_event_count} id_switch_candidates={id_switch_candidate_count}".format(
                    **summary
                )
            )
        elif name == "stage4_linecross" and summary:
            lines.append(
                "  events={total_events} in={in_events} out={out_events}".format(
                    **summary
                )
            )
        if info.get("output_dir"):
            lines.append(f"  output=`{info['output_dir']}`")

    lines.extend(
        [
            "",
            "## Final Artifacts",
            "",
            f"- `{final_report_path}`",
            f"- `{final_summary_path}`",
            f"- `{stage_status_path}`",
            "",
        ]
    )
    final_summary_path.write_text("\n".join(lines), encoding="utf-8")


def run_requested_stages(args: argparse.Namespace) -> Dict:
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    session_dir = create_session_dir(output_root, args.session_dir)
    stages_to_run = stage_sequence(args.stage)

    report = {
        "status": "running",
        "mode": args.mode,
        "source": str(args.input) if args.mode == "video" else str(args.camera),
        "stage_request": args.stage,
        "session_dir": str(session_dir),
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "finished_at": None,
        "stages": {
            "stage1_mog2": {"status": "not_requested", "output_dir": str(session_dir / "stage1_mog2")},
            "stage2_yolo": {"status": "not_requested", "output_dir": str(session_dir / "stage2_yolo")},
            "stage3_bytetrack": {"status": "not_requested", "output_dir": str(session_dir / "stage3_bytetrack")},
            "stage4_linecross": {"status": "not_requested", "output_dir": str(session_dir / "stage4_linecross")},
        },
        "outputs": {},
    }

    stage1_dir = session_dir / "stage1_mog2"
    stage2_dir = session_dir / "stage2_yolo"
    stage3_dir = session_dir / "stage3_bytetrack"
    stage4_dir = session_dir / "stage4_linecross"

    try:
        if 1 in stages_to_run:
            report["stages"]["stage1_mog2"]["status"] = "running"
            max_frames = args.max_frames
            if max_frames is None:
                max_frames = 300 if args.mode == "live" else 0
            if args.mode == "video":
                if not args.input:
                    raise RuntimeError("--mode video requires --input")
                require_path(args.input, "Input video")
                summary = run_stage1(
                    source_type="video",
                    source=str(args.input),
                    output_dir=stage1_dir,
                    max_frames=max_frames,
                    frame_stride=max(1, args.frame_stride),
                    target_fps=args.stage1_fps,
                    motion_threshold=args.motion_threshold,
                    jpeg_quality=args.jpeg_quality,
                )
            else:
                summary = run_stage1(
                    source_type="camera",
                    source=str(args.camera),
                    output_dir=stage1_dir,
                    max_frames=max_frames,
                    frame_stride=max(1, args.frame_stride),
                    target_fps=args.stage1_fps,
                    motion_threshold=args.motion_threshold,
                    jpeg_quality=args.jpeg_quality,
                )
            report["stages"]["stage1_mog2"].update(
                {
                    "status": "complete",
                    "summary": summary,
                    "summary_path": str(stage1_dir / "mog2_summary.json"),
                }
            )

        if 2 in stages_to_run:
            report["stages"]["stage2_yolo"]["status"] = "running"
            selected_frames = args.selected_frames or (stage1_dir / "selected_frames")
            require_path(selected_frames, "selected_frames")
            summary = run_stage2(
                selected_frames_dir=selected_frames,
                output_dir=stage2_dir,
                model_path=args.model,
                confidence_threshold=args.confidence_threshold,
                allow_c_fallback=not args.no_c_fallback,
                jpeg_quality=args.jpeg_quality,
            )
            report["stages"]["stage2_yolo"].update(
                {
                    "status": "complete",
                    "summary": summary,
                    "summary_path": str(stage2_dir / "model_summary.json"),
                }
            )

        if 3 in stages_to_run:
            report["stages"]["stage3_bytetrack"]["status"] = "running"
            detections_json = args.detections or (stage2_dir / "detections.json")
            require_path(detections_json, "detections.json")
            summary = run_stage3(
                detections_json=detections_json,
                output_dir=stage3_dir,
                max_age=args.max_age,
                high_thresh=args.high_thresh,
                match_thresh=args.match_thresh,
                id_switch_iou=args.id_switch_iou,
                jpeg_quality=args.jpeg_quality,
            )
            report["stages"]["stage3_bytetrack"].update(
                {
                    "status": "complete",
                    "summary": summary,
                    "summary_path": str(stage3_dir / "tracks.json"),
                }
            )

        if 4 in stages_to_run:
            report["stages"]["stage4_linecross"]["status"] = "running"
            tracks_json = args.tracks or (stage3_dir / "tracks.json")
            require_path(tracks_json, "tracks.json")
            summary = run_stage4(
                tracks_json=tracks_json,
                output_dir=stage4_dir,
                line_config=args.line_config,
                line_type=args.line_type,
                line_pos=args.line_pos,
                jpeg_quality=args.jpeg_quality,
            )
            report["stages"]["stage4_linecross"].update(
                {
                    "status": "complete",
                    "summary": summary,
                    "summary_path": str(stage4_dir / "event_summary.json"),
                }
            )

        report["status"] = "complete"
    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["error"] = str(exc)
        for info in report["stages"].values():
            if info.get("status") == "running":
                info["status"] = "failed"
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        write_final_artifacts(session_dir, report)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRTApp offline/live staged test runner")
    parser.add_argument("--mode", choices=["video", "live"], required=True)
    parser.add_argument("--input", type=Path, help="Video path for --mode video")
    parser.add_argument("--camera", default="/dev/video0", help="Camera device for --mode live")
    parser.add_argument("--stage", choices=["1", "2", "3", "4", "all"], default="all")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--session-dir", type=Path, help="Reuse or continue a session directory")

    parser.add_argument("--max-frames", type=int, help="Default: video=all, live=300")
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument(
        "--stage1-fps",
        type=float,
        default=5.0,
        help="Limit stage 1 processing rate. Default matches FRTApp: 5 FPS. Use 0 to disable.",
    )
    parser.add_argument("--motion-threshold", type=float, default=1.0)

    parser.add_argument("--selected-frames", type=Path, help="Override stage2 selected_frames input")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--confidence-threshold", type=float, default=0.2)
    parser.add_argument("--no-c-fallback", action="store_true")

    parser.add_argument("--detections", type=Path, help="Override stage3 detections.json input")
    parser.add_argument("--max-age", type=int, default=30)
    parser.add_argument("--high-thresh", type=float, default=0.85)
    parser.add_argument("--match-thresh", type=float, default=0.8)
    parser.add_argument("--id-switch-iou", type=float, default=0.8)

    parser.add_argument("--tracks", type=Path, help="Override stage4 tracks.json input")
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
        report = run_requested_stages(args)
        logging.info("FRT test complete: %s", report["session_dir"])
    except Exception as exc:  # noqa: BLE001
        logging.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
