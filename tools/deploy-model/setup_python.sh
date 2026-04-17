#!/usr/bin/env bash

#
# Setup Python Environment
#

echo "Dang cai dat uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Cap nhat PATH cho session hien tai de co the dung uv ngay lap tuc
source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

echo "Dang cai dat Python 3.11.5..."
uv python install 3.11.5

mkdir -p ./fss-test
cd ./fss-test # Tro den thu muc tim

echo "Dang khoi tao moi truong ao..."
# Dang co --seed de tu dong cai san pip, setuptools, wheel vao venv
uv venv --python 3.11.5 --seed

# Kich hoat moi truong
source .venv/bin/activate

echo "Dang cai dat cac thu vien..."
pip install tflite-runtime opencv-python-headless "numpy<2" --no-cache-dir

echo "Don dep cache..."
pip cache purge