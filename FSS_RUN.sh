#!/usr/bin/env bash
# ==============================================================================
# FSS_RUN.sh — FSS Full System Runner
#
# Starts ALL FSS daemons in correct dependency order:
#   1. SensorDaemon    (C++ hardware I/O)
#   2. DBDaemon        (Python data controller)
#   3. FRT Camera Core (C++ V4L2 → POSIX SHM)
#   4. FRT AI Core     (Python YOLO inference)
#   5. RecipeExtractor  (Python NLP)
#   6. RecommendDaemon  (Python business logic)
#   7. MagicMirror UI   (Node.js Electron via PM2)
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
MAX_RETRIES=5

declare -A DAEMON_RETRIES
DAEMON_RETRIES=(
    ["sensor"]=0
    ["db"]=0
    ["camera"]=0
    ["ai"]=0
    ["recipe"]=0
    ["recommend"]=0
    ["magicmirror"]=0
)

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
    ["magicmirror"]="MagicMirror:magicmirror"
)

declare -A DAEMON_NAMES
DAEMON_NAMES=(
    ["sensor"]="SensorDaemon"
    ["db"]="DBDaemon"
    ["camera"]="FRTApp Camera Core"
    ["ai"]="FRTApp AI Core"
    ["recipe"]="RecipeExtractor"
    ["recommend"]="RecommendDaemon"
    ["magicmirror"]="MagicMirror UI"
)

declare -A DAEMON_CMDS
DAEMON_CMDS=(
    ["sensor"]="sudo ${FSS_SENSOR_EXEC}"
    ["db"]="sudo ${FSS_VENV_DB_DAEMON}/bin/python ${FSS_ROOT}/db_daemon/src/main.py"
    ["camera"]="sudo ${FSS_CAMERA_EXEC} --fps 10"
    ["ai"]="sudo ${FSS_VENV_FRT_AI}/bin/python ${FSS_ROOT}/frt_app/py_ai_core/src/main.py --use-c-backend --model /opt/fss/models/0607_best_int8.tflite --model-precision int8"
    ["recipe"]="sudo ${FSS_VENV_RECIPE_EXTRACTOR}/bin/python ${FSS_ROOT}/recipe_extractor/src/recipe_extractor_main.py"
    ["recommend"]="sudo ${FSS_VENV_RECOMMEND_DAEMON}/bin/python ${FSS_ROOT}/recommend_daemon/src/main.py"
    ["magicmirror"]="pm2"
)

declare -A DAEMON_LOGS
DAEMON_LOGS=(
    ["sensor"]="${LOG_DIR}/sensor_daemon.log"
    ["db"]="${LOG_DIR}/db_daemon.log"
    ["camera"]="${LOG_DIR}/frt_camera.log"
    ["ai"]="${LOG_DIR}/frt_ai.log"
    ["recipe"]="${LOG_DIR}/recipe_extractor.log"
    ["recommend"]="${LOG_DIR}/recommend_daemon.log"
    ["magicmirror"]="${LOG_DIR}/magicmirror.log"
)

