#!/bin/bash
# ==============================================================================
# @file verify_dbus_config.sh
# @brief Validate D-Bus system configuration for all FSS components.
#
# Checks:
#   1. Whether /etc/dbus-1/system.d/vn.edu.uit.FSS.conf exists
#   2. Whether it contains all required service policies (own, send, receive)
#   3. Generates the complete config file if missing
#
# D-Bus services covered:
#   - vn.edu.uit.FSS.Sensor  (C++: hardware I/O)
#   - vn.edu.uit.FSS.FRTApp        (C++/Python: food recognition)
#   - vn.edu.uit.FSS.DBDaemon      (Python: data controller)
#   - vn.edu.uit.FSS.RecommendDaemon (Python: business logic)
#
# Usage:
#   bash tools/verify_dbus_config.sh          # Check only
#   bash tools/verify_dbus_config.sh --fix    # Generate config if missing
#   bash tools/verify_dbus_config.sh --force  # Overwrite existing config
# ==============================================================================

set -euo pipefail

CONFIG_PATH="/etc/dbus-1/system.d/vn.edu.uit.FSS.conf"
BACKUP_SUFFIX=".backup.$(date +%Y%m%d_%H%M%S)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS + 1)); echo -e "  ${GREEN}✓${NC} $1"; }
fail() { FAIL=$((FAIL + 1)); echo -e "  ${RED}✗${NC} $1"; }
warn() { WARN=$((WARN + 1)); echo -e "  ${YELLOW}⚠${NC} $1"; }

# ==============================================================================
# REQUIRED D-BUS SERVICE POLICIES
# ==============================================================================

# All services that must have <allow own="..."/> policy
REQUIRED_OWN_SERVICES=(
    "vn.edu.uit.FSS.Sensor"
    "vn.edu.uit.FSS.FRTApp"
    "vn.edu.uit.FSS.DBDaemon"
    "vn.edu.uit.FSS.RecommendDaemon"
)

# All send_destination policies (who sends to whom)
# Format: "sender_interface destination_service"
REQUIRED_SEND_DESTINATIONS=(
    "vn.edu.uit.FSS.Sensor org.freedesktop.DBus"
    "vn.edu.uit.FSS.FRTApp org.freedesktop.DBus"
    "vn.edu.uit.FSS.DBDaemon org.freedesktop.DBus"
    "vn.edu.uit.FSS.RecommendDaemon org.freedesktop.DBus"
    "vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.RecommendDaemon"
)

# All receive_sender policies (who receives from whom)
REQUIRED_RECEIVE_SENDERS=(
    "vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.Sensor"
    "vn.edu.uit.FSS.DBDaemon vn.edu.uit.FSS.FRTApp"
    "vn.edu.uit.FSS.RecommendDaemon vn.edu.uit.FSS.DBDaemon"
)

# ==============================================================================
# CHECK: File existence
# ==============================================================================
echo ""
echo "============================================"
echo " FSS D-Bus Configuration Validation"
echo "============================================"
echo ""

echo "--- [1] File Existence ---"
if [[ -f "$CONFIG_PATH" ]]; then
    pass "Config file exists at $CONFIG_PATH"
    CONFIG_EXISTS=true
else
    fail "Config file MISSING at $CONFIG_PATH"
    CONFIG_EXISTS=false
fi

# ==============================================================================
# GET CONTENT FOR PARSING
# ==============================================================================
CONFIG_CONTENT=""
if [[ -f "$CONFIG_PATH" ]]; then
    CONFIG_CONTENT=$(cat "$CONFIG_PATH")
fi

check_allow_own() {
    local service="$1"
    if echo "$CONFIG_CONTENT" | grep -qP "<allow\s+own\s*=\s*\"$service\"\s*/>"; then
        pass "Policy 'own=\"$service\"' found"
    else
        fail "Policy 'own=\"$service\"' MISSING"
    fi
}

check_send_destination() {
    local interface="$1"
    local destination="$2"
    if echo "$CONFIG_CONTENT" | grep -qP "<allow\s+send_destination\s*=\s*\"$destination\"\s*/>"; then
        pass "Policy 'send_destination=\"$destination\"' found (context: $interface)"
    else
        warn "Policy 'send_destination=\"$destination\"' missing (context: $interface)"
    fi
}

