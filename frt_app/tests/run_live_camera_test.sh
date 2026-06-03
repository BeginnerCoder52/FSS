#!/usr/bin/env bash
# ==============================================================================
# run_live_camera_test.sh — FRTApp Live Camera AI Test
# ==============================================================================
#
# Purpose:
#     Real hardware test: captures ~3-5s of live camera, runs the full FRTApp
#     YOLO pipeline (MOG2 → Preprocess → YOLOv11 → ByteTrack), and produces:
#
#     Output (in OUTPUT_DIR/):
#       1. full_log.txt              — Complete timestamped pipeline log
#       2. annotated_result.jpg      — Best frame with bbox + food class labels
#       3. mog2_foreground_mask.jpg  — MOG2 foreground (green overlay)
#       4. mog2_heatmap.jpg          — MOG2 heatmap visualization
#       5. preprocess_rgb.jpg        — BGR→RGB conversion result
#       6. preprocess_letterbox.jpg  — Letterboxed 640x640 frame
#       7. inference_table.csv       — Full detection CSV
#       8. inference_table.md        — Formatted markdown table
#       9. pipeline_report.json      — Structured metrics + summary
#
# Usage:
#     sudo bash run_live_camera_test.sh                    # Default 5s
#     sudo bash run_live_camera_test.sh --duration 3       # 3 seconds
#     sudo bash run_live_camera_test.sh --output /tmp/mytest
#     sudo bash run_live_camera_test.sh --camera /dev/video2
#     sudo bash run_live_camera_test.sh --model /opt/fss/models/yolov11n.tflite
#     sudo bash run_live_camera_test.sh --debug
#     sudo bash run_live_camera_test.sh --help
#
# Requirements:
#     - Camera at /dev/video0 (or specify with --camera)
#     - YOLO model at /opt/fss/models/yolov11n.tflite
#     - fss_env_setup.sh run OR system deps installed
#     - Python venv: frt_app/py_ai_core/venv/ (or system python3 with deps)
#
# Exit Codes:
#     0 — All pipeline stages completed successfully
#     1 — Prerequisite check failed (no camera/model)
#     2 — Pipeline runtime error
#
# Author: FSS Project Team
# License: Proprietary
# ==============================================================================

set -euo pipefail

# ==============================================================================
# CONFIGURATION
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FSS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FSS_ROOT="$(cd "$FSS_ROOT" && pwd)"

CAMERA_DEVICE="/dev/video0"
MODEL_PATH="/opt/fss/models/yolov11n.tflite"
DURATION=5
OUTPUT_DIR=""
DEBUG=false

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
        --camera)    CAMERA_DEVICE="$2"; shift 2 ;;
        --model)     MODEL_PATH="$2"; shift 2 ;;
        --duration)  DURATION="$2"; shift 2 ;;
        --output)    OUTPUT_DIR="$2"; shift 2 ;;
        --debug)     DEBUG=true; shift ;;
        --help|-h)   show_help ;;
        *)           echo "Unknown option: $1"; show_help ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="/tmp/frt_live_test_$(date +%Y%m%d_%H%M%S)"
fi

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

