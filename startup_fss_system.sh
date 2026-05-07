#!/bin/bash

################################################################################
# @file startup_fss_system.sh
# @brief FSS (Fridge Supervisor System) - Integrated Startup Script
#
# This script manages the startup and lifecycle of the complete FSS system:
# - SensorDaemon (C/C++) - Hardware sensor interface and IPC layer
# - DBDaemon (Python) - Data persistence and event processing layer
#
# Features:
# - Graceful shutdown with signal handlers
# - Automatic service restart on failure
# - Comprehensive logging
# - Process monitoring and health checks
# - Clean resource cleanup on exit
################################################################################

set -e

# ============================================================================

# CONFIGURATION
# ============================================================================
FSS_ROOT="/home/richardmelvin52/FSS"
VENV_PATH="${FSS_ROOT}/.venv"
LOG_DIR="/var/log/fss"
PID_FILE="/tmp/fss_system.pid"

# Component paths
SENSOR_DAEMON_BUILD="${FSS_ROOT}/sensor_daemon/build"
SENSOR_DAEMON_EXEC="${SENSOR_DAEMON_BUILD}/sensor_daemon_exec"
DB_DAEMON_SRC="${FSS_ROOT}/db_daemon/src"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# FUNCTIONS
# ============================================================================

#
# Print colored message to stdout
#
log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} INFO: $1"
}

#
# Print warning message to stdout
#
log_warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN: $1${NC}"
}

#
# Print error message to stderr
#
log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

#
# Print success message
#
log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓ $1${NC}"
}

#
# Check if executable exists and is readable
#
check_executable() {
    if [[ ! -f "$1" ]]; then
        log_error "Executable not found: $1"
        return 1
    fi
    if [[ ! -x "$1" ]]; then
        log_error "Executable not executable: $1"
        return 1
    fi
    return 0
}

#
# Check if virtual environment exists and activate
#
activate_venv() {
    if [[ ! -d "${VENV_PATH}" ]]; then
        log_error "Virtual environment not found at ${VENV_PATH}"
        return 1
    fi
    source "${VENV_PATH}/bin/activate"
    log_success "Virtual environment activated"
    return 0
}

#
# Create log directory with proper permissions
#
setup_log_directory() {
    if [[ ! -d "${LOG_DIR}" ]]; then
        mkdir -p "${LOG_DIR}" || {
            log_error "Failed to create log directory: ${LOG_DIR}"
            return 1
        }
    fi
    
    # Check write permissions
    if [[ ! -w "${LOG_DIR}" ]]; then
        log_warn "Log directory not writable, attempting to fix permissions..."
        sudo chmod 755 "${LOG_DIR}" 2>/dev/null || {
            log_warn "Could not fix log directory permissions. Using fallback."
            return 0
        }
    fi
    
    log_success "Log directory ready: ${LOG_DIR}"
    return 0
}

#
# Start SensorDaemon
#
start_sensor_daemon() {
    log_info "Starting SensorDaemon..."
    
    if ! check_executable "${SENSOR_DAEMON_EXEC}"; then
        log_error "SensorDaemon executable check failed"
        return 1
    fi
    
    # Run with elevated privileges if needed for GPIO/I2C access
    if [[ $EUID -ne 0 ]]; then
        log_warn "Not running as root. SensorDaemon may fail if GPIO access required."
        log_info "To run with full permissions: sudo $0"
    fi
    
    # Start daemon in background with sudo for system bus and hardware access
    nohup sudo "${SENSOR_DAEMON_EXEC}" >"${LOG_DIR}/sensor_daemon.log" 2>&1 &
    SENSOR_PID=$!
    
    sleep 1
    
    # Check if process is still running
    if ! kill -0 $SENSOR_PID 2>/dev/null; then
        log_error "SensorDaemon failed to start. Check logs: ${LOG_DIR}/sensor_daemon.log"
        return 1
    fi
    
    log_success "SensorDaemon started (PID: $SENSOR_PID)"
    rm -f "/tmp/sensor_daemon.pid"
    echo "$SENSOR_PID" > "/tmp/sensor_daemon.pid"
    return 0
}

#
# Start DBDaemon
#
start_db_daemon() {
    log_info "Starting DBDaemon..."
    
    # Activate virtual environment (still useful for pip check)
    if ! activate_venv; then
        log_error "Failed to activate virtual environment"
        return 1
    fi
    
    # Verify Python dependencies
    if ! "${VENV_PATH}/bin/python3" -c "import sdbus" 2>/dev/null; then
        log_warn "sdbus-python not installed in venv. Installing dependencies..."
        "${VENV_PATH}/bin/pip" install -r "${FSS_ROOT}/db_daemon/requirements.txt" || {
            log_error "Failed to install dependencies"
            return 1
        }
    fi
    
    # Check for D-Bus configuration
    if [[ ! -f "/etc/dbus-1/system.d/vn.edu.uit.FSS.conf" ]]; then
        log_warn "D-Bus configuration file missing at /etc/dbus-1/system.d/vn.edu.uit.FSS.conf"
        log_info "Please ensure the D-Bus configuration is installed for system bus access."
    fi
    
    # Start daemon in background with sudo and full path to venv python
    # We use sudo to allow owning the bus name on the system bus
    nohup sudo "${VENV_PATH}/bin/python3" "${DB_DAEMON_SRC}/main.py" >"${LOG_DIR}/db_daemon.log" 2>&1 &
    DB_PID=$!
    
    sleep 2
    
    # Check if process is still running
    if ! kill -0 $DB_PID 2>/dev/null; then
        log_error "DBDaemon failed to start. Check logs: ${LOG_DIR}/db_daemon.log"
        return 1
    fi
    
    log_success "DBDaemon started (PID: $DB_PID)"
    rm -f "/tmp/db_daemon.pid"
    echo "$DB_PID" > "/tmp/db_daemon.pid"
    return 0
}

