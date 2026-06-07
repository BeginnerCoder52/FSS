#!/usr/bin/env bash
# ==============================================================================
# FSS_RUN.sh — FSS Full System Runner
#
# Starts ALL FSS daemons in correct dependency order:
#   1. SensorDaemon   (C++ hardware I/O)
#   2. DBDaemon       (Python data controller)
#   3. FRT Camera Core (C++ V4L2 → POSIX SHM)
#   4. FRT AI Core    (Python YOLO inference)
#   5. RecipeExtractor (Python NLP)
#   6. RecommendDaemon (Python business logic)
#
# Features:
#   - Auto-detects if daemons are already running via systemd
#   - Manages PID files for monitoring/cleanup
#   - Graceful shutdown on SIGINT/SIGTERM
#   - Process health monitoring (auto-restart on crash)
#   - Per-daemon log files in /var/log/fss/
#   - Status display
#
# Usage:
#   bash FSS_RUN.sh                          # run all daemons (default)
#   bash FSS_RUN.sh --daemon sensor          # run only SensorDaemon
#   bash FSS_RUN.sh --daemon db              # run only DBDaemon
#   bash FSS_RUN.sh --daemon camera,ai       # run camera + AI only
#   bash FSS_RUN.sh --no-monitor              # run without auto-restart
#   bash FSS_RUN.sh --status                  # show daemon status
#   bash FSS_RUN.sh --stop                    # stop all daemons
#   bash FSS_RUN.sh --help                    # show full help
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Source profile
. "${SCRIPT_DIR}/fss_profile.conf"

LOG_DIR="${FSS_LOG_DIR:-/var/log/fss}"
PID_DIR="/tmp/fss"
MONITOR=true
SELECTED_DAEMONS=""

# ==============================================================================
# Daemon registry: defines all daemons with their metadata
# ==============================================================================
declare -A DAEMON_MAP
DAEMON_MAP=(
    ["sensor"]="SensorDaemon:sensor"
    ["db"]="DBDaemon:db"
    ["camera"]="FRTApp Camera:camera"
    ["ai"]="FRTApp AI:ai"
    ["recipe"]="RecipeExtractor:recipe"
    ["recommend"]="RecommendDaemon:recommend"
)

declare -A DAEMON_NAMES
DAEMON_NAMES=(
    ["sensor"]="SensorDaemon"
    ["db"]="DBDaemon"
    ["camera"]="FRTApp Camera Core"
    ["ai"]="FRTApp AI Core"
    ["recipe"]="RecipeExtractor"
    ["recommend"]="RecommendDaemon"
)

declare -A DAEMON_CMDS
DAEMON_CMDS=(
    ["sensor"]="sudo ${FSS_SENSOR_EXEC}"
    ["db"]="sudo ${FSS_VENV_DB_DAEMON}/bin/python ${FSS_ROOT}/db_daemon/src/main.py"
    ["camera"]="sudo ${FSS_CAMERA_EXEC}"
    ["ai"]="sudo ${FSS_VENV_FRT_AI}/bin/python ${FSS_ROOT}/frt_app/py_ai_core/src/main.py --use-c-backend"
    ["recipe"]="sudo ${FSS_VENV_RECIPE_EXTRACTOR}/bin/python ${FSS_ROOT}/recipe_extractor/src/recipe_extractor_main.py"
    ["recommend"]="sudo ${FSS_VENV_RECOMMEND_DAEMON}/bin/python ${FSS_ROOT}/recommend_daemon/src/main.py"
)

declare -A DAEMON_LOGS
DAEMON_LOGS=(
    ["sensor"]="${LOG_DIR}/sensor_daemon.log"
    ["db"]="${LOG_DIR}/db_daemon.log"
    ["camera"]="${LOG_DIR}/frt_camera.log"
    ["ai"]="${LOG_DIR}/frt_ai.log"
    ["recipe"]="${LOG_DIR}/recipe_extractor.log"
    ["recommend"]="${LOG_DIR}/recommend_daemon.log"
)

declare -A DAEMON_CHECKS
DAEMON_CHECKS=(
    ["sensor"]="check_file_exec"
    ["db"]="check_venv"
    ["camera"]="check_file_exec"
    ["ai"]="check_venv"
    ["recipe"]="check_venv"
    ["recommend"]="check_venv"
)

