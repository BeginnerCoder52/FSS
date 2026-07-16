# DB Daemon (Python)

**Vai trò chính:** Data Controller (Điều phối dữ liệu) và IPC Broker (Trung tâm giao tiếp tiến trình) - Không chứa Business Logic.

## Luồng thực thi (Execution Flow)
1. **`main.py` / `DbDaemonMain.py`**: Điểm bắt đầu (Entry point), thiết lập một Event Loop bất đồng bộ `asyncio` để xử lý các I/O task hiệu năng cao.
2. **`SqliteManager.py`**: Khởi tạo cấu trúc các Database (`fss_data.db`, `FSS_Inventory.db`, `FSS_Request.db`). Chịu trách nhiệm thực thi các truy vấn CRUD vào bảng `environment_log`, `door_event_log`, `current_inventory`.
3. **`DbDbusInterface.py`**: 
   - *Lắng nghe (Listen)*: Bắt các tín hiệu Broadcast từ `SensorDaemon` (nhiệt độ/cửa) để lưu trữ. Bắt các tín hiệu từ `RecommendDaemon` hoặc AI.
   - *Phát sóng (Emit)*: Gửi đi `UIUpdateRequired` bất cứ khi nào state thay đổi để cập nhật MagicMirror.
4. **`PosixShmReader.py` & `DiskFileManager.py`**: Khi luồng AI báo có thức ăn nhận diện, tiến trình này đọc dữ liệu raw bitmap JPEG trực tiếp từ Shared Memory (`/fss_video_frame`) và ghi vĩnh viễn xuống ổ cứng nội bộ `/opt/fss/` thay vì lưu vào DB, tối ưu hóa kích thước DB.
