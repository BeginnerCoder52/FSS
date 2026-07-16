# Electron App (MagicMirror UI)

**Ngôn ngữ:** Node.js (JS/HTML/CSS) & Python
**Chức năng chính:** Giao diện người dùng đồ họa (GUI) chính của FSS, được xây dựng và tùy biến dựa trên nền tảng hiển thị MagicMirror².

Đây là trung tâm tương tác trực quan với người dùng, bao gồm 2 lớp (layer) cốt lõi:
- **Lớp hiển thị Electron (Frontend)**: Tích hợp các module giao diện như hiển thị Nhiệt độ/Độ ẩm (`MMM-FSS-Env`), Cửa và trạng thái giám sát (`MMM-FSS-Monitor`), Tồn kho thực phẩm (`MMM-FSS-Inventory`), cũng như Camera trực tiếp (`MMM-FSS-LivePreview`).
- **Lớp Python Bridge (Backend tích hợp)**: Sử dụng các script Python cục bộ (chạy ngầm thông qua thư viện `python-shell` của Node) để làm "cầu nối" (Bridge). Các script này lắng nghe tín hiệu D-Bus từ các C/Python Daemon khác (Sensor, DB, AI) sau đó biên dịch thành các sự kiện Socket.IO để UI render lại trên màn hình với tốc độ gần như theo thời gian thực (Zero-latency UI updates).