# ==============================================================================
# Utility functions
# ==============================================================================

usage() {
    echo "Usage: bash FSS_RUN.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --daemon <list>   Comma-separated list: sensor,db,camera,ai,recipe,recommend"
    echo "  --no-monitor      Run without auto-restart monitoring"
    echo "  --status          Show daemon status and exit"
    echo "  --stop            Stop all running daemons"
    echo "  --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  bash FSS_RUN.sh                           # run everything"
    echo "  bash FSS_RUN.sh --daemon sensor,db        # run sensor + db"
    echo "  bash FSS_RUN.sh --status                  # check status"
    echo "  bash FSS_RUN.sh --stop                    # stop all"
    exit 0
}

# ==============================================================================
# Parse arguments
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --daemon)   SELECTED_DAEMONS="$2"; shift 2 ;;
        --no-monitor) MONITOR=false; shift ;;
        --status)   print_status; exit 0 ;;
        --stop)     stop_all; exit 0 ;;
        --help|-h)  usage ;;
        *)          echo "Unknown: $1"; usage ;;
    esac
done

# ==============================================================================
# Initialization
# ==============================================================================

setup_log_directory() {
    if [[ ! -d "$LOG_DIR" ]]; then
        sudo mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="${FSS_ROOT}/logs"
        mkdir -p "$LOG_DIR" 2>/dev/null || true
    fi
    mkdir -p "$PID_DIR"
}

check_file_exec() {
    local key="$1"
    local cmd="${DAEMON_CMDS[$key]}"
    local exec_path
    exec_path=$(echo "$cmd" | awk '{print $2}')
    if [[ ! -x "$exec_path" ]]; then
        fss_log_error "${DAEMON_NAMES[$key]} not found at $exec_path. Run FSS_SETUP.sh first."
        return 1
    fi
    return 0
}

check_venv() {
    local key="$1"
    local cmd="${DAEMON_CMDS[$key]}"
    local python_path
    python_path=$(echo "$cmd" | awk '{print $2}')
    if [[ ! -f "$python_path" ]]; then
        fss_log_error "Virtual env for ${DAEMON_NAMES[$key]} not found. Run FSS_SETUP.sh first."
        return 1
    fi
    return 0
}

