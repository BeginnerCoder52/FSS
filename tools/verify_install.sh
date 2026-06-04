#!/usr/bin/env bash
# ==============================================================================
# verify_install.sh — FSS Post-Install Verification
# ==============================================================================
#
# Comprehensive check that the FSS installation is complete and functional.
# Run after setup.sh to verify everything works.
#
# Usage:
#   bash tools/verify_install.sh
#
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FSS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source profile
. "$FSS_ROOT/fss_profile.conf"

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS + 1)); echo -e "  ${_FSS_GREEN}✓${_FSS_NC} $1"; }
fail() { FAIL=$((FAIL + 1)); echo -e "  ${_FSS_RED}✗${_FSS_NC} $1"; }
warn() { WARN=$((WARN + 1)); echo -e "  ${_FSS_YELLOW}⚠${_FSS_NC} $1"; }

echo ""
echo "============================================"
echo " FSS Post-Install Verification"
echo "============================================"
echo "  Profile: FSS_MODE=$FSS_MODE, FSS_DEVICE=$FSS_DEVICE"
echo "  User:    FSS_RUNTIME_USER=$FSS_RUNTIME_USER"
echo "  Root:    $FSS_ROOT"
echo ""

# --- 1. Binary existence -----------------------------------------------------
echo "--- [1] C++ Binaries ---"
if [[ -x "$FSS_SENSOR_EXEC" ]]; then
    pass "sensor_daemon_exec exists"
else
    fail "sensor_daemon_exec NOT FOUND at $FSS_SENSOR_EXEC"
fi

if [[ -x "$FSS_CAMERA_EXEC" ]]; then
    pass "camera_core_exec exists"
else
    fail "camera_core_exec NOT FOUND at $FSS_CAMERA_EXEC"
fi

if [[ -f "$FSS_TFLITE_LIB" ]]; then
    pass "libtflite_reader.so exists"
else
    warn "libtflite_reader.so NOT FOUND (optional C backend)"
fi

# --- 2. Python virtual environments ------------------------------------------
echo ""
echo "--- [2] Python Virtual Environments ---"
for entry in "${FSS_PYTHON_VENVS[@]}" "${FSS_MM_BRIDGE_VENVS[@]}"; do
    IFS=':' read -r venv_path flags <<< "$entry"
    full_path="$FSS_ROOT/$venv_path/venv/bin/python"
    if [[ -f "$full_path" ]]; then
        pass "$venv_path/venv"
    else
        fail "$venv_path/venv NOT FOUND"
    fi
done

# --- 3. Writable /opt/fss paths -----------------------------------------------
echo ""
echo "--- [3] Runtime Directories ---"
for dir in "$FSS_DATA_DIR" "$FSS_MODEL_DIR" "$FSS_ASSET_DIR" "$FSS_IMAGE_DIR"; do
    if [[ -d "$dir" ]]; then
        if [[ -w "$dir" ]]; then
            pass "$dir (writable)"
        else
            fail "$dir (exists but NOT writable)"
        fi
    else
        fail "$dir does NOT exist"
    fi
done

# Check /var/log/fss
if [[ -d "$FSS_LOG_DIR" ]]; then
    pass "$FSS_LOG_DIR exists"
else
    warn "$FSS_LOG_DIR does not exist (will use fallback)"
fi

# --- 4. D-Bus validation ------------------------------------------------------
echo ""
echo "--- [4] D-Bus Configuration ---"
if [[ -f "$FSS_DBUS_CONF_SYSTEM" ]]; then
    pass "D-Bus config installed at $FSS_DBUS_CONF_SYSTEM"
    # Validate XML syntax
    if command -v xmllint &>/dev/null; then
        if xmllint --noout "$FSS_DBUS_CONF_SYSTEM" 2>/dev/null; then
            pass "D-Bus config XML syntax valid"
        else
            fail "D-Bus config XML syntax INVALID"
        fi
    else
        warn "xmllint not available, skipping XML validation"
    fi
else
    fail "D-Bus config NOT installed at $FSS_DBUS_CONF_SYSTEM"
fi