declare -A DAEMON_CHECKS
DAEMON_CHECKS=(
    ["sensor"]="check_file_exec"
    ["db"]="check_venv"
    ["camera"]="check_file_exec"
    ["ai"]="check_venv"
    ["recipe"]="check_venv"
    ["recommend"]="check_venv"
    ["magicmirror"]="check_pm2"
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
    echo "  --disable-door-sensor Run MagicMirror with door sensor disabled"
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



# ==============================================================================
# Initialization
# ==============================================================================

setup_log_directory() {
    if [[ ! -d "$LOG_DIR" ]]; then
        if [[ "$LOG_DIR" == /var/log/* ]]; then
            sudo mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="${FSS_ROOT}/tests/logs/magicmirror/mm_log_$(date +%Y%m%d_%H%M%S)"
            sudo chown -R "$USER:$USER" "$LOG_DIR" 2>/dev/null || true
        fi
        mkdir -p "$LOG_DIR" 2>/dev/null || true
    fi
    mkdir -p "$PID_DIR"
    sudo chown -R "$USER:$USER" "$PID_DIR" 2>/dev/null || true
}

check_pm2() {
    # if ! command -v pm2 &>/dev/null; then
    #     fss_log_error "PM2 not found. Install Node.js/PM2 first."
    #     return 1
    # fi
    if [[ ! -d "${FSS_ROOT}/electron_app/magicmirror/node_modules" ]]; then
        fss_log_error "MagicMirror node_modules missing. Run FSS_SETUP.sh first."
        return 1
    fi
    return 0
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

wait_for_dbus_service() {
    local service_name="$1"
    local max_wait="$2"
    max_wait="${max_wait:-10}"
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if dbus-send --system --print-reply --dest=org.freedesktop.DBus \
            /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
            string:"$service_name" 2>/dev/null | grep -q "boolean true"; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

wait_for_dbus_release() {
    local service_name="$1"
    local max_wait="${2:-5}"
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus \
            /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
            string:"$service_name" 2>/dev/null | grep -q "boolean true"; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

# Map daemon keys to their D-Bus service names for registration verification.
# NOTES:
#   - "sensor" (C++): connects to system bus but does NOT request a well-known name;
#     it emits signals from its unique bus name only → no NameHasOwner check.
#   - "camera" (C++): pure V4L2→SHM capture, no D-Bus code → skip.
#   - Others (Python): use sdbus.request_default_bus_name_async() → service IS registered.
declare -A DBUS_SERVICE_MAP
DBUS_SERVICE_MAP=(
    ["db"]="vn.edu.uit.FSS.DBDaemon"
    ["ai"]="vn.edu.uit.FSS.FRTApp"
    ["recipe"]="vn.edu.uit.FSS.RecipeExtractor"
    ["recommend"]="vn.edu.uit.FSS.RecommendDaemon"
)

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

    # Verify INT8 model file exists for AI daemon
    if [[ "$key" == "ai" ]]; then
        local int8_model="/opt/fss/models/0607_best_int8.tflite"
        if [[ ! -f "$int8_model" ]]; then
            fss_log_error "INT8 model not found at ${int8_model}. Run FSS_SETUP.sh to deploy models."
            return 1
        fi
        fss_log_info "  INT8 model: ${int8_model}"
    fi

    if [[ "$key" == "magicmirror" ]]; then
        # Fix PM2 version mismatch and clean old instances
        # pm2 update 2>/dev/null || true
        # pm2 delete MagicMirror 2>/dev/null || true
        sleep 1
        cd "${FSS_ROOT}/electron_app/magicmirror"
        local mm_env="DISPLAY=:0"
        if [[ "${DISABLE_DOOR:-0}" == "1" ]]; then
            mm_env="$mm_env FSS_DISABLE_DOOR_SENSOR=1"
        fi
        
        if [[ $EUID -eq 0 ]]; then
            local run_user="${SUDO_USER:-$(logname)}"
            local run_uid=$(id -u "$run_user")
            mm_env="HOME=/home/${run_user} XDG_RUNTIME_DIR=/run/user/${run_uid} XAUTHORITY=/home/${run_user}/.Xauthority DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${run_uid}/bus ${mm_env}"
            nohup sudo -u "$run_user" bash -c "cd ${FSS_ROOT}/electron_app/magicmirror && $mm_env npm run start:x11" >> "$log" 2>&1 &
        else
            nohup bash -c "$mm_env npm run start:x11" >> "$log" 2>&1 &
        fi
        local pid=$!
        disown $pid 2>/dev/null
        cd "${FSS_ROOT}"
        sleep 3
        if kill -0 "$pid" 2>/dev/null; then
            fss_log_ok "${name} started (PID: ${pid})"
            echo "$pid" > "$pidfile"
            DAEMON_RETRIES["$key"]=0
            return 0
        fi
        fss_log_error "${name} failed to start via npm. Check ${log}"
        return 1
    fi

    nohup $cmd >>"$log" 2>&1 &
    local pid=$!
    disown $pid 2>/dev/null

    local sleep_time=2
    [[ "$key" == "sensor" || "$key" == "camera" ]] && sleep_time=1

    sleep "$sleep_time"

    if kill -0 "$pid" 2>/dev/null; then
        fss_log_ok "${name} started (PID: $pid)"
        echo "$pid" > "$pidfile"

        # Wait for D-Bus service registration (if applicable)
        local dbus_svc="${DBUS_SERVICE_MAP[$key]:-}"
        if [[ -n "$dbus_svc" ]]; then
            fss_log_info "  Waiting for D-Bus service ${dbus_svc}..."
            if wait_for_dbus_service "$dbus_svc" 8; then
                fss_log_ok "  D-Bus service ${dbus_svc} registered"
            else
                fss_log_warn "  D-Bus service ${dbus_svc} not registered within timeout"
            fi
        fi
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
        if [[ "$key" == "magicmirror" ]]; then
            fss_log_info "Stopping ${name}..."
            # pm2 stop MagicMirror >> "${LOG_DIR}/magicmirror.log" 2>&1 || true
            # pm2 delete MagicMirror >> "${LOG_DIR}/magicmirror.log" 2>&1 || true
            if kill -0 "$pid" 2>/dev/null; then
                kill -SIGTERM "$pid" 2>/dev/null
                sleep 2
                kill -SIGKILL "$pid" 2>/dev/null || true
            fi
            fss_log_ok "${name} stopped"
        elif kill -0 "$pid" 2>/dev/null; then
            fss_log_info "Stopping ${name} (PID: ${pid})..."
            kill -SIGTERM "$pid" 2>/dev/null
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                kill -SIGKILL "$pid" 2>/dev/null || true
            fi
            fss_log_ok "${name} stopped"
        fi
        sudo rm -f "$pidfile"
    fi
}

stop_all() {
    fss_log_info "Shutting down all daemons..."
    for key in magicmirror recommend recipe ai camera db sensor; do
        stop_daemon "$key"
    done
    fss_log_ok "All daemons stopped"

    for svc in vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.RecommendDaemon \
               vn.edu.uit.FSS.FRTApp vn.edu.uit.FSS.Sensor \
               vn.edu.uit.FSS.RecipeExtractor; do
        wait_for_dbus_release "$svc" || true
    done

    sudo rm -f "$PID_DIR"/*.pid 2>/dev/null || true
    # Kill the monitor loop if it's running
    pids=$(pgrep -f "bash FSS_RUN.sh" | grep -v $$)
    if [[ -n "$pids" ]]; then
        kill $pids 2>/dev/null || true
    fi
}

cleanup_stale() {
    fss_log_info "Cleaning up stale processes..."

    for svc in fss-sensor fss-camera fss-ai fss-db fss-recommend fss-magicmirror; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            fss_log_warn "Stopping systemd service $svc..."
            sudo systemctl stop "$svc" 2>/dev/null || true
            sleep 1
        fi
    done

    # Kill PM2 MagicMirror if running
    if command -v pm2 &>/dev/null && pm2 pid MagicMirror 2>/dev/null | grep -qE '[0-9]+'; then
        fss_log_warn "Stopping PM2 MagicMirror..."
        pm2 stop MagicMirror 2>/dev/null || true
        pm2 delete MagicMirror 2>/dev/null || true
    fi

    for proc in sensor_daemon_exec camera_core_exec db_daemon recommend_daemon \
                recipe_extractor py_ai_core magicmirror; do
        pids=$(pgrep -f "$proc" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            fss_log_warn "Killing stale $proc (PIDs: $pids)"
            kill $pids 2>/dev/null || true
            sleep 1
            pids=$(pgrep -f "$proc" 2>/dev/null || true)
            [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
        fi
    done

    sudo rm -f "$PID_DIR"/*.pid 2>/dev/null || true
    fss_log_ok "Stale processes cleaned"
}

# ==============================================================================
# Monitoring
# ==============================================================================

monitor_daemons() {
    while true; do
        sleep 5
        for key in sensor db camera ai recipe recommend magicmirror; do
            local pidfile="${PID_DIR}/${key}.pid"
            local name="${DAEMON_NAMES[$key]}"
            if [[ -f "$pidfile" ]]; then
                local pid
                pid=$(cat "$pidfile" | head -1)
                
                local is_running=false
                if [[ "$key" == "magicmirror" ]]; then
                    # local current_pid=$(pm2 pid MagicMirror 2>/dev/null | grep -oE '[0-9]+' | head -1)
                    # if [[ -n "$current_pid" && "$current_pid" != "0" ]]; then
                    #     is_running=true
                    #     # Update pidfile in case PM2 restarted it
                    #     if [[ "$current_pid" != "$pid" ]]; then
                    #         echo "$current_pid" > "$pidfile"
                    #     fi
                    # fi
                    if kill -0 "$pid" 2>/dev/null; then
                        is_running=true
                    fi
                else
                    if kill -0 "$pid" 2>/dev/null; then
                        is_running=true
                    fi
                fi

                if [[ "$is_running" == false ]]; then
                    local retries=${DAEMON_RETRIES["$key"]}
                    if [[ "$retries" -ge "$MAX_RETRIES" ]]; then
                        fss_log_error "${name} has failed ${MAX_RETRIES} times. Giving up."
                        continue
                    fi
                    DAEMON_RETRIES["$key"]=$((retries + 1))
                    fss_log_warn "${name} died. Restarting (attempt $((retries + 1))/${MAX_RETRIES})..."
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
    for key in sensor db camera ai recipe recommend magicmirror; do
        local name="${DAEMON_NAMES[$key]}"
        local pidfile="${PID_DIR}/${key}.pid"
        
        local is_running=false
        local pid=""
        if [[ -f "$pidfile" ]]; then
            if [[ "$key" == "magicmirror" ]]; then
                # pid=$(pm2 pid MagicMirror 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "")
                # if [[ -n "$pid" && "$pid" != "0" ]]; then
                #     is_running=true
                # fi
                pid=$(cat "$pidfile")
                if kill -0 "$pid" 2>/dev/null; then
                    is_running=true
                fi
            else
                pid=$(cat "$pidfile")
                if kill -0 "$pid" 2>/dev/null; then
                    is_running=true
                fi
            fi
        fi

        if [[ "$is_running" == true ]]; then
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
    for svc in vn.edu.uit.FSS.FRTApp \
               vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.RecommendDaemon \
               vn.edu.uit.FSS.RecipeExtractor; do
        if dbus-send --system --print-reply --dest=org.freedesktop.DBus \
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

int_handler() {
    echo ""
    fss_log_info "Ctrl+C received — exiting monitor (daemons keep running)"
    fss_log_info "Run 'bash FSS_RUN.sh --stop' to stop all daemons"
    exit 0
}

trap shutdown_handler SIGTERM
trap int_handler SIGINT

# ==============================================================================
# Main
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --daemon)   SELECTED_DAEMONS="$2"; shift 2 ;;
        --no-monitor) MONITOR=false; shift ;;
        --status)   print_status; exit 0 ;;
        --stop)     stop_all; exit 0 ;;
        --disable-door-sensor) DISABLE_DOOR=1; shift ;;
        --help|-h)  usage ;;
        *)          echo "Unknown: $1"; usage ;;
    esac
done

setup_log_directory
cleanup_stale

# Determine which daemons to start
DISABLED_DAEMONS=("camera") # Default is disable fss-camera

if [[ -z "$SELECTED_DAEMONS" ]]; then
    DAEMON_ORDER=("sensor" "db" "camera" "ai" "recipe" "recommend" "magicmirror")
else
    IFS=',' read -ra DAEMON_ORDER <<< "$SELECTED_DAEMONS"
fi

# Start daemons
fss_log_info "Starting FSS daemons..."
for key in "${DAEMON_ORDER[@]}"; do
    if [[ " ${DISABLED_DAEMONS[@]} " =~ " ${key} " ]]; then
        fss_log_info "Skipping ${DAEMON_NAMES[$key]} as it is disabled."
        continue
    fi
    start_daemon "$key" || fss_log_warn "${DAEMON_NAMES[$key]} failed to start, continuing..."
    if [[ "$key" == "sensor" ]]; then
        sleep 2
        fss_log_info "--- Sensor Smoke Test ---"
        python3 /home/richardmelvin52/FSS/tools/smoke_test.py
        fss_log_info "-------------------------"
    fi
done

print_status

# Monitor or wait
if [[ "$MONITOR" == true ]]; then
    fss_log_info "Monitoring enabled. Press Ctrl+C to exit monitor (daemons keep running)."
    monitor_daemons
else
    fss_log_info "All daemons started (no monitoring). Press Ctrl+C to exit (daemons keep running)."
    while true; do sleep 10; done
fi
