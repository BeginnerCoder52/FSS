# Chapter 4 — Evaluation: Kết quả Thử nghiệm

## 4.x Đánh giá Hệ thống Đề xuất Nguyên liệu

### 4.x.1 Kịch bản Thử nghiệm

Thử nghiệm với 10 món ăn phổ biến, mỗi món được kiểm tra với 3 trạng thái tồn kho khác nhau:

| Kịch bản | Mô tả tồn kho |
|----------|--------------|
| **A** (Đầy đủ) | Tủ lạnh có sẵn tất cả nguyên liệu (mô phỏng sau khi đi chợ) |
| **B** (Một phần) | Tủ lạnh có khoảng 40-60% nguyên liệu (trạng thái thường gặp) |
| **C** (Thiếu nhiều) | Tủ lạnh có <20% nguyên liệu (cần đi chợ) |

### 4.x.2 Bảng So sánh Đề xuất (Recipe Comparison)

#### Gỏi Trộn Khô Mực (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Bưởi | 1 trái | 0 | 1 trái | ✅ Bưởi (1 trái) |
| Mực khô | 1 con (50g) | 1 con | 0 | — |
| Thịt ba chỉ | 100g | 50g | 50g | ✅ Thịt ba chỉ (50g) |
| Tôm tươi | 100g | 100g | 0 | — |
| Cà rốt | 100g | 0 | 100g | ✅ Cà rốt (100g) |
| Rau răm, hành tím | 1 bó | 0 | 1 bó | ✅ Rau răm, hành tím |
| Mè trắng, ớt sừng | 1M | 10g | 0 | — |
| Bánh phồng tôm | 1 gói | 0 | 1 gói | ✅ Bánh phồng tôm |
| Gia vị | Đủ | Đủ | 0 | — |

**Tổng hợp**: 4/9 nguyên liệu thiếu → Cần mua 4 món.

#### Cánh Gà Chiên Sa Tế Tôm (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Cánh gà | 3 cái | 2 cái | 1 cái | ✅ Cánh gà (1 cái) |
| Sa tế tôm | 2M | 0 | 2M | ✅ Sa tế tôm |
| Tôm khô | 20g | 20g | 0 | — |
| Hành lá | 5 cọng | 3 cọng | 2 cọng | ✅ Hành lá (2 cọng) |
| Tỏi băm | 1M | Đủ | 0 | — |
| Ớt sừng | 1 trái | 0 | 1 trái | ✅ Ớt sừng (1 trái) |
| Gia vị | Đủ | Đủ | 0 | — |

**Tổng hợp**: 4/7 nguyên liệu thiếu → Cần mua 4 món.

#### Lẩu Ghẹ Kim Chi (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Nghêu | 1kg | 500g | 500g | ✅ Nghêu (500g) |
| Ghẹ | 2 con (700g) | 0 | 2 con | ✅ Ghẹ (2 con) |
| Bắp bò hoa | 300g | 200g | 100g | ✅ Bắp bò hoa (100g) |
| Kim chi bắp cải | 500g | 1 hộp | 0 | — |
| Nấm kim châm | 200g | 0 | 200g | ✅ Nấm kim châm (200g) |
| Bún gạo | 300g | 300g | 0 | — |
| Củ cải trắng | 1 củ | 0 | 1 củ | ✅ Củ cải trắng |
| Rau tần ô | 1 bó | 0 | 1 bó | ✅ Rau tần ô |
| Gia vị | Đủ | Đủ | 0 | — |

**Tổng hợp**: 6/10 nguyên liệu thiếu → Cần mua 6 món.

#### Bò Kho Dưa Kiệu (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Bắp bò | 300g | 0 | 300g | ✅ Bắp bò (300g) |
| Hành tím băm | 50g | 30g | 20g | ✅ Hành tím (20g) |
| Dưa kiệu | 200g | 0 | 200g | ✅ Dưa kiệu (200g) |
| Ngò gai | 20g | 0 | 20g | ✅ Ngò gai |
| Sữa tươi | 220ml | 500ml | 0 | — |
| Gia vị (cà ri, nghệ) | Đủ | Một phần | Bột nghệ | ✅ Bột nghệ |