check_receive_sender() {
    local interface="$1"
    local sender="$2"
    if echo "$CONFIG_CONTENT" | grep -qP "<allow\s+receive_sender\s*=\s*\"$sender\"\s*/>"; then
        pass "Policy 'receive_sender=\"$sender\"' found (context: $interface)"
    else
        warn "Policy 'receive_sender=\"$sender\"' missing (context: $interface)"
    fi
}

# ==============================================================================
# CHECK: Required policies
# ==============================================================================
if [[ "$CONFIG_EXISTS" == true ]]; then
    echo ""
    echo "--- [2] Service Ownership Policies ---"
    for svc in "${REQUIRED_OWN_SERVICES[@]}"; do
        check_allow_own "$svc"
    done

    echo ""
    echo "--- [3] Send Destination Policies ---"
    for entry in "${REQUIRED_SEND_DESTINATIONS[@]}"; do
        IFS=' ' read -r iface dest <<< "$entry"
        check_send_destination "$iface" "$dest"
    done

    echo ""
    echo "--- [4] Receive Sender Policies ---"
    for entry in "${REQUIRED_RECEIVE_SENDERS[@]}"; do
        IFS=' ' read -r iface sender <<< "$entry"
        check_receive_sender "$iface" "$sender"
    done

    echo ""
    echo "--- [5] XML Structure ---"
    if echo "$CONFIG_CONTENT" | grep -qP '<!DOCTYPE busconfig'; then
        pass "DOCTYPE busconfig declaration found"
    else
        fail "DOCTYPE busconfig declaration MISSING"
    fi

    if echo "$CONFIG_CONTENT" | grep -qP '<policy\s+context="default">'; then
        pass "Default policy context found"
    else
        fail "Default policy context MISSING"
    fi

    if echo "$CONFIG_CONTENT" | grep -qP '<policy\s+user="root">'; then
        pass "Root user policy found"
    else
        fail "Root user policy MISSING"
    fi
fi

# ==============================================================================
# CHECK: Runtime D-Bus service status
# ==============================================================================
echo ""
echo "--- [6] Runtime D-Bus Service Registration ---"
for svc in "${REQUIRED_OWN_SERVICES[@]}"; do
    if dbus-send --system --dest=org.freedesktop.DBus \
        /org/freedesktop/DBus org.freedesktop.DBus.ListNames \
        2>/dev/null | grep -qF "$svc"; then
        pass "Service '$svc' registered on system bus"
    else
        warn "Service '$svc' NOT registered (daemon may not be running)"
    fi
done

# ==============================================================================
# CHECK: Python sdbus availability (for each component venv)
# ==============================================================================
echo ""
echo "--- [7] Python sdbus Dependency Check ---"
COMPONENT_VENVS=(
    "/home/richardmelvin52/FSS/db_daemon/venv"
    "/home/richardmelvin52/FSS/recommend_daemon/venv"
    "/home/richardmelvin52/FSS/frt_app/py_ai_core/venv"
)
for venv in "${COMPONENT_VENVS[@]}"; do
    if [[ -f "$venv/bin/python" ]]; then
        if "$venv/bin/python" -c "import sdbus" 2>/dev/null; then
            pass "sdbus available in $venv"
        else
            warn "sdbus NOT installed in $venv (run: pip install sdbus)"
        fi
    else
        warn "Venv not found: $venv (may not be created yet)"
    fi
done

