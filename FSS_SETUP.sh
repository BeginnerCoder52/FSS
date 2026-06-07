#!/usr/bin/env bash
# ==============================================================================
# FSS_SETUP.sh — FSS Full System Setup & Verification Script
#
# Installs ALL dependencies, builds C++ components, creates Python venvs,
# deploys models, configures D-Bus, and verifies the entire installation.
#
# This is the single entry point for setting up FSS from scratch.
# Run ONCE after cloning the repository on your target device.
#
# Usage:
#   bash FSS_SETUP.sh                          # dev mode
#   FSS_MODE=production bash FSS_SETUP.sh       # production mode
#   bash FSS_SETUP.sh --skip-models             # skip model download
#   bash FSS_SETUP.sh --skip-verify             # skip post-install verify
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Source profile
. "${SCRIPT_DIR}/fss_profile.conf"

SKIP_MODELS=false
SKIP_VERIFY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-models) SKIP_MODELS=true; shift ;;
        --skip-verify) SKIP_VERIFY=true; shift ;;
        --help|-h)
            echo "Usage: bash FSS_SETUP.sh [--skip-models] [--skip-verify]"
            exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

fss_log_info "=============================================="
fss_log_info "FSS SETUP START"
fss_log_info "  Mode:   ${FSS_MODE}"
fss_log_info "  Device: ${FSS_DEVICE}"
fss_log_info "  User:   ${FSS_RUNTIME_USER}"
fss_log_info "  Root:   ${FSS_ROOT}"
fss_log_info "=============================================="

# ==============================================================================
# STEP 1: System Dependencies (APT)
# ==============================================================================
fss_log_info "--- Step 1: Installing system APT dependencies ---"
sudo apt-get update
sudo apt-get install -y "${FSS_APT_PACKAGES[@]}"
fss_log_ok "APT packages installed"

# ==============================================================================
# STEP 2: Hardware Access Groups
# ==============================================================================
fss_log_info "--- Step 2: Configuring hardware access groups ---"
sudo usermod -aG i2c,video,gpio "${FSS_RUNTIME_USER}" || true
fss_log_ok "Hardware groups configured"

# ==============================================================================
# STEP 3: Runtime Directories
# ==============================================================================
fss_log_info "--- Step 3: Creating runtime directories ---"
sudo mkdir -p "${FSS_DATA_DIR}" "${FSS_MODEL_DIR}" "${FSS_ASSET_DIR}" \
            "${FSS_IMAGE_DIR}" "${FSS_LOG_DIR}"
sudo chown -R "${FSS_RUNTIME_USER}:${FSS_RUNTIME_USER}" "${FSS_RUNTIME_DIR}"
sudo chmod -R 755 "${FSS_RUNTIME_DIR}"
sudo chown -R "${FSS_RUNTIME_USER}:${FSS_RUNTIME_USER}" "${FSS_LOG_DIR}" 2>/dev/null || true
fss_log_ok "Runtime directories created at ${FSS_RUNTIME_DIR}"

# ==============================================================================
# STEP 4: Build C++ Components
# ==============================================================================
fss_log_info "--- Step 4: Building C++ components ---"

if [[ "$FSS_DEVICE" == "rpi4b" ]]; then
    # SensorDaemon
    fss_log_info " -> Building SensorDaemon..."
    mkdir -p "${FSS_ROOT}/sensor_daemon/build"
    cmake -S "${FSS_ROOT}/sensor_daemon" -B "${FSS_ROOT}/sensor_daemon/build" \
          -DCMAKE_BUILD_TYPE=Release
    make -C "${FSS_ROOT}/sensor_daemon/build" -j4

    # FRT Camera Core + C TFLite Reader
    fss_log_info " -> Building FRT Camera Core and C TFLite Reader..."
    mkdir -p "${FSS_ROOT}/frt_app/build"
    cmake -S "${FSS_ROOT}/frt_app" -B "${FSS_ROOT}/frt_app/build" \
          -DCMAKE_BUILD_TYPE=Release
    make -C "${FSS_ROOT}/frt_app/build" -j4

    # Install libtflite_reader.so
    if [[ -f "${FSS_TFLITE_LIB}" ]]; then
        fss_log_info " -> Installing libtflite_reader.so..."
        sudo cp "${FSS_TFLITE_LIB}" /usr/local/lib/
        sudo ldconfig
    fi
    fss_log_ok "C++ components built"
