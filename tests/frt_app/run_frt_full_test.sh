#!/usr/bin/env bash
# ==============================================================================
# run_frt_full_test.sh — FRTApp Isolated Full Test Orchestrator
# ==============================================================================
#
# Purpose:
#     Runs the complete FRTApp test in an isolated environment:
#       1. Stops ALL FSS systemd services (free camera, DB, D-Bus)
#       2. Creates POSIX SHM (/dev/shm/fss_video_frame) via camera_core_exec
#       3. Runs the test with a unique timestamp session
#       4. Cleans up SHM
#       5. Restarts all FSS services
#
# Modes:
#     --mode auto      (default) main.py --bypass-door-sensor — full FRTApp
#                        pipeline: camera → MOG2 → YOLO → ByteTrack → Boundary
#                        Wave hand to auto-detect CHECK_IN/CHECK_OUT.
#     --mode scenario  user_scenario_pipeline.py — live check-in/check-out
#       --scenario check-in   S1: hand+fuit enters → YOLO detects → "added"
#       --scenario check-out  S2: fruit leaves → YOLO detects → "removed"
#     --mode unit      test_user_scenario_frtapp.py — 38 unit tests
#     --mode comprehensive  [FRT-MAIN]-test_comprehensive_frt.py — 7-stage
#                        end-to-end validation of ALL pipeline components:
#                        Camera → Preproc → MOG2 → YOLO → ByteTrack →
#                        YoloPipeline → Annotated Output
#
# Usage:
#     sudo bash run_frt_full_test.sh                                # default auto mode
#     sudo bash run_frt_full_test.sh --mode auto                    # full FRTApp pipeline
#     sudo bash run_frt_full_test.sh --mode scenario --scenario check-in
#     sudo bash run_frt_full_test.sh --mode scenario --scenario check-out --duration 20
#     sudo bash run_frt_full_test.sh --mode unit --duration 3
#     sudo bash run_frt_full_test.sh --mode comprehensive           # 7-stage validation
#     sudo bash run_frt_full_test.sh --mode comprehensive --synthetic  # no hardware needed
#     sudo bash run_frt_full_test.sh --mode comprehensive --python-backend  # Python tflite-runtime (no C backend)
#     sudo bash run_frt_full_test.sh --confidence 0.85              # detection threshold
#     sudo bash run_frt_full_test.sh --save-results                 # save to system_results/
#     sudo bash run_frt_full_test.sh --skip-services
#     sudo bash run_frt_full_test.sh --debug
#     sudo bash run_frt_full_test.sh --help
#
# Session Directory (default output):
#     <PROJECT_ROOT>/system_results/frt_session_<YYYYMMDD_HHMMSS>/
#       ├── full_log.txt              — Complete FRTApp daemon log (also on terminal)
#       ├── pipeline_report.json      — Structured metrics + boundary events + detections
#       ├── boundary_events.json      — All CHECK_IN / CHECK_OUT events
#       ├── track_trajectories.json   — Per-track trajectory data (ByteTrack)
#       ├── pipeline_metrics.json     — FPS, latency, NMS stats per component
#       ├── nms_stats.json           — Per-inference NMS before/after box counts
#       ├── user_notifications.txt    — Human-readable test instructions
#       ├── frt_session_summary.txt   — Tester-friendly session summary
#       │
#       ├── annotated_result.jpg      — (scenario) Best frame with YOLO bboxes + labels
#       ├── mog2_foreground_mask.jpg  — (scenario) MOG2 foreground (green channel)
#       ├── mog2_heatmap.jpg          — (scenario) MOG2 heatmap (COLORMAP_JET)
#       ├── preprocess_rgb.jpg        — (scenario) BGR→RGB conversion result
#       ├── preprocess_letterbox.jpg  — (scenario) Letterboxed 640×640 input
#       ├── latest_frames/            — (scenario) Per-frame annotated + MOG2 viz
#       │   ├── frame_{0..4}_annotated.jpg
#       │   ├── frame_{0..4}_mog2_mask.jpg
#       │   └── frame_{0..4}_mog2_heatmap.jpg
#       │
#       ├── sample_frame.jpg          — (unit) First captured camera frame
#       ├── latest_preview.jpg        — (unit) LivePreview-style annotated frame
#       ├── scenario_report.json      — (scenario) State transition report
#       ├── frtapp_scenario_report.json (unit) Full test results
#       └── inference_table.{csv,md}  — (scenario) Detection tabulation
#
# Custom session dir (--session-dir) is used as-is; no copy to system_results.
#
# Exit Codes:
#     0 — All tests passed
#     1 — Prerequisite failure
#     2 — Test failure
#     3 — Service management error
#
# Author: FSS Project Team
# ==============================================================================

set -euo pipefail

# ==============================================================================
# CONFIGURATION
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FSS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CAMERA_DEVICE="/dev/video0"
MODEL_PATH="/opt/fss/models/YOLOv11n_260518_best_int8.tflite"
DURATION=15
DEBUG=false
NO_SHM=false
SKIP_SERVICES=false
SYNTHETIC=false
SESSION_DIR=""
SHM_SECONDS=3
PIPELINE_FPS=10
MODE="auto"
SCENARIO="check-in"
CONFIDENCE=0.85
SAVE_RESULTS=false
RUNTIME=0
PYTHON_BACKEND=false