# ==============================================================================
# GENERATE OR FIX CONFIG
# ==============================================================================
if [[ "$CONFIG_EXISTS" == false || "$*" == *"--force"* ]]; then
    if [[ "$*" == *"--fix"* || "$*" == *"--force"* ]]; then
        echo ""
        echo "--- [GENERATE] Creating D-Bus configuration ---"

        if [[ "$CONFIG_EXISTS" == true && "$*" == *"--force"* ]]; then
            sudo cp "$CONFIG_PATH" "${CONFIG_PATH}${BACKUP_SUFFIX}"
            echo "  Backed up existing config to ${CONFIG_PATH}${BACKUP_SUFFIX}"
        fi

        sudo tee "$CONFIG_PATH" > /dev/null << 'CONFIGEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE busconfig PUBLIC
 "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>

  <!-- ============================================================
       FSS (Fridge Supervisor System) D-Bus Security Policy
       
       Covers all daemons:
         - vn.edu.uit.FSS.Sensor   (C++: hardware I/O)
         - vn.edu.uit.FSS.FRTApp         (C++/Python: food recognition)
         - vn.edu.uit.FSS.DBDaemon       (Python: data controller)
         - vn.edu.uit.FSS.RecommendDaemon (Python: business logic)
       ============================================================ -->

  <!-- Default policy: deny all (whitelist approach) -->
  <policy context="default">
    <deny own="*"/>
    <deny send_destination="*"/>
    <deny receive_sender="*"/>
  </policy>

  <!-- Root can do everything (for debugging with sudo) -->
  <policy user="root">
    <allow own="*"/>
    <allow send_destination="*"/>
    <allow receive_sender="*"/>
  </policy>

  <!-- ============================================================
       FSS Daemon User Policy
       ============================================================ -->
  <policy user="fss">
    <!-- Allow owning service names -->
    <allow own="vn.edu.uit.FSS.Sensor"/>
    <allow own="vn.edu.uit.FSS.FRTApp"/>
    <allow own="vn.edu.uit.FSS.DBDaemon"/>
    <allow own="vn.edu.uit.FSS.RecommendDaemon"/>

    <!-- Allow talking to D-Bus daemon (required for all) -->
    <allow send_destination="org.freedesktop.DBus"/>

    <!-- Sensor → DBDaemon (environment data, door events) -->
    <allow send_destination="vn.edu.uit.FSS.DBDaemon"/>

    <!-- FRTApp → DBDaemon (food detection results) -->
    <allow send_destination="vn.edu.uit.FSS.DBDaemon"/>

    <!-- DBDaemon → RecommendDaemon (inventory data for Bù Trừ) -->
    <allow send_destination="vn.edu.uit.FSS.RecommendDaemon"/>

    <!-- DBDaemon ← Sensor (receive sensor events) -->
    <allow receive_sender="vn.edu.uit.FSS.Sensor"/>

    <!-- DBDaemon ← FRTApp (receive food detection events) -->
    <allow receive_sender="vn.edu.uit.FSS.FRTApp"/>

    <!-- RecommendDaemon ← DBDaemon (receive inventory for comparison) -->
    <allow receive_sender="vn.edu.uit.FSS.DBDaemon"/>

    <!-- UI listeners (MagicMirror Python bridges) can receive from all daemons -->
    <allow receive_sender="vn.edu.uit.FSS.Sensor"/>
    <allow receive_sender="vn.edu.uit.FSS.FRTApp"/>
    <allow receive_sender="vn.edu.uit.FSS.DBDaemon"/>
    <allow receive_sender="vn.edu.uit.FSS.RecommendDaemon"/>
  </policy>

  <!-- Allow the building user (pi/richardmelvin52) for development -->
  <policy user="richardmelvin52">
    <allow own="vn.edu.uit.FSS.Sensor"/>
    <allow own="vn.edu.uit.FSS.FRTApp"/>
    <allow own="vn.edu.uit.FSS.DBDaemon"/>
    <allow own="vn.edu.uit.FSS.RecommendDaemon"/>
    <allow send_destination="*"/>
    <allow receive_sender="*"/>
  </policy>

</busconfig>
CONFIGEOF

        if [[ $? -eq 0 ]]; then
            echo -e "  ${GREEN}✓${NC} Config generated at $CONFIG_PATH"

            # Validate XML syntax
            if command -v xmllint &>/dev/null; then
                if xmllint --noout "$CONFIG_PATH" 2>/dev/null; then
                    echo -e "  ${GREEN}✓${NC} XML syntax valid"
                else
                    echo -e "  ${RED}✗${NC} XML syntax INVALID"
                fi
            fi

            # Set permissions
            sudo chmod 644 "$CONFIG_PATH"
            echo -e "  ${GREEN}✓${NC} Permissions set to 644"
        else
            echo -e "  ${RED}✗${NC} Failed to generate config"
        fi
    fi
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo "============================================"
echo -e " RESULTS: ${GREEN}$PASS passed${NC}, ${YELLOW}$WARN warnings${NC}, ${RED}$FAIL failed${NC}"
echo "============================================"
echo ""

if [[ "$CONFIG_EXISTS" == false && "$*" != *"--fix"* ]]; then
    echo -e "${YELLOW}NOTICE:${NC} D-Bus config file is missing!"
    echo "  Run with --fix to generate it:"
    echo "    sudo bash tools/verify_dbus_config.sh --fix"
    echo ""
fi

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
