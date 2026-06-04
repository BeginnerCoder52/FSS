#!/usr/bin/env bash
# ==============================================================================
# Helper script to generate systemd services for FSS production mode.
# Called by setup.sh when FSS_MODE=production
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/fss_profile.conf"

if [[ "${1:-}" != "--generate-systemd" ]]; then
    fss_log_error "This script is a helper and should be called by setup.sh in production mode."
    echo "Usage: $0 --generate-systemd"
    exit 1
fi

fss_log_info "Creating systemd service files..."
SERVICE_DIR="/etc/systemd/system"

generate_service() {
    local name="$1"
    local desc="$2"
    local exec="$3"
    local wd="$4"
    local after="$5"
    
    sudo tee "$SERVICE_DIR/${name}.service" > /dev/null <<EOF
[Unit]
Description=${desc}
After=${after}

[Service]
ExecStart=${exec}
WorkingDirectory=${wd}
Restart=always
User=${FSS_RUNTIME_USER}

[Install]
WantedBy=multi-user.target
EOF
    fss_log_ok "Generated ${name}.service"
}

# 1. Sensor Daemon
sudo tee "$SERVICE_DIR/${FSS_SERVICE_SENSOR}.service" > /dev/null <<EOF
[Unit]
Description=FSS Sensor Daemon (C++)
After=network.target

[Service]
ExecStart=${FSS_SENSOR_EXEC}
WorkingDirectory=${FSS_ROOT}/sensor_daemon
Restart=always
WatchdogSec=10s
User=${FSS_RUNTIME_USER}

[Install]
WantedBy=multi-user.target
EOF
fss_log_ok "Generated ${FSS_SERVICE_SENSOR}.service"

# 2. Camera Core
generate_service "${FSS_SERVICE_CAMERA}" "FSS Camera Core (C++)" "${FSS_CAMERA_EXEC}" "${FSS_ROOT}/frt_app/cpp_camera_core" "${FSS_SERVICE_SENSOR}.service"

# 3. FRT AI Core
generate_service "${FSS_SERVICE_AI}" "FSS AI Core (Python YOLO)" "${FSS_VENV_FRT_AI}/bin/python ${FSS_ROOT}/frt_app/py_ai_core/src/main.py" "${FSS_ROOT}/frt_app/py_ai_core" "${FSS_SERVICE_CAMERA}.service"

# 4. DB Daemon
generate_service "${FSS_SERVICE_DB}" "FSS Database Daemon (Python)" "${FSS_VENV_DB_DAEMON}/bin/python ${FSS_ROOT}/db_daemon/src/main.py" "${FSS_ROOT}/db_daemon" "${FSS_SERVICE_SENSOR}.service"

# 5. Recommend Daemon
generate_service "${FSS_SERVICE_RECOMMEND}" "FSS Recommend Daemon (Python)" "${FSS_VENV_RECOMMEND_DAEMON}/bin/python ${FSS_ROOT}/recommend_daemon/src/main.py" "${FSS_ROOT}/recommend_daemon" "${FSS_SERVICE_DB}.service"

fss_log_info "Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable ${FSS_SERVICE_SENSOR}.service
sudo systemctl enable ${FSS_SERVICE_CAMERA}.service
sudo systemctl enable ${FSS_SERVICE_AI}.service
sudo systemctl enable ${FSS_SERVICE_DB}.service
sudo systemctl enable ${FSS_SERVICE_RECOMMEND}.service

fss_log_info "Configuring PM2 for MagicMirror UI..."
cd "${FSS_ROOT}/electron_app/magicmirror"
pm2 start npm --name "MagicMirror" -- run start 2>/dev/null || true
pm2 save
sudo env PATH="$PATH:/usr/bin" /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u "${FSS_RUNTIME_USER}" --hp "/home/${FSS_RUNTIME_USER}" 2>/dev/null || true

fss_log_ok "Done! Start all daemons with:"
echo "    sudo systemctl start ${FSS_SERVICE_SENSOR} ${FSS_SERVICE_CAMERA} ${FSS_SERVICE_AI} ${FSS_SERVICE_DB} ${FSS_SERVICE_RECOMMEND}"
