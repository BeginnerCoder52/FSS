#!/bin/bash
# ==============================================================================
# Trình cài đặt hệ thống Fridge Supervisor System (FSS) v0.5
# Kiến trúc: C/C++, Python, Node.js
# ==============================================================================

set -e

echo "[*] Cập nhật hệ thống & Cài đặt Build Tools, C++ Dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential cmake pkg-config \
                        libi2c-dev libv4l-dev \
                        libsystemd-dev libsdbus-c++-dev \
                        libzmq3-dev libsqlite3-dev \
                        python3-venv python3-dev \
                        nodejs npm

echo "[*] Cấu hình thư mục Data chia sẻ (/opt/fss)..."
sudo mkdir -p /opt/fss/images
sudo mkdir -p /opt/fss/logs
sudo chown -R $USER:$USER /opt/fss
sudo chmod -R 755 /opt/fss

echo "[*] Biên dịch các module C/C++..."
# 1. Biện dịch Sensor Daemon
echo " -> Biên dịch SensorDaemon (C/C++)..."
mkdir -p sensor_daemon/build && cd sensor_daemon/build
cmake ..
make -j4
cd ../../

# 2. Biên dịch Core Camera của FRT App
echo " -> Biên dịch FRT Camera Core (C/C++)..."
mkdir -p frt_app/cpp_camera_core/build && cd frt_app/cpp_camera_core/build
cmake ..
make -j4
cd ../../../

echo "[*] Cài đặt Python Virtual Environments..."
# Cài đặt venv cho FRT AI Core
python3 -m venv frt_app/py_ai_core/venv
source frt_app/py_ai_core/venv/bin/activate
pip install -r frt_app/py_ai_core/requirements.txt
deactivate

# Cài đặt venv cho DB Daemon
python3 -m venv db_daemon/venv
source db_daemon/venv/bin/activate
pip install -r db_daemon/requirements.txt
deactivate

echo "[*] Cài đặt UI & Python Bridge cho MagicMirror..."
cd magicmirror
npm install
# Cấu hình module Food
cd modules/MMM-FSS-Food
npm install # Cài python-shell cho node_helper
python3 -m venv py_bridge/venv
py_bridge/venv/bin/pip install -r py_bridge/requirements.txt
# Cấu hình module Env
cd ../MMM-FSS-Env
npm install
python3 -m venv py_bridge/venv
py_bridge/venv/bin/pip install -r py_bridge/requirements.txt
cd ../../../

echo "[+] Hoàn tất thiết lập! Các file thực thi C++ đã nằm trong thư mục build/."