else
    fss_log_skip "Skipping C++ build on ${FSS_DEVICE} (requires rpi4b)"
fi

# ==============================================================================
# STEP 5: Python Virtual Environments
# ==============================================================================
fss_log_info "--- Step 5: Creating Python virtual environments ---"

setup_venv() {
    local venv_def="$1"
    IFS=':' read -r path flags <<< "$venv_def"
    local dir="${FSS_ROOT}/${path}"
    local venv_args=""
    if [[ "$flags" == "ssp" ]]; then
        venv_args="--system-site-packages"
    fi
    fss_log_info " -> ${path}"
    python3 -m venv $venv_args "${dir}/venv"
    "${dir}/venv/bin/pip" install --upgrade pip setuptools wheel
    if [[ -f "${dir}/requirements.txt" ]]; then
        "${dir}/venv/bin/pip" install -r "${dir}/requirements.txt"
    fi
}

for v in "${FSS_PYTHON_VENVS[@]}"; do
    setup_venv "$v"
done
fss_log_ok "Python venvs created"

# ==============================================================================
# STEP 6: MagicMirror UI
# ==============================================================================
fss_log_info "--- Step 6: Installing MagicMirror UI ---"
if [[ -d "${FSS_ROOT}/electron_app/magicmirror" ]]; then
    cd "${FSS_ROOT}/electron_app/magicmirror"
    npm install
    cd "${FSS_ROOT}"

    for v in "${FSS_MM_BRIDGE_VENVS[@]}"; do
        mm_path=$(echo "$v" | sed 's/\/py_bridge.*//')
        cd "${FSS_ROOT}/${mm_path}"
        npm install 2>/dev/null || true
        cd "${FSS_ROOT}"
        setup_venv "$v"
    done
    fss_log_ok "MagicMirror installed"
else
    fss_log_warn "MagicMirror directory not found, skipping"
fi

# ==============================================================================
# STEP 7: D-Bus Configuration
# ==============================================================================
fss_log_info "--- Step 7: Deploying D-Bus security policy ---"
if [[ -f "${FSS_DBUS_CONF_TEMPLATE}" ]]; then
    sudo mkdir -p /etc/dbus-1/system.d
    sed "s/@@FSS_RUNTIME_USER@@/${FSS_RUNTIME_USER}/g" \
        "${FSS_DBUS_CONF_TEMPLATE}" | sudo tee "${FSS_DBUS_CONF_SYSTEM}" > /dev/null
    sudo systemctl reload dbus 2>/dev/null || true
    fss_log_ok "D-Bus policy deployed"
else
    fss_log_warn "D-Bus template not found at ${FSS_DBUS_CONF_TEMPLATE}"
fi

# ==============================================================================
# STEP 8: Deploy AI Models
# ==============================================================================
fss_log_info "--- Step 8: Deploying AI models ---"
if [[ "$SKIP_MODELS" == false ]]; then
    if [[ -x "${FSS_ROOT}/tools/deploy-model/deploy_model.sh" ]]; then
        bash "${FSS_ROOT}/tools/deploy-model/deploy_model.sh"
        fss_log_ok "Models deployed"
    else
        fss_log_warn "deploy_model.sh not executable or missing"
    fi
else
    fss_log_skip "Model download skipped (--skip-models)"
fi

# ==============================================================================
# STEP 9: Systemd Services (Production Only)
# ==============================================================================
if [[ "$FSS_MODE" == "production" ]]; then
    fss_log_info "--- Step 9: Generating systemd services ---"
    bash "${FSS_ROOT}/fss_env_setup.sh" --generate-systemd
    fss_log_ok "Systemd services generated"
fi

# ==============================================================================
# STEP 10: Verify Installation
# ==============================================================================
if [[ "$SKIP_VERIFY" == false ]]; then
    fss_log_info "--- Step 10: Verifying installation ---"
    if [[ -x "${FSS_ROOT}/tools/verify_install.sh" ]]; then
        bash "${FSS_ROOT}/tools/verify_install.sh"
    else
        fss_log_warn "verify_install.sh not found"
    fi
else
    fss_log_skip "Verification skipped (--skip-verify)"
fi

# ==============================================================================
# DONE
# ==============================================================================
fss_log_info "=============================================="
fss_log_ok "FSS SETUP COMPLETE"
fss_log_info "  Next: source venvs and run daemons"
fss_log_info "  Quick start: bash FSS_RUN.sh"
fss_log_info "=============================================="
