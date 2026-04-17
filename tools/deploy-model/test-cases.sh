#!/bin/bash

# ==============================================================================
# Script tự động chạy Benchmark cho các mô hình YOLO TFLite (INT8, FP32, FP16)
# ==============================================================================

# --- Cấu hình thư mục ---
IMAGE_DIR="test-images/images"
LABELS_DIR="test-images/labels" # Để trống ("") nếu bạn không có nhãn ground-truth
OUTPUT_DIR="benchmark_results"

# --- Cấu hình đường dẫn mô hình ---
MODEL_INT8="models/best_int8.tflite"
MODEL_FP32="models/best_fp32.tflite"
MODEL_FP16="models/best_fp16.tflite"

# Tạo thư mục output nếu chưa có
mkdir -p "$OUTPUT_DIR"

echo "============================================================"
echo " BẮT ĐẦU CHẠY BENCHMARK SUY LUẬN AI TRÊN RASPBERRY PI"
echo "============================================================"

# 1. Benchmark mô hình INT8 (Thử nghiệm 1, 2 và 4 threads)
if [ -f "$MODEL_INT8" ]; then
    echo -e "\n[1/3] Đang chạy Benchmark cho mô hình INT8..."
    python test-inference.py \
        --model "$MODEL_INT8" \
        --image-dir "$IMAGE_DIR" \
        --labels-dir "$LABELS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --benchmark-num-threads 1,2,4
else
    echo "[CẢNH BÁO] Không tìm thấy $MODEL_INT8. Bỏ qua..."
fi

# 2. Benchmark mô hình FP32 (Thử nghiệm 1, 2 và 4 threads)
if [ -f "$MODEL_FP32" ]; then
    echo -e "\n[2/3] Đang chạy Benchmark cho mô hình FP32..."
    python test-inference.py \
        --model "$MODEL_FP32" \
        --image-dir "$IMAGE_DIR" \
        --labels-dir "$LABELS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --benchmark-num-threads 1,2,4
else
    echo "[CẢNH BÁO] Không tìm thấy $MODEL_FP32. Bỏ qua..."
fi

# 3. Thử nghiệm mô hình FP16 (Chạy cố định 4 luồng vì không yêu cầu benchmark threads)
if [ -f "$MODEL_FP16" ]; then
    echo -e "\n[3/3] Đang chạy thử nghiệm cho mô hình FP16 (4 threads)..."
    python test-inference.py \
        --model "$MODEL_FP16" \
        --image-dir "$IMAGE_DIR" \
        --labels-dir "$LABELS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --num-threads 4
else
    echo "[CẢNH BÁO] Không tìm thấy $MODEL_FP16. Bỏ qua..."
fi

echo -e "\n============================================================"
echo " HOÀN TẤT! Kết quả và báo cáo CSV được lưu tại thư mục: $OUTPUT_DIR"
echo "============================================================"