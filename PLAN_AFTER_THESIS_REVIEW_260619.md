# Plan After Thesis Review — 26/06/19

> Based on teacher feedback on the graduation thesis (Khóa luận tốt nghiệp).
> Project: **DEVELOPMENT OF AN AI-INTEGRATED APPLICATION TO SUPPORT FOOD MANAGEMENT AND REFRIGERATOR ENVIRONMENT MONITORING**

---

## Table of Contents

1. [NLP Pipeline — Replace CRF NER with Filter + Sort](#1-nlp-pipeline--replace-crf-ner-with-filter--sort)
2. [Sensor Daemon — Temperature Anomaly Detection](#2-sensor-daemon--temperature-anomaly-detection)
3. [MagicMirror — Clickable Recipe Suggestion Chips](#3-magicmirror--clickable-recipe-suggestion-chips)
4. [Recipe Download via QR Code](#4-recipe-download-via-qr-code)
5. [Thesis Documentation Updates](#5-thesis-documentation-updates)
6. [YOLO/FRT Pipeline — Friend's Tasks](#6-yolofrt-pipeline--friends-tasks)
7. [Teacher Feedback Cross-Reference](#7-teacher-feedback-cross-reference)

---

## 1. NLP Pipeline — Replace CRF NER with Filter + Sort

### Teacher feedback

> *"Nhánh xử lý ngôn ngữ tự nhiên đang sử dụng ngôn ngữ mô tả công nghệ không hợp lý (công nghệ quá lớn dùng để xử lý một tác vụ quá nhỏ) => nên thay đổi thành filter và sort"*

### Problem

The current pipeline uses a CRF (Conditional Random Fields) model — a Machine Learning approach — to extract ingredients from recipe text. However, the 2470 recipe JSON files already store ingredients in a structured format (`normal_ingredients: ["Bưởi : 1 trái", ...]`). Running an ML model on pre-structured data is overkill:

- Model: 0.09 MB `fss_ner_crf_optimized.joblib`
- Dependencies: `sklearn-crfsuite`, `pyvi` (Vietnamese tokenizer), `joblib`
- Inference: ~3.22ms per recipe (unnecessary since data is already parsed)
- Memory: <100MB at runtime for a simple dictionary lookup

### Solution (implement in 10 days)

Remove the CRF model entirely. Replace processing with three steps:

**Filter**: Look up the recipe name in the loaded dictionary (O(1) hash lookup).

**Parse**: Split each ingredient string on `" : "` delimiter:
```
"Bưởi : 1 trái" → ingredient="Bưởi", quantity="1 trái"
"Mực khô : 1 con (50g)" → ingredient="Mực khô", quantity="1 con (50g)"
```
If no delimiter found, quantity defaults to `"1"`.

**Sort**: Sort ingredients alphabetically by name for consistent display.

### Output format change

The current output returns only parsed `{ingredient, quantity}` pairs. The new output returns the **full original recipe data** including all fields from the JSON file:

```json
{
    "status": "SUCCESS",
    "dish": "gỏi trộn khô mực",
    "original_ingredients": ["Bưởi : 1 trái", "Mực khô : 1 con (50g)", ...],
    "original_spices": ["Hạt nêm Aji-ngon® Heo", ...],
    "serving": "4 người",
    "times": "30 Phút",
    "difficulty": "Dễ",
    "process": ["Tôm luộc chín...", ...],
    "cook": ["Pha nước trộn...", ...],
    "usage": ["Bày gỏi ra dĩa...", ...],
    "tips": ["Chọn bưởi chưa chín hẳn...", ...],
    "processing_time_ms": 0.01
}
```

This preserves the complete recipe for:
- Download to phone (QR code)
- Comparison between original and suggested recipe (thesis evidence)
- Future LLM integration

### Files to modify

| File | Action | Description |
|------|--------|-------------|
| `recipe_extractor/src/RecipeAnalyzerAPI.py` | Rewrite | Remove CRF model, BIO tags, feature extraction, NER inference. Replace with filter + parse + sort on structured JSON data |
| `recipe_extractor/src/RecipeProcessor.py` | Trim | Remove `tokenize_vietnamese()`, `extract_features()`, `sentence_to_features()`. Keep `remove_special_characters()`, `normalize_unicode()` |
| `recipe_extractor/src/recipe_extractor_main.py` | Modify | Remove `NLP_MODEL_PATH`, remove lazy CRF engine loading. Engine now only needs `recipe_db_path` |
| `recipe_extractor/requirements.txt` | Modify | Remove `sklearn-crfsuite`, `pyvi`, `joblib`. Keep only `sdbus` |
| `recipe_extractor/models/fss_ner_crf_optimized.joblib` | Delete | No longer used in production (keep `FSS_NLP.ipynb` as thesis reference) |
| `recipe_extractor/tests/test_recipe_analyzer.py` | Rewrite | Remove CRF-specific tests (BIO schema, word2features, sent2features, model loading). Add tests for filter+parse+sort logic |
| `recommend_daemon/src/RecommendEngine.py` | Modify | Lines 55-62: change from `nlp_result.get("ingredients", [])` to parsing `original_ingredients` strings by splitting on `" : "` |

### RecommendDaemon impact

The `generate_shopping_list()` method currently expects `ingredients` as `[{ingredient, quantity}]`. With the new format, it must parse `original_ingredients` raw strings:

```python
# Old (removed):
ingredients = nlp_result.get("ingredients", [])

# New (simple string parsing):
raw_strings = nlp_result.get("original_ingredients", [])
ingredients = []
for item_str in raw_strings:
    parts = item_str.split(" : ", 1)
    name = parts[0].strip()
    qty = parts[1].strip() if len(parts) > 1 else "1"
    ingredients.append({"ingredient": name, "quantity": qty})
```

The rest of the Bù Trừ algorithm (inventory comparison, classification into available/needed/missing) is unchanged.

### Thesis justification

> *"Dữ liệu 2470 công thức nấu ăn đã được lưu trữ dưới dạng JSON có cấu trúc với trường `normal_ingredients` chứa nguyên liệu và số lượng. Do đó, việc sử dụng mô hình CRF (Conditional Random Field) để trích xuất thực thể là không cần thiết. Nhóm quyết định thay thế bằng cơ chế filter (tra cứu tên món) và sort (sắp xếp nguyên liệu) kết hợp với xử lý chuỗi đơn giản (tách bằng delimiter `": "`). Giải pháp này giảm kích thước dependency từ 3 thư viện ML (sklearn-crfsuite, pyvi, joblib) xuống còn 0, thời gian xử lý từ 3.22ms xuống dưới 0.1ms, và loại bỏ hoàn toàn rủi ro bảo trì mô hình."*

---

## 2. Sensor Daemon — Temperature Anomaly Detection

### Teacher feedback

> *"Chưa nêu ra được chi tiết tính năng giám sát môi trường cụ thể là giám sát những gì mà mới chỉ thực hiện hiển thị số liệu thôi. Có thể giám sát nhiệt độ bất thường do bỏ nhiều đồ, hoặc là thất thoát nhiệt do cửa mở..."*

### Problem

The current SensorDaemon reads sensor values (temperature, humidity, distance, door state) and broadcasts them via D-Bus, but performs **zero analysis** on the data. It is a data acquisition pipeline, not a monitoring system.

What exists: raw data display only.
What's missing: any form of anomaly detection, threshold alerts, or event detection.

### Solution (implement in 10 days)

Create a `TemperatureMonitor` class that analyzes temperature readings in real-time and emits D-Bus alerts when anomalies are detected.

### Detection rules

| Rule | Condition | Trigger | D-Bus Signal |
|------|-----------|---------|-------------|
| **LOAD_WARM_FOOD** | ΔT > +2°C within 10s window on primary sensor | Sudden temperature rise from placing warm food in fridge | `TemperatureAnomaly` with type `LOAD_WARM_FOOD` |
| **FRIDGE_OVERHEATING** | Primary temp > 8°C for 3 consecutive samples (15s sustained) | Fridge compartment too warm | `TemperatureAnomaly` with type `FRIDGE_OVERHEATING` |
| **FREEZER_WARNING** | Secondary temp > -15°C | Freezer losing cooling | `TemperatureAnomaly` with type `FREEZER_WARNING` |

### Algorithm

```
Rolling buffer: deque<float> temp_history (max 10 readings = 50s window)
Rolling buffer: deque<float> temp2_history (max 10 readings = 50s window)

On each env poll (every 5s):
1. Append primary temp to temp_history
2. Append secondary temp to temp2_history
3. If buffer has ≥3 samples:
   a. Rate-of-change: slope = (temp[-1] - temp[0]) / (N_samples * 5s)
   b. If slope > 0.4 °C/s → LOAD_WARM_FOOD
   c. If all last 3 samples > 8°C → FRIDGE_OVERHEATING
   d. If all last 3 samples (temp2) > -15°C → FREEZER_WARNING
4. Emit signal ONLY on state transition (normal→alert, alert→normal)
   Prevents alert spam
```

### D-Bus signal format

```
Signal: TemperatureAnomaly
Payload: JSON string
{
    "type": "LOAD_WARM_FOOD",
    "temp_c": 25.5,
    "delta_c": 3.2,
    "duration_s": 10,
    "sensor": "primary",
    "timestamp": 1718000000
}
```

### Files to create/modify

| File | Action | Description |
|------|--------|-------------|
| `sensor_daemon/include/TemperatureMonitor.hpp` | Create | Header: `TemperatureMonitor` class with rolling buffer, threshold constants, state machine (NORMAL / WARNING / CRITICAL) |
| `sensor_daemon/src/TemperatureMonitor.cpp` | Create | Implementation: sliding window analysis, rate-of-change computation, state transition logic |
| `sensor_daemon/include/SensorDaemonMain.hpp` | Modify | Add `unique_ptr<TemperatureMonitor>` member, add `anomaly_check_rate_ms` config (default: every env poll) |
| `sensor_daemon/src/SensorDaemonMain.cpp` | Modify | In `process_environment_data()`: after polling, feed data to TemperatureMonitor. Handle anomaly result → call OutputProcessor |
| `sensor_daemon/include/OutputProcessor.hpp` | Modify | Add `broadcast_temperature_anomaly(type, details)` |
| `sensor_daemon/src/OutputProcessor.cpp` | Modify | Implement: format JSON string, call D-Bus interface |
| `sensor_daemon/include/SensorDbusInterface.hpp` | Modify | Add `emit_temperature_anomaly(json_string)` |
| `sensor_daemon/src/SensorDbusInterface.cpp` | Modify | Register `TemperatureAnomaly` signal with string payload |
| `sensor_daemon/CMakeLists.txt` | Modify | Add `TemperatureMonitor.cpp` to `add_executable` sources |

### Thesis justification

> *"Khác với các hệ thống giám sát chỉ hiển thị số liệu cảm biến thô, nhóm đã phát triển mô-đun TemperatureMonitor với cơ chế phân tích dựa trên cửa sổ trượt (sliding window) để phát hiện ba dạng bất thường: (1) tăng nhiệt đột biến do bỏ thực phẩm mới, (2) tủ lạnh quá nhiệt >8°C kéo dài, (3) ngăn đông mất nhiệt >-15°C. Mỗi bất thường được phát tán qua D-Bus signal kèm thông tin chi tiết (nhiệt độ hiện tại, mức chênh lệch, thời gian kéo dài) để UI có thể hiển thị cảnh báo cụ thể thay vì chỉ con số."*

---

## 3. MagicMirror — Clickable Recipe Suggestion Chips

### Teacher feedback

> *"Tính năng đề xuất nguyên liệu chưa đủ tính bất ngờ... cần đặt vấn đề nếu có một món ăn ở ngoài cái database của em thì người dùng sẽ thêm món ăn đó vào ra làm sao?"*

Also indirectly: suggestions for misspelled / out-of-database recipes should be visible and clickable.

### Problem

Currently, the only way to search a recipe is:
1. Click the input row
2. Full-screen keyboard opens
3. Type the recipe name
4. Press "SEND!"
5. Wait for result

If the recipe is misspelled or not found, the error is silently logged to console. No suggestions are shown to the user.

### Solution (implement in 10 days)

Add a grid of **clickable recipe suggestion chips** below the input search bar. These appear before any search is performed, showing popular recipes from the available list.

### UI layout

```
┌─────────────────────────────────────┐
│ [🔍 Nhập tên món ăn...]             │  ← existing input row
├─────────────────────────────────────┤
│ Gợi ý nhanh:                        │
│ [Phở bò] [Bún chả] [Cơm tấm]        │  ← NEW: clickable chips (max 5)
│ [Bánh mì] [Hủ tiếu] [Xem thêm ▾]    │
└─────────────────────────────────────┘
```

### Behavior

- On module load: randomly sample 5 recipes from `availableRecipes[]` (already populated on startup)
- On chip click: immediately trigger recipe search (same as typing and pressing SEND)
- "Xem thêm" button: rotate to next 5 random recipes
- Chips use the same touch-friendly styling as the rest of the UI (min 44×44px target, dark theme, rounded pills)
- Chips are re-randomized on each `updateDom()` call

### Files to modify

| File | Action | Description |
|------|--------|-------------|
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.js` | Modify | Add `this.suggestedRecipes` array, shuffle logic, chip rendering in `getDom()`, click handler to trigger search |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.css` | Modify | Add `.fss-chip-grid`, `.fss-chip` CSS classes (rounded pills, dark bg, hover/active states, max 5 per row) |

### No backend changes needed

The `availableRecipes` list is already populated on module startup via the existing `GET_RECIPES` → `RECIPES` socket flow.

### Thesis justification

> *"Để cải thiện trải nghiệm người dùng, nhóm bổ sung gợi ý món ăn dạng chip có thể nhấp được bên dưới thanh tìm kiếm. Các chip này hiển thị ngẫu nhiên 5 món từ database 2470 công thức, cho phép người dùng khám phá món ăn và tìm kiếm ngay lập tức chỉ với một chạm, tương tự cơ chế gợi ý tìm kiếm trên các nền tảng thương mại điện tử."*

---

## 4. Recipe Download via QR Code

### Teacher feedback

> *"giải pháp nhóm đặt ra chưa mang tính thực tiễn, chưa gắn với end-user"*

### Problem

The system runs on a Raspberry Pi with a MagicMirror display. After searching a recipe, the user sees the ingredient list on screen but has no way to take it with them (e.g., to go grocery shopping). Writing it down manually is impractical.

### Solution (implement in 10 days)

Add a "📱 Tải về" (Download) button after each recipe search. When clicked, the system generates a QR code encoding the full recipe as plain text. The user scans the QR code with their phone camera (most modern phones have built-in QR scanners) and saves the recipe as a `.txt` file.

### Flow

```
Search result displayed
  → "📱 Tải về" button appears below shopping list
  → On click: send GET_RECIPE_DETAIL to Python bridge
  → Python bridge:
      1. Receives recipe name
      2. Formats recipe as human-readable plain text
      3. Generates QR code using python-qrcode library
      4. Returns base64-encoded PNG image
  → Frontend displays QR in overlay modal
  → User scans with phone camera → reads recipe on phone
  → Overlay auto-closes after 30s or tap outside
```

### QR code text format

```
=== MÓN: Phở Bò ===
📋 Khẩu phần: 4 người
⏱ Thời gian: 45 Phút
📊 Độ khó: Trung bình

🥘 NGUYÊN LIỆU CHÍNH:
• Bánh phở: 1 kg
• Thịt bò: 500g
• ...

🧂 GIA VỊ:
• Hạt nêm
• Muối
• ...

📝 SƠ CHẾ:
1. ...

🔥 NẤU:
1. ...

🍽 DÙNG:
1. ...

💡 MẸO:
• ...
```

### QR code specs

| Parameter | Value |
|-----------|-------|
| Library | `python-qrcode` (`qrcode[pil]`) |
| Version | Auto (2-6, depending on text length) |
| Error correction | M (~15%) |
| Box size | 10 |
| Border | 4 modules |
| Format | PNG, base64-encoded |
| Text length | ~500-1000 chars per recipe → fits in QR v10-15 |

### Files to create/modify

| File | Action | Description |
|------|--------|-------------|
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.js` | Modify | Add "📱 Tải về" button in `getDom()` when result exists. Add QR overlay display logic |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.css` | Modify | Add `.fss-qr-overlay`, `.fss-qr-modal`, `.fss-qr-image` styles |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/py_bridge/qr_generator.py` | Create | Utility: takes plain text → generates QR code → returns base64 PNG |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/node_helper.js` | Modify | Add handler for `GENERATE_QR` socket notification → calls `qr_generator.py` |
| `recommend_daemon/py_bridge/recommend_dbus_listener.py` | Modify | Add `GET_RECIPE_DETAIL` command: returns full recipe data from database |

### Why QR code?

| Method | Network needed? | Setup complexity | User friction |
|--------|----------------|------------------|---------------|
| QR Code | No | None | Scan with phone camera |
| WiFi Hotspot + HTTP | Yes (RPi as AP) | High (hostapd, dnsmasq) | Connect to WiFi, open browser |
| Bluetooth | No | Medium (pairing) | Pair devices |
| Email | Yes | High (SMTP config) | Enter email address |
| USB | No | N/A | Physical connection |

QR code is the only method with zero setup, zero network requirement, and zero user friction. It is well-documented in IoT research for local data transfer.

### Thesis justification

> *"Để giải quyết bài toán thực tiễn — người dùng cần mang danh sách nguyên liệu đi chợ — nhóm tích hợp tính năng xuất QR code. Sau khi tìm kiếm món ăn, người dùng chạm nút 'Tải về', màn hình hiển thị mã QR chứa toàn bộ thông tin công thức dưới dạng văn bản thuần túy. Người dùng dùng camera điện thoại quét mã và lưu lại. Giải pháp này không yêu cầu kết nối mạng, không cần ghép nối Bluetooth, và tương thích với mọi dòng điện thoại thông minh hiện nay."*

---

## 5. Thesis Documentation Updates

### Teacher feedback cross-reference

| # | Feedback | Thesis section to update | Type |
|---|----------|--------------------------|------|
| 1 | Bỏ qua yêu cầu về cơ khí | Add "Yêu cầu về phần cứng" section | **Improvement** (design only) |
| 2 | Thay ảnh minh họa thuật toán bằng ảnh sản phẩm thật | All chapters: replace generic diagrams with screenshots | **Implement** in 10 days |
| 3 | NLP dùng công nghệ quá lớn | Chapter 3 (NLP): rewrite as filter+sort | **Implement** in 10 days |
| 4 | Độ chính xác mô hình nhận diện không tốt | Chapter 3 (FRT): add accuracy metrics table | Friend's task |
| 5 | Thiếu minh chứng cho mô hình xử lý ảnh và đề xuất nguyên liệu | Chapter 4 (Evaluation): add comparison table & images | **Implement** in 10 days |
| 6 | Đề xuất nguyên liệu chưa đủ bất ngờ | Section "Hướng phát triển": add LLM API proposal | **Improvement** (future work) |
| 7 | Giám sát môi trường chỉ hiển thị số liệu | Chapter 3 (Sensor): add anomaly detection | **Implement** in 10 days |
| 8 | Tính bảo mật chủ quan | Section "Bảo mật": rewrite with realistic scenarios | **Improvement** (future work) |

### What can be implemented in 10 days

| Section | Change | Deliverable |
|---------|--------|-------------|
| Chapter 3 (NLP) | Replace CRF description with filter+sort. Update architecture diagram | Text rewrite + new diagram |
| Chapter 3 (Sensor) | Add TemperatureMonitor description, anomaly rules table, D-Bus signal spec | New section |
| Chapter 4 (Evaluation) | Add recipe comparison table, sensor anomaly test results | Table + screenshots |
| All chapters | Replace generic AI/algorithm diagrams with actual product screenshots | ~10 new screenshots |

### Screenshots to capture

| Screenshot | Source | Location in thesis |
|------------|--------|-------------------|
| Shopping list UI | MagicMirror MMM-FSS-Recommend panel | Chapter 4 — Recommendation |
| Sensor data display | MagicMirror MMM-FSS-Env panel | Chapter 3 — Sensor |
| Door/ distance status | MagicMirror MMM-FSS-Monitor panel | Chapter 3 — Sensor |
| Annotated YOLO detection | `system_results/*/annotated_result.jpg` | Chapter 3 — FRT |
| MOG2 foreground mask | `system_results/*/mog2_foreground_mask.jpg` | Chapter 3 — FRT |
| Recipe chips suggestions | MagicMirror after Day 5 implementation | Chapter 4 — Recommendation |
| QR code download | MagicMirror after Day 8 implementation | Chapter 4 — Recommendation |
| Temperature anomaly alert | SensorDaemon log + D-Bus monitor | Chapter 3 — Sensor |

### Recipe comparison table (for Chapter 4)

| Món ăn | Nguyên liệu gốc | Tồn kho | Đề xuất mua thêm |
|---------|-----------------|---------|------------------|
| Phở bò | Bánh phở, Thịt bò, Hành, ... | Thịt bò (có) | Bánh phở, Hành, ... |
| ... | ... | ... | ... |

### What goes in "Improvement" section only (not implemented)

These are design proposals for the thesis that are too large to implement in 10 days:

#### 6a. LLM API integration for out-of-database recipes

**Problem**: The system is limited to 2470 recipes. If a user wants to cook a dish outside this set, there is no way to add it.

**Proposal**: When a recipe is not found in the local database, the system calls a cloud LLM API (GPT-4o or Gemini) to generate the ingredient list. The response is parsed, presented to the user for verification, and optionally saved to the local database for future use.

```
User inputs: "Bún bò Huế"
  → NOT found in 2470 recipes
  → Call Gemini API: "List ingredients for Bún bò Huế for 4 people"
  → LLM returns: ["Bún: 1kg", "Bò: 500g", ...]
  → User reviews and confirms
  → Save to local DB → run Bù Trừ → shopping list
```

**Security considerations**:
- API key stored encrypted (not in plaintext config)
- HTTPS for all API calls
- Rate limiting (max 10 calls/hour)
- User confirmation before using LLM results
- Audit log of all API calls

**Why not implement now**: Requires API key management, internet connectivity handling, error handling for API failures, and user confirmation UI — too large for 10 days.

#### 6b. Proactive recommendation engine

**Problem**: The current Bù Trừ algorithm is purely reactive — it only responds when the user explicitly searches for a recipe. It cannot suggest "what can I cook with what I have."

**Proposal**: Invert the algorithm. Scan the current inventory and find all recipes that can be made with available ingredients. Sort by coverage percentage (e.g., 80%+ ingredients available). Present as "Bạn có thể nấu các món sau với nguyên liệu hiện có."

**Why not implement now**: Requires indexing recipes by ingredient (inverted index), scoring algorithm, and UI for displaying suggestions — medium complexity but low priority for thesis defense.

#### 6c. Distributed system security

**Problem**: Current security assumes complete offline isolation. Realistically, the system may need network access for LLM API, recipe updates, or firmware upgrades.

**Proposal**: A layered security model:
- **Layer 1** (hardware): Encrypted storage for keys, secure boot
- **Layer 2** (OS): AppArmor/SELinux profiles per daemon, minimal capabilities
- **Layer 3** (application): API key encryption, HTTPS, input sanitization on all D-Bus methods, rate limiting
- **Layer 4** (network): Firewall rules (allow only specific outbound endpoints), VPN for remote access

**Why not implement now**: Requires system-level changes (AppArmor profiles, firewall rules) that are beyond thesis scope.

---

## 6. YOLO/FRT Pipeline — Friend's Tasks

### Teacher feedback

> *"Độ chính xác của mô hình nhận diện không được tốt => Cần nêu rõ quá trình cải thiện mô hình."*
> *"Còn thiếu các minh chứng cho mô hình xử lý ảnh"*

### Tasks for friend

| Task | Description | Effort |
|------|-------------|--------|
| **Accuracy benchmark** | Run all 5 YOLOv11n quantization variants on a labeled test set. Generate mAP, precision, recall, F1 table | 2 days |
| **Fix ByteTrack** | Debug why `total_events: 0` across all sessions (likely virtual line calibration or confidence threshold). Annotate tracking results | 2 days |
| **Improvement log** | Document: base model → fine-tuning → improved model. Show before/after metrics with annotated images | 1 day |
| **Evidence collection** | Select best annotated frames from `system_results/`, create comparison grids (ground truth vs detection) | 1 day |
| **Replace diagrams** | Replace YOLO architecture diagrams in thesis with actual `annotated_result.jpg` images from real sessions | 1 day |

### What goes in "Improvement" section

- Fine-tuning YOLO on a custom fridge-food dataset (currently using COCO-pretrained weights)
- Experimenting with YOLOv26n variants for better speed-accuracy tradeoff
- Deploying on NVIDIA Jetson or TPU for real-time inference

---

## 7. Teacher Feedback Cross-Reference

| # | Feedback | Solution | Section | Timeline |
|---|----------|----------|---------|----------|
| 1 | Bỏ qua yêu cầu cơ khí | Add hardware requirement section to thesis | **Thesis §2.1** | Improvement |
| 2 | Thay ảnh minh họa bằng ảnh thật | Capture 10+ screenshots from system_results/ and UI | **Thesis all chapters** | 10 days |
| 3 | NLP công nghệ quá lớn | Remove CRF, replace with filter+sort | **§1 — NLP Pipeline** | 10 days |
| 4 | Độ chính xác FRT không tốt | Run benchmarks, document improvement process | Friend's task | 10 days |
| 5 | Thiếu minh chứng | Recipe comparison table + FRT accuracy table | **§5 — Thesis docs** + Friend | 10 days |
| 6 | Đề xuất chưa bất ngờ | LLM API proposal + proactive recipe suggestion | **§6a/b — Improvement** | Improvement |
| 7 | Giám sát chỉ hiển thị số liệu | TemperatureMonitor with 3 anomaly rules | **§2 — Sensor Daemon** | 10 days |
| 8 | Bảo mật chủ quan | Layered security model with LLM API security | **§6c — Improvement** | Improvement |

### Legend

| Label | Meaning |
|-------|---------|
| **10 days** | Can be implemented within the 10-day window |
| **Improvement** | Proposed in thesis "Hướng phát triển" section only |
| **Friend's task** | Assigned to team member working on FRT/YOLO pipeline |
