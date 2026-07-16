# Fridge Supervisor System (FSS)

Hệ thống nhúng quản lý thực phẩm và giám sát tủ lạnh thông minh, tích hợp AI Vision (YOLOv11), kiến trúc đa tiến trình (C/C++, Python) và giao diện MagicMirror. FSS được thiết kế tối ưu hóa cho Raspberry Pi 4B.

---

## 🚀 Kiến Trúc Đa Ngôn Ngữ (Polyglot Architecture)

Hệ thống tận dụng thế mạnh của từng ngôn ngữ để giải quyết bài toán hiệu năng trên thiết bị nhúng:

1. **SensorDaemon (C/C++)**: Giao tiếp trực tiếp với I2C và GPIO ở cấp độ Kernel thông qua `libsmbus2` và `libgpiod`. Đảm bảo độ trễ thấp nhất (Zero-latency) khi đọc cảm biến, gửi tín hiệu Broadcast qua D-Bus.
2. **FRTApp (Hybrid C/C++ & Python)**:
   - **Camera Core (C/C++)**: Giao tiếp trực tiếp phần cứng camera qua chuẩn V4L2. Ghi mảng byte thô thẳng vào POSIX Shared Memory (`/fss_video_frame`).
   - **AI Core (Python)**: Xử lý inference YOLOv11 bằng `tflite-runtime` (tối ưu hóa INT8) và thuật toán tracking ByteTrack. Giao tiếp với DB qua D-Bus.
3. **DBDaemon (Python)**: Trái tim lưu trữ và luân chuyển dữ liệu. Sử dụng `sqlite3` và Event Loop `asyncio`. Quản lý I/O bất đồng bộ và đóng vai trò IPC Broker (luân chuyển ảnh qua `/opt/fss/`).
4. **RecommendDaemon (Python)**: Điều phối logic nghiệp vụ cốt lõi, gọi API sang NLP Engine (RecipeExtractor) để phân tách nguyên liệu, chạy thuật toán "Bù-Trừ" với Tồn kho thực tế, từ đó sinh ra Danh sách mua sắm.
5. **MagicMirror UI (Node.js & Python)**: Front-end chạy bằng Electron framework. Dùng các Python Bridge Subprocess để bắt tín hiệu D-Bus, truyền tải qua Socket.IO tới Javascript để render giao diện Real-time.

---

## 📁 Cây Thư Mục Toàn Hệ Thống

```text
FSS/
├── fss_profile.conf             # (Cấu hình) Biến môi trường, user, đường dẫn cài đặt
├── FSS_SETUP.sh                 # Script Setup toàn bộ (Cài packages, biên dịch, venvs)
├── FSS_RUN.sh                   # Script Khởi chạy toàn bộ hệ thống (Quản lý PID, monitoring)
├── README.md                    # File thông tin tổng quan hệ thống (Bạn đang đọc)
├── .gitignore                   # Quy tắc bỏ qua file của Git
├── LICENSE                      # Giấy phép mã nguồn
│
├── sensor_daemon/               # [C/C++] Xử lý phần cứng (Nhiệt, Ẩm, Cửa)
│   ├── CMakeLists.txt           # File build C++
│   ├── include/                 # Header files (SensorDaemonMain.hpp,...)
│   └── src/                     # Source files (main.cpp, InputProcessor.cpp,...)
│
├── frt_app/                     # [C/C++ & Python] Nhận diện món ăn (AI)
│   ├── cpp_camera_core/         # Lõi C++ V4L2 đẩy ảnh vào RAM (Shared Memory)
│   ├── c_tflite_reader/         # Lõi C++ TF-Lite C API inference engine
│   └── py_ai_core/              # Lõi Python YOLO Pipeline + ByteTrack
│
├── db_daemon/                   # [Python] Bộ trung chuyển dữ liệu & SQLite
│   ├── requirements.txt         # Package phụ thuộc
│   └── src/                     # main.py, SqliteManager.py, PosixShmReader.py
│
├── recommend_daemon/            # [Python] Logic Gợi ý mua sắm & Bù-Trừ
│   ├── requirements.txt
│   └── src/                     # RecommendEngine.py, DbusInterface.py
│
├── recipe_extractor/            # [Python] Model NLP xử lý Tiếng Việt (NER)
│   ├── models/                  # File trọng số (fss_ner_crf_optimized.joblib)
│   └── src/                     # RecipeAnalyzerAPI.py
│
├── electron_app/                # [Node.js] UI hiển thị trên Màn hình tủ lạnh
│   ├── magicmirror/             # Core MagicMirror (HTML/CSS/JS)
│   └── py_bridge/               # Các script Python đẩy tín hiệu D-bus sang UI
│
├── fss-test/                    # [Test] Benchmark và Integration tests
├── tests/                       # [Test] Validation phase 1 (Database schema tests)
├── tools/                       # [Tools] Các công cụ deploy model, verify config
└── drivers/                     # [Drivers] Hardware Abstraction Layer (HAL)
```

