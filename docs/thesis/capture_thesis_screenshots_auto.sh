#!/usr/bin/env bash
#===============================================================================
# Automated Thesis Screenshot Capture (RPi4 + MagicMirror)
#
# Fully automated version that:
#   1. Launches all FSS daemons
#   2. Opens MagicMirror with specific modules
#   3. Injects recipe searches via keyboard simulation (xdotool)
#   4. Captures all 8 thesis screenshots
#   5. Shuts down cleanly
#
# Usage:
#   bash docs/thesis/capture_thesis_screenshots_auto.sh
#
# Dependencies: imagemagick, xdotool, xclip
#   sudo apt install imagemagick xdotool xclip
#===============================================================================

set -euo pipefail

OUTPUT_DIR="thesis_screenshots_auto"
DISPLAY="${DISPLAY:-:0}"
FSS_ROOT="/home/pi/FSS"
PI_USER="pi"
LOG_FILE="${OUTPUT_DIR}/capture.log"

mkdir -p "${OUTPUT_DIR}"

log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
snap() { import -window root "${OUTPUT_DIR}/${1}.png"; log "  → Saved ${1}.png"; }

type_text() {
    xdotool type --delay 50 "$1"
    sleep 0.5
}

press_key() {
    xdotool key "$1"
    sleep 0.3
}

#===============================================================================
# 1. Start Daemons
#===============================================================================
log "=== Starting FSS daemons ==="

# Kill any existing processes
sudo pkill sensor_daemon_exec 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "MagicMirror" 2>/dev/null || true
sleep 2

# Start SensorDaemon
log "Starting SensorDaemon..."
sudo "${FSS_ROOT}/sensor_daemon/build/sensor_daemon_exec" &
SENSOR_PID=$!
sleep 2

# Start DBDaemon
log "Starting DBDaemon..."
source "${FSS_ROOT}/db_daemon/venv/bin/activate"
python "${FSS_ROOT}/db_daemon/src/main.py" &
DE_PID=$!
sleep 3

# Start RecommendDaemon
log "Starting RecommendDaemon..."
source "${FSS_ROOT}/recommend_daemon/venv/bin/activate"
python "${FSS_ROOT}/recommend_daemon/src/main.py" &
REC_PID=$!
sleep 2

#===============================================================================
# 2. Start MagicMirror
#===============================================================================
log "Starting MagicMirror..."
export ELECTRON_ENABLE_STACK_DUMPING=true
export ELECTRON_ENABLE_LOGGING=1

cd "${FSS_ROOT}/electron_app/magicmirror"
DISPLAY="${DISPLAY}" npm start &
MM_PID=$!

# Wait for MagicMirror to fully load
log "Waiting for MagicMirror to load (15s)..."
sleep 15

# Get MagicMirror window ID
MM_WINDOW=$(xdotool search --name "MagicMirror" 2>/dev/null | head -1)
if [ -z "${MM_WINDOW}" ]; then
    log "WARNING: MagicMirror window not found. Trying fallback..."
    MM_WINDOW=$(xdotool search --class "electron" 2>/dev/null | head -1)
fi

if [ -n "${MM_WINDOW}" ]; then
    xdotool windowactivate "${MM_WINDOW}"
    log "MagicMirror window activated (ID: ${MM_WINDOW})"
fi
sleep 2

#===============================================================================
# 3. Screenshot 2 — Sensor Data (MMM-FSS-Env)
#===============================================================================
log "=== Screenshot 2: Environment Sensor Data ==="
sleep 3  # Let sensor data accumulate
snap "02_env_sensor"

#===============================================================================
# 4. Screenshot 3 — Monitor Panel (MMM-FSS-Monitor)
#===============================================================================
log "=== Screenshot 3: Monitor Panel ==="
snap "03_monitor_panel"

#===============================================================================
# 5. Screenshot 6 — Recipe Chips
#===============================================================================
log "=== Screenshot 6: Recipe Chips ==="
# Click on the recommend search input area
# Coordinates depend on MagicMirror layout — adjust as needed
xdotool mousemove 400 300 click 1
sleep 1