#
# Monitor running processes and restart if they die
#
monitor_processes() {
    log_info "Starting process monitor..."
    
    SENSOR_PID=$(cat "/tmp/sensor_daemon.pid" 2>/dev/null || echo "")
    DB_PID=$(cat "/tmp/db_daemon.pid" 2>/dev/null || echo "")
    
    while true; do
        sleep 5
        
        # Check SensorDaemon
        if [[ ! -z "$SENSOR_PID" ]] && ! kill -0 $SENSOR_PID 2>/dev/null; then
            log_warn "SensorDaemon died (PID $SENSOR_PID). Restarting..."
            if ! start_sensor_daemon; then
                log_error "Failed to restart SensorDaemon"
            fi
            SENSOR_PID=$(cat "/tmp/sensor_daemon.pid" 2>/dev/null || echo "")
        fi
        
        # Check DBDaemon
        if [[ ! -z "$DB_PID" ]] && ! kill -0 $DB_PID 2>/dev/null; then
            log_warn "DBDaemon died (PID $DB_PID). Restarting..."
            if ! start_db_daemon; then
                log_error "Failed to restart DBDaemon"
            fi
            DB_PID=$(cat "/tmp/db_daemon.pid" 2>/dev/null || echo "")
        fi
    done
}

#
# Graceful shutdown handler
#
shutdown_handler() {
    log_info "Received shutdown signal. Gracefully stopping FSS system..."
    
    # Kill DBDaemon first (it depends on SensorDaemon)
    if [[ -f "/tmp/db_daemon.pid" ]]; then
        DB_PID=$(cat "/tmp/db_daemon.pid")
        if kill -0 $DB_PID 2>/dev/null; then
            log_info "Stopping DBDaemon (PID: $DB_PID)..."
            kill -SIGTERM $DB_PID
            sleep 2
            if kill -0 $DB_PID 2>/dev/null; then
                log_warn "DBDaemon did not stop gracefully, forcing..."
                kill -SIGKILL $DB_PID
            fi
            log_success "DBDaemon stopped"
        fi
        rm -f "/tmp/db_daemon.pid"
    fi
    
    # Kill SensorDaemon
    if [[ -f "/tmp/sensor_daemon.pid" ]]; then
        SENSOR_PID=$(cat "/tmp/sensor_daemon.pid")
        if kill -0 $SENSOR_PID 2>/dev/null; then
            log_info "Stopping SensorDaemon (PID: $SENSOR_PID)..."
            kill -SIGTERM $SENSOR_PID
            sleep 2
            if kill -0 $SENSOR_PID 2>/dev/null; then
                log_warn "SensorDaemon did not stop gracefully, forcing..."
                kill -SIGKILL $SENSOR_PID
            fi
            log_success "SensorDaemon stopped"
        fi
        rm -f "/tmp/sensor_daemon.pid"
    fi
    
    log_success "FSS System stopped"
    exit 0
}

#
# Print startup banner
#
print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Fridge Supervisor System (FSS) - Startup Manager        ║${NC}"
    echo -e "${BLUE}║   Integrated Multi-Daemon Startup & Monitoring            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

#
# Print status information
#
print_status() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   FSS System Status                                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    
    echo -e "  Root Directory: ${FSS_ROOT}"
    echo -e "  Log Directory:  ${LOG_DIR}"
    echo -e "  Python Env:     ${VENV_PATH}"
    echo ""
    
    if [[ -f "/tmp/sensor_daemon.pid" ]]; then
        SENSOR_PID=$(cat "/tmp/sensor_daemon.pid")
        if kill -0 $SENSOR_PID 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} SensorDaemon  RUNNING (PID: $SENSOR_PID)"
        else
            echo -e "  ${RED}✗${NC} SensorDaemon  STOPPED"
        fi
    else
        echo -e "  ${RED}✗${NC} SensorDaemon  NOT STARTED"
    fi
    
    if [[ -f "/tmp/db_daemon.pid" ]]; then
        DB_PID=$(cat "/tmp/db_daemon.pid")
        if kill -0 $DB_PID 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} DBDaemon      RUNNING (PID: $DB_PID)"
        else
            echo -e "  ${RED}✗${NC} DBDaemon      STOPPED"
        fi
    else
        echo -e "  ${RED}✗${NC} DBDaemon      NOT STARTED"
    fi
    
    echo ""
    echo "  Log Files:"
    echo "    - Sensor:  ${LOG_DIR}/sensor_daemon.log"
    echo "    - DB:      ${LOG_DIR}/db_daemon.log"
    echo ""
    echo "  To stop: Press Ctrl+C"
    echo ""
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

print_banner

# Validate environment
log_info "Validating FSS environment..."
if [[ ! -d "${FSS_ROOT}" ]]; then
    log_error "FSS root directory not found: ${FSS_ROOT}"
    exit 1
fi

# Setup logging
if ! setup_log_directory; then
    log_warn "Log directory setup failed, continuing with fallback"
fi

# Setup signal handlers
trap shutdown_handler SIGTERM SIGINT EXIT

# Start both daemons
if ! start_sensor_daemon; then
    log_error "Failed to start SensorDaemon"
    exit 1
fi

if ! start_db_daemon; then
    log_error "Failed to start DBDaemon"
    exit 1
fi

# Print startup success message
print_status

# Start monitoring loop
monitor_processes
