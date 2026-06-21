#!/usr/bin/env bash
#===============================================================================
# Thesis Screenshot Capture Script
# Target: Raspberry Pi 4B running FSS MagicMirror (X11/Electron)
#
# Captures all 8 screenshots needed for thesis documentation:
#   1. Shopping list UI (MMM-FSS-Recommend panel)
#   2. Sensor data display (MMM-FSS-Env panel)
#   3. Door/distance status (MMM-FSS-Monitor panel)
#   4. Annotated YOLO detection
#   5. MOG2 foreground mask
#   6. Recipe chips suggestions
#   7. QR code download overlay
#   8. Temperature anomaly alert (D-Bus monitor)
#
# Usage:
#   bash docs/thesis/capture_thesis_screenshots.sh [--dir OUTPUT_DIR]
#
# Dependencies:
#   - ImageMagick (import command): sudo apt install imagemagick
#   - xdotool: sudo apt install xdotool
#   - Running MagicMirror on DISPLAY=:0
#===============================================================================

set -euo pipefail

# --- Config ---
OUTPUT_DIR="${1:-thesis_screenshots}"
DISPLAY="${DISPLAY:-:0}"
FSS_ROOT="/home/pi/FSS"
MAGICMIRROR_DIR="${FSS_ROOT}/electron_app/magicmirror"
SYSTEM_RESULTS_DIR="${FSS_ROOT}/system_results"

# Ensure fresh output dir
mkdir -p "${OUTPUT_DIR}"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
snap() {
    local name="$1" desc="$2"
    log "Capturing: ${desc} → ${OUTPUT_DIR}/${name}.png"
    import -window root "${OUTPUT_DIR}/${name}.png"
}

# --- Check prerequisites ---
if ! command -v import &>/dev/null; then
    echo "ERROR: ImageMagick 'import' not found. Install: sudo apt install imagemagick"
    exit 1
fi

if ! command -v xdotool &>/dev/null; then
    echo "WARNING: xdotool not found. Install: sudo apt install xdotool"
    echo "Will proceed without window focus automation."
    XDOTOOL=false
else
    XDOTOOL=true
fi

# Verify display
if ! xdpyinfo -display "${DISPLAY}" &>/dev/null; then
    echo "ERROR: Cannot connect to display ${DISPLAY}"
    echo "Make sure X11/Electron is running."
    exit 1
fi

log "=== Thesis Screenshot Capture ==="
log "Output:  ${OUTPUT_DIR}"
log "Display: ${DISPLAY}"

# --- 1. Shopping List UI ---
snap "01_shopping_list" "Shopping list from RecommendDaemon (after recipe search)"
log "  → Open MagicMirror, search a recipe (e.g. 'Gỏi Trộn'), wait for result"

# --- 2. Sensor Data Display ---
snap "02_env_sensor" "Environment sensor panel (temperature + humidity)"
log "  → Ensure MMM-FSS-Env panel is visible on screen"

# --- 3. Door/Distance Status ---
snap "03_monitor_panel" "Monitor panel (door state + distance sensor)"
log "  → Ensure MMM-FSS-Monitor panel is visible"

# --- 4. Annotated YOLO Detection ---
LATEST_SESSION=$(ls -t "${SYSTEM_RESULTS_DIR}" 2>/dev/null | head -1)
if [ -n "${LATEST_SESSION}" ]; then
    ANNOTATED="${SYSTEM_RESULTS_DIR}/${LATEST_SESSION}/annotated_result.jpg"
    if [ -f "${ANNOTATED}" ]; then
        cp "${ANNOTATED}" "${OUTPUT_DIR}/04_yolo_annotation.jpg"
        log "Copied annotated YOLO result from ${ANNOTATED}"
    else
        log "WARNING: No annotated_result.jpg found in ${LATEST_SESSION}"
    fi
else
    log "WARNING: No FRT sessions found in ${SYSTEM_RESULTS_DIR}"
fi

# --- 5. MOG2 Foreground Mask ---
if [ -n "${LATEST_SESSION}" ]; then
    MOG2="${SYSTEM_RESULTS_DIR}/${LATEST_SESSION}/mog2_foreground_mask.jpg"
    if [ -f "${MOG2}" ]; then
        cp "${MOG2}" "${OUTPUT_DIR}/05_mog2_mask.jpg"
        log "Copied MOG2 mask from ${MOG2}"
    else
        log "WARNING: No mog2_foreground_mask.jpg found in ${LATEST_SESSION}"
    fi
fi

# --- 6. Recipe Chips Suggestions ---
snap "06_recipe_chips" "Recipe chip suggestions below search input"
log "  → Type partial recipe name, wait for chip suggestions to appear"

# --- 7. QR Code Download Overlay ---
snap "07_qr_download" "QR code download overlay on recommendation result"
log "  → Click '📱 Tải về' button, wait for QR overlay to appear"

# --- 8. Temperature Anomaly Alert ---
snap "08_temp_anomaly" "Temperature anomaly alert (D-Bus monitor)"
log "  → Simulate temperature spike (e.g., fridge door left open)"
log "  → Capture the D-Bus monitor or UI notification"

# --- Summary ---
log ""
log "=== Capture Complete ==="
log "Files saved to: ${OUTPUT_DIR}/"
ls -lh "${OUTPUT_DIR}/"
echo ""
echo "Manual steps needed for each screenshot:"
echo "  1. Shopping list   : Open MM, search recipe, wait for result"
echo "  2. Env sensor      : Position MMM-FSS-Env panel in view"
echo "  3. Monitor         : Position MMM-FSS-Monitor panel in view"
echo "  4. YOLO            : Auto-copied from system_results/"
echo "  5. MOG2            : Auto-copied from system_results/"
echo "  6. Recipe chips    : Type partial name, wait for chips"
echo "  7. QR overlay      : Click Tải về button"
echo "  8. Temp anomaly    : Open door / heat source near sensor"
echo ""
echo "For fully automated capture on RPi4 with stable UI state:"
echo "  bash docs/thesis/capture_thesis_screenshots_auto.sh"