# Type partial recipe name
type_text "gỏi"
sleep 2
snap "06_recipe_chips"

#===============================================================================
# 6. Screenshot 1 + 7 — Search recipe → Shopping List → QR
#===============================================================================
log "=== Screenshot 1: Shopping List ==="

# Clear and type full recipe name
press_key "ctrl+a"
press_key "Delete"
sleep 0.5

type_text "gỏi trộn khô mực"
press_key "Return"
sleep 5  # Wait for NLP + D-Bus roundtrip

snap "01_shopping_list"

# Screenshot 7: QR code
log "=== Screenshot 7: QR Download ==="
# Click Tải về button (adjust coordinates)
xdotool mousemove 700 500 click 1
sleep 3
snap "07_qr_download"

# Click close button to dismiss QR overlay
xdotool mousemove 400 200 click 1
sleep 1

#===============================================================================
# 7. Screenshot 8 — Temperature Anomaly
#===============================================================================
log "=== Screenshot 8: Temperature Anomaly ==="
# Simulate high temperature by publishing a D-Bus signal
dbus-send --system --type=signal \
    --dest=vn.edu.uit.FSS.SensorDaemon \
    /vn/edu/uit/FSS/Interface \
    vn.edu.uit.FSS.Interface.TemperatureAnomaly \
    string:'{"temperature":13.5,"humidity":72,"severity":"critical","rule_id":2}'

sleep 2
snap "08_temp_anomaly"

#===============================================================================
# 8. Copy FRT Pipeline Outputs (Screenshots 4 + 5)
#===============================================================================
log "=== Screenshots 4 + 5: FRT Pipeline ==="
LATEST_SESSION=$(ls -t "${FSS_ROOT}/system_results" 2>/dev/null | head -1)
if [ -n "${LATEST_SESSION}" ]; then
    SESSION_DIR="${FSS_ROOT}/system_results/${LATEST_SESSION}"
    [ -f "${SESSION_DIR}/annotated_result.jpg" ] && \
        cp "${SESSION_DIR}/annotated_result.jpg" "${OUTPUT_DIR}/04_yolo_annotation.jpg"
    [ -f "${SESSION_DIR}/mog2_foreground_mask.jpg" ] && \
        cp "${SESSION_DIR}/mog2_foreground_mask.jpg" "${OUTPUT_DIR}/05_mog2_mask.jpg"
    log "  → Copied from ${SESSION_DIR}"
fi

#===============================================================================
# 9. Cleanup
#===============================================================================
log "=== Shutting down ==="

# Close MagicMirror
if [ -n "${MM_WINDOW}" ]; then
    xdotool windowclose "${MM_WINDOW}"
fi
kill "${MM_PID}" 2>/dev/null || true

# Kill daemons
kill "${REC_PID}" 2>/dev/null || true
kill "${DE_PID}" 2>/dev/null || true
sudo kill "${SENSOR_PID}" 2>/dev/null || true
sleep 2

# Force cleanup
sudo pkill -f sensor_daemon_exec 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true

log ""
log "========================================"
log "CAPTURE COMPLETE — ${OUTPUT_DIR}/"
log "========================================"
ls -lh "${OUTPUT_DIR}/" | grep -v log

echo ""
echo "Results:"
echo "  02_env_sensor.png          — Environment sensor data (MMM-FSS-Env)"
echo "  03_monitor_panel.png       — Door/distance status (MMM-FSS-Monitor)"
echo "  04_yolo_annotation.jpg     — Annotated YOLO detection"
echo "  05_mog2_mask.jpg           — MOG2 foreground mask"
echo "  06_recipe_chips.png        — Recipe chip suggestions"
echo "  01_shopping_list.png       — Shopping list from search"
echo "  07_qr_download.png         — QR code overlay"
echo "  08_temp_anomaly.png        — Temperature anomaly alert"
echo ""
echo "NOTE: Coordinate values (mousemove) may need adjustment"
echo "for your specific MagicMirror layout. Edit this script"
echo "to fine-tune click positions."
