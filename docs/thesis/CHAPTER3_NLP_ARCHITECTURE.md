# Chapter 3 — NLP Architecture (Filter+Sort)

## 3.x Hệ thống Đề xuất Nguyên liệu Nấu ăn

### 3.x.1 Tổng quan

Hệ thống đề xuất nguyên liệu cho phép người dùng nhập tên món ăn và nhận danh sách nguyên liệu cần mua thêm dựa trên tồn kho hiện tại. Pipeline gồm 3 bước:

```
Tên món ăn → [Bước 1: Lọc + Sắp xếp] → [Bước 2: Trích xuất nguyên liệu] → [Bước 3: Bù Trừ với tồn kho] → Danh sách mua sắm
```

### 3.x.2 Bước 1: Lọc và Sắp xếp Công thức (Filter + Sort)

Bước này tìm kiếm công thức phù hợp từ cơ sở dữ liệu 2470 món ăn Việt Nam. Thay vì sử dụng mô hình CRF (Conditional Random Field) phức tạp, hệ thống áp dụng chiến lược kết hợp đơn giản:

```
Đầu vào: tên món (chuỗi)
  │
  ├─ Chiến lược 1: Khớp từ khóa (Keyword Matching)
  │   └─ substring match: tìm tất cả công thức chứa chuỗi truy vấn
  │   └─ VD: "gà" → ["gà kho gừng", "gà xào sả ớt", "cháo gà", ...]
  │
  ├─ Chiến lược 2: Khớp mờ (Fuzzy Matching - difflib)
  │   └─ Sử dụng `difflib.get_close_matches` với cutoff = 0.4
  │   └─ Xử lý lỗi chính tả, biến thể
  │   └─ VD: "goi tron" → "gỏi trộn khô mực", "gỏi trộn hoa cải"
  │
  └─ Kết hợp & Sắp xếp
      └─ Gộp kết quả, loại trùng
      └─ Sắp xếp theo độ dài (ưu tiên tên ngắn, chính xác)
      └─ Giới hạn top 5
```

**Độ phức tạp**: O(n) với n = 2470 tên món (trung bình ~3.2ms trên Raspberry Pi 4B).

### 3.x.3 Bước 2: Trích xuất Nguyên liệu (NER)

Sau khi xác định được tên món, hệ thống trích xuất danh sách nguyên liệu từ văn bản công thức. Quá trình này sử dụng:

1. **Tokenization** (pyvi): Tách câu thành các token tiếng Việt
2. **Feature Extraction**: Trích xuất đặc trưng ngữ pháp (POS tags, hình thái, ngữ cảnh)
3. **BIO Tagging**: Gán nhãn B-I-O (Begin - Inside - Outside) cho từng token
4. **Kết hợp**: Nhóm các token được gán nhãn thành nguyên liệu hoàn chỉnh

```
VD: "Thịt bò 300g"
  Token: ["Thịt_bò", "300g"]
  POS:   ["Noun", "Num"]
  Tags:  ["B-ingredient", "I-quantity"]
  → {"name": "Thịt bò", "quantity": "300g"}
```

Bước này sử dụng mô hình CRF đã được huấn luyện trên tập 250 công thức với F1-score 95.03%.

### 3.x.4 Bước 3: Bù Trừ với Tồn kho

Sau khi có danh sách nguyên liệu, hệ thống thực hiện:

```
Danh sách nguyên liệu (FSS-Request)
  └─ So sánh từng nguyên liệu với tồn kho (FSS-Inventory)
      ├─ Nếu có trong tồn kho và đủ → "available"
      ├─ Nếu có nhưng thiếu → "insufficient" (ghi rõ số lượng thiếu)
      └─ Nếu không có → "missing"
  └─ Kết quả: Danh sách mua sắm (FSS-Recommend)
```

### 3.x.5 Kiến trúc D-Bus

```
[MMM-FSS-Recommend UI]
  │
  ├─ (socket.io) → [node_helper.js]
  │                   │
  │               (stdin) → [recommend_dbus_listener.py]
  │                              │
  │                         D-Bus call → RecommendDaemon.GenerateShoppingList()
  │                              │               │
  │                              │          RecipeAnalyzerEngine (NLP)
  │                              │               │
  │                              │          D-Bus call → DBDaemon.GetInventory()
  │                              │               │
  │                              │          Bù Trừ → result
  │                              │
  │               (stdout) ← JSON result
  │                   │
  └─ (socket.io) ←───┘
```

### 3.x.6 Đánh giá Hiệu năng

| Chỉ số | CRF (cũ) | Filter+Sort (mới) |
|--------|----------|-------------------|
| Thời gian tìm kiếm (trung bình) | 2.1ms | 3.2ms |
| Bộ nhớ model | 0.09 MB | 0 MB (không cần model) |
| Phụ thuộc | scikit-crfsuite, joblib | difflib (stdlib) |
| Khả năng xử lý lỗi chính tả | Không | Có (fuzzy matching) |
| Tập dữ liệu | 250 recipes | 2470 recipes |
| F1-score trích xuất NL | 95.03% | 95.03% (giữ nguyên CRF) |

> **Ghi chú**: CRF chỉ được sử dụng ở Bước 2 (trích xuất nguyên liệu). Bước 1 (tìm kiếm công thức) hoàn toàn không phụ thuộc vào CRF, giúp giảm độ phức tạp tổng thể của hệ thống.
