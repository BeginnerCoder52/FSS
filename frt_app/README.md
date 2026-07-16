# FRT App (Food Recognition Technology)

**Ngôn ngữ:** C/C++ (Camera Core) và Python (AI Core)
**Chức năng chính:** Ứng dụng Hybrid chịu trách nhiệm xử lý luồng Video và nhận diện thực phẩm tự động.

Do việc nhận diện hình ảnh cần tối ưu hóa rất lớn về tài nguyên, FRT App được chia làm 2 tiến trình cốt lõi nhằm chia sẻ tác vụ:
1. **Camera Core (C/C++)**: 
   - Đảm nhiệm việc truy cập camera vật lý (`/dev/video0`) thông qua API V4L2.
   - Trực tiếp ghi frame ảnh thô (raw bytes) vào bộ nhớ dùng chung POSIX Shared Memory (`/fss_video_frame`), tránh việc phải sao chép qua lại trong RAM.
2. **AI Core (Python)**:
   - Đọc dữ liệu ảnh từ POSIX Shared Memory.
   - Đưa dữ liệu qua ma trận NumPy, xử lý trước và chạy thuật toán suy luận YOLOv11 (bằng tflite-runtime).
   - Kết hợp thuật toán ByteTrack để theo dõi, định vị vật thể liên tục qua nhiều khung hình.
   - Khi phát hiện thay đổi (thức ăn được thêm vào/rút ra), AI Core sẽ phát tín hiệu D-Bus `FoodDetected` cho DBDaemon.