**Tổng hợp**: 5/7 nguyên liệu thiếu → Cần mua 5 món.

#### Bún Mè Đen Xào Nghêu (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Bún mè đen | 150g | 0 | 150g | ✅ Bún mè đen |
| Nghêu tươi | 1kg | 300g | 700g | ✅ Nghêu (700g) |
| Bông mướp | 200g | 0 | 200g | ✅ Bông mướp |
| Bông hẹ | 50g | 0 | 50g | ✅ Bông hẹ |
| Ớt chuông đỏ | 1/2 trái | 1 trái | 0 | — |
| Hành tây | 1/2 củ | 1 củ | 0 | — |
| Gia vị | Đủ | Đủ | 0 | — |

**Tổng hợp**: 4/8 nguyên liệu thiếu → Cần mua 4 món.

#### Sụn Heo Xáo Nghệ (4 người)

| Nguyên liệu gốc | Yêu cầu | Tồn kho (B) | Thiếu | Đề xuất mua thêm |
|----------------|---------|-------------|-------|-----------------|
| Sụn heo | 300g | 150g | 150g | ✅ Sụn heo (150g) |
| Mẻ | 2M | 0 | 2M | ✅ Mẻ |
| Mắm tôm | 1/2M | 1M | 0 | — |
| Lá lốt | 1 nhánh | 0 | 1 nhánh | ✅ Lá lốt |
| Cà tím | 1 trái | 2 trái | 0 | — |
| Gia vị (riềng, nghệ) | Đủ | Đủ | 0 | — |

**Tổng hợp**: 3/7 nguyên liệu thiếu → Cần mua 3 món.

### 4.x.3 Thống kê Tổng hợp (10 món ăn, Kịch bản B)

| Món ăn | Tổng NL | Có trong kho | Thiếu | Tỉ lệ thiếu | Số món cần mua |
|--------|---------|-------------|-------|------------|----------------|
| Gỏi Trộn Khô Mực | 9 | 5 | 4 | 44.4% | 4 |
| Cánh Gà Chiên Sa Tế Tôm | 7 | 3 | 4 | 57.1% | 4 |
| Lẩu Ghẹ Kim Chi | 10 | 4 | 6 | 60.0% | 6 |
| Bò Kho Dưa Kiệu | 7 | 2 | 5 | 71.4% | 5 |
| Bún Mè Đen Xào Nghêu | 8 | 4 | 4 | 50.0% | 4 |
| Sụn Heo Xáo Nghệ | 7 | 4 | 3 | 42.9% | 3 |
| Gỏi Chân Gà Tôm Chua | 12 | 7 | 5 | 41.7% | 5 |
| Salad Cua Táo Xanh | 10 | 5 | 5 | 50.0% | 5 |
| Chả Đùm | 12 | 6 | 6 | 50.0% | 6 |
| Salad Dưa Lê | 10 | 4 | 6 | 60.0% | 6 |
| **Trung bình** | **9.2** | **4.4** | **4.8** | **52.2%** | **4.8** |

### 4.x.4 Độ chính xác Đề xuất

| Kịch bản | Đúng (đề xuất đúng NL thiếu) | Sai (đề xuất thừa) | Thiếu (bỏ sót) | Precision | Recall | F1 |
|-----------|------------------------------|-------------------|----------------|-----------|--------|-----|
| A (Đầy đủ) | 0 | 0 | 0 | — | — | — |
| B (Một phần) | 48 | 0 | 2 | 100% | 96% | 0.98 |
| C (Thiếu nhiều) | 62 | 0 | 0 | 100% | 100% | 1.0 |

> **Ghi chú**: Sai sót trong Kịch bản B đến từ việc nguyên liệu có tên không khớp chính xác (vd: "hành tím" trong công thức vs "hành tím tươi" trong tồn kho). Đây là vấn đề về chuẩn hóa danh pháp, không phải lỗi thuật toán Bù Trừ.

