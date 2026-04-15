#!/usr/bin/env bash

#
# Run in user mode
#

usage() {
    echo "Use: $0 [--disable-swap] [--force-cpu]"
    echo "  --disable-swap     Disable swap file and config zram"
    echo "  --force-cpu        Set performance mode for CPU"
    echo "  --download-models  Download models"
    exit 1
}

if [ $# -eq 0 ]; then
    #
    # Update and Install packages
    #
    sudo apt update && sudo apt full-upgrade -y # Cập nhật các gói và nâng cấp hệ thống
    sudo apt install -y htop curl wget git

    #
    # Create folder test
    #
    mkdir -p fss-test/models
    mkdir -p fss-test/test-images

    #
    # Disable unnecessary services
    #
    sudo systemctl disable bluetooth # Tắt bluetooth service không cần thiết sử dụng Bluetooth
    sudo systemctl disable hciuart # Tắt hciuart service không cần thiết sử dụng Bluetooth
    sudo systemctl disable ModemManager.service # Tắt Modem Manager vì không cần sử dụng modem dữ liệu di động
fi

for arg in "$@"; do
    case $arg in
        --download-models)
            #
            # Download models
            #
            mkdir -p ./fss-test/models
            cd ./fss-test/models
            MODEL_INT8_URL="https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_int8.tflite"
            MODEL_FP32_URL="https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_float32.tflite"
            echo "[+] Downloading models..."
            wget -O model_int8.tflite "$MODEL_INT8_URL"
            wget -O model_fp32.tflite "$MODEL_FP32_URL"
            shift
            ;;
        --disable-swap)
            #
            # Disable swap file, change to zram
            #
            sudo apt install zram-tools
            echo "[+] Disabling swap and enabling zram..."
            sudo apt purge -y dphys-swapfile # Xóa hoàn toàn phần tương tác file swap
            sudo rm -f /var/swap # Tắt swap file để bảo vệ thẻ nhớ
            sudo bash -c 'cat <<EOF > /etc/default/zramswap
ALGO=lz4
PERCENT=50
EOF'
            sudo systemctl restart zramswap # Tái khởi tạo zram nhằm tối ưu bộ nhớ

            shift
            ;;
        --force-cpu)
            #
            # Force CPU performance
            #
            sudo apt install linux-cpupower
            sudo bash -c 'cat <<EOF > /etc/systemd/system/cpupower-performance.service
[Unit]
Description=Set CPU governor to performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/cpupower frequency-set -g performance

[Install]
WantedBy=multi-user.target
EOF' # Tạo một service để khởi động mỗi khi khởi động
            sudo systemctl daemon-reload # Reload daemon
            sudo systemctl enable cpupower-performance.service # Mở service mới viết
            sudo systemctl start cpupower-performance.service # Khởi động service mới tạo

            BOOT_CONFIG="/boot/firmware/config.txt"
            if [ ! -f "$BOOT_CONFIG" ]; then
                BOOT_CONFIG="/boot/config.txt"
            fi
            if ! grep -q "arm_freq=1350" "$BOOT_CONFIG"; then
            sudo bash -c "cat <<EOF > \"$BOOT_CONFIG\"
arm_freq=1350
core_freq=500
over_voltage=4
temp_limit=80
EOF"
            fi
            shift
            ;;
        *)
            usage
            ;;
    esac
done
