#!/bin/bash
# ==============================================================================
# Setup script for Fridge Supervisor System (FSS)
# Builds C++ components and creates Python virtual environments.
# ==============================================================================

set -euo pipefail

echo "[*] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake pkg-config \
    libi2c-dev i2c-tools \
    libv4l-dev v4l-utils \
    libsystemd-dev libsdbus-c++-dev libdbus-1-dev \
    libzmq3-dev \
    libsqlite3-dev \
    libopencv-dev \
    python3-venv python3-dev \
    nodejs npm

echo "[*] Configuring shared data directory (/opt/fss)..."
sudo mkdir -p /opt/fss/images /opt/fss/logs
sudo chown -R "$USER:$USER" /opt/fss
sudo chmod -R 755 /opt/fss

echo "[*] Building C++ components..."
echo " -> SensorDaemon..."
mkdir -p sensor_daemon/build && cd sensor_daemon/build
cmake .. && make -j4
cd ../../

echo " -> FRT Camera Core..."
mkdir -p frt_app/cpp_camera_core/build && cd frt_app/cpp_camera_core/build
cmake .. && make -j4
cd ../../../

echo "[*] Creating Python virtual environments..."
setup_venv() {
    local dir="$1"
    echo " -> $dir..."
    python3 -m venv "$dir/venv"
    "$dir/venv/bin/pip" install --upgrade pip setuptools
    if [[ -f "$dir/requirements.txt" ]]; then
        "$dir/venv/bin/pip" install -r "$dir/requirements.txt"
    fi
}

setup_venv "db_daemon"
setup_venv "recommend_daemon"
setup_venv "frt_app/py_ai_core"

echo "[*] Installing MagicMirror UI..."
cd electron_app/magicmirror || { echo "WARNING: magicmirror directory not found"; exit 0; }
npm install

# Note: MMM-FSS-Food module is planned but not yet implemented.
# When implemented:
#   cd modules/MMM-FSS-Food && npm install && python3 -m venv py_bridge/venv
#   py_bridge/venv/bin/pip install -r py_bridge/requirements.txt

for module in MMM-FSS-Env MMM-FSS-Inventory MMM-FSS-Monitor; do
    if [[ -d "modules/$module" ]]; then
        echo " -> $module..."
        cd "modules/$module"
        npm install
        if [[ -d "py_bridge" ]]; then
            python3 -m venv py_bridge/venv
            py_bridge/venv/bin/pip install -r py_bridge/requirements.txt
        fi
        cd ../../
    fi
done

echo "[+] Setup complete! C++ binaries are in build/ directories."
