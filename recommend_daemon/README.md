# Recommend Daemon (Python)

**Vai trò chính:** Não bộ kinh doanh (Business Logic) và Đề xuất mua sắm (Shopping Recommender).

## Luồng thực thi (Execution Flow)
1. **`main.py`**: Khởi tạo D-Bus interface (`vn.edu.uit.FSS.RecommendDaemon`) để chờ các request gửi từ MagicMirror UI.
2. **Nạp dữ liệu tĩnh**: Khởi động lazy-load module NLP (`RecipeAnalyzerAPI.py` từ thư mục `recipe_extractor`) vào bộ nhớ.
3. **`DbusInterface.py`**: Tiếp nhận Method Call từ UI (VD: `GenerateShoppingList(recipe_name)`).
4. **`RecommendEngine.py`**:
   - Gửi yêu cầu truy vấn đến `DBDaemon` để lấy tổng lượng thức ăn Tồn Kho Hiện Tại (Inventory).
   - Truyền tên món ăn cho NLP Model để trích xuất ra nguyên liệu cấu thành.
   - **Thuật toán Bù-Trừ (Comparison Method)**: Trừ các nguyên liệu yêu cầu (FSS-Request) cho thức ăn tồn kho (FSS-Inventory) để tính ra định lượng nguyên liệu còn thiếu.
5. **`RecommendDbManager.py`**: Lưu trữ kết quả thuật toán bù trừ trên vào `FSS-Recommend.db` và trả về kết quả qua tín hiệu D-Bus (`RecommendationUpdated`).
