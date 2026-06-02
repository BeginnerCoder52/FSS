#!/usr/bin/env bash
# ==============================================================================
# collect_debug_logs.sh - FSS Full Debug Log Collection
# ==============================================================================
# Collects all available debug logs from:
#   - MagicMirror modules (MMM-FSS-*)
#   - FRTApp (AI + Camera)
#   - RecommendSystem (NLP)
#   - RecommendDaemon (Business logic)
#   - DBDaemon (Data controller)
#   - SensorDaemon (Hardware I/O)
#
# Usage:
#   sudo bash scripts/collect_debug_logs.sh [--output-dir /tmp/fss_debug_YYYYMMDD]
#
# Output: Single tarball with all logs, system state, and D-Bus snapshot.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FSS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${1:-/tmp/fss_debug_$TIMESTAMP}"
OUTPUT_DIR="$(realpath -m "$OUTPUT_DIR")"

REPORT_FILE="$OUTPUT_DIR/fss_debug_report.txt"
TARBALL="${OUTPUT_DIR}.tar.gz"

# ==============================================================================
# Helper Functions
# ==============================================================================

section() {
    echo "" | tee -a "$REPORT_FILE"
    echo "========================================================================" | tee -a "$REPORT_FILE"
    echo "  $1" | tee -a "$REPORT_FILE"
    echo "========================================================================" | tee -a "$REPORT_FILE"
}

sub() {
    echo "" >> "$REPORT_FILE"
    echo "--- $1 ---" >> "$REPORT_FILE"
}

capture_cmd() {
    local label="$1"
    shift
    sub "$label"
    "$@" >> "$REPORT_FILE" 2>&1 || echo "[WARN] Command failed: $*" >> "$REPORT_FILE"
}

collect_file() {
    local src="$1"
    local dest="$OUTPUT_DIR/$2"
    if [ -f "$src" ]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        echo "[OK]   $src" >> "$REPORT_FILE"
    else
        echo "[MISS] $src" >> "$REPORT_FILE"
    fi
}

# ==============================================================================
# Setup
# ==============================================================================

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

exec > >(tee -a "$REPORT_FILE") 2>&1

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║            FSS DEBUG LOG COLLECTION                                 ║"
echo "║  Timestamp: $TIMESTAMP                                             ║"
echo "║  Output:    $OUTPUT_DIR                                            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"

# ==============================================================================
# 1. SYSTEM INFORMATION
# ==============================================================================

section "1. SYSTEM INFORMATION"

capture_cmd "Date/Timezone" date
capture_cmd "Uptime" uptime
capture_cmd "Kernel" uname -a
capture_cmd "OS Release" cat /etc/os-release
capture_cmd "Hostname" hostname
capture_cmd "CPU Info" cat /proc/cpuinfo
capture_cmd "Memory" free -h
capture_cmd "Disk Usage" df -h / /opt/fss
capture_cmd "Running Processes (FSS)" ps aux | grep -E "(fss|frt|sensor|daemon|python|electron)" || echo "[INFO] No FSS processes running"

# ==============================================================================
# 2. D-BUS STATUS
# ==============================================================================

section "2. D-BUS STATUS"

capture_cmd "System Bus Names" dbus-send --system --print-reply --dest=org.freedesktop.DBus \
    /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>&1 || \
    echo "[WARN] D-Bus not available on system bus"

capture_cmd "D-Bus Monitor (snapshot)" timeout 3 dbus-monitor --system \
    "interface=vn.edu.uit.FSS.Interface" 2>&1 || \
    echo "[WARN] dbus-monitor failed (expected if no FSS services running)"

sub "D-Bus Configuration Files"
ls -la /etc/dbus-1/system.d/vn.edu.uit.FSS.conf 2>&1 || echo "[MISS] D-Bus config not installed"

# ==============================================================================
# 3. HARDWARE / DEVICES
# ==============================================================================

section "3. HARDWARE & DEVICES"

sub "Video Devices (V4L2)"
ls -la /dev/video* 2>&1 || echo "[INFO] No /dev/video* devices"
if command -v v4l2-ctl &>/dev/null; then
    for dev in /dev/video*; do
        [ -e "$dev" ] && v4l2-ctl --all -d "$dev" 2>&1 || true
    done
fi

sub "I2C Devices"
ls -la /dev/i2c-* 2>&1 || echo "[INFO] No /dev/i2c-* devices"
if command -v i2cdetect &>/dev/null; then
    for bus in /dev/i2c-*; do
        bus_num="${bus##*-}"
        i2cdetect -y "$bus_num" 2>&1 || true
    done