pass()  { echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
info()  { echo -e "  ${CYAN}→${NC} $1"; }
header(){ echo -e "\n${CYAN}$1${NC}"; echo "────────────────────────────────────────"; }

cleanup() {
    if [[ -n "${CAMERA_PID:-}" ]]; then
        kill "$CAMERA_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

# ==============================================================================
# STEP 1: Prerequisite Checks
# ==============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      FRTApp — LIVE CAMERA AI TEST (BASH WRAPPER)           ║"
echo "║  Camera → MOG2 → Preprocess → YOLOv11 → ByteTrack → Output ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Camera:   $CAMERA_DEVICE"
echo "  Model:    $MODEL_PATH"
echo "  Duration: ${DURATION}s"
echo "  Output:   $OUTPUT_DIR"
echo "  Debug:    $DEBUG"
echo "  FSS_ROOT: $FSS_ROOT"
echo ""

header "STEP 1: Prerequisite Checks"

PREREQ_FAIL=false

# --- 1a. Camera device ---
info "Camera device: $CAMERA_DEVICE"
if [[ -c "$CAMERA_DEVICE" ]]; then
    pass "Camera device found (character device)"
else
    fail "Camera device $CAMERA_DEVICE not found or not a character device"
    PREREQ_FAIL=true
fi

# Check if camera is claimed by another process
if command -v fuser &>/dev/null; then
    if fuser "$CAMERA_DEVICE" &>/dev/null; then
        warn "Camera $CAMERA_DEVICE is in use by another process"
        info "Run: sudo systemctl stop fss-camera fss-ai"
    fi
fi

# --- 1b. YOLO model ---
info "YOLO model: $MODEL_PATH"
if [[ -f "$MODEL_PATH" ]]; then
    MODEL_SIZE=$(du -h "$MODEL_PATH" | cut -f1)
    pass "YOLO model found ($MODEL_SIZE)"
else
    fail "YOLO model not found at $MODEL_PATH"
    warn "Place model at $MODEL_PATH or use --model"
    PREREQ_FAIL=true
fi

# --- 1c. Python + venv ---
info "Python environment"
PYTHON_CMD=""
if [[ -f "$FSS_ROOT/frt_app/py_ai_core/venv/bin/python3" ]]; then
    PYTHON_CMD="$FSS_ROOT/frt_app/py_ai_core/venv/bin/python3"
    pass "Using component venv: frt_app/py_ai_core/venv/"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    pass "Using system python3"
else
    fail "No Python 3 interpreter found"
    PREREQ_FAIL=true
fi

# --- 1d. Python dependencies ---
info "Python dependencies"
if [[ -n "$PYTHON_CMD" ]]; then
    DEPS_OK=true
    for mod in cv2 numpy loguru; do
        if "$PYTHON_CMD" -c "import $mod" 2>/dev/null; then
            : # ok
        else
            warn "Module '$mod' not available in selected Python"
            DEPS_OK=false
        fi
    done
    if $DEPS_OK; then
        pass "Core Python dependencies (cv2, numpy, loguru)"
    else
        warn "Some dependencies missing — pipeline may fail"
    fi

    # Check TFLite backend
    if "$PYTHON_CMD" -c "import ctypes; lib=ctypes.CDLL('libtflite_reader.so')" 2>/dev/null; then
        pass "TFLite C backend: libtflite_reader.so loaded"
    elif "$PYTHON_CMD" -c "import tflite_runtime" 2>/dev/null; then
        pass "TFLite Python backend: tflite_runtime available"
    else
        warn "No TFLite backend found — YOLO inference will fail"
    fi
fi

# --- 1e. Output directory ---
info "Output directory: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
pass "Output directory created"

if $PREREQ_FAIL; then
    echo ""
    fail "Prerequisite checks failed — aborting"
    echo "  Fix issues above and re-run"
    exit 1
fi

echo ""
pass "All prerequisites met"
echo ""

# ==============================================================================
# STEP 2: Run Pipeline
# ==============================================================================

header "STEP 2: Running Live Camera Pipeline"

PIPELINE_SCRIPT="$SCRIPT_DIR/live_camera_pipeline.py"
if [[ ! -f "$PIPELINE_SCRIPT" ]]; then
    fail "Pipeline script not found: $PIPELINE_SCRIPT"
    exit 2
fi

if [[ $EUID -ne 0 ]]; then
    warn "Not running as root — camera access may fail"
    info "Re-run with: sudo bash $0"
fi

CMD_ARGS=(
    "$PYTHON_CMD" "$PIPELINE_SCRIPT"
    "--camera" "$CAMERA_DEVICE"
    "--model" "$MODEL_PATH"
    "--duration" "$DURATION"
    "--output-dir" "$OUTPUT_DIR"
)

if $DEBUG; then
    CMD_ARGS+=("--debug")
fi

echo "  Running: ${CMD_ARGS[*]}"
echo ""

START_TS=$(date +%s)
set +e
"${CMD_ARGS[@]}"
PIPELINE_EXIT=$?
set -e
END_TS=$(date +%s)
RUNTIME=$((END_TS - START_TS))

echo ""
if [[ $PIPELINE_EXIT -eq 0 ]]; then
    pass "Pipeline completed in ${RUNTIME}s (exit=$PIPELINE_EXIT)"
else
    fail "Pipeline failed (exit=$PIPELINE_EXIT) after ${RUNTIME}s"
fi

# ==============================================================================
# STEP 3: Verify Outputs
# ==============================================================================

header "STEP 3: Output Artifacts Verification"

OUTPUT_FILES=(
    "full_log.txt"
    "annotated_result.jpg"
    "mog2_foreground_mask.jpg"
    "mog2_heatmap.jpg"
    "preprocess_rgb.jpg"
    "preprocess_letterbox.jpg"
    "inference_table.csv"
    "inference_table.md"
    "pipeline_report.json"
)

FILES_PRESENT=0
FILES_MISSING=0

for f in "${OUTPUT_FILES[@]}"; do
    FPATH="$OUTPUT_DIR/$f"
    if [[ -f "$FPATH" ]]; then
        SIZE=$(du -h "$FPATH" | cut -f1)
        pass "$f ($SIZE)"
        FILES_PRESENT=$((FILES_PRESENT + 1))
    else
        warn "$f — not generated"
        FILES_MISSING=$((FILES_MISSING + 1))
    fi
done

echo ""
echo "  Files present: $FILES_PRESENT / ${#OUTPUT_FILES[@]}"
if [[ $FILES_MISSING -gt 0 ]]; then
    echo "  Files missing: $FILES_MISSING"
fi

# ==============================================================================
# STEP 4: Show Inference Summary
# ==============================================================================

header "STEP 4: Inference Summary"

if [[ -f "$OUTPUT_DIR/pipeline_report.json" ]]; then
    TOTAL_DETS=$(python3 -c "import json; r=json.load(open('$OUTPUT_DIR/pipeline_report.json')); print(r.get('total_detections',0))" 2>/dev/null || echo "N/A")
    BEST_CONF=$(python3 -c "import json; r=json.load(open('$OUTPUT_DIR/pipeline_report.json')); print(r.get('best_confidence',0))" 2>/dev/null || echo "N/A")
    YOLO_AVG=$(python3 -c "import json; r=json.load(open('$OUTPUT_DIR/pipeline_report.json')); print(r['performance'].get('yolo_avg_ms',0))" 2>/dev/null || echo "N/A")
    FRAMES=$(python3 -c "import json; r=json.load(open('$OUTPUT_DIR/pipeline_report.json')); print(r.get('frames_captured',0))" 2>/dev/null || echo "N/A")
    INFERS=$(python3 -c "import json; r=json.load(open('$OUTPUT_DIR/pipeline_report.json')); print(r.get('inferences_run',0))" 2>/dev/null || echo "N/A")

    echo "  Total frames captured:  $FRAMES"
    echo "  Inferences run:         $INFERS"
    echo "  Total detections:       $TOTAL_DETS"
    echo "  Best confidence:        $BEST_CONF"
    echo "  Avg YOLO latency:       ${YOLO_AVG}ms"

    # Show per-class breakdown
    CLASS_DATA=$(python3 -c "
import json
r = json.load(open('$OUTPUT_DIR/pipeline_report.json'))
by_class = r.get('detections_by_class', {})
if by_class:
    for cid, cnt in sorted(by_class.items()):
        print(f'    Class #{cid}: {cnt} detections')
else:
    print('    (no class breakdown — all detections unknown)')
" 2>/dev/null || true)
    echo ""
    echo "  Detections by class:"
    echo "$CLASS_DATA"
else
    warn "pipeline_report.json not found — cannot show summary"
fi

# Show sample from CSV if available
if [[ -f "$OUTPUT_DIR/inference_table.csv" ]]; then
    LINE_COUNT=$(wc -l < "$OUTPUT_DIR/inference_table.csv")
    if [[ $LINE_COUNT -gt 1 ]]; then
        echo ""
        echo "  Top detections (from inference_table.csv):"
        head -6 "$OUTPUT_DIR/inference_table.csv" | column -t -s','
    fi
fi

# ==============================================================================
# FINAL SUMMARY
# ==============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    TEST COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  All outputs saved to:"
echo "    $OUTPUT_DIR/"
echo ""
echo "  Key files:"
echo "    Log:          $OUTPUT_DIR/full_log.txt"
echo "    Annotated:    $OUTPUT_DIR/annotated_result.jpg"
echo "    MOG2 mask:    $OUTPUT_DIR/mog2_foreground_mask.jpg"
echo "    MOG2 heatmap: $OUTPUT_DIR/mog2_heatmap.jpg"
echo "    RGB preview:  $OUTPUT_DIR/preprocess_rgb.jpg"
echo "    Letterbox:    $OUTPUT_DIR/preprocess_letterbox.jpg"
echo "    CSV table:    $OUTPUT_DIR/inference_table.csv"
echo "    MD table:     $OUTPUT_DIR/inference_table.md"
echo "    Report JSON:  $OUTPUT_DIR/pipeline_report.json"
echo ""
echo "  Quick view:"
echo "    cat $OUTPUT_DIR/full_log.txt"
echo "    cat $OUTPUT_DIR/inference_table.md"
echo "    eog $OUTPUT_DIR/annotated_result.jpg"
echo ""

if [[ $PIPELINE_EXIT -eq 0 ]]; then
    echo -e "  ${GREEN}✓ TEST PASSED${NC}"
    exit 0
else
    echo -e "  ${RED}✗ TEST FAILED (exit code $PIPELINE_EXIT)${NC}"
    exit 2
fi
