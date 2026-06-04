#!/bin/bash
# ==============================================================================
# @file verify_dbus_fix.sh
# @brief Verify D-Bus listener implementations for all FSS components.
#
# Checks Python syntax, signal subscription patterns, error handling,
# reconnection logic, and JSON output format for all UI bridge listeners.
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo -e "${GREEN}  ✓${NC} $1"; }
fail() { FAIL=$((FAIL + 1)); echo -e "${RED}  ✗${NC} $1"; }

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
FSS_ROOT="$SCRIPT_DIR"
. "${FSS_ROOT}/fss_profile.conf" 2>/dev/null || true

check_file() {
    local file="$1"
    local name="$2"
    if [[ ! -f "$file" ]]; then
        fail "$name not found: $file"
        return 1
    fi
    if python3 -m py_compile "$file" 2>/dev/null; then
        pass "$name syntax OK"
        return 0
    else
        fail "$name has syntax errors"
        python3 -m py_compile "$file"
        return 1
    fi
}

check_contains() {
    local file="$1"
    local pattern="$2"
    local description="$3"
    if grep -q "$pattern" "$file"; then
        pass "$description"
        return 0
    else
        fail "$description NOT found"
        return 1
    fi
}

echo "============================================"
echo " FSS D-Bus Listener Verification"
echo "============================================"
echo ""

LISTENERS=(
    "$FSS_ROOT/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py"
    "$FSS_ROOT/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py"
    "$FSS_ROOT/electron_app/magicmirror/modules/MMM-FSS-Inventory/py_bridge/inventory_dbus_listener.py"
)

echo "--- [1] Python Syntax ---"
for f in "${LISTENERS[@]}"; do
    check_file "$f" "$(basename "$f")"
done

echo ""
echo "--- [2] D-Bus Signal Subscription (async for pattern) ---"
check_contains "${LISTENERS[0]}" "async for.*EnvironmentUpdateRequired" "EnvironmentUpdateRequired signal"
check_contains "${LISTENERS[0]}" "async for.*SecondaryEnvironmentUpdateRequired" "SecondaryEnvironmentUpdateRequired signal"
check_contains "${LISTENERS[1]}" "async for.*DoorStateUpdate" "DoorStateUpdate signal"
check_contains "${LISTENERS[1]}" "async for.*DistanceAlert" "DistanceAlert signal"
check_contains "${LISTENERS[1]}" "async for.*UserPresenceUpdate" "UserPresenceUpdate signal"
check_contains "${LISTENERS[2]}" "async for.*UIUpdateRequired" "UIUpdateRequired signal"

echo ""
echo "--- [3] Error Handling ---"
for f in "${LISTENERS[@]}"; do
    check_contains "$f" "except Exception" "$(basename "$f") has error handling"
done

echo ""
echo "--- [4] Reconnection Logic ---"
for f in "${LISTENERS[@]}"; do
    check_contains "$f" "attempt_reconnect\|max_reconnect_attempts" "$(basename "$f") has reconnection"
done

echo ""
echo "--- [5] JSON Output Format ---"
check_contains "${LISTENERS[0]}" 'ENVIRONMENT_UPDATE' "env: ENVIRONMENT_UPDATE output"
check_contains "${LISTENERS[1]}" 'DOOR_STATE_UPDATE' "monitor: DOOR_STATE_UPDATE output"
check_contains "${LISTENERS[1]}" 'DISTANCE_ALERT' "monitor: DISTANCE_ALERT output"
check_contains "${LISTENERS[2]}" 'FRT_UPDATE' "inventory: FRT_UPDATE output"

echo ""
echo "--- [6] RecommendDaemon D-Bus Source Files ---"
RECOMMEND_SRC=(
    "$FSS_ROOT/recommend_daemon/src/RecommendEngine.py"
    "$FSS_ROOT/recommend_daemon/src/DbusInterface.py"
    "$FSS_ROOT/recommend_daemon/src/RecommendDbManager.py"
    "$FSS_ROOT/recommend_daemon/src/main.py"
)
for f in "${RECOMMEND_SRC[@]}"; do
    check_file "$f" "$(basename "$f")"
done

check_contains "${RECOMMEND_SRC[1]}" "RecommendationUpdated" "DbusInterface: RecommendationUpdated signal"
check_contains "${RECOMMEND_SRC[1]}" "GenerateShoppingList" "DbusInterface: GenerateShoppingList method"
check_contains "${RECOMMEND_SRC[1]}" "GetAvailableRecipes" "DbusInterface: GetAvailableRecipes method"
check_contains "${RECOMMEND_SRC[1]}" "GetShoppingList" "DbusInterface: GetShoppingList method"
check_contains "${RECOMMEND_SRC[1]}" "MarkItemPurchased" "DbusInterface: MarkItemPurchased method"
check_contains "${RECOMMEND_SRC[0]}" "bu_tru\|Bù Trừ\|generate_shopping_list" "Engine: Bù Trừ algorithm"

echo ""
echo "============================================"
echo -e " RESULTS: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "============================================"
exit $FAIL