## 4.y Đánh giá Phát hiện Bất thường Cảm biến

### 4.y.1 Kịch bản Kiểm tra

| Kịch bản | Mô tả | Kết quả mong đợi |
|----------|-------|-----------------|
| T1: Nhiệt độ bình thường | 4.5°C, độ ẩm 65% | Không cảnh báo |
| T2: Cảnh báo nhiệt độ | 9.2°C (ngưỡng: 8°C) | Signal `TemperatureAnomaly` severity=warning |
| T3: Nguy hiểm nhiệt độ | 13.5°C (ngưỡng: 12°C) | Signal `TemperatureAnomaly` severity=critical |
| T4: Tăng đột biến | 4°C → 8°C trong 30s | Signal `TemperatureAnomaly` severity=unusual |
| T5: Mất kết nối I2C | 4 lần đọc lỗi liên tiếp | Signal `SensorError` |
| T6: Độ ẩm cao | 85% + 7°C | Signal `EnvironmentWarning` |

### 4.y.2 Kết quả Kiểm tra

| Kịch bản | Input | Signal nhận được | Severity | Thời gian phản hồi | Pass |
|----------|-------|-------------------|----------|-------------------|------|
| T1 | 4.5°C, 65% | `EnvironmentDataUpdated` | — | 5000ms (chu kỳ) | ✅ |
| T2 | 9.2°C, 72% | `TemperatureAnomaly` + `EnvironmentDataUpdated` | warning | 150ms (sau khi đọc) | ✅ |
| T3 | 13.5°C, 70% | `TemperatureAnomaly` + `EnvironmentDataUpdated` | critical | 120ms | ✅ |
| T4 | 4→8°C trong 30s (6 mẫu) | `TemperatureAnomaly` | unusual | 30.2s (sau mẫu thứ 6) | ✅ |
| T5 | 4 lần lỗi I2C | `SensorError` | error | 80ms (sau lỗi thứ 4) | ✅ |
| T6 | 85%, 7°C | `EnvironmentWarning` | warning | 200ms | ✅ |

### 4.y.3 Thời gian phản hồi Trung bình

| Loại tín hiệu | Thời gian trung bình |
|---------------|---------------------|
| EnvironmentDataUpdated | 5000ms (theo chu kỳ poll) |
| TemperatureAnomaly (ngưỡng) | 135ms |
| TemperatureAnomaly (đột biến) | 30.2s (cần 6 mẫu) |
| SensorError | 80ms |
| EnvironmentWarning | 200ms |

## 4.z So sánh CRF vs Filter+Sort (Hiệu năng NLP)

| Tiêu chí | CRF-based (trước) | Filter+Sort (nay) |
|----------|------------------|-------------------|
| Phụ thuộc thư viện | scikit-crfsuite, joblib, pyvi, sklearn | difflib (stdlib), pyvi |
| Dung lượng model | 0.09 MB (joblib) | 0 MB |
| Thời gian tải | ~800ms (load + warm-up) | ~50ms (load danh sách tên) |
| Thời gian tìm kiếm | 2.1ms | 3.2ms |
| F1-score trích xuất NL | 95.03% | 95.03% (giữ nguyên CRF) |
| Xử lý lỗi chính tả | Không | Có (fuzzy matching) |
| Bảo trì | Cần retrain nếu thêm data | Không cần retrain |
| Phù hợp với 2470 recipes | Quá mức (overkill) | Vừa đủ (fit-for-purpose) |

> **Kết luận**: Việc thay thế CRF bằng Filter+Sort cho bước tìm kiếm công thức giúp giảm phụ thuộc thư viện, đơn giản hóa kiến trúc mà không làm giảm chất lượng đề xuất. CRF vẫn được giữ lại cho bước trích xuất nguyên liệu (NER), nơi nó thực sự cần thiết.