fi

sub "GPIO / libgpiod"
if command -v gpioinfo &>/dev/null; then
    gpioinfo 2>&1 || echo "[WARN] gpioinfo failed"
fi

sub "POSIX Shared Memory"
ls -la /dev/shm/ | grep fss 2>&1 || echo "[INFO] No FSS shared memory segments"

# ==============================================================================
# 4. FSS RUNTIME DIRECTORIES
# ==============================================================================

section "4. FSS RUNTIME DIRECTORIES (/opt/fss/)"

sub "Directory Structure"
ls -laR /opt/fss/ 2>&1 || echo "[MISS] /opt/fss/ does not exist"

sub "Disk Usage"
du -sh /opt/fss/* 2>&1 || true

collect_file "/opt/fss/logs/" "fss_logs/" 2>/dev/null || true

# ==============================================================================
# 5. MAGICMIRROR MODULES
# ==============================================================================

section "5. MAGICMIRROR MODULES"

MM_DIR="$FSS_ROOT/electron_app/magicmirror/modules"
if [ -d "$MM_DIR" ]; then
    for mod in "$MM_DIR"/MMM-FSS-*; do
        [ -d "$mod" ] || continue
        mod_name="$(basename "$mod")"
        sub "Module: $mod_name"

        # Module JS
        js_file="$mod/$mod_name.js"
        [ -f "$js_file" ] && echo "[OK]   $mod_name.js" || echo "[MISS] $mod_name.js"

        # CSS
        css_file="$mod/$mod_name.css"
        [ -f "$css_file" ] && echo "[OK]   $mod_name.css" || echo "[MISS] $mod_name.css"

        # node_helper
        helper="$mod/node_helper.js"
        [ -f "$helper" ] && echo "[OK]   node_helper.js" || echo "[MISS] node_helper.js"

        # py_bridge
        if [ -d "$mod/py_bridge" ]; then
            echo "[OK]   py_bridge/ present"
            bridge_files=("$mod/py_bridge"/*.py)
            for bf in "${bridge_files[@]}"; do
                [ -f "$bf" ] && echo "         - $(basename "$bf")"
            done
            # Copy bridge python files and requirements
            mkdir -p "$OUTPUT_DIR/modules/$mod_name/py_bridge"
            cp "$mod/py_bridge"/*.py "$OUTPUT_DIR/modules/$mod_name/py_bridge/" 2>/dev/null || true
            [ -f "$mod/py_bridge/requirements.txt" ] && \
                cp "$mod/py_bridge/requirements.txt" "$OUTPUT_DIR/modules/$mod_name/py_bridge/"
            # Check venv
            if [ -d "$mod/py_bridge/venv" ]; then
                echo "[OK]   py_bridge/venv/ exists" >> "$REPORT_FILE"
            else
                echo "[MISS] py_bridge/venv/ (run setup_venv)" >> "$REPORT_FILE"
            fi
        else
            echo "[MISS] py_bridge/"
        fi
    done
else
    echo "[MISS] MagicMirror modules directory not found at $MM_DIR"
fi

# ==============================================================================
# 6. FRTApp (Food Recognition)
# ==============================================================================

section "6. FRTApp (Food Recognition & Tracking)"

FRT_DIR="$FSS_ROOT/frt_app"
sub "FRTApp Directory"
ls -la "$FRT_DIR/" 2>&1 || echo "[MISS] frt_app directory"

sub "Python AI Core Files"
ls -la "$FRT_DIR/py_ai_core/src/" 2>&1 || echo "[MISS] py_ai_core/src/"

sub "C++ Build Status"
if [ -f "$FRT_DIR/build/cpp_camera_core/camera_core_exec" ]; then
    echo "[OK]   camera_core_exec built"
    file "$FRT_DIR/build/cpp_camera_core/camera_core_exec" >> "$REPORT_FILE"
else
    echo "[MISS] camera_core_exec not built (run: cd frt_app && mkdir build && cd build && cmake .. && make)"
fi

sub "C TFLite Reader"
if [ -f "$FRT_DIR/build/c_tflite_reader/libtflite_reader.so" ]; then
    echo "[OK]   libtflite_reader.so built"
else
    echo "[MISS] libtflite_reader.so not built"
fi
ldconfig -p | grep tflite 2>&1 || echo "[INFO] libtflite_reader.so not in ldconfig"

sub "Model Files"
ls -la "$FRT_DIR/py_ai_core/models/" 2>&1 || ls -la /opt/fss/models/ 2>&1 || echo "[MISS] No model files found"

sub "FRTApp Log"
collect_file "/var/log/frt_app.log" "logs/frt_app.log"

sub "Python venv"
if [ -d "$FRT_DIR/py_ai_core/venv" ]; then
    echo "[OK]   py_ai_core/venv/ exists"
    "$FRT_DIR/py_ai_core/venv/bin/pip" freeze > "$OUTPUT_DIR/frt_venv_packages.txt" 2>&1 || true
else
    echo "[MISS] py_ai_core/venv/ (run setup_venv)"
fi

# ==============================================================================
# 7. Recommend System (NLP)
# ==============================================================================

section "7. Recommend System (NLP / Recipe Analyzer)"

RS_DIR="$FSS_ROOT/recommend_system"
sub "Directory Structure"
ls -la "$RS_DIR/src/" 2>&1 || echo "[MISS] recommend_system/src/"

sub "Trained Model"
collect_file "$RS_DIR/models/fss_ner_crf_optimized.joblib" "models/fss_ner_crf_optimized.joblib"

sub "Test Status"
if [ -d "$RS_DIR/tests" ]; then
    echo "[OK]   tests/ directory present"
    ls "$RS_DIR/tests/" >> "$REPORT_FILE"
else
    echo "[MISS] tests/ directory"
fi

sub "D-Bus Service"
collect_file "$RS_DIR/src/dbus_service.py" "recommend_system/dbus_service.py"

sub "Python venv"
if [ -d "$RS_DIR/venv" ]; then
    echo "[OK]   venv/ exists"
    "$RS_DIR/venv/bin/pip" freeze > "$OUTPUT_DIR/recommend_system_venv_packages.txt" 2>&1 || true
else
    echo "[MISS] venv/ (run setup_venv)"
fi

# ==============================================================================
# 8. RecommendDaemon (Business Logic)
# ==============================================================================

section "8. RecommendDaemon (Business Logic Orchestrator)"

RD_DIR="$FSS_ROOT/recommend_daemon"
sub "Directory Structure"
ls -la "$RD_DIR/src/" 2>&1 || echo "[MISS] recommend_daemon/src/"

sub "Database Files"
ls -la /opt/fss/data/FSS-Recommend.db 2>&1 || echo "[MISS] FSS-Recommend.db (no recommendations yet)"
ls -la /opt/fss/data/FSS_Request.db 2>&1 || echo "[MISS] FSS_Request.db"

collect_file "/opt/fss/data/FSS-Recommend.db" "data/FSS-Recommend.db"
collect_file "/opt/fss/data/FSS_Request.db" "data/FSS_Request.db"

sub "Test Files"
if [ -d "$RD_DIR/tests" ]; then
    echo "[OK]   tests/ directory"
    ls "$RD_DIR/tests/" >> "$REPORT_FILE"
else
    echo "[MISS] tests/"
fi

sub "Python venv"
if [ -d "$RD_DIR/venv" ]; then
    echo "[OK]   venv/ exists"
    "$RD_DIR/venv/bin/pip" freeze > "$OUTPUT_DIR/recommend_daemon_venv_packages.txt" 2>&1 || true
else
    echo "[MISS] venv/ (run setup_venv)"
fi

# ==============================================================================
# 9. DBDaemon (Data Controller)
# ==============================================================================

section "9. DBDaemon (Data Controller)"

DB_DIR="$FSS_ROOT/db_daemon"
sub "Directory Structure"
ls -la "$DB_DIR/src/" 2>&1 || echo "[MISS] db_daemon/src/"

sub "Databases"
for db in fss_data.db FSS_Inventory.db FSS_Request.db; do
    collect_file "/opt/fss/data/$db" "data/$db"
done

sub "Python venv"
if [ -d "$DB_DIR/venv" ]; then
    echo "[OK]   venv/ exists"
    "$DB_DIR/venv/bin/pip" freeze > "$OUTPUT_DIR/db_daemon_venv_packages.txt" 2>&1 || true
else
    echo "[MISS] venv/ (run setup_venv)"
fi

# ==============================================================================
# 10. SENSOR DAEMON (C++)
# ==============================================================================

section "10. SensorDaemon (Hardware I/O)"

SD_DIR="$FSS_ROOT/sensor_daemon"
sub "Build Status"
if [ -f "$SD_DIR/build/sensor_daemon_exec" ]; then
    echo "[OK]   sensor_daemon_exec built"
    file "$SD_DIR/build/sensor_daemon_exec" >> "$REPORT_FILE"
else
    echo "[MISS] sensor_daemon_exec not built"
fi

# ==============================================================================
# 11. SYSTEMD SERVICES
# ==============================================================================

section "11. SYSTEMD SERVICES"

for svc in fss-sensor fss-camera fss-ai fss-db fss-recommend fss-magicmirror; do
    sub "Service: $svc"
    systemctl status "$svc" 2>&1 || echo "[INFO] $svc not installed"
    journalctl -u "$svc" -n 30 --no-pager 2>&1 || true
done

# ==============================================================================
# 12. NODE.JS / ELECTRON
# ==============================================================================

section "12. NODE.JS / ELECTRON"

capture_cmd "Node Version" node --version
capture_cmd "NPM Version" npm --version
capture_cmd "PM2 Status" pm2 list 2>&1 || echo "[INFO] PM2 not available"

sub "MagicMirror Package Status"
MM_ELECTRON_DIR="$FSS_ROOT/electron_app/magicmirror"
if [ -d "$MM_ELECTRON_DIR" ]; then
    if [ -d "$MM_ELECTRON_DIR/node_modules" ]; then
        echo "[OK]   node_modules/ installed"
        ls "$MM_ELECTRON_DIR/node_modules" | head -20 >> "$REPORT_FILE"
    else
        echo "[MISS] node_modules/ (run: cd electron_app/magicmirror && npm install)"
    fi
fi

# ==============================================================================
# 13. NETWORK & CONNECTIVITY
# ==============================================================================

section "13. NETWORK & CONNECTIVITY"

capture_cmd "Network Interfaces" ip addr show 2>&1
capture_cmd "Listening Ports" ss -tlnp 2>&1

# ==============================================================================
# 14. RECENT LOGS COLLECTION
# ==============================================================================

section "14. ADDITIONAL LOG FILES"

sub "System Logs"
collect_file "/var/log/syslog" "logs/syslog" 2>/dev/null || true
collect_file "/var/log/messages" "logs/messages" 2>/dev/null || true
collect_file "/var/log/daemon.log" "logs/daemon.log" 2>/dev/null || true

journalctl --since "1 hour ago" -n 200 --no-pager > "$OUTPUT_DIR/logs/journalctl_recent.log" 2>&1 || true

# ==============================================================================
# 15. PACKAGE CONFIGURATION FILES
# ==============================================================================

section "15. CONFIGURATION FILES"

collect_file "$FSS_ROOT/electron_app/magicmirror/config/config.js" "config/config.js"
collect_file "$FSS_ROOT/dbus_config/vn.edu.uit.FSS.conf" "config/dbus.conf"
collect_file "$FSS_ROOT/tools/verify_dbus_config.sh" "config/verify_dbus_config.sh"
collect_file "$FSS_ROOT/setup.sh" "config/setup.sh"
collect_file "$FSS_ROOT/fss_env_setup.sh" "config/fss_env_setup.sh"
collect_file "$FSS_ROOT/startup_fss_system.sh" "config/startup_fss_system.sh"

# ==============================================================================
# 16. FRTApp Test Log
# ==============================================================================

section "16. FRTAPP USER SCENARIO TEST"

if [ -f "$FSS_ROOT/frt_app/py_ai_core/src/test_user_scenario_frtapp.py" ]; then
    echo "[OK]   test_user_scenario_frtapp.py exists"
    cp "$FSS_ROOT/frt_app/py_ai_core/src/test_user_scenario_frtapp.py" \
       "$OUTPUT_DIR/test_user_scenario_frtapp.py"
    echo "[OK]   Copied to debug output"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================

section "SUMMARY"
echo "  Output directory: $OUTPUT_DIR"
echo "  Report file:      $REPORT_FILE"
echo ""
echo "  Collected artifacts:"
find "$OUTPUT_DIR" -type f | sort | while read -r f; do
    size=$(stat --format=%s "$f" 2>/dev/null)
    echo "    $(echo "$f" | sed "s|$OUTPUT_DIR/||" )  (${size} bytes)"
done

echo ""
echo "  To view the report:"
echo "    less $REPORT_FILE"
echo ""
echo "  To archive for sharing:"
echo "    tar czf $TARBALL -C $(dirname "$OUTPUT_DIR") $(basename "$OUTPUT_DIR")"
echo ""

# Create tarball automatically
tar czf "$TARBALL" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")" 2>/dev/null
echo "  ✓ Tarball created: $TARBALL"

exit 0