FSS_SERVICES=("fss-sensor" "fss-camera" "fss-ai" "fss-db" "fss-recommend")
SYSTEM_RESULTS_DIR="$FSS_ROOT/system_results"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ==============================================================================
# HELP
# ==============================================================================

show_help() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
    exit 0
}

# ==============================================================================
# PARSE ARGS
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --camera)       CAMERA_DEVICE="$2"; shift 2 ;;
        --model)        MODEL_PATH="$2"; shift 2 ;;
        --duration)     DURATION="$2"; shift 2 ;;
        --session-dir)  SESSION_DIR="$2"; shift 2 ;;
        --mode)         MODE="$2"; shift 2 ;;
        --scenario)     SCENARIO="$2"; shift 2 ;;
        --no-shm)       NO_SHM=true; shift ;;
        --skip-services) SKIP_SERVICES=true; shift ;;
        --synthetic)    SYNTHETIC=true; shift ;;
        --confidence)   CONFIDENCE="$2"; shift 2 ;;
        --python-backend) PYTHON_BACKEND=true; shift ;;
        --save-results)  SAVE_RESULTS=true; shift ;;
        --shm-seconds)  SHM_SECONDS="$2"; shift 2 ;;
        --pipeline-fps) PIPELINE_FPS="$2"; shift 2 ;;
        --debug)        DEBUG=true; shift ;;
        --help|-h)      show_help ;;
        *)              echo "Unknown option: $1"; show_help ;;
    esac
done

# Generate timestamped session directory if not provided
if [[ -z "$SESSION_DIR" ]]; then
    mkdir -p "$SYSTEM_RESULTS_DIR"
    SESSION_DIR="$SYSTEM_RESULTS_DIR/frt_session_$(date +%Y%m%d_%H%M%S)"
fi

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