# Check template exists
if [[ -f "$FSS_DBUS_CONF_TEMPLATE" ]]; then
    pass "D-Bus config template exists in repo"
else
    fail "D-Bus config template MISSING"
fi

# --- 5. Model presence --------------------------------------------------------
echo ""
echo "--- [5] Model Files ---"
if [[ -f "$FSS_MODEL_PATH" ]]; then
    FILE_SIZE=$(stat --format=%s "$FSS_MODEL_PATH" 2>/dev/null || stat -f%z "$FSS_MODEL_PATH" 2>/dev/null || echo 0)
    if [[ "$FILE_SIZE" -gt 0 ]]; then
        pass "Model: $FSS_MODEL_PATH ($FILE_SIZE bytes)"
    else
        fail "Model file is empty: $FSS_MODEL_PATH"
    fi
else
    warn "Model not deployed yet: $FSS_MODEL_PATH"
    warn "  Run: bash tools/deploy-model/deploy_model.sh"
fi

# --- 6. Node.js / MagicMirror -------------------------------------------------
echo ""
echo "--- [6] Node.js / MagicMirror ---"
if command -v node &>/dev/null; then
    pass "Node.js $(node --version 2>/dev/null || echo 'unknown')"
else
    fail "Node.js not installed"
fi

MM_DIR="$FSS_ROOT/electron_app/magicmirror"
if [[ -d "$MM_DIR/node_modules" ]]; then
    pass "MagicMirror node_modules installed"
else
    fail "MagicMirror node_modules MISSING (run: cd electron_app/magicmirror && npm install)"
fi

# --- 7. Permissions (if applicable) -------------------------------------------
echo ""
echo "--- [7] Permissions ---"
if id "$FSS_RUNTIME_USER" &>/dev/null; then
    pass "User '$FSS_RUNTIME_USER' exists"
    for group in i2c video gpio; do
        if id -nG "$FSS_RUNTIME_USER" 2>/dev/null | grep -qw "$group"; then
            pass "$FSS_RUNTIME_USER in group '$group'"
        else
            warn "$FSS_RUNTIME_USER NOT in group '$group' (may need: sudo usermod -aG $group $FSS_RUNTIME_USER)"
        fi
    done
else
    if [[ "$FSS_MODE" == "production" ]]; then
        fail "Runtime user '$FSS_RUNTIME_USER' does NOT exist"
    else
        warn "Runtime user '$FSS_RUNTIME_USER' not found (OK for dev mode on non-Linux)"
    fi
fi

# --- 8. Hardcoded path check --------------------------------------------------
echo ""
echo "--- [8] Hardcoded Path Check ---"
HARDCODED=$(grep -rn "/home/richardmelvin52" \
    --include="*.py" --include="*.js" --include="*.sh" --include="*.conf" \
    "$FSS_ROOT" 2>/dev/null | grep -v ".md:" | grep -v ".git/" | grep -v "HANDOVER" | grep -v "FINAL_UPGRADE" || true)
if [[ -z "$HARDCODED" ]]; then
    pass "No hardcoded /home/richardmelvin52 paths in source files"
else
    fail "Found hardcoded paths:"
    echo "$HARDCODED" | head -10
fi

# --- 9. Phase 1 tests ---------------------------------------------------------
echo ""
echo "--- [9] Phase 1 Tests ---"
if [[ -f "$FSS_ROOT/tests/run_phase1_tests.py" ]]; then
    pass "Phase 1 test file exists"
    # Note: Actually running tests requires the correct venv and Linux
    warn "Run manually: python3 tests/run_phase1_tests.py"
else
    fail "Phase 1 test file MISSING"
fi

# --- Summary ------------------------------------------------------------------
echo ""
echo "============================================"
echo -e " RESULTS: ${_FSS_GREEN}$PASS passed${_FSS_NC}, ${_FSS_YELLOW}$WARN warnings${_FSS_NC}, ${_FSS_RED}$FAIL failed${_FSS_NC}"
echo "============================================"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo "Some checks failed. Review the output above and re-run setup.sh if needed."
    exit 1
fi
exit 0