---

## ⚙️ Hướng dẫn Cài đặt Môi trường (FSS_SETUP.sh)

`FSS_SETUP.sh` là script duy nhất bạn cần chạy để build từ đầu (zero). Nó sẽ cài APT dependencies, cấp quyền group phần cứng (`video`, `i2c`, `gpio`), tạo thư mục `/opt/fss`, build C++, tạo môi trường ảo Python venv, và cài node_modules.

**Cú pháp chạy nhanh (Khuyên dùng cho người mới):**
```bash
sudo bash FSS_SETUP.sh
```

**Các Options (Macro) hỗ trợ:**
| Option / Biến Môi trường | Ý nghĩa |
|--------------------------|---------|
| `--skip-models` | Bỏ qua việc tải model YOLO (hữu ích nếu đã có sẵn model trong folder). |
| `--skip-verify` | Bỏ qua bước kiểm tra lại hệ thống (`verify_install.sh`) sau khi cài xong. |
| `FSS_MODE=production` | Đặt trước lệnh chạy. Cài đặt ở chế độ Production (Tự động sinh các Systemd Service để khởi động cùng hệ điều hành). Mặc định là `dev`. |
| `--help` | Hiện bảng hướng dẫn chi tiết. |

*Ví dụ đầy đủ:*
```bash
FSS_MODE=production bash FSS_SETUP.sh --skip-models --skip-verify
```

---

## 🚀 Hướng dẫn Khởi chạy Hệ thống (FSS_RUN.sh)

`FSS_RUN.sh` là trái tim luân chuyển vận hành. Nó gọi tuần tự các daemon theo đúng dependency, lưu trữ PID của chúng để dễ quản lý, và liên tục monitor (theo dõi) nếu tiến trình bị treo sẽ tự động restart.

**Cú pháp chạy nhanh (Khuyên dùng):**
```bash
sudo bash FSS_RUN.sh
```

**Các Options (Macro) hỗ trợ:**
| Option | Ý nghĩa |
|--------|---------|
| `--daemon <list>` | Chạy giới hạn các daemon được chỉ định. Ví dụ: `--daemon sensor,db,camera,ai,recipe,recommend,magicmirror`. |
| `--no-monitor` | Khởi chạy các tiến trình ngầm nhưng KHÔNG bật vòng lặp giám sát (Auto-restart) ở terminal hiện tại. |
| `--status` | Không chạy hệ thống, chỉ kiểm tra các PID hiện hành xem daemon nào đang sống/chết và D-Bus có đăng ký thành công không. |
| `--stop` | Gửi tín hiệu Graceful Shutdown (SIGTERM/SIGKILL) tắt toàn bộ các Daemon FSS đang chạy. |
| `--disable-door-sensor`| Khởi chạy MagicMirror mà bỏ qua (disable) tín hiệu từ cảm biến cửa (tiện lợi khi debug không có phần cứng). |
| `--help` | Hiển thị bảng trợ giúp. |

*Luồng khởi động (Thứ tự nghiêm ngặt):*
1. **SensorDaemon** (Hardware IO)
2. **DBDaemon** (SQLite Ready)
3. **FRT Camera** (V4L2 Stream Ready)
4. **FRT AI** (YOLO Model Ready)
5. **RecipeExtractor** (NLP Ready)
6. **RecommendDaemon** (Business Logic Ready)
7. **MagicMirror UI** (Trình chiếu)

*Ví dụ khởi chạy rút gọn cho Debug AI:*
```bash
bash FSS_RUN.sh --daemon db,camera,ai --no-monitor
```
