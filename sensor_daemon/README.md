# Sensor Daemon (C/C++)

**Vai trò chính:** Lớp trừu tượng phần cứng (Hardware Abstraction Layer) đảm bảo thu thập dữ liệu với độ trễ thấp (zero-latency).

## Luồng thực thi (Execution Flow)
1. **`main.cpp`**: Khởi tạo tiến trình và gắn bộ xử lý tín hiệu (Signal Handler).
2. **`SensorDaemonApp.cpp`**: Core App đóng vai trò điều phối giữa Input và Output.
3. **`InputProcessor.cpp`**: Chịu trách nhiệm Polling dữ liệu.
   - Gọi `I2cHandler` đọc SHT3x (Nhiệt độ/Độ ẩm) mỗi chu kỳ tĩnh.
   - Gọi `GpioHandler` theo dõi sự thay đổi trạng thái của cảm biến cửa từ (MC-38).
4. **`OutputProcessor.cpp`**: Khi có dữ liệu mới từ InputProcessor, thành phần này nhận trách nhiệm đẩy (Broadcast) tín hiệu lên D-Bus:
   - Các tín hiệu bao gồm `DOOR_OPEN`, `DOOR_CLOSE`, và `EnvironmentDataUpdated`.
5. **`SystemdWatchdog.cpp`**: Đảm bảo daemon sống ổn định bằng cách giao tiếp với hệ thống khởi động systemd để ngăn chặn treo tiến trình (systemd watchdog ping).
