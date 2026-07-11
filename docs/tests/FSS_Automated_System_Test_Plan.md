# FSS Automated System Test Plan
**Version**: 1.1
**Target Environment**: Raspberry Pi 4B / WSL (Ubuntu)

## 1. Overview
Tài liệu này mô tả chi tiết các kịch bản kiểm thử tích hợp tự động (Automated Integration/E2E Tests) cho toàn bộ hệ thống Fridge Supervisor System (FSS). Bộ test sử dụng Python `pytest` và tập trung vào việc kiểm thử khả năng giao tiếp liên tiến trình (IPC) qua D-Bus cũng như tính toàn vẹn của dữ liệu trong các file SQLite (`/opt/fss/data`).

## 2. Test Architecture
- **Framework**: `pytest`
- **Location**: `tests/system_tests/`
- **Runner**: `tools/run_e2e_tests.sh` (yêu cầu quyền `sudo` để truy cập System D-Bus).
- **Markers**:
  - `@pytest.mark.health`: Các test kiểm tra sức khỏe hạ tầng cơ bản.
  - `@pytest.mark.dbus`: Các test phụ thuộc vào D-Bus System Bus.
  - `@pytest.mark.e2e`: Các test chạy end-to-end xuyên suốt các Daemon.

## 3. Test Phases & Scenarios

---

### Phase 1: Health Checks (`test_01_health_check.py`)
**Mục tiêu:** Đảm bảo các hạ tầng cơ bản (DB) và các tiến trình nền của FSS đã sẵn sàng chạy trước khi tiến hành test nghiệp vụ.

**Yêu cầu chuẩn bị:**
- Đã chạy script setup hệ thống (`setup.sh`).
- Cấu trúc thư mục `/opt/fss/data` đã được cấp quyền khởi tạo.
- Daemon `fss-db` (DBDaemon) đang chạy trên nền hệ thống.

**Các bước thực hiện:**
1. Trích xuất đường dẫn của 4 file DB (Data, Inventory, Request, Recommend). Kiểm tra sự tồn tại và kích thước (dung lượng) của các file này.
2. Gọi lệnh truy vấn D-Bus hệ thống (`org.freedesktop.DBus.ListNames`) để liệt kê tất cả các dịch vụ đang chạy trên System Bus.
3. So khớp xem `vn.edu.uit.FSS.DBDaemon` có nằm trong danh sách trả về hay không.

**Kết quả cần đạt được:**
- *Bước 1*: Cả 4 file SQLite phải tồn tại (`os.path.exists`) và có dung lượng lớn hơn 0 bytes.
- *Bước 2 & 3*: Lệnh `dbus-send` thực thi thành công (Exit Code 0). Dịch vụ `vn.edu.uit.FSS.DBDaemon` được xác nhận đang chiếm giữ kênh D-Bus hệ thống.

---

### Phase 2: Inventory Pipeline (`test_02_inventory_pipeline.py`)
**Mục tiêu:** Kiểm thử E2E quá trình FRTApp nhận diện thực phẩm, truyền qua D-Bus và được DBDaemon lưu vào Database thành công.

**Yêu cầu chuẩn bị:**
- Hoàn thành xuất sắc Phase 1.
- `DBDaemon` đang ở trạng thái IDLE và lắng nghe System Bus.
- Cài đặt package `sdbus-python` trong test environment.

**Các bước thực hiện:**
1. **Kiểm thử Add Food:**
   - Đọc số lượng hiện tại của món `test_apple` trong SQLite `FSS_Inventory.db`.
   - Chạy script giả lập `vn.edu.uit.FSS.FRTApp` phát tín hiệu `FoodDetected` qua D-Bus mang payload `{"id": "test_apple", "qty": 2}`.
   - Chờ 2 giây cho DBDaemon xử lý. Truy vấn lại SQLite.
2. **Kiểm thử Remove Food:**
   - Nếu số lượng `test_apple` nhỏ hơn 1, tự động thêm 2 món để lấy dữ liệu test.
   - Phát tín hiệu `FoodDetected` với payload `{"id": "test_apple", "qty": -1}`.
   - Chờ 2 giây và truy vấn lại SQLite.
   - Dọn dẹp lại dữ liệu test (reset số lượng `test_apple` về 0).

**Kết quả cần đạt được:**
- *Bước 1*: Số lượng `test_apple` truy vấn lần hai trong DB phải bằng đúng (Số lượng ban đầu + 2).
- *Bước 2*: Số lượng `test_apple` truy vấn lần hai trong DB phải bị trừ đi chính xác 1 đơn vị. Việc dọn dẹp cuối phiên thành công không để lại dữ liệu rác.

---

### Phase 3: Recommendation Pipeline (`test_03_recommend_pipeline.py`)
**Mục tiêu:** Kiểm thử luồng gọi yêu cầu phân tích công thức món ăn đến RecommendDaemon và lưu kết quả danh sách mua sắm.

**Yêu cầu chuẩn bị:**
- Tiến trình `RecommendDaemon` phải đang chạy và đăng ký thành công dịch vụ `vn.edu.uit.FSS.RecommendDaemon`.
- Database `FSS-Recommend.db` không bị khóa (locked).

**Các bước thực hiện:**
1. **Kiểm thử Get Available Recipes:**
   - Dùng subprocess gọi D-Bus method `GetAvailableRecipes` của `RecommendDaemon`.
   - Thu thập chuỗi JSON trả về.
2. **Kiểm thử Generate Shopping List:**
   - Tạo ngẫu nhiên một `batch_id` (VD: `test_batch_123456`).
   - Gọi D-Bus method `GenerateShoppingList` của `RecommendDaemon` truyền vào "Mock Recipe" và `batch_id`.
   - Đợi thuật toán NLP xử lý và chèn dữ liệu vào cơ sở dữ liệu (~ 2 giây).
   - Truy vấn file `FSS-Recommend.db` bảng `recommendation_log` để kiểm tra sự tồn tại của `batch_id`.

**Kết quả cần đạt được:**
- *Bước 1*: Trả về dữ liệu dạng `string` chứa JSON array hợp lệ, không ném exception time-out.
- *Bước 2*: Lệnh gọi qua D-Bus thành công. Query DB trả về đúng dữ liệu `batch_id` đã truyền vào chứng minh RecommendDaemon đã nhận, xử lý Bù Trừ và ghi log đầy đủ.

## 4. Execution
```bash
# Kích hoạt quá trình kiểm thử tự động toàn diện
sudo bash tools/run_e2e_tests.sh
```
*Lưu ý: Script sẽ tự động kích tra quyền `sudo`, kích hoạt venv của `DBDaemon` và kiểm tra/cài đặt tự động framework `pytest` nếu bị thiếu.*
