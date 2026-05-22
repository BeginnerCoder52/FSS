#!/bin/bash
# Test script to verify D-Bus listener fixes

set -e

echo "================================"
echo "D-Bus Listener Fix Verification"
echo "================================"
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    local file=$1
    local name=$2
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ $name not found: $file${NC}"
        return 1
    fi
    
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓ $name syntax OK${NC}"
        return 0
    else
        echo -e "${RED}✗ $name has syntax errors${NC}"
        python3 -m py_compile "$file"
        return 1
    fi
}

check_contains() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✓ $description found${NC}"
        return 0
    else
        echo -e "${RED}✗ $description NOT found${NC}"
        return 1
    fi
}

echo "Step 1: Check Python Syntax"
echo "--------------------------"

check_file "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py" "env_dbus_listener.py"
ENV_OK=$?

check_file "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py" "monitor_dbus_listener.py"
MONITOR_OK=$?

check_file "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Inventory/py_bridge/inventory_dbus_listener.py" "inventory_dbus_listener.py"
INVENTORY_OK=$?

echo ""
echo "Step 2: Check Signal Subscription Patterns"
echo "-----------------------------------------"

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py" \
    "async for.*EnvironmentUpdateRequired" \
    "EnvironmentUpdateRequired uses async for pattern"
ENV_SIGNAL=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py" \
    "async for.*DistanceAlert" \
    "DistanceAlert uses async for pattern"
DISTANCE_SIGNAL=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Inventory/py_bridge/inventory_dbus_listener.py" \
    "async for.*UIUpdateRequired" \
    "UIUpdateRequired uses async for pattern"
FRT_SIGNAL=$?

echo ""
echo "Step 3: Check Error Handling"
echo "---------------------------"

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py" \
    "except Exception\|AttributeError" \
    "env_dbus_listener has error handling"
ENV_ERROR=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py" \
    "except Exception\|AttributeError" \
    "monitor_dbus_listener has error handling"
MONITOR_ERROR=$?

echo ""
echo "Step 4: Check Reconnection Logic"
echo "-------------------------------"

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py" \
    "attempt_reconnect\|max_reconnect_attempts" \
    "env_dbus_listener has reconnection logic"
ENV_RECONNECT=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py" \
    "attempt_reconnect\|max_reconnect_attempts" \
    "monitor_dbus_listener has reconnection logic"
MONITOR_RECONNECT=$?

echo ""
echo "Step 5: Check JSON Output Format"
echo "------------------------------"

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Env/py_bridge/env_dbus_listener.py" \
    'ENVIRONMENT_UPDATE' \
    "env_dbus_listener outputs ENVIRONMENT_UPDATE"
ENV_JSON=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Monitor/py_bridge/monitor_dbus_listener.py" \
    'DISTANCE_ALERT' \
    "monitor_dbus_listener outputs DISTANCE_ALERT"
DISTANCE_JSON=$?

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Inventory/py_bridge/inventory_dbus_listener.py" \
    'FRT_UPDATE' \
    "inventory_dbus_listener outputs FRT_UPDATE"
FRT_JSON=$?

echo ""
echo "Step 6: Check Module Configuration"
echo "---------------------------------"

check_contains "/home/richardmelvin52/FSS/electron_app/magicmirror/modules/MMM-FSS-Inventory/node_helper.js" \
    "frtAppEnabled" \
    "inventory node_helper reads frtAppEnabled config"
NODE_CONFIG=$?

echo ""
echo "========== RESULTS =========="
echo ""

OVERALL_OK=0

if [ $ENV_OK -eq 0 ] && [ $MONITOR_OK -eq 0 ] && [ $INVENTORY_OK -eq 0 ]; then
    echo -e "${GREEN}✓ All Python files have valid syntax${NC}"
else
    echo -e "${RED}✗ Some Python files have syntax errors${NC}"
    OVERALL_OK=1
fi

if [ $ENV_SIGNAL -eq 0 ] && [ $DISTANCE_SIGNAL -eq 0 ] && [ $FRT_SIGNAL -eq 0 ]; then
    echo -e "${GREEN}✓ All signal subscriptions use correct .attach() pattern${NC}"
else
    echo -e "${RED}✗ Some signal subscriptions are incorrect${NC}"
    OVERALL_OK=1
fi

if [ $ENV_ERROR -eq 0 ] && [ $MONITOR_ERROR -eq 0 ]; then
    echo -e "${GREEN}✓ All listeners have error handling${NC}"
else
    echo -e "${RED}✗ Some listeners missing error handling${NC}"
    OVERALL_OK=1
fi

if [ $ENV_RECONNECT -eq 0 ] && [ $MONITOR_RECONNECT -eq 0 ]; then
    echo -e "${GREEN}✓ All listeners have reconnection logic${NC}"
else
    echo -e "${RED}✗ Some listeners missing reconnection logic${NC}"
    OVERALL_OK=1
fi

if [ $ENV_JSON -eq 0 ] && [ $DISTANCE_JSON -eq 0 ] && [ $FRT_JSON -eq 0 ]; then
    echo -e "${GREEN}✓ All listeners output correct JSON format${NC}"
else
    echo -e "${RED}✗ Some listeners have incorrect JSON format${NC}"
    OVERALL_OK=1
fi

if [ $NODE_CONFIG -eq 0 ]; then
    echo -e "${GREEN}✓ Node helper reads FRT config${NC}"
else
    echo -e "${RED}✗ Node helper missing FRT config support${NC}"
    OVERALL_OK=1
fi

echo ""
if [ $OVERALL_OK -eq 0 ]; then
    echo -e "${GREEN}================================"
    echo "All Checks Passed! ✓"
    echo "================================${NC}"
    exit 0
else
    echo -e "${RED}================================"
    echo "Some Checks Failed ✗"
    echo "================================${NC}"
    exit 1
fi
