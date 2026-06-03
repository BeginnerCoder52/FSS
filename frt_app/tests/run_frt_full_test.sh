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
#     --mode unit       (default) test_user_scenario_frtapp.py — 38 unit tests
#     --mode scenario   user_scenario_pipeline.py — live check-in/check-out
#       --scenario check-in   S1: hand+fuit enters → YOLO detects → "added"
#       --scenario check-out  S2: fruit leaves → YOLO detects → "removed"
#
# Usage:
#     sudo bash run_frt_full_test.sh                          # default unit mode
#     sudo bash run_frt_full_test.sh --mode scenario --scenario check-in
#     sudo bash run_frt_full_test.sh --mode scenario --scenario check-out --duration 20
#     sudo bash run_frt_full_test.sh --mode unit --duration 3
#     sudo bash run_frt_full_test.sh --no-shm
#     sudo bash run_frt_full_test.sh --skip-services
#     sudo bash run_frt_full_test.sh --debug
#     sudo bash run_frt_full_test.sh --help
#
# Session Directory:
#     /tmp/frt_session_<YYYYMMDD_HHMMSS>/
#       ├── full_log.txt
#       ├── pipeline_report.json
#       ├── annotated_result.jpg      (bbox + COCO class labels in scenario mode)
#       ├── inference_table.csv
#       ├── inference_table.md
#       ├── scenario_report.json      (scenario mode only)
#       ├── frtapp_scenario_report.json (unit mode only)
#       └── ... (other artifacts)
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
MODEL_PATH="/opt/fss/models/yolov11n.tflite"
DURATION=15
DEBUG=false
NO_SHM=false
SKIP_SERVICES=false
SYNTHETIC=false
SESSION_DIR=""
SHM_SECONDS=3
PIPELINE_FPS=10
MODE="scenario"
SCENARIO="check-in"

FSS_SERVICES=("fss-sensor" "fss-camera" "fss-ai" "fss-db" "fss-recommend")

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
        --shm-seconds)  SHM_SECONDS="$2"; shift 2 ;;
        --pipeline-fps) PIPELINE_FPS="$2"; shift 2 ;;
        --debug)        DEBUG=true; shift ;;
        --help|-h)      show_help ;;
        *)              echo "Unknown option: $1"; show_help ;;
    esac
done

# Generate timestamped session directory if not provided
if [[ -z "$SESSION_DIR" ]]; then
    SESSION_DIR="/tmp/frt_session_$(date +%Y%m%d_%H%M%S)"
fi

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

pass()  { echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
info()  { echo -e "  ${CYAN}→${NC} $1"; }
header(){ echo -e "\n${CYAN}══════════════════════════════════════════════${NC}"; echo -e "${CYAN} $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════════${NC}"; }

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

    # Remove SHM if we created it
    if $SHM_CREATED && [[ -f "/dev/shm/fss_video_frame" ]]; then
        info "Removing SHM /dev/shm/fss_video_frame..."
        rm -f "/dev/shm/fss_video_frame"
        pass "SHM removed"
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
echo "║            FRTApp — FULL ISOLATED TEST ORCHESTRATOR                ║"
echo "║  Stop Services → Create SHM → Run Scenario → Cleanup → Restart    ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Camera:       $CAMERA_DEVICE"
echo "  Model:        $MODEL_PATH"
echo "  Duration:     ${DURATION}s"
echo "  Session:      $SESSION_DIR"
echo "  Mode:         $MODE"
if [[ "$MODE" == "scenario" ]]; then
    echo "  Scenario:     $SCENARIO"
fi
echo "  Synthetic:    $SYNTHETIC"
echo "  Create SHM:   $([[ $NO_SHM == true ]] && echo 'no' || echo 'yes')"
echo "  SHM seconds:  ${SHM_SECONDS}s"
echo "  Pipeline FPS: $PIPELINE_FPS"
echo "  Stop svcs:    $([[ $SKIP_SERVICES == true ]] && echo 'no' || echo 'yes')"
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
        pass "Camera $CAMERA_DEVICE is free"
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

if [[ "$MODE" == "unit" ]]; then
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

else
    fail "Unknown mode: $MODE (use --mode unit or --mode scenario)"
    exit 2
fi

# ==============================================================================
# STEP 5: Session Summary
# ==============================================================================

header "STEP 5: Session Summary"

echo "  Session:   $SESSION_DIR/"
echo "  Mode:      $MODE"
if [[ "$MODE" == "scenario" ]]; then
    echo "  Scenario:  $SCENARIO"
fi
echo "  Duration:  ${RUNTIME}s"
echo "  Exit code: $TEST_EXIT"
echo ""

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
