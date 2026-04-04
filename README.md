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

FSS/
├── setup.sh # Script tự động cấu hình môi trường, build C++ và cài Python/Node
├── fss_env_setup.sh # Script cấu hình systemd service và mount /opt/fss vào RAM (tmpfs)
├── docs/ # Chứa tài liệu SAD, SDD, Class Diagram
│
├── drivers/ # Hardware Abstraction Layer (HAL)
│ ├── sensor/
│ │ ├── mc-38/ # Driver cho cảm biến cửa từ tính
│ │ ├── sht3x/ # Driver I2C cho cảm biến nhiệt độ/độ ẩm
│ │ └── vl53l0x/ # Driver I2C cho cảm biến khoảng cách ToF
│ └── usb_web_camera/ # Driver bọc các hàm V4L2 cho Camera
│
├── sensor_daemon/ # [C/C++] Core giao tiếp phần cứng tốc độ cao
│ ├── CMakeLists.txt # File cấu hình build CMake
│ ├── include/ # Header files (_.h, _.hpp)
│ │ ├── SensorDaemonApp.hpp
│ │ ├── InputProcessor.hpp # Đọc I2C SHT3x, GPIO Door/Distance Sensor
│ │ ├── OutputProcessor.hpp # Bắn ZMQ IPC
│ │ ├── SystemdWatchdog.hpp
│ │ └── SdbusInterface.hpp # Giao tiếp D-Bus C++ (sdbus-c++)
│ └── src/ # Source files (\*.cpp)
│ ├── main.cpp
│ ├── SensorDaemonApp.cpp
│ └── ... (các file implement tương ứng)
│
├── frt_app/ # [C/C++ & Python] Hybrid AI Vision Core
│ ├── cpp_camera_core/ # [C/C++] Xử lý V4L2 và ghi Shared Memory siêu tốc
│ │ ├── CMakeLists.txt
│ │ ├── include/
│ │ └── src/
│ │ ├── main.cpp
│ │ ├── VideoCapture.cpp # Đọc USB Camera qua V4L2 API
│ │ └── ShmWriter.cpp # Ghi mảng byte frame vào /fss_video_frame
│ │
│ └── py_ai_core/ # [Python] Chạy suy luận YOLOv11
│ ├── requirements.txt # ultralytics, numpy, zmq, sdbus-python
│ ├── models/ # Chứa weights YOLO (.pt)
│ └── src/
│ ├── **init**.py
│ ├── main.py
│ ├── FrtDaemonApp.py
│ ├── YoloPipeline.py # Đọc frame từ SHM, chạy model
│ └── SdbusInterface.py# Bắn tín hiệu FoodDetected qua D-Bus
│
├── db_daemon/ # [Python] Data Controller trung tâm
│ ├── requirements.txt # sqlite3, asyncio, zmq, sdbus-python
│ ├── data/ # Nơi chứa db fss_core.db
│ └── src/
│ ├── **init**.py
│ ├── main.py
│ ├── DbDaemonApp.py
│ ├── SqliteManager.py # Cập nhật số lượng thực phẩm
│ ├── PosixShmReader.py # Lấy ảnh lúc có sự kiện đóng cửa
│ ├── DiskFileManager.py # Lưu file vật lý
│ └── DbDbusInterface.py # Phát tín hiệu lên UI (UIUpdateRequired)
│
└── magicmirror/ # [Node.js & Python] UI & Dashboard
├── package.json
├── serveronly/
├── js/
├── config/
│ └── config.js
└── modules/
├── MMM-FSS-Food/ # UI Quản lý thực phẩm
│ ├── MMM-FSS-Food.js # [JS] Render DOM, hiệu ứng Frontend
│ ├── MMM-FSS-Food.css
│ ├── node_helper.js # [JS] Quản lý vòng đời module Node.js
│ └── py_bridge/ # [Python] Script chạy ngầm để hứng IPC/D-Bus
│ ├── requirements.txt
│ └── food_dbus_listener.py # Chuyển D-Bus thành JSON bắn qua stdout cho node_helper
│
└── MMM-FSS-Env/ # UI Giám sát môi trường
├── MMM-FSS-Env.js
├── MMM-FSS-Env.css
├── node_helper.js
└── py_bridge/
├── requirements.txt
└── env_zmq_client.py # Client Python lắng nghe EnvDataUpdated qua ZMQ

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