wait_for_dbus_release() {
    local service_name="$1"
    local max_wait=5
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if ! dbus-send --system --dest=org.freedesktop.DBus \
            /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
            string:"$service_name" 2>/dev/null | grep -q "boolean true"; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

# ==============================================================================
# Daemon lifecycle
# ==============================================================================

start_daemon() {
    local key="$1"
    local name="${DAEMON_NAMES[$key]}"
    local cmd="${DAEMON_CMDS[$key]}"
    local log="${DAEMON_LOGS[$key]}"
    local check="${DAEMON_CHECKS[$key]}"
    local pidfile="${PID_DIR}/${key}.pid"

    fss_log_info "Starting ${name}..."

    "$check" "$key" || return 1

    nohup $cmd >"$log" 2>&1 &
    local pid=$!

    local sleep_time=2
    [[ "$key" == "sensor" || "$key" == "camera" ]] && sleep_time=1

    sleep "$sleep_time"

    if kill -0 "$pid" 2>/dev/null; then
        fss_log_ok "${name} started (PID: $pid)"
        echo "$pid" > "$pidfile"
        return 0
    fi

    fss_log_error "${name} failed to start. Check ${log}"
    return 1
}

stop_daemon() {
    local key="$1"
    local name="${DAEMON_NAMES[$key]}"
    local pidfile="${PID_DIR}/${key}.pid"

    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            fss_log_info "Stopping ${name} (PID: ${pid})..."
            kill -SIGTERM "$pid" 2>/dev/null
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                kill -SIGKILL "$pid" 2>/dev/null || true
            fi
            fss_log_ok "${name} stopped"
        fi
        rm -f "$pidfile"
    fi
}

stop_all() {
    fss_log_info "Shutting down all daemons..."
    # Stop in reverse dependency order
    for key in recommend recipe ai camera db sensor; do
        stop_daemon "$key"
    done
    fss_log_ok "All daemons stopped"

    for svc in vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.RecommendDaemon \
               vn.edu.uit.FSS.FRTApp vn.edu.uit.FSS.Sensor \
               vn.edu.uit.FSS.RecipeExtractor; do
        wait_for_dbus_release "$svc" || true
    done

    rm -f "$PID_DIR"/*.pid 2>/dev/null || true
}

cleanup_stale() {
    fss_log_info "Cleaning up stale processes..."

    for svc in fss-sensor fss-camera fss-ai fss-db fss-recommend; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            fss_log_warn "Stopping systemd service $svc..."
            sudo systemctl stop "$svc" 2>/dev/null || true
            sleep 1
        fi
    done

    for proc in sensor_daemon_exec camera_core_exec db_daemon recommend_daemon \
                recipe_extractor frt_ai; do
        pids=$(pgrep -f "$proc" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            fss_log_warn "Killing stale $proc (PIDs: $pids)"
            kill $pids 2>/dev/null || true
            sleep 1
            pids=$(pgrep -f "$proc" 2>/dev/null || true)
            [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
        fi
    done

    rm -f "$PID_DIR"/*.pid 2>/dev/null || true
    fss_log_ok "Stale processes cleaned"
}

# ==============================================================================
# Monitoring
# ==============================================================================

monitor_daemons() {
    while true; do
        sleep 5
        for key in sensor db camera ai recipe recommend; do
            local pidfile="${PID_DIR}/${key}.pid"
            local name="${DAEMON_NAMES[$key]}"
            if [[ -f "$pidfile" ]]; then
                local pid
                pid=$(cat "$pidfile")
                if ! kill -0 "$pid" 2>/dev/null; then
                    fss_log_warn "${name} died. Restarting..."
                    start_daemon "$key" || fss_log_error "Failed to restart ${name}"
                fi
            fi
        done
    done
}

# ==============================================================================
# Status
# ==============================================================================

print_status() {
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║  FSS Daemon Status                        ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    for key in sensor db camera ai recipe recommend; do
        local name="${DAEMON_NAMES[$key]}"
        local pidfile="${PID_DIR}/${key}.pid"
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            local pid
            pid=$(cat "$pidfile")
            local log="${DAEMON_LOGS[$key]}"
            echo -e "  ${_FSS_GREEN}✓${_FSS_NC} ${name} RUNNING (PID: ${pid})"
            echo -e "     Log: ${log}"
        else
            echo -e "  ${_FSS_RED}✗${_FSS_NC} ${name} STOPPED"
        fi
    done
    echo ""

    # D-Bus status
    echo "  D-Bus Services:"
    for svc in vn.edu.uit.FSS.Sensor vn.edu.uit.FSS.FRTApp \
               vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.RecommendDaemon \
               vn.edu.uit.FSS.RecipeExtractor; do
        if dbus-send --system --dest=org.freedesktop.DBus \
            /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
            string:"$svc" 2>/dev/null | grep -q "boolean true"; then
            echo -e "     ${_FSS_GREEN}✓${_FSS_NC} ${svc}"
        else
            echo -e "     ${_FSS_RED}✗${_FSS_NC} ${svc} (not registered)"
        fi
    done
    echo ""
}

# ==============================================================================
# Signal handler
# ==============================================================================

shutdown_handler() {
    echo ""
    fss_log_info "Received shutdown signal..."
    stop_all
    exit 0
}

trap shutdown_handler SIGTERM SIGINT

# ==============================================================================
# Main
# ==============================================================================

setup_log_directory
cleanup_stale

# Determine which daemons to start
if [[ -z "$SELECTED_DAEMONS" ]]; then
    DAEMON_ORDER=("sensor" "db" "camera" "ai" "recipe" "recommend")
else
    IFS=',' read -ra DAEMON_ORDER <<< "$SELECTED_DAEMONS"
fi

# Start daemons
fss_log_info "Starting FSS daemons..."
for key in "${DAEMON_ORDER[@]}"; do
    start_daemon "$key" || fss_log_warn "${DAEMON_NAMES[$key]} failed to start, continuing..."
done

print_status

# Monitor or wait
if [[ "$MONITOR" == true ]]; then
    fss_log_info "Monitoring enabled. Press Ctrl+C to stop all daemons."
    monitor_daemons
else
    fss_log_info "All daemons started (no monitoring). Press Ctrl+C to stop."
    while true; do sleep 10; done
fi