pass()  { echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
info()  { echo -e "  ${CYAN}→${NC} $1"; }
header(){ echo -e "\n${CYAN}══════════════════════════════════════════════${NC}"; echo -e "${CYAN} $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════════${NC}"; }

# ==============================================================================
# POST-PROCESSING: Parse session log → structured output files
# ==============================================================================

postprocess_session() {
    local log="$SESSION_DIR/full_log.txt"
    [[ ! -f "$log" ]] && { warn "No full_log.txt to post-process"; return; }

    info "Generating structured output files from session log..."

    python3 <<-PYEOF 2>/dev/null || warn "Post-processing script failed"
import json, re, os, statistics
from collections import defaultdict

log_path = "$log"
session_dir = "$SESSION_DIR"

with open(log_path) as f:
    lines = f.readlines()

boundary_events = []
tracks = defaultdict(list)
fps_samples = []
detection_samples = []
nms_samples = []

for line in lines:
    # Boundary crossing events
    m = re.search(r'(\d{2}:\d{2}:\d{2}\.\d+).*?CHECK_(IN|OUT).*?track_id[=:](\d+)', line)
    if m:
        boundary_events.append({
            "timestamp": m.group(1),
            "event": "CHECK_" + m.group(2),
            "track_id": int(m.group(3))
        })

    # Trajectory data
    m = re.search(r'track_id[=:](\d+).*?center[=:]\(?([\d.]+),\s*([\d.]+)\)?', line)
    if m:
        tracks[int(m.group(1))].append({
            "x": float(m.group(2)),
            "y": float(m.group(3))
        })

    # FPS
    m = re.search(r'Pipeline Metrics.*?FPS:\s*([\d.]+)', line)
    if m:
        fps_samples.append(float(m.group(1)))

    # Detections
    m = re.search(r'Detected:\s*(\d+).*?conf:\s*([\d.]+).*?class_id[=:](\d+)', line)
    if m:
        detection_samples.append({
            "count": int(m.group(1)),
            "conf": float(m.group(2)),
            "class_id": int(m.group(3))
        })

    # Alternative detection pattern
    m = re.search(r'detections[=:](\d+).*?confidence[=:]([\d.]+)', line)
    if m:
        detection_samples.append({
            "count": int(m.group(1)),
            "conf": float(m.group(2)),
            "class_id": -1
        })

    # NMS stats
    m = re.search(r'NMS:\s*before=(\d+)\s*after=(\d+)\s*iou=([\d.]+)\s*conf=([\d.]+)', line)
    if m:
        nms_samples.append({
            "before": int(m.group(1)),
            "after": int(m.group(2)),
            "iou_threshold": float(m.group(3)),
            "confidence_threshold": float(m.group(4))
        })

# Boundary events
be_path = os.path.join(session_dir, "boundary_events.json")
with open(be_path, "w") as f:
    json.dump(boundary_events, f, indent=2)

# Track trajectories
tt_path = os.path.join(session_dir, "track_trajectories.json")
trajectories = {str(tid): pts for tid, pts in tracks.items()}
with open(tt_path, "w") as f:
    json.dump(trajectories, f, indent=2)

# Pipeline metrics
pm_path = os.path.join(session_dir, "pipeline_metrics.json")
nms_before = [s["before"] for s in nms_samples]
nms_after = [s["after"] for s in nms_samples]
metrics = {
    "fps_samples": fps_samples,
    "fps_avg": round(statistics.mean(fps_samples), 2) if fps_samples else 0,
    "fps_min": round(min(fps_samples), 2) if fps_samples else 0,
    "fps_max": round(max(fps_samples), 2) if fps_samples else 0,
    "fps_stdev": round(statistics.stdev(fps_samples), 2) if len(fps_samples) > 1 else 0,
    "total_events": len(boundary_events),
    "check_in_count": sum(1 for e in boundary_events if e["event"] == "CHECK_IN"),
    "check_out_count": sum(1 for e in boundary_events if e["event"] == "CHECK_OUT"),
    "unique_tracks": len(tracks),
    "total_detections": len(detection_samples),
    "detection_samples": detection_samples,
    "nms": {
        "total_inferences": len(nms_samples),
        "boxes_before_nms_total": sum(nms_before),
        "boxes_after_nms_total": sum(nms_after),
        "boxes_before_nms_avg": round(statistics.mean(nms_before), 2) if nms_before else 0,
        "boxes_after_nms_avg": round(statistics.mean(nms_after), 2) if nms_after else 0,
        "boxes_before_nms_min": min(nms_before) if nms_before else 0,
        "boxes_before_nms_max": max(nms_before) if nms_before else 0,
        "boxes_after_nms_min": min(nms_after) if nms_after else 0,
        "boxes_after_nms_max": max(nms_after) if nms_after else 0,
        "iou_threshold": nms_samples[0]["iou_threshold"] if nms_samples else 0,
        "confidence_threshold": nms_samples[0]["confidence_threshold"] if nms_samples else 0,
        "suppression_rate_avg": round(
            (1 - statistics.mean(nms_after) / statistics.mean(nms_before)) * 100, 2
        ) if nms_before and statistics.mean(nms_before) > 0 else 0
    }
}
with open(pm_path, "w") as f:
    json.dump(metrics, f, indent=2)

# NMS stats
nms_path = os.path.join(session_dir, "nms_stats.json")
nms_stats = {
    "nms_samples": nms_samples,
    "summary": {
        "total_inferences": metrics["nms"]["total_inferences"],
        "boxes_before_nms_avg": metrics["nms"]["boxes_before_nms_avg"],
        "boxes_after_nms_avg": metrics["nms"]["boxes_after_nms_avg"],
        "suppression_rate_avg": metrics["nms"]["suppression_rate_avg"],
        "iou_threshold": metrics["nms"]["iou_threshold"],
        "confidence_threshold": metrics["nms"]["confidence_threshold"]
    }
}
with open(nms_path, "w") as f:
    json.dump(nms_stats, f, indent=2)

# Pipeline report
pr_path = os.path.join(session_dir, "pipeline_report.json")
report = {
    "session": os.path.basename(session_dir),
    "mode": "$MODE",
    "boundary_events": boundary_events,
    "metrics": metrics,
    "track_count": len(tracks),
    "fps_summary": {
        "avg": metrics["fps_avg"],
        "min": metrics["fps_min"],
        "max": metrics["fps_max"],
        "samples": len(fps_samples)
    },
    "nms_summary": metrics["nms"]
}
with open(pr_path, "w") as f:
    json.dump(report, f, indent=2)

# User notifications
un_path = os.path.join(session_dir, "user_notifications.txt")
with open(un_path, "w") as f:
    f.write("FRTApp Session — Actionable Notifications\n")
    f.write("=" * 45 + "\n\n")
    if not boundary_events:
        f.write("⚠ No boundary crossings detected.\n")
        f.write("  Suggestion: Wave an object vertically across the frame middle.\n")
    else:
        f.write(f"Detected {len(boundary_events)} boundary crossing events:\n")
        for ev in boundary_events:
            label = "ENTER (add to inventory)" if ev["event"] == "CHECK_IN" else "LEAVE (remove from inventory)"
            f.write(f"  [{ev['timestamp']}] Track {ev['track_id']}: {ev['event']} → {label}\n")
    f.write("\n")
    if fps_samples:
        avg_fps = statistics.mean(fps_samples)
        f.write(f"Pipeline health: {avg_fps:.1f} FPS avg\n")
        if avg_fps < 5:
            f.write("  WARNING: Low FPS — reduce model size or input resolution\n")
        else:
            f.write("  FPS is acceptable for real-time operation\n")
    if nms_samples:
        avg_before = metrics["nms"]["boxes_before_nms_avg"]
        avg_after = metrics["nms"]["boxes_after_nms_avg"]
        sr = metrics["nms"]["suppression_rate_avg"]
        f.write(f"\nNMS stats ({len(nms_samples)} inferences):\n")
        f.write(f"  Avg boxes before NMS: {avg_before:.1f}\n")
        f.write(f"  Avg boxes after NMS:  {avg_after:.1f}\n")
        f.write(f"  Suppression rate:     {sr:.1f}%\n")
        f.write(f"  IoU threshold:        {nms_samples[0]['iou_threshold']}\n")
        f.write(f"  Confidence threshold: {nms_samples[0]['confidence_threshold']}\n")
    f.write("\n--- End of Notifications ---\n")

# Session summary
ss_path = os.path.join(session_dir, "frt_session_summary.txt")
with open(ss_path, "w") as f:
    f.write("FRTApp Session Summary\n")
    f.write("=" * 45 + "\n\n")
    f.write(f"Session:  {os.path.basename(session_dir)}\n")
    f.write(f"Mode:     {"$MODE"}\n")
    f.write(f"Duration: {"$RUNTIME"}s\n\n")
    f.write(f"Boundary crossings: {len(boundary_events)}\n")
    f.write(f"  CHECK_IN  (enter):  {metrics['check_in_count']}\n")
    f.write(f"  CHECK_OUT (leave):  {metrics['check_out_count']}\n\n")
    f.write(f"Tracks tracked:      {len(tracks)}\n")
    f.write(f"Total detections:    {len(detection_samples)}\n\n")
    if fps_samples:
        f.write(f"Pipeline FPS:\n")
        f.write(f"  Average: {metrics['fps_avg']}\n")
        f.write(f"  Min:     {metrics['fps_min']}\n")
        f.write(f"  Max:     {metrics['fps_max']}\n")
        if len(fps_samples) > 1:
            f.write(f"  StdDev:  {metrics['fps_stdev']}\n")
    if nms_samples:
        f.write(f"\nNMS (Non-Maximum Suppression):\n")
        f.write(f"  Inferences with NMS:    {len(nms_samples)}\n")
        f.write(f"  Avg boxes before NMS:   {metrics['nms']['boxes_before_nms_avg']}\n")
        f.write(f"  Avg boxes after NMS:    {metrics['nms']['boxes_after_nms_avg']}\n")
        f.write(f"  Suppression rate:       {metrics['nms']['suppression_rate_avg']}%\n")
        f.write(f"  IoU threshold:          {metrics['nms']['iou_threshold']}\n")
        f.write(f"  Confidence threshold:   {metrics['nms']['confidence_threshold']}\n")
    f.write("\n--- End of Summary ---\n")

print(f"Generated: boundary_events.json ({len(boundary_events)} events)")
print(f"Generated: track_trajectories.json ({len(tracks)} tracks)")
print(f"Generated: pipeline_metrics.json ({len(fps_samples)} FPS samples)")
print(f"Generated: nms_stats.json ({len(nms_samples)} NMS samples)")
print(f"Generated: pipeline_report.json")
print(f"Generated: user_notifications.txt")
print(f"Generated: frt_session_summary.txt")
PYEOF

    info "Post-processing complete"
}

SERVICES_STOPPED=false
SHM_CREATED=false
CAMERA_CORE_PID=""

cleanup() {
    echo ""
    header "CLEANUP"

    # Kill camera_core_exec if we started it
    if [[ -n "$CAMERA_CORE_PID" ]]; then
        info "Killing camera_core_exec (PID $CAMERA_CORE_PID)..."
        kill -9 "$CAMERA_CORE_PID" 2>/dev/null || true
        wait "$CAMERA_CORE_PID" 2>/dev/null || true
        pass "camera_core_exec killed"
    fi

    # Remove SHM if we created it (needs sudo for /dev/shm)
    if $SHM_CREATED && [[ -f "/dev/shm/fss_video_frame" ]]; then
        info "Removing SHM /dev/shm/fss_video_frame (with sudo)..."
        sudo rm -f "/dev/shm/fss_video_frame"
        if [[ ! -f "/dev/shm/fss_video_frame" ]]; then
            pass "SHM removed"
        else
            warn "SHM could not be removed — try: sudo rm -f /dev/shm/fss_video_frame"
        fi
    fi

    # Restart services if we stopped them
    if $SERVICES_STOPPED; then
        info "Restarting FSS services..."
        for svc in "${FSS_SERVICES[@]}"; do
            sudo systemctl start "$svc" 2>/dev/null || warn "Failed to start $svc"
        done
        sleep 2
        for svc in "${FSS_SERVICES[@]}"; do
            if systemctl is-active --quiet "$svc"; then
                pass "$svc is active"
            else
                warn "$svc did not start — check: sudo journalctl -u $svc -n 20"
            fi
        done
        pass "All services restarted"
    fi

    # Archive results if --save-results (skip if already in system_results)
    if $SAVE_RESULTS && [[ -d "$SESSION_DIR" ]]; then
        if [[ "$SESSION_DIR" == "$SYSTEM_RESULTS_DIR"/* ]]; then
            pass "Results already in system_results: $SESSION_DIR/"
        else
            mkdir -p "$SYSTEM_RESULTS_DIR"
            local dest="$SYSTEM_RESULTS_DIR/$(basename "$SESSION_DIR")"
            info "Archiving session to $dest/..."
            cp -a "$SESSION_DIR" "$dest"
            pass "Results saved: $dest/"
        fi
    fi

    echo ""
    if [[ $? -eq 0 || ${1:-} -eq 0 ]]; then
        echo -e "  ${GREEN}✓ TEST SESSION COMPLETE${NC}"
    else
        echo -e "  ${RED}✗ TEST SESSION FAILED${NC}"
    fi
    echo -e "  Session: $SESSION_DIR/"
}

trap 'cleanup $?' EXIT INT TERM

# ==============================================================================
# BANNER
# ==============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║     FRTApp — FULL TEST: Camera → MOG2 → YOLO(NMS) → ByteTrack     ║"
echo "║        Boundary CHECK_IN / CHECK_OUT auto-detect                   ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Camera:       $CAMERA_DEVICE"
echo "  Model:        $MODEL_PATH"
echo "  Duration:     ${DURATION}s"
echo "  Session:      $SESSION_DIR"
echo "  Mode:         $MODE"
if [[ "$MODE" == "scenario" ]]; then
    echo "  Scenario:     $SCENARIO"
elif [[ "$MODE" == "auto" ]]; then
    echo "  Pipeline:     Camera → MOG2 → YOLO(NMS) → ByteTrack → Boundary"
elif [[ "$MODE" == "comprehensive" ]]; then
    echo "  Pipeline:     Camera → Preproc → MOG2 → YOLO → ByteTrack → Pipeline → Output"
fi
echo "  Synthetic:    $SYNTHETIC"
echo "  Confidence:   $CONFIDENCE"
echo "  Backend:      $($PYTHON_BACKEND && echo 'Python (tflite-runtime)' || echo 'C (libtflite_reader.so)')"
echo "  Create SHM:   $([[ $NO_SHM == true ]] && echo 'no' || echo 'yes')"
echo "  SHM seconds:  ${SHM_SECONDS}s"
echo "  Pipeline FPS: $PIPELINE_FPS"
echo "  Stop svcs:    $([[ $SKIP_SERVICES == true ]] && echo 'no' || echo 'yes')"
echo "  Output dir:   $SYSTEM_RESULTS_DIR/"
echo "  Debug:        $DEBUG"
echo ""

mkdir -p "$SESSION_DIR"

# ==============================================================================
# STEP 1: Prerequisite Checks
# ==============================================================================

header "STEP 1: Prerequisite Checks"
PREREQ_FAIL=false

# Camera device
if ! $SYNTHETIC; then
    if [[ -c "$CAMERA_DEVICE" ]]; then
        pass "Camera device $CAMERA_DEVICE"
    else
        fail "Camera device $CAMERA_DEVICE not found (use --synthetic to skip)"
        PREREQ_FAIL=true
    fi
fi

# YOLO model
if ! $SYNTHETIC; then
    if [[ -f "$MODEL_PATH" ]]; then
        pass "YOLO model $(du -h "$MODEL_PATH" | cut -f1)"
    else
        fail "Model $MODEL_PATH not found (use --synthetic to skip)"
        PREREQ_FAIL=true
    fi
fi

# Python
PYTHON_CMD=""
if [[ -f "$FSS_ROOT/frt_app/py_ai_core/venv/bin/python3" ]]; then
    PYTHON_CMD="$FSS_ROOT/frt_app/py_ai_core/venv/bin/python3"
    pass "Python venv: frt_app/py_ai_core/venv/"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    pass "Python: system python3"
else
    fail "No Python 3 found"
    PREREQ_FAIL=true
fi

# Python deps
if [[ -n "$PYTHON_CMD" ]]; then
    for mod in cv2 numpy loguru; do
        "$PYTHON_CMD" -c "import $mod" 2>/dev/null || { warn "Module '$mod' missing"; }
    done
    "$PYTHON_CMD" -c "import ctypes; lib=ctypes.CDLL('libtflite_reader.so')" 2>/dev/null \
        && pass "C backend (libtflite_reader.so)" \
        || warn "C backend not available"
fi

# Camera core binary for SHM
CAMERA_CORE_BIN="$FSS_ROOT/frt_app/build/cpp_camera_core/camera_core_exec"
if [[ -x "$CAMERA_CORE_BIN" ]]; then
    pass "camera_core_exec binary found"
else
    if $NO_SHM; then
        warn "camera_core_exec not found at $CAMERA_CORE_BIN (--no-shm set, continuing)"
    else
        fail "camera_core_exec not found at $CAMERA_CORE_BIN — rebuild with: cd frt_app/build && cmake .. && make"
        PREREQ_FAIL=true
    fi
fi

if $PREREQ_FAIL; then
    echo ""
    fail "Prerequisites failed — aborting"
    exit 1
fi
echo ""
pass "All prerequisites met"

# ==============================================================================
# STEP 2: Stop All FSS Services
# ==============================================================================

if ! $SKIP_SERVICES; then
    header "STEP 2: Stop All FSS Services"
    for svc in "${FSS_SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            info "Stopping $svc..."
            sudo systemctl stop "$svc"
            pass "$svc stopped"
        else
            info "$svc already stopped"
        fi
    done
    SERVICES_STOPPED=true
    # Verify camera is free
    sleep 1
    if ! $SYNTHETIC; then
        if command -v fuser &>/dev/null; then
            if fuser "$CAMERA_DEVICE" &>/dev/null; then
                fail "Camera $CAMERA_DEVICE still held after stopping services"
                info "Check: sudo fuser -v $CAMERA_DEVICE"
                exit 3
            fi
        fi
        echo ""
        echo -e "  ${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${GREEN}║  ✅ Camera $CAMERA_DEVICE is FREE — ready for test  ║${NC}"
        echo -e "  ${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
        echo ""
    fi
    echo ""
    pass "All services stopped, camera is free"
else
    header "STEP 2: Skip Stopping Services"
    info "Skipping service management (--skip-services)"
fi

# ==============================================================================
# STEP 3: Create POSIX SHM
# ==============================================================================

if ! $NO_SHM; then
    header "STEP 3: Create POSIX Shared Memory"
    if [[ -f "/dev/shm/fss_video_frame" ]]; then
        SHM_SIZE=$(stat -c%s "/dev/shm/fss_video_frame" 2>/dev/null || echo "?")
        info "SHM /dev/shm/fss_video_frame already exists ($SHM_SIZE bytes)"
        pass "SHM already present"
    else
        info "Starting camera_core_exec for ${SHM_SECONDS}s to create SHM..."
        SHM_LOG="$SESSION_DIR/camera_core_shm.log"
        # Use timeout -s KILL: SIGKILL prevents destructor from calling shm_unlink,
        # so the SHM persists in /dev/shm after the process dies
        # Exit code 124 = timeout killed it (expected); other codes = error
        set +e
        sudo timeout -s KILL "$SHM_SECONDS" \
            "$CAMERA_CORE_BIN" --device "$CAMERA_DEVICE" --width 640 --height 480 \
            >"$SHM_LOG" 2>&1
        SHM_EXIT=$?
        set -e
        if [[ -f "/dev/shm/fss_video_frame" ]]; then
            SHM_SIZE=$(stat -c%s "/dev/shm/fss_video_frame" 2>/dev/null || echo "?")
            pass "SHM created at /dev/shm/fss_video_frame ($SHM_SIZE bytes) (camera_core exit=$SHM_EXIT)"
            SHM_CREATED=true
        else
            warn "SHM was not created — continuing without it (camera_core exit=$SHM_EXIT)"
            warn "Log: $SHM_LOG"
        fi
    fi
    echo ""
else
    header "STEP 3: Skip SHM Creation"
    info "Skipping SHM creation (--no-shm)"
fi

# ==============================================================================
# STEP 4: Run Test (mode: $MODE)
# ==============================================================================

if [[ "$MODE" == "auto" ]]; then
    header "STEP 4: Run FRTApp Auto-Detect Mode (main.py --bypass-door-sensor)"

    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════════╗"
    echo "  ║  FRTApp AUTO-DETECT MODE (with NMS post-processing)            ║"
    echo "  ║  Door sensor is BYPASSED — pipeline starts immediately.        ║"
    echo "  ║  Virtual boundary line divides the frame (default: middle).     ║"
    echo "  ║    • Top  → Bottom crossing = CHECK_IN  (object enters)        ║"
    echo "  ║    • Bottom → Top crossing  = CHECK_OUT (object leaves)        ║"
    echo "  ║                                                               ║"
    echo "  ║  HOW TO TEST:                                                  ║"
    echo "  ║  1. Hold any object (hand, fruit, can) in front of camera      ║"
    echo "  ║  2. Move it vertically across the middle of the frame          ║"
    echo "  ║  3. WATCH TERMINAL for CHECK_IN / CHECK_OUT notifications      ║"
    echo "  ║  4. Output also saved to full_log.txt in session dir           ║"
    echo "  ║  5. Press Ctrl+C to stop the test                              ║"
    echo "  ║                                                               ║"
    echo "  ║  Results saved to session directory with boundary log          ║"
    echo "  ╚══════════════════════════════════════════════════════════════════╝"
    echo ""

    MAIN_SCRIPT="$FSS_ROOT/frt_app/py_ai_core/src/main.py"
    if [[ ! -f "$MAIN_SCRIPT" ]]; then
        fail "main.py not found: $MAIN_SCRIPT"
        exit 2
    fi

    CMD_ARGS=(
        "$PYTHON_CMD" "$MAIN_SCRIPT"
        "--bypass-door-sensor"
        "--confidence" "$CONFIDENCE"
    )
    if ! $SYNTHETIC; then
        CMD_ARGS+=("--camera" "$CAMERA_DEVICE" "--model" "$MODEL_PATH")
    fi
    if $DEBUG; then
        CMD_ARGS+=("--debug")
    fi

    echo "  Running: ${CMD_ARGS[*]}"
    echo "  (auto-detect runs for ${DURATION}s via timeout, then Ctrl+C)"
    echo ""

    START_TS=$(date +%s)
    set +e
    set +o pipefail
    FULL_LOG="$SESSION_DIR/full_log.txt"
    timeout -s INT "$DURATION" "${CMD_ARGS[@]}" 2>&1 | tee -a "$FULL_LOG"
    TEST_EXIT=${PIPESTATUS[0]}
    set -o pipefail
    set -e
    END_TS=$(date +%s)
    RUNTIME=$((END_TS - START_TS))

    echo ""
    if [[ $TEST_EXIT -eq 0 ]]; then
        pass "FRTApp auto-detect PASSED (exit=$TEST_EXIT, ${RUNTIME}s)"
    else
        fail "FRTApp auto-detect FAILED (exit=$TEST_EXIT, ${RUNTIME}s)"
    fi

    postprocess_session

elif [[ "$MODE" == "unit" ]]; then
    header "STEP 4: Run Unit Scenario Test (test_user_scenario_frtapp.py)"

    SCENARIO_SCRIPT="$SCRIPT_DIR/test_user_scenario_frtapp.py"
    if [[ ! -f "$SCENARIO_SCRIPT" ]]; then
        fail "Test script not found: $SCENARIO_SCRIPT"
        exit 2
    fi

    CMD_ARGS=(
        "$PYTHON_CMD" "$SCENARIO_SCRIPT"
        "--output-dir" "$SESSION_DIR"
        "--target-fps" "$PIPELINE_FPS"
    )
    if ! $SYNTHETIC; then
        CMD_ARGS+=("--camera" "$CAMERA_DEVICE" "--model" "$MODEL_PATH")
    else
        CMD_ARGS+=("--synthetic")
    fi
    if $DEBUG; then
        CMD_ARGS+=("--debug")
    fi

    echo "  Running: ${CMD_ARGS[*]}"
    echo ""

    START_TS=$(date +%s)
    set +e
    "${CMD_ARGS[@]}"
    TEST_EXIT=$?
    set -e
    END_TS=$(date +%s)
    RUNTIME=$((END_TS - START_TS))

    echo ""
    if [[ $TEST_EXIT -eq 0 ]]; then
        pass "Unit test PASSED (exit=$TEST_EXIT, ${RUNTIME}s)"
    else
        fail "Unit test FAILED (exit=$TEST_EXIT, ${RUNTIME}s)"
    fi

    postprocess_session

elif [[ "$MODE" == "scenario" ]]; then
    header "STEP 4: Run User Scenario Pipeline ($SCENARIO)"

    SCENARIO_SCRIPT="$SCRIPT_DIR/user_scenario_pipeline.py"
    if [[ ! -f "$SCENARIO_SCRIPT" ]]; then
        fail "Scenario script not found: $SCENARIO_SCRIPT"
        exit 2
    fi

    CMD_ARGS=(
        "$PYTHON_CMD" "$SCENARIO_SCRIPT"
        "--scenario" "$SCENARIO"
        "--camera" "$CAMERA_DEVICE"
        "--model" "$MODEL_PATH"
        "--duration" "$DURATION"
        "--confidence" "$CONFIDENCE"
        "--output-dir" "$SESSION_DIR"
    )
    if $DEBUG; then
        CMD_ARGS+=("--debug")
    fi

    echo "  Running: ${CMD_ARGS[*]}"
    echo ""

    START_TS=$(date +%s)
    set +e
    "${CMD_ARGS[@]}"
    TEST_EXIT=$?
    set -e
    END_TS=$(date +%s)
    RUNTIME=$((END_TS - START_TS))

    echo ""
    if [[ $TEST_EXIT -eq 0 ]]; then
        pass "Scenario pipeline PASSED (exit=$TEST_EXIT, ${RUNTIME}s)"
    else
        fail "Scenario pipeline FAILED (exit=$TEST_EXIT, ${RUNTIME}s)"
    fi

    postprocess_session

elif [[ "$MODE" == "comprehensive" ]]; then
    header "STEP 4: Run Comprehensive FRT Pipeline Test ([FRT-MAIN]-test_comprehensive_frt.py)"

    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════════╗"
    echo "  ║  7-STAGE COMPREHENSIVE FRT TEST                                 ║"
    echo "  ║  1. CameraUvcDriver    — USB camera init, capture, FPS          ║"
    echo "  ║  2. ImagePreprocessor  — BGR→RGB, letterbox, normalize, tensor  ║"
    echo "  ║  3. MotionDetector     — MOG2 init, subtraction, motion detect  ║"
    echo "  ║  4. YoloTfliteEngine   — YOLO model load, inference, outputs    ║"
    echo "  ║  5. ByteTrack          — IoU tracking, persistence, quantity    ║"
    echo "  ║  6. YoloPipeline       — Full integration pipeline              ║"
    echo "  ║  7. Annotated Output   — BBox viz + base64 terminal display     ║"
    echo "  ╚══════════════════════════════════════════════════════════════════╝"
    echo ""

    COMPREHENSIVE_SCRIPT="$SCRIPT_DIR/[FRT-MAIN]-test_comprehensive_frt.py"
    if [[ ! -f "$COMPREHENSIVE_SCRIPT" ]]; then
        fail "Comprehensive test script not found: $COMPREHENSIVE_SCRIPT"
        exit 2
    fi

    CMD_ARGS=(
        "$PYTHON_CMD" "$COMPREHENSIVE_SCRIPT"
        "--camera" "$CAMERA_DEVICE"
        "--model" "$MODEL_PATH"
        "--output-dir" "$SESSION_DIR"
    )
    if $SYNTHETIC; then
        CMD_ARGS+=("--synthetic")
    fi
    if $PYTHON_BACKEND; then
        CMD_ARGS+=("--python-backend")
    fi
    if $DEBUG; then
        CMD_ARGS+=("--debug")
    fi

    echo "  Running: ${CMD_ARGS[*]}"
    echo ""

    START_TS=$(date +%s)
    set +e
    set +o pipefail
    FULL_LOG="$SESSION_DIR/full_log.txt"
    "${CMD_ARGS[@]}" 2>&1 | tee -a "$FULL_LOG"
    TEST_EXIT=${PIPESTATUS[0]}
    set -o pipefail
    set -e
    END_TS=$(date +%s)
    RUNTIME=$((END_TS - START_TS))

    echo ""
    if [[ $TEST_EXIT -eq 0 ]]; then
        pass "Comprehensive test PASSED (exit=$TEST_EXIT, ${RUNTIME}s)"
    else
        fail "Comprehensive test FAILED (exit=$TEST_EXIT, ${RUNTIME}s)"
    fi

    postprocess_session

fi

# ==============================================================================
# STEP 5: Session Summary
# ==============================================================================
# ==============================================================================

header "STEP 5: Session Summary"

echo "  Session:   $SESSION_DIR/"
echo "  Mode:      $MODE"
if [[ "$MODE" == "scenario" ]]; then
    echo "  Scenario:  $SCENARIO"
fi
if [[ "$MODE" == "comprehensive" ]]; then
    echo "  Pipeline:  Camera → Preproc → MOG2 → YOLO → ByteTrack → Pipeline → Output"
fi
echo "  Duration:  ${RUNTIME}s"
echo "  Exit code: $TEST_EXIT"
echo ""

# Auto mode: show boundary crossing summary from log
if [[ "$MODE" == "auto" ]] && [[ -f "$SESSION_DIR/full_log.txt" ]]; then
    CI_COUNT=$(grep -c "CHECK_IN" "$SESSION_DIR/full_log.txt" 2>/dev/null || echo "0")
    CO_COUNT=$(grep -c "CHECK_OUT" "$SESSION_DIR/full_log.txt" 2>/dev/null || echo "0")
    echo "  Boundary crossings:"
    echo "    CHECK_IN  (enter):  $CI_COUNT"
    echo "    CHECK_OUT (leave):  $CO_COUNT"
    echo ""
fi

# Unit mode: show report
if [[ "$MODE" == "unit" ]] && [[ -f "$SESSION_DIR/frtapp_scenario_report.json" ]]; then
    echo "  Test report:"
    echo "    $(python3 -c "
import json
with open('$SESSION_DIR/frtapp_scenario_report.json') as f:
    r = json.load(f)
res = r.get('results', {})
print(f\"Passed: {res.get('passed', 0)}  Failed: {res.get('failed', 0)}  Skipped: {res.get('skipped', 0)}\")
print(f\"FPS samples: {r.get('fps_samples', [])}\")
" 2>/dev/null || echo '    (unable to parse)')"
fi

# Auto mode: show FRTApp summary from log
if [[ "$MODE" == "auto" ]] && [[ -f "$SESSION_DIR/full_log.txt" ]]; then
    FPS_VALS=$(grep "Pipeline Metrics" "$SESSION_DIR/full_log.txt" | tail -3 | sed 's/.*FPS: //;s/ .*//' | tr '\n' ' ')
    echo "  Pipeline FPS samples: $FPS_VALS"
    echo ""
    NMS_COUNT=$(grep -c "NMS:" "$SESSION_DIR/full_log.txt" 2>/dev/null || echo "0")
    NMS_BEFORE=$(grep "NMS:" "$SESSION_DIR/full_log.txt" | head -1 | sed 's/.*before=//;s/ .*//' 2>/dev/null || echo "?")
    NMS_AFTER=$(grep "NMS:" "$SESSION_DIR/full_log.txt" | head -1 | sed 's/.*after=//;s/ .*//' 2>/dev/null || echo "?")
    echo "  NMS inferences:  $NMS_COUNT"
    echo "  NMS suppression: $NMS_BEFORE → $NMS_AFTER boxes (first frame)"
    echo ""
fi

# Comprehensive mode: show report
if [[ "$MODE" == "comprehensive" ]] && [[ -f "$SESSION_DIR/frt_comprehensive_report.json" ]]; then
    echo "  Comprehensive test report:"
    echo "    $(python3 -c "
import json
with open('$SESSION_DIR/frt_comprehensive_report.json') as f:
    r = json.load(f)
res = r.get('results', {})
print(f'Passed: {res.get(\"passed\", 0)}  Failed: {res.get(\"failed\", 0)}  Skipped: {res.get(\"skipped\", 0)}')
print(f'Camera FPS: {r.get(\"metrics\",{}).get(\"camera_fps\",\"N/A\")}')
print(f'YOLO avg: {r.get(\"metrics\",{}).get(\"yolo_avg_latency_ms\",\"N/A\")}ms')
" 2>/dev/null || echo '    (unable to parse)')"
    echo ""
fi

# Scenario mode: show pipeline summary
if [[ "$MODE" == "scenario" ]] && [[ -f "$SESSION_DIR/pipeline_report.json" ]]; then
    echo "  Pipeline summary:"
    echo "    $(python3 -c "
import json
with open('$SESSION_DIR/pipeline_report.json') as f:
    r = json.load(f)
print(f'Frames: {r.get(\"frames_captured\",0)}  Inferences: {r.get(\"inferences_run\",0)}  Detections: {r.get(\"total_detections\",0)}')
print(f'Best conf: {r.get(\"best_confidence\",0)}  YOLO avg: {r[\"performance\"].get(\"yolo_avg_ms\",0)}ms')
print(f'Notifications: {r.get(\"notifications\",0)}  State transitions: {r.get(\"state_transitions\",0)}')
" 2>/dev/null || echo '    (unable to parse)')"
fi

echo ""
echo "  Artifacts:"
ls -1 "$SESSION_DIR/" 2>/dev/null | while IFS= read -r f; do
    SIZE=$(du -h "$SESSION_DIR/$f" 2>/dev/null | cut -f1)
    echo "    $SIZE  $f"
done

echo ""

# ==============================================================================
# EXIT (cleanup handles service restart)
# ==============================================================================

if [[ $TEST_EXIT -eq 0 ]]; then
    pass "TEST SESSION COMPLETED SUCCESSFULLY"
    exit 0
else
    fail "TEST SESSION FAILED — review logs in $SESSION_DIR/"
    exit 2
fi
