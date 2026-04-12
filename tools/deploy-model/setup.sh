#!/usr/bin/env bash

#
# Download models
#

mkdir -p ./models
cd ./models
MODEL_INT8_URL = "https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_int8.tflite"
MODEL_FP32_URL = "https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_float32.tflite"
echo "[+] Downloading models..."
wget -O models/model_int8.tflite "$MODEL_INT8_URL"
wget -O models/model_fp32.tflite "$MODEL_FP32_URL"