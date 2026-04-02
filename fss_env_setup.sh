#!/bin/bash
# ==============================================================================
# Thiết lập Runtime Environment & Systemd Services cho FSS trên Raspberry Pi
# ==============================================================================

set -e

echo "[*] Thiết lập quyền truy cập phần cứng (I2C, Video) cho user hiện tại..."
sudo usermod -aG i2c,video,gpio $USER

echo "[*] Kiểm tra và tạo cấu trúc thư mục Data (/opt/fss)..."
sudo mkdir -p /opt/fss/images
sudo mkdir -p /opt/fss/logs
sudo chown -R $USER:$USER /opt/fss
sudo chmod -R 755 /opt/fss

# Lưu ý: /dev/shm (POSIX Shared Memory) đã được Linux tự động mount vào RAM (tmpfs).
# App C++ của bạn gọi shm_open("/fss_video_frame") sẽ tự lưu vào /dev/shm/fss_video_frame.
# Không cần mount thủ công!

echo "[*] Tạo Systemd Service cho các Daemon..."
SERVICE_DIR="/etc/systemd/system"
PROJECT_DIR=$(pwd)

# 1. Sensor Daemon (C++ - Có Systemd Watchdog)
cat <<EOF | sudo tee $SERVICE_DIR/fss-sensor.service
[Unit]
Description=FSS Sensor Daemon (C++)
After=network.target

[Service]
ExecStart=$PROJECT_DIR/sensor_daemon/build/sensor_daemon_exec
WorkingDirectory=$PROJECT_DIR/sensor_daemon
Restart=always
# Watchdog kích hoạt, nếu app C++ không gọi sd_notify() trong 10s, OS sẽ kill & restart
WatchdogSec=10s
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 2. Camera Core (C++)
cat <<EOF | sudo tee $SERVICE_DIR/fss-camera.service
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
cat <<EOF | sudo tee $SERVICE_DIR/fss-ai.service
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
cat <<EOF | sudo tee $SERVICE_DIR/fss-db.service
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

echo "[*] Nạp lại Systemd và kích hoạt khởi động cùng hệ thống..."
sudo systemctl daemon-reload
sudo systemctl enable fss-sensor.service
sudo systemctl enable fss-camera.service
sudo systemctl enable fss-ai.service
sudo systemctl enable fss-db.service

echo "[*] Cấu hình PM2 để khởi chạy MagicMirror UI..."
# Di chuyển vào thư mục UI
cd $PROJECT_DIR/magicmirror

# Khởi tạo tiến trình MagicMirror qua pm2
pm2 start npm --name "MagicMirror" -- run start

# Lưu danh sách tiến trình hiện tại của pm2
pm2 save

# Tạo script để pm2 tự khởi động cùng OS khi Pi bật nguồn
# Lệnh này sinh ra một command, ta thực thi command đó ngay lập tức
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u $USER --hp /home/$USER
# -----------------------------------

echo "[+] Hoàn tất! Hệ thống Backend dùng Systemd, Frontend dùng PM2."

echo "[+] Hoàn tất! Bạn có thể khởi động toàn hệ thống bằng lệnh:"
echo "    sudo systemctl start fss-sensor fss-camera fss-ai fss-db"
echo "    Để xem log: journalctl -u fss-sensor -f"
