#!/usr/bin/env bash
# ==============================================================================
# FSS Unified Setup Script
# ==============================================================================

set -euo pipefail

# Source profile
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -f "${SCRIPT_DIR}/fss_profile.conf" ]]; then
    echo "ERROR: fss_profile.conf not found."
    exit 1
fi
. "${SCRIPT_DIR}/fss_profile.conf"

fss_log_info "Starting FSS Installation in ${FSS_MODE} mode for ${FSS_DEVICE}..."
fss_log_info "Runtime user: ${FSS_RUNTIME_USER}"
fss_log_info "Root: ${FSS_ROOT}"

# 1. System Dependencies
fss_log_info "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y "${FSS_APT_PACKAGES[@]}"

# 2. Hardware access
fss_log_info "Setting up hardware access groups..."
sudo usermod -aG i2c,video,gpio "${FSS_RUNTIME_USER}" || true

# 3. Create Runtime Directories
fss_log_info "Configuring shared data directory (${FSS_RUNTIME_DIR})..."
sudo mkdir -p "${FSS_DATA_DIR}" "${FSS_MODEL_DIR}" "${FSS_ASSET_DIR}" "${FSS_IMAGE_DIR}" "${FSS_LOG_DIR}"
sudo chown -R "${FSS_RUNTIME_USER}:${FSS_RUNTIME_USER}" "${FSS_RUNTIME_DIR}"
sudo chmod -R 755 "${FSS_RUNTIME_DIR}"
sudo chown -R "${FSS_RUNTIME_USER}:${FSS_RUNTIME_USER}" "${FSS_LOG_DIR}"

# 4. Build C++ Components
fss_log_info "Building C++ components..."
fss_log_info " -> SensorDaemon..."
mkdir -p "${FSS_ROOT}/sensor_daemon/build" && cd "${FSS_ROOT}/sensor_daemon/build"
cmake .. && make -j4
cd "${FSS_ROOT}"

fss_log_info " -> FRT Camera Core and C TFLite Reader..."
mkdir -p "${FSS_ROOT}/frt_app/build" && cd "${FSS_ROOT}/frt_app/build"
cmake .. && make -j4
cd "${FSS_ROOT}"

# Copy libtflite_reader.so to /usr/local/lib
if [[ -f "${FSS_TFLITE_LIB}" ]]; then
    fss_log_info "Installing libtflite_reader.so..."
    sudo cp "${FSS_TFLITE_LIB}" /usr/local/lib/
    sudo ldconfig
fi

# 5. Create Python Virtual Environments
fss_log_info "Creating Python virtual environments..."
setup_venv() {
    local venv_def="$1"
    IFS=':' read -r path flags <<< "$venv_def"
    local dir="${FSS_ROOT}/${path}"
    fss_log_info " -> ${dir}"
    local venv_args=""
    if [[ "$flags" == "ssp" ]]; then
        venv_args="--system-site-packages"
    fi
    python3 -m venv $venv_args "${dir}/venv"
    "${dir}/venv/bin/pip" install --upgrade pip setuptools
    if [[ -f "${dir}/requirements.txt" ]]; then
        "${dir}/venv/bin/pip" install -r "${dir}/requirements.txt"
    fi
}

for v in "${FSS_PYTHON_VENVS[@]}"; do
    setup_venv "$v"
done

fss_log_info "Installing MagicMirror UI..."
if [[ -d "${FSS_ROOT}/electron_app/magicmirror" ]]; then
    cd "${FSS_ROOT}/electron_app/magicmirror"
    npm install
    cd "${FSS_ROOT}"
    for v in "${FSS_MM_BRIDGE_VENVS[@]}"; do
        # Extract base path without py_bridge since setup_venv handles relative paths
        mm_path=$(echo "$v" | sed 's/\/py_bridge.*//')
        cd "${FSS_ROOT}/${mm_path}"
        npm install
        cd "${FSS_ROOT}"
        setup_venv "$v"
    done
else
    fss_log_warn "magicmirror directory not found, skipping."
fi

# 6. Generate D-Bus config
fss_log_info "Generating D-Bus security policy..."
if [[ -f "${FSS_DBUS_CONF_TEMPLATE}" ]]; then
    sudo mkdir -p /etc/dbus-1/system.d
    sed "s/@@FSS_RUNTIME_USER@@/${FSS_RUNTIME_USER}/g" "${FSS_DBUS_CONF_TEMPLATE}" | sudo tee "${FSS_DBUS_CONF_SYSTEM}" > /dev/null
    sudo systemctl reload dbus || true
    fss_log_ok "D-Bus policy deployed."
else
    fss_log_warn "D-Bus template not found at ${FSS_DBUS_CONF_TEMPLATE}"
fi

# 7. Model Deployment
fss_log_info "Fetching AI models..."
if [[ -x "${FSS_ROOT}/tools/deploy-model/deploy_model.sh" ]]; then
    bash "${FSS_ROOT}/tools/deploy-model/deploy_model.sh"
else
    fss_log_warn "deploy_model.sh not executable or missing."
fi

# 8. Setup Systemd (if production mode)
if [[ "$FSS_MODE" == "production" ]]; then
    fss_log_info "Production mode: Generating systemd services..."
    bash "${FSS_ROOT}/fss_env_setup.sh" --generate-systemd
fi

fss_log_ok "Setup complete!"
