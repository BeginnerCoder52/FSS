#!/bin/bash
# ==============================================================================
# Runtime Environment & Systemd Services setup for FSS on Raspberry Pi
# ==============================================================================

set -euo pipefail

echo "[*] Setting up hardware access (I2C, Video, GPIO)..."
sudo usermod -aG i2c,video,gpio "$USER"

echo "[*] Creating data directories..."
sudo mkdir -p /opt/fss/images /opt/fss/logs
sudo chown -R "$USER:$USER" /opt/fss
sudo chmod -R 755 /opt/fss

echo "[*] Creating systemd service files..."
SERVICE_DIR="/etc/systemd/system"
PROJECT_DIR=$(pwd)

# 1. Sensor Daemon (C++)
sudo tee "$SERVICE_DIR/fss-sensor.service" > /dev/null <<EOF
[Unit]
Description=FSS Sensor Daemon (C++)
After=network.target

[Service]
ExecStart=$PROJECT_DIR/sensor_daemon/build/sensor_daemon_exec
WorkingDirectory=$PROJECT_DIR/sensor_daemon
Restart=always
WatchdogSec=10s
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 2. Camera Core (C++)
sudo tee "$SERVICE_DIR/fss-camera.service" > /dev/null <<EOF
[Unit]
Description=FSS Camera Core (C++)
After=fss-sensor.service

[Service]
ExecStart=$PROJECT_DIR/frt_app/cpp_camera_core/build/camera_core_exec
WorkingDirectory=$PROJECT_DIR/frt_app/cpp_camera_core
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 3. FRT AI Core (Python)
sudo tee "$SERVICE_DIR/fss-ai.service" > /dev/null <<EOF
[Unit]
Description=FSS AI Core (Python YOLO)
After=fss-camera.service

[Service]
ExecStart=$PROJECT_DIR/frt_app/py_ai_core/venv/bin/python $PROJECT_DIR/frt_app/py_ai_core/src/main.py
WorkingDirectory=$PROJECT_DIR/frt_app/py_ai_core
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 4. DB Daemon (Python)
sudo tee "$SERVICE_DIR/fss-db.service" > /dev/null <<EOF
[Unit]
Description=FSS Database Daemon (Python)
After=fss-sensor.service

[Service]
ExecStart=$PROJECT_DIR/db_daemon/venv/bin/python $PROJECT_DIR/db_daemon/src/main.py
WorkingDirectory=$PROJECT_DIR/db_daemon
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 5. Recommend Daemon (Python) - NEW
sudo tee "$SERVICE_DIR/fss-recommend.service" > /dev/null <<EOF
[Unit]
Description=FSS Recommend Daemon (Python) - Business Logic Orchestrator
After=fss-db.service

[Service]
ExecStart=$PROJECT_DIR/recommend_daemon/venv/bin/python $PROJECT_DIR/recommend_daemon/src/main.py
WorkingDirectory=$PROJECT_DIR/recommend_daemon
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable fss-sensor.service
sudo systemctl enable fss-camera.service
sudo systemctl enable fss-ai.service
sudo systemctl enable fss-db.service
sudo systemctl enable fss-recommend.service

echo "[*] Configuring PM2 for MagicMirror UI..."
cd "$PROJECT_DIR/electron_app/magicmirror"
pm2 start npm --name "MagicMirror" -- run start 2>/dev/null || true
pm2 save
sudo env PATH="$PATH:/usr/bin" /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u "$USER" --hp "/home/$USER" 2>/dev/null || true

echo "[+] Done! Start all daemons with:"
echo "    sudo systemctl start fss-sensor fss-camera fss-ai fss-db fss-recommend"
echo "    or: journalctl -u fss-sensor -f"
