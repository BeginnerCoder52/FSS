#!/bin/bash
# ==============================================================================
# @file startup_fss_system.sh
# @brief FSS (Fridge Supervisor System) - Integrated Startup Script
#
# Manages startup and lifecycle of all FSS daemons:
#   - SensorDaemon (C++)       - Hardware sensor interface
#   - DBDaemon (Python)        - Data persistence layer
#   - FRTApp Camera Core (C++) - V4L2 capture -> POSIX SHM
#   - FRTApp AI Core (Python)  - YOLO inference on SHM frames
#   - RecommendDaemon (Python) - Business logic orchestrator
#
# Features:
#   - Graceful shutdown with signal handlers
#   - Automatic service restart on failure
#   - Comprehensive logging
#   - Process monitoring and health checks
# ==============================================================================

set -uo pipefail

FSS_ROOT="$(dirname "$(readlink -f "$0")")"
LOG_DIR="/var/log/fss"
PID_DIR="/tmp/fss"

SENSOR_DAEMON_EXEC="${FSS_ROOT}/sensor_daemon/build/sensor_daemon_exec"
DB_DAEMON_SRC="${FSS_ROOT}/db_daemon/src"
DB_DAEMON_VENV="${FSS_ROOT}/db_daemon/venv"
FRT_CAMERA_EXEC="${FSS_ROOT}/frt_app/build/cpp_camera_core/camera_core_exec"
FRT_AI_SRC="${FSS_ROOT}/frt_app/py_ai_core/src"
FRT_AI_VENV="${FSS_ROOT}/frt_app/py_ai_core/venv"
RECOMMEND_DAEMON_SRC="${FSS_ROOT}/recommend_daemon/src"
RECOMMEND_DAEMON_VENV="${FSS_ROOT}/recommend_daemon/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} INFO: $1"; }
log_warn()  { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN: $1${NC}"; }
log_error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2; }
log_ok()    { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓ $1${NC}"; }

setup_log_directory() {
    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR" 2>/dev/null || {
            log_warn "Cannot create $LOG_DIR, using ${FSS_ROOT}/logs"
            LOG_DIR="${FSS_ROOT}/logs"
            mkdir -p "$LOG_DIR"
        }
    fi
    mkdir -p "$PID_DIR"
    log_ok "Log directory: $LOG_DIR"
}

