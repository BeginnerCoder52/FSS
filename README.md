# Fridge Supervisor System (FSS)

Hệ thống nhúng quản lý thực phẩm và giám sát tủ lạnh thông minh, tích hợp AI Vision (YOLOv11), kiến trúc đa tiến trình (C/C++, Python) và giao diện MagicMirror.

## 🚀 Kiến Trúc Đa Ngôn Ngữ (Polyglot Architecture)

Dựa trên sơ đồ SAD và SDD mới nhất, hệ thống được tối ưu hóa theo ngôn ngữ lập trình để tận dụng tối đa sức mạnh phần cứng:

1. **SensorDaemon (C/C++)**: Giao tiếp trực tiếp với I2C và GPIO ở cấp độ Kernel. Viết bằng C/C++ đảm bảo không có độ trễ (Zero-latency) khi đọc cảm biến, đồng thời tích hợp trực tiếp với `systemd` watchdog.
2. **FRTApp (Hybrid C/C++ & Python)**:
   - **C++ Core**: Đảm nhiệm việc mở V4L2 Camera và đẩy frame thô (Raw bytes) thẳng vào POSIX Shared Memory (`/fss_video_frame`).
   - **Python Core**: Đọc ảnh trực tiếp từ bộ nhớ RAM, đưa qua ma trận NumPy và chạy suy luận YOLOv11 qua `ultralytics`.
3. **DBDaemon (Python)**: Quản lý logic nghiệp vụ và cơ sở dữ liệu. Sử dụng `sqlite3` và `asyncio` để xử lý các luồng sự kiện I/O bất đồng bộ, lưu ảnh vật lý xuống `/opt/fss` và đẩy trạng thái.
4. **MagicMirror UI (Node.js & Python)**: Core UI chạy bằng Electron (JS/HTML/CSS). Các `node_helper.js` sử dụng thư viện `python-shell` để gọi các script Python Bridge cục bộ. Lớp Python này đóng vai trò lắng nghe D-Bus/ZMQ, xử lý payload phức tạp và trả dữ liệu sạch về cho JS render.

## 📁 Cấu Trúc Hệ Thống

_(Tham khảo cây thư mục bên trên)_

## ⚙️ Hướng dẫn Khởi chạy (Dành cho Development)

Sau khi chạy thành công `./setup.sh`, bạn cần mở 5 terminal để khởi chạy độc lập các thành phần:

```bash
# Terminal 1: Chạy Core Sensor (C++)
./sensor_daemon/build/sensor_daemon_exec

# Terminal 2: Chạy Camera Core (C++)
./frt_app/cpp_camera_core/build/camera_core_exec

# Terminal 3: Chạy AI Pipeline (Python)
source frt_app/py_ai_core/venv/bin/activate && python frt_app/py_ai_core/src/main.py

# Terminal 4: Chạy Data Controller (Python)
source db_daemon/venv/bin/activate && python db_daemon/src/main.py

# Terminal 5: Khởi chạy Giao diện
cd magicmirror && npm run start
```
