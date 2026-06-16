#!/bin/bash
# ==============================================================================
# test_nlp_pipeline.sh — Start RecommendDaemon + MagicMirror for NLP testing
#
# Usage:
#   bash tools/test_nlp_pipeline.sh              # Start both daemon + UI
#   bash tools/test_nlp_pipeline.sh --mock        # Use mock data (no daemon)
#   bash tools/test_nlp_pipeline.sh --help        # Show help
#
# What it does:
#   1. Starts RecommendDaemon (D-Bus service for NLP)
#   2. Starts MagicMirror (Electron UI with MMM-FSS-Recommend + MMM-Keyboard)
#   3. Cleans up both on Ctrl+C
# ==============================================================================
set -euo pipefail

FSS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$FSS_ROOT"

MODE="${1:-full}"

if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
    sed -n '3,15p' "$0"
    exit 0
fi

cleanup_stale() {
    # Stop systemd service first (prevents auto-restart)
    if systemctl is-active --quiet fss-recommend 2>/dev/null; then
        echo "Stopping fss-recommend systemd service..."
        sudo systemctl stop fss-recommend 2>/dev/null || true
        sleep 1
    fi

    local name="recommend_daemon"
    local pids
    pids=$(pgrep -f "$name" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "Cleaning up stale $name (PIDs: $pids)..."
        kill $pids 2>/dev/null || true
        sleep 1
        pids=$(pgrep -f "$name" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            kill -9 $pids 2>/dev/null || true
        fi
        sleep 1
    fi
    # Wait for D-Bus name release
    local svc="vn.edu.uit.FSS.RecommendDaemon"
    local waited=0
    while [[ $waited -lt 5 ]]; do
        if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus \
            /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
            string:"$svc" 2>/dev/null | grep -q "true"; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "WARNING: D-Bus name $svc still held, continuing..."
}

cleanup() {
    echo ""
    echo "Shutting down..."
    if [[ -n "${RECOMMEND_PID:-}" ]] && kill -0 "$RECOMMEND_PID" 2>/dev/null; then
        kill -SIGTERM "$RECOMMEND_PID" 2>/dev/null || true
        echo "RecommendDaemon stopped (PID $RECOMMEND_PID)"
    fi
    if [[ -n "${MM_PID:-}" ]] && kill -0 "$MM_PID" 2>/dev/null; then
        kill -SIGTERM "$MM_PID" 2>/dev/null || true
        echo "MagicMirror stopped (PID $MM_PID)"
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT

# --- Check display ---
if [[ -z "${DISPLAY:-}" ]]; then
    if [[ -f /tmp/.X0-lock ]]; then
        export DISPLAY=:0
        echo "Display set to :0 (detected)"
    else
        echo "ERROR: No X display found. Set DISPLAY or use --mock."
        echo "  export DISPLAY=:0"
        exit 1
    fi
fi

# --- Mock mode ---
if [[ "$MODE" == "--mock" ]]; then
    echo "=== MOCK MODE ==="
    echo "No daemon needed — bridge returns mock data for recipe 'test' or 'dev'"
    echo ""
    echo "In MagicMirror, type 'test' or 'dev' in the search box to see mock results."
    echo ""
    # Start MagicMirror only
    cd "$FSS_ROOT/electron_app/magicmirror"
    echo "Starting MagicMirror..."
    DISPLAY="$DISPLAY" npm run start:x11:dev &
    MM_PID=$!
    echo "MagicMirror started (PID $MM_PID)"
    wait $MM_PID
    exit 0
fi

# --- Full mode: start RecommendDaemon ---
echo "=== FULL NLP PIPELINE MODE ==="
echo ""

# Clean up any stale daemon from prior sessions
cleanup_stale

echo "Starting RecommendDaemon (D-Bus: vn.edu.uit.FSS.RecommendDaemon)..."

# Ensure data dir exists
mkdir -p /opt/fss/data

# Start RecommendDaemon in background
"$FSS_ROOT/recommend_daemon/venv/bin/python" \
    "$FSS_ROOT/recommend_daemon/src/main.py" &
RECOMMEND_PID=$!
echo "RecommendDaemon started (PID $RECOMMEND_PID)"

# Wait for D-Bus registration
sleep 3
if kill -0 "$RECOMMEND_PID" 2>/dev/null; then
    echo "RecommendDaemon is running"
else
    echo "ERROR: RecommendDaemon failed to start"
    exit 1
fi

# Verify D-Bus service registered (also retry if slow)
echo "Verifying D-Bus registration..."
for i in 1 2 3; do
    if dbus-send --system --print-reply --dest=org.freedesktop.DBus \
        /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
        string:"vn.edu.uit.FSS.RecommendDaemon" 2>/dev/null | grep -q "true"; then
        echo "D-Bus service registered ✓"
        break
    fi
    if [[ $i -lt 3 ]]; then sleep 1; fi
done || echo "WARNING: D-Bus not yet registered (UI bridge will use mock fallback)"

echo ""
echo "=== READY ==="
echo "Type a Vietnamese recipe name (e.g., 'thịt kho tàu, canh chua')"
echo "in the MagicMirror search box → MMM-Keyboard → SEND"
echo ""

# Start MagicMirror
cd "$FSS_ROOT/electron_app/magicmirror"
echo "Starting MagicMirror..."
DISPLAY="$DISPLAY" npm run start:x11:dev &
MM_PID=$!
echo "MagicMirror started (PID $MM_PID)"

# Wait for either process to exit
wait -n $RECOMMEND_PID $MM_PID 2>/dev/null || true
cleanup
