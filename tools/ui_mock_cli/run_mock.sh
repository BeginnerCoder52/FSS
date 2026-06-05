#!/bin/bash
# run_mock.sh
# Kích hoạt virtualenv độc lập cho mock_cli

cd "$(dirname "$0")"

VENV_PATH="./venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "Đang tạo môi trường ảo độc lập (Standalone Test Environment)..."
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

# Cài đặt sdbus-python nếu chưa có
pip install -r requirements.txt > /dev/null 2>&1

echo "Đã kích hoạt môi trường ảo."
echo "Đang chạy CLI Mock..."

# D-Bus yêu cầu chạy dưới quyền root (sudo) cho System Bus
sudo -E $(which python) mock_cli.py
