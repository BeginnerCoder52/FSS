#!/bin/bash
# run_mock.sh
# Kích hoạt virtualenv của db_daemon và chạy python script giả lập

cd "$(dirname "$0")"

VENV_PATH="../../db_daemon/venv"

if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "Đã kích hoạt virtualenv của db_daemon."
else
    echo "Cảnh báo: Không tìm thấy virtualenv tại $VENV_PATH"
    echo "Hãy chắc chắn rằng db_daemon đã được setup."
fi

# D-Bus yêu cầu chạy dưới quyền root (sudo) cho System Bus
sudo -E $(which python) mock_cli.py
