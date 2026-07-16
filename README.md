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

```
FSS/
├── fss_profile.conf            # Central configuration profile for paths and user settings
├── setup.sh                    # Unified installer (dependencies, build, venvs, DBus, systemd)
├── fss_env_setup.sh            # Helper script for systemd services (called by setup.sh)
├── startup_fss_system.sh       # Integrated startup (all daemons + systemd watchdog)
├── tools/verify_install.sh     # Post-install verification script
├── docs/                       # Chứa tài liệu SAD, SDD, Class Diagram
│
├── drivers/                    # Hardware Abstraction Layer (HAL)
│   ├── sensor/
│   │   ├── mc-38/              # Driver cho cảm biến cửa từ tính
│   │   ├── sht3x/              # Driver I2C cho cảm biến nhiệt độ/độ ẩm
│   │   └── vl53l0x/            # Driver I2C cho cảm biến khoảng cách ToF
│   └── usb_web_camera/         # Driver bọc các hàm V4L2 cho Camera
│
├── sensor_daemon/              # [C/C++] Core giao tiếp phần cứng tốc độ cao
│   ├── CMakeLists.txt
│   ├── include/
│   │   ├── SensorDaemonApp.hpp
│   │   ├── InputProcessor.hpp
│   │   ├── OutputProcessor.hpp
│   │   ├── SystemdWatchdog.hpp
│   │   └── SdbusInterface.hpp
│   ├── src/
│   │   ├── main.cpp
│   │   ├── SensorDaemonApp.cpp
│   │   └── ...
│   └── tests/
│
├── frt_app/                    # [C/C++ & Python] Hybrid AI Vision Core
│   ├── CMakeLists.txt          # Root build: builds cpp_camera_core + c_tflite_reader
│   ├── cpp_camera_core/        # [C/C++] V4L2 capture + POSIX SHM writer
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   │       ├── main.cpp
│   │       ├── VideoCapture.cpp
│   │       └── ShmWriter.cpp
│   ├── c_tflite_reader/        # [C] Standalone TF Lite C API inference engine
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   │   └── TfliteReader.h
│   │   └── src/
│   │       ├── TfliteReader.c
│   │       └── tflite_reader_test.c
│   └── py_ai_core/             # [Python] YOLOv11 inference + ByteTrack
│       ├── requirements.txt
│       ├── models/
│       └── src/
│           ├── __init__.py
│           ├── main.py
│           ├── FrtDaemonApp.py  # (planned: FrtMain.py in Phase 1)
│           ├── YoloPipeline.py
│           └── SdbusInterface.py
│
├── db_daemon/                  # [Python] Data Controller & IPC Broker
│   ├── requirements.txt
│   └── src/
│       ├── __init__.py
│       ├── main.py
│       ├── DbDaemonMain.py
│       ├── SqliteManager.py
│       ├── PosixShmReader.py
│       ├── DiskFileManager.py
│       └── DbDbusInterface.py
│
├── recipe_extractor/           # [Python] NLP/Recipe Analysis Library (CRF-based NER)
│   ├── requirements.txt
│   ├── data/
│   │   └── recipes/            # ~250 Vietnamese recipes
│   ├── models/                 # fss_ner_crf_optimized.joblib
│   └── src/
│       ├── __init__.py
│       ├── RecipeAnalyzerAPI.py
│       ├── RecipeProcessor.py
│       └── ...
│
├── recommend_daemon/           # [Python] Business Logic Orchestrator
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── RecommendEngine.py  # Bù Trừ algorithm
│   │   ├── RecommendDbManager.py
│   │   └── DbusInterface.py
│   ├── systemd/
│   │   └── recommend_daemon.service
│   └── tests/
│       └── test_recommend_engine.py
│
├── electron_app/               # [Node.js & Python] UI & Dashboard
│   ├── config.json
│   ├── magicmirror/            # Core Electron/MagicMirror app
│   │   ├── package.json
│   │   ├── config/
│   │   │   └── config.js
│   │   └── modules/
│   │       ├── MMM-FSS-Env/          # Môi trường (nhiệt độ/độ ẩm)
│   │       ├── MMM-FSS-Monitor/      # Giám sát cửa & khoảng cách
│   │       ├── MMM-FSS-Inventory/    # Tồn kho thực phẩm
│   │       ├── MMM-FSS-LivePreview/  # Xem trước camera trực tiếp
│   │       ├── MMM-FSS-VirtualKeyboard/ # Bàn phím ảo tìm kiếm
│   │       ├── MMM-FSS-Recommend/    # Gợi ý mua sắm thông minh
│   │       └── MMM-FSS-Notification/ # Thông báo trung tâm
│   └── py_bridge/              # Python D-Bus listeners (relay → socket.io)
│       ├── requirements.txt
│       ├── env_dbus_listener.py
│       ├── monitor_dbus_listener.py
│       ├── inventory_dbus_listener.py
│       ├── live_preview_bridge.py
│       └── recommend_dbus_listener.py
│
├── fss-test/                   # Integration & benchmark tests
│   ├── test-cases.sh
│   ├── test-inference.py
│   ├── models/
│   └── results/
│
├── tests/                      # Phase 1 validation suite
│   ├── run_phase1_tests.py
│   └── unit/
│       └── db_daemon/
│
├── tools/                      # Utility scripts
│   ├── verify_dbus_config.sh
│   └── deploy-model/
│
└── docs/                       # Tài liệu thiết kế
```

## ⚙️ Hướng dẫn Cài đặt & Khởi chạy

Toàn bộ hệ thống được cài đặt thông qua 1 file cấu hình duy nhất: `fss_profile.conf` và script `setup.sh`.

### 1. Cài đặt hệ thống
Bạn có thể cài đặt theo 2 chế độ: Development (chạy thủ công bằng Terminal) hoặc Production (chạy tự động ngầm qua systemd).

**Cài đặt Development (Mặc định)**:
```bash
bash setup.sh
bash tools/verify_install.sh
```

**Cài đặt Production (Raspberry Pi)**:
```bash
FSS_MODE=production bash setup.sh
bash tools/verify_install.sh
```

### 2. Khởi chạy (Chế độ Development)
Sau khi cài đặt xong, bạn có thể mở 6 terminal để khởi chạy độc lập các thành phần, hoặc dùng script tự động:

```bash
# Terminal 1: Chạy Core Sensor (C++)
./sensor_daemon/build/sensor_daemon_exec

# Terminal 2: Chạy Camera Core (C++)
./frt_app/cpp_camera_core/build/camera_core_exec

# Terminal 3: Chạy AI Pipeline (Python)
source frt_app/py_ai_core/venv/bin/activate && python frt_app/py_ai_core/src/main.py

# Terminal 4: Chạy Data Controller (Python)
source db_daemon/venv/bin/activate && python db_daemon/src/main.py

# Terminal 5: Chạy Recommend Daemon (Python)
source recommend_daemon/venv/bin/activate && python recommend_daemon/src/main.py

# Terminal 6: Khởi chạy Giao diện
cd electron_app/magicmirror && npm run start

# --- Hoặc khởi chạy toàn bộ hệ thống tự động ---
bash startup_fss_system.sh
```
