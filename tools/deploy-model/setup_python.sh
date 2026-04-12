#!/usr/bin/env bash

#
# Setup Python Environment
#

curl -LsSf https://astral.sh/uv/install.sh | sh # Tải công cụ uv
uv python install 3.11.5 # Tải python
mkdir -p ~/tools/deploy-model
cd ~/tools/deploy-model # Trỏ đến thư mục tạm
uv venv --python 3.11.5 # Tạo môi trường với python
source .venv/bin/activate # Kích hoạt môi trường
python -m ensurepip --default-pip # Đảm bảo pip tồn tại
python -m pip install --upgrade pip setuptools wheel # Tải các công cụ cơ bản
pip install tflite-runtime opencv-python-headless “numpy<2” --no-cache-dir # Cài đặt tflite-runtime-2.14.0, opencv-python-headless-4.11.0.86 và numpy-1.26.4
pip cache purge # Dọn cache sau khi cài đặt