cleanup_stale_processes() {
    log_info "Cleaning up stale daemon processes..."
    for proc in sensor_daemon_exec camera_core_exec "db_daemon" "recommend_daemon" "frt_ai"; do
        pids=$(pgrep -f "$proc" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            log_warn "Killing stale $proc (PIDs: $pids)"
            kill $pids 2>/dev/null || true
            sleep 1
            # Force kill if still alive
            pids=$(pgrep -f "$proc" 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                kill -9 $pids 2>/dev/null || true
            fi
        fi
    done
    # Remove stale PID files
    rm -f "$PID_DIR"/*.pid 2>/dev/null || true
    log_ok "Stale processes cleaned"
}

check_venv() {
    local venv="$1"
    if [[ ! -f "$venv/bin/python" ]]; then
        log_error "Virtual env not found at $venv. Run setup.sh first."
        return 1
    fi
}

start_sensor_daemon() {
    log_info "Starting SensorDaemon..."
    if [[ ! -x "$SENSOR_DAEMON_EXEC" ]]; then
        log_error "SensorDaemon not built. Run setup.sh first."
        return 1
    fi
    nohup sudo "$SENSOR_DAEMON_EXEC" >"${LOG_DIR}/sensor_daemon.log" 2>&1 &
    local pid=$!
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        log_ok "SensorDaemon started (PID: $pid)"
        echo "$pid" > "$PID_DIR/sensor_daemon.pid"
        return 0
    fi
    log_error "SensorDaemon failed. Check ${LOG_DIR}/sensor_daemon.log"
    return 1
}

start_db_daemon() {
    log_info "Starting DBDaemon..."
    check_venv "$DB_DAEMON_VENV" || return 1
    nohup sudo "${DB_DAEMON_VENV}/bin/python" "${DB_DAEMON_SRC}/main.py" \
        >"${LOG_DIR}/db_daemon.log" 2>&1 &
    local pid=$!
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        log_ok "DBDaemon started (PID: $pid)"
        echo "$pid" > "$PID_DIR/db_daemon.pid"
        return 0
    fi
    log_error "DBDaemon failed. Check ${LOG_DIR}/db_daemon.log"
    return 1
}

start_recommend_daemon() {
    log_info "Starting RecommendDaemon..."
    check_venv "$RECOMMEND_DAEMON_VENV" || return 1
    nohup sudo "${RECOMMEND_DAEMON_VENV}/bin/python" "${RECOMMEND_DAEMON_SRC}/main.py" \
        >"${LOG_DIR}/recommend_daemon.log" 2>&1 &
    local pid=$!
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        log_ok "RecommendDaemon started (PID: $pid)"
        echo "$pid" > "$PID_DIR/recommend_daemon.pid"
        return 0
    fi
    log_error "RecommendDaemon failed. Check ${LOG_DIR}/recommend_daemon.log"
    return 1
}

start_frt_camera() {
    log_info "Starting FRTApp Camera Core..."
    if [[ ! -x "$FRT_CAMERA_EXEC" ]]; then
        log_error "FRTApp Camera Core not built. Run setup.sh first."
        return 1
    fi
    nohup sudo "$FRT_CAMERA_EXEC" >"${LOG_DIR}/frt_camera.log" 2>&1 &
    local pid=$!
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        log_ok "FRTApp Camera Core started (PID: $pid)"
        echo "$pid" > "$PID_DIR/frt_camera.pid"
        return 0
    fi
    log_error "FRTApp Camera Core failed. Check ${LOG_DIR}/frt_camera.log"
    return 1
}

start_frt_ai() {
    log_info "Starting FRTApp AI Core..."
    check_venv "$FRT_AI_VENV" || return 1
    nohup sudo "${FRT_AI_VENV}/bin/python" "${FRT_AI_SRC}/main.py" \
        --use-c-backend >"${LOG_DIR}/frt_ai.log" 2>&1 &
    local pid=$!
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        log_ok "FRTApp AI Core started (PID: $pid)"
        echo "$pid" > "$PID_DIR/frt_ai.pid"
        return 0
    fi
    log_error "FRTApp AI Core failed. Check ${LOG_DIR}/frt_ai.log"
    return 1
}

stop_daemon_by_pidfile() {
    local pidfile="$1"
    local name="$2"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 $pid 2>/dev/null; then
            log_info "Stopping $name (PID: $pid)..."
            kill -SIGTERM $pid
            sleep 2
            if kill -0 $pid 2>/dev/null; then
                log_warn "$name did not stop, forcing..."
                kill -SIGKILL $pid 2>/dev/null || true
            fi
            log_ok "$name stopped"
        fi
        rm -f "$pidfile"
    fi
}

shutdown_handler() {
    log_info "Shutting down FSS system..."
    stop_daemon_by_pidfile "$PID_DIR/frt_ai.pid" "FRTApp AI Core"
    stop_daemon_by_pidfile "$PID_DIR/frt_camera.pid" "FRTApp Camera Core"
    stop_daemon_by_pidfile "$PID_DIR/recommend_daemon.pid" "RecommendDaemon"
    stop_daemon_by_pidfile "$PID_DIR/db_daemon.pid" "DBDaemon"
    stop_daemon_by_pidfile "$PID_DIR/sensor_daemon.pid" "SensorDaemon"
    log_ok "FSS system stopped"
    exit 0
}

monitor_processes() {
    while true; do
        sleep 5
        for pair in \
            "$PID_DIR/sensor_daemon.pid:SensorDaemon:start_sensor_daemon" \
            "$PID_DIR/db_daemon.pid:DBDaemon:start_db_daemon" \
            "$PID_DIR/frt_camera.pid:FRTApp Camera:start_frt_camera" \
            "$PID_DIR/frt_ai.pid:FRTApp AI:start_frt_ai" \
            "$PID_DIR/recommend_daemon.pid:RecommendDaemon:start_recommend_daemon"; do
            IFS=':' read -r pidfile name func <<< "$pair"
            if [[ -f "$pidfile" ]]; then
                pid=$(cat "$pidfile")
                if ! kill -0 $pid 2>/dev/null; then
                    log_warn "$name died. Restarting..."
                    $func || log_error "Failed to restart $name"
                fi
            fi
        done
    done
}

print_status() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  FSS System Status${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo "  Root: $FSS_ROOT"
    echo "  Logs: $LOG_DIR"
    echo ""
    for pair in \
        "$PID_DIR/sensor_daemon.pid:SensorDaemon" \
        "$PID_DIR/db_daemon.pid:DBDaemon" \
        "$PID_DIR/frt_camera.pid:FRTApp Camera Core" \
        "$PID_DIR/frt_ai.pid:FRTApp AI Core" \
        "$PID_DIR/recommend_daemon.pid:RecommendDaemon"; do
        IFS=':' read -r pidfile name <<< "$pair"
        if [[ -f "$pidfile" ]] && kill -0 $(cat "$pidfile") 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $name RUNNING (PID: $(cat "$pidfile"))"
        else
            echo -e "  ${RED}✗${NC} $name STOPPED"
        fi
    done
    echo ""
}

trap shutdown_handler SIGTERM SIGINT
setup_log_directory
cleanup_stale_processes

log_info "Starting FSS system..."
start_sensor_daemon || log_warn "SensorDaemon failed to start, continuing..."
start_db_daemon || log_warn "DBDaemon failed to start, continuing..."
start_frt_camera || log_warn "FRTApp Camera Core skipped (no camera?)"
start_frt_ai || log_warn "FRTApp AI Core skipped"
start_recommend_daemon || log_warn "RecommendDaemon failed to start, continuing..."
print_status

# Keep running and monitor
while true; do
    monitor_processes
    sleep 1
done
