# FSS System Test Guide — How to Test Each Daemon & Capture Evidence for Thesis

## Table of Contents

1. [Overview](#1-overview)
2. [SensorDaemon (C++) — Hardware I/O](#2-sensordaemon-c)
3. [DBDaemon (Python) — Data Controller](#3-dbdaemon-python)
4. [FRT Pipeline (C++ + Python) — Food Recognition](#4-frt-pipeline-c--python)
5. [Recommend System (Python) — NLP Recipe Extraction](#5-recommend-system-python-nlp)
6. [RecommendDaemon (Python) — Business Logic](#6-recommenddaemon-python)
7. [MagicMirror UI (Node.js + Electron)](#7-magicmirror-ui-nodejs--electron)

---

## 1. Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ SensorDaemon │    │   FRTApp     │    │  DBDaemon    │    │ RecommendSys  │    │  MagicMirror │
│   (C++)      │◄──►│  (C++/Python)│◄──►│  (Python)    │◄──►│  (Python)    │◄──►│  (Electron)  │
│              │    │              │    │              │    │              │    │              │
│ I2C / GPIO   │    │ V4L2 / YOLO  │    │ SQLite / SHM  │    │ CRF / NER    │    │ Electron UI  │
│ D-Bus emit   │    │ D-Bus emit   │    │ D-Bus listen  │    │ D-Bus proxy  │    │ socket.io    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                    │                    │                    │                   │
       └──────────── D-Bus System Bus ───────────┴────────────────────┴───────────────────┘
```

Each daemon has its own test procedure. Below is the step-by-step guide for each, including **how to capture screenshots** for thesis evidence.

---

## 2. SensorDaemon (C++)

### Purpose
Reads temperature/humidity (SHT3x via I2C), door state (MC-38 via GPIO), distance (VL53L0x via I2C). Broadcasts via D-Bus.

### Test Procedure

```bash
# 1. Build
cd sensor_daemon/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# 2. Run (needs sudo for GPIO/I2C)
sudo ./sensor_daemon_exec

# In another terminal:
# 3. Check D-Bus signals
dbus-monitor --system "interface=vn.edu.uit.FSS.Interface"
# Expected output:
#   signal time=... sender=:1.xxx -> destination=(null destination)
#     string "{"type":"EnvironmentDataUpdated","temperature":4.5,"humidity":65.2,...}"
#   signal time=... sender=:1.xxx -> destination=(null destination)
#     string "{"type":"DOOR_OPEN",...}"

# 4. Verify sensor readings (check terminal output)
# Expected:
#   [INFO] SHT3x: 4.5°C, 65.2% RH
#   [INFO] Distance: 12.3 cm
#   [INFO] Door: CLOSED
```

### Per-Stage Artifacts & Screenshots

| Stage | What to capture | How to capture | Thesis use |
|-------|----------------|----------------|------------|
| I2C communication | Terminal showing SHT3x read commands | `import -window root sensor_i2c.png` | Proves I2C bus is working |
| D-Bus signal | `dbus-monitor` output showing EnvironmentDataUpdated | `import -window root sensor_dbus_signal.png` | Proves D-Bus broadcast works |
| Sensor data display | MagicMirror MMM-FSS-Env panel | `import -window root env_panel.png` | Shows real-time sensor data |

### Screenshot Instructions

```bash
# Terminal screenshot of daemon running
import -window root thesis_screenshots/sensor_daemon_terminal.png

# D-Bus monitor screenshot
import -window root thesis_screenshots/sensor_dbus_monitor.png

# MagicMirror UI screenshot
import -window root thesis_screenshots/sensor_mm_env_panel.png
```

---

## 3. DBDaemon (Python)

### Purpose
Data controller: manages 3 SQLite databases, listens to D-Bus signals, reads POSIX SHM for video frames.

### Test Procedure

```bash
# 1. Start DBDaemon
source db_daemon/venv/bin/activate
python db_daemon/src/main.py

# 2. Check databases created
ls -la /opt/fss/data/
# Expected:
#   fss_data.db
#   FSS_Inventory.db
#   FSS_Request.db

# 3. Check database tables
sqlite3 /opt/fss/data/fss_data.db ".tables"
# Expected:
#   environment_log  door_event_log  distance_sensor_log  presence_sensor_log

sqlite3 /opt/fss/data/FSS_Inventory.db ".tables"
# Expected:
#   current_inventory  food_history  custom_food_labels

# 4. Query recent logs
sqlite3 /opt/fss/data/fss_data.db \
  "SELECT timestamp, temperature, humidity FROM environment_log ORDER BY timestamp DESC LIMIT 5;"
```

### Per-Stage Artifacts & Screenshots

| Stage | What to capture | How to capture | Thesis use |
|-------|----------------|----------------|------------|
| Database schema | SQLite `.tables` + `.schema` output | `import -window root db_schema.png` | Proves DB structure |
| Data insertion | SELECT query showing environment_log rows | `import -window root db_data.png` | Proves data persistence |
| SHM read | Terminal showing SHM frame read | `import -window root db_shm_read.png` | Proves IPC with FRTApp |

---

## 4. FRT Pipeline (C++ + Python)

### 4.1 Pipeline Architecture (7 Stages)

This is the **most important section for thesis evidence**. The FRT pipeline has 7 stages, each producing a concrete output file:

```
Camera ──► MOG2 ──► Preprocess ──► YOLO ──► NMS ──► ByteTrack ──► Annotated
 (/dev/video0)  (motion filter)   (640×640)  (inference)  (dedup)   (tracking)   (output)
      │              │               │          │           │            │            │
      ▼              ▼               ▼          ▼           ▼            ▼            ▼
 sample_frame   mog2_mask     preprocess_rgb  inference  nms_stats   track_traj   annotated
    .jpg         .jpg           .jpg          .csv        .json       .json        .jpg
```

### 4.2 Quick Test (Full Pipeline)

```bash
# Step 1: Run comprehensive test
cd tests/frt_app
sudo bash run_frt_full_test.sh --mode comprehensive --duration 30 --countdown 5

# Step 2: Run demo script (7-stage standalone, no camera hardware needed for some stages)
bash scripts/frt_pipeline_demo.sh --duration 30 --countdown 5

# With synthetic mode (no camera needed):
bash scripts/frt_pipeline_demo.sh --synthetic
bash run_frt_full_test.sh --mode comprehensive --synthetic
```

### 4.3 Per-Stage Verification with Screenshots

Below is how to test each stage **individually** and capture the output for thesis evidence:

#### Stage 1: Camera Capture

```bash
# Test camera directly
python3 -c "
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    cv2.imwrite('thesis_screenshots/stage1_sample_frame.jpg', frame)
    print(f'Frame: {frame.shape}')
cap.release()
"

# Screenshot for thesis:
#   File: thesis_screenshots/stage1_sample_frame.jpg
#   Proves: Camera works at expected resolution
```

| Thesis use | Expected output |
|------------|----------------|
| "Hệ thống nhận diện sử dụng camera USB tại /dev/video0 với độ phân giải 640×480" | sample_frame.jpg showing fridge interior |

#### Stage 2: MOG2 Motion Detection

```bash
python3 -c "
import cv2
frame = cv2.imread('thesis_screenshots/stage1_sample_frame.jpg')

mog2 = cv2.createBackgroundSubtractorMOG2()
for _ in range(10): fgmask = mog2.apply(frame)
fgmask = mog2.apply(frame)

cv2.imwrite('thesis_screenshots/stage2_mog2_mask.jpg', fgmask)
heatmap = cv2.applyColorMap(fgmask, cv2.COLORMAP_JET)
cv2.imwrite('thesis_screenshots/stage2_mog2_heatmap.jpg', heatmap)

motion_pct = (np.count_nonzero(fgmask) / fgmask.size) * 100
print(f'Motion: {motion_pct:.1f}% of frame')
"
```

| Thesis use | Expected output |
|------------|----------------|
| "MOG2 loại bỏ các khung hình không có chuyển động, giúp giảm tải xử lý" | mask.jpg (black = no motion, white = motion) |
| "Heatmap trực quan hóa vùng có chuyển động" | heatmap.jpg (blue→red gradient) |

#### Stage 3: Image Preprocessing

```bash
python3 -c "
import cv2, numpy as np

frame = cv2.imread('thesis_screenshots/stage1_sample_frame.jpg')
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
cv2.imwrite('thesis_screenshots/stage3_rgb.jpg', cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

h, w = frame.shape[:2]
target = 640
scale = min(target / w, target / h)
new_w, new_h = int(w * scale), int(h * scale)
resized = cv2.resize(rgb, (new_w, new_h))

letterbox = np.full((target, target, 3), 114, dtype=np.uint8)
x_off = (target - new_w) // 2
y_off = (target - new_h) // 2
letterbox[y_off:y_off+new_h, x_off:x_off+new_w] = resized
cv2.imwrite('thesis_screenshots/stage3_letterbox.jpg', cv2.cvtColor(letterbox, cv2.COLOR_RGB2BGR))

print(f'Original {w}x{h} → Letterbox {target}x{target}')
"
```

| Thesis use | Expected output |
|------------|----------------|
| "Ảnh được chuyển đổi BGR→RGB theo yêu cầu đầu vào của YOLO" | rgb.jpg |
| "Letterbox resize đảm bảo ảnh đầu vào 640×640 không bị méo" | letterbox.jpg (with gray padding) |

#### Stage 4: YOLO Inference

```bash
# Using the comprehensive test script
cd tests/frt_app
sudo bash run_frt_full_test.sh --mode comprehensive --duration 15

# Check output
cat system_results/frt_session_*/inference_table.csv

# Manually verify model accuracy
python3 -c "
import csv
with open('system_results/frt_session_*/inference_table.csv') as f:
    reader = csv.DictReader(f)
    confs = [float(r['confidence']) for r in reader]
    print(f'Detections: {len(confs)}')
    print(f'Confidence range: {min(confs):.4f} - {max(confs):.4f}')
    print(f'Avg confidence: {sum(confs)/len(confs):.4f}')
"
```

| Thesis use | Expected output |
|------------|----------------|
| "Mô hình YOLOv11n chạy trên TFLite với độ trễ trung bình Xms" | inference_table.csv with latencies |
| "Bảng kết quả nhận diện với độ tin cậy từng đối tượng" | CSV with class_id, confidence, bbox |

#### Stage 5: NMS Filtering

```bash
# Results automatically generated in system_results/*/nms_stats.json
python3 -c "
import json, glob
nms_file = glob.glob('system_results/frt_session_*/nms_stats.json')[0]
nms = json.load(open(nms_file))
s = nms['summary']
print(f'Before NMS: {s[\"total_before\"]}')
print(f'After NMS:  {s[\"total_after\"]}')
print(f'Suppression: {s[\"suppression_rate_pct\"]}%')
"
```

| Thesis use | Expected output |
|------------|----------------|
| "NMS loại bỏ các khung trùng lặp, giảm X% số lượng detection" | nms_stats.json showing before/after counts |

#### Stage 6: ByteTrack Tracking

```bash
python3 -c "
import json, glob
be_file = glob.glob('system_results/frt_session_*/boundary_events.json')[0]
events = json.load(open(be_file))
tt_file = glob.glob('system_results/frt_session_*/track_trajectories.json')[0]
tracks = json.load(open(tt_file))
ci = sum(1 for e in events if e['event'] == 'CHECK_IN')
co = sum(1 for e in events if e['event'] == 'CHECK_OUT')
print(f'Events: {len(events)} (CI={ci} CO={co})')
print(f'Tracks: {len(tracks)}')
for e in events[-5:]:
    print(f'  → [{e[\"timestamp\"]}] Track {e[\"track_id\"]}: {e[\"event\"]}')
"
```

| Thesis use | Expected output |
|------------|----------------|
| "ByteTrack gán ID theo dõi cho từng đối tượng xuyên suốt các khung hình" | track_trajectories.json with per-track coordinates |
| "Phát hiện sự kiện CHECK_IN/CHECK_OUT khi đối tượng đi qua đường biên ảo" | boundary_events.json with event list |

#### Stage 7: Annotated Output

```bash
# Find the best annotated frame
ls -la system_results/frt_session_*/annotated_result.jpg
ls -la system_results/frt_session_*/latest_frames/

# Copy to thesis folder
cp system_results/frt_session_*/annotated_result.jpg thesis_screenshots/
```

| Thesis use | Expected output |
|------------|----------------|
| "Kết quả nhận diện được hiển thị trực quan trên khung hình" | annotated_result.jpg with bboxes, labels, confidence |
| "Các khung hình có đối tượng được đánh dấu và gán nhãn" | Per-frame annotated images |

### 4.4 Screenshot Compound Grid for Thesis

```bash
# Create a 2×4 grid of all 7 stages + final result
python3 -c "
import cv2, numpy as np, glob, os

stages = {
    '1_Camera': 'stage1_sample_frame.jpg',
    '2_MOG2': 'stage2_mog2_mask.jpg',
    '3_Letterbox': 'stage3_letterbox.jpg',
    '4_YOLO': None,  # Use terminal screenshot
    '5_NMS': None,   # Use terminal screenshot
    '6_Tracking': None,  # Use terminal screenshot
    '7_Annotated': 'annotated_result.jpg'
}

# Create a summary comparison image
frames = []
for name, fname in stages.items():
    if fname:
        img = cv2.imread(f'thesis_screenshots/{fname}')
        if img is not None:
            img = cv2.resize(img, (320, 240))
            cv2.putText(img, name, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
            frames.append(img)

if frames:
    # Arrange in a grid (2 cols, N rows)
    cols = 2
    rows = (len(frames) + cols - 1) // cols
    grid_w = 320 * cols
    grid_h = 240 * rows
    grid = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    for i, img in enumerate(frames):
        r, c = i // cols, i % cols
        grid[r*240:(r+1)*240, c*320:(c+1)*320] = img
    cv2.imwrite('thesis_screenshots/pipeline_comparison_grid.jpg', grid)
    print(f'Grid: {rows}x{cols} = {rows*cols} cells -> pipeline_comparison_grid.jpg')
"
```

---

## 5. Recommend System (Python — NLP)

### 5.1 Architecture

The recipe extraction pipeline has 3 steps:

```
Recipe Name
    │
    ├── Step 1: Filter+Sort (recipe search)
    │   ├── Keyword matching (substring)
    │   └── Fuzzy matching (difflib, cutoff 0.4)
    │
    ├── Step 2: NER Ingredient Extraction
    │   ├── Tokenization (pyvi)
    │   ├── Feature extraction (POS tags, context)
    │   ├── CRF inference (BIO tagging)
    │   └── Group tokens → ingredient list
    │
    └── Step 3: Quantity Normalization
        ├── Parse số lượng (một→1, hai→2, ...)
        └── Chuẩn hóa đơn vị (ki-lô→kg, muỗng→M, ...)
```

### 5.2 Test Procedure

```bash
# 1. Test recipe search (Filter+Sort)
cd recipe_extractor
source venv/bin/activate
python3 -c "
from src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
engine = RecipeAnalyzerEngine()
results = engine.suggest_recipe('gà')
print(f'Found {len(results)} recipes:')
for r in results:
    print(f'  → {r}')
"
# Expected: ['cánh gà chiên sa tế tôm', 'gà kho gừng', ...]

# 2. Test ingredient extraction (NLP full pipeline)
python3 -c "
from src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
engine = RecipeAnalyzerEngine()
result = engine.generate_fss_request('Gỏi trộn khô mực')
print(f'Dish: {result[\"dish\"]}')
for ing in result['ingredients']:
    print(f'  → {ing[\"ingredient\"]}: {ing[\"quantity\"]}')
"
# Expected:
#   Dish: Gỏi trộn khô mực
#   → Bưởi: 1 trái
#   → Mực khô: 1 con (50g)
#   → Thịt ba chỉ: 100g
#   → ...

# 3. Test D-Bus service
python3 -c "
import subprocess, json
# Call via dbus-send
result = subprocess.run([
    'dbus-send', '--system', '--print-reply',
    '--dest=vn.edu.uit.FSS.RecipeExtractor',
    '/vn/edu/uit/FSS/RecipeExtractor',
    'vn.edu.uit.FSS.RecipeExtractor.ExtractAndPersistRecipe',
    f'string:Thit kho trung'
], capture_output=True, text=True)
print(result.stdout[:500])
"
```

### 5.3 Per-Stage Artifacts & Screenshots

| Stage | What to test | Command | Screenshot for thesis |
|-------|-------------|---------|----------------------|
| Recipe Search (Filter) | `suggest_recipe('gà')` → list | `python3 -c "..."` | Terminal showing search results |
| NER Ingredient Extraction | `generate_fss_request('Gỏi trộn...')` → JSON | `python3 -c "..."` | Terminal showing extracted ingredients + quantities |
| Bù Trừ (Comparison) | Compare recipe vs inventory → shopping list | Via RecommendDaemon | MagicMirror UI showing shopping list |
| D-Bus Service | `ExtractAndPersistRecipe` via dbus-send | `dbus-send --system ...` | Terminal with D-Bus return |

### 5.4 Unit Tests

```bash
# Run all NLP tests
cd tests
source recipe_extractor/venv/bin/activate
pytest recipe_extractor/test_recipe_analyzer.py -v

# Expected output:
# tests/recipe_extractor/test_recipe_analyzer.py::test_suggest_recipe PASSED
# tests/recipe_extractor/test_recipe_analyzer.py::test_generate_request PASSED
# ...
```

### 5.5 Screenshot: Recipe Comparison Table for Thesis

```bash
# Generate the comparison table as a CSV for thesis
python3 -c "
from src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
import csv

engine = RecipeAnalyzerEngine()
recipes = ['Gỏi trộn khô mực', 'Cánh gà chiên sa tế tôm',
           'Lẩu ghẹ kim chi', 'Bò kho dưa kiệu']

with open('thesis_screenshots/recipe_comparison.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Món ăn', 'Nguyên liệu', 'Số lượng', 'Tồn kho', 'Thiếu', 'Gợi ý'])
    for r in recipes:
        result = engine.generate_fss_request(r)
        for ing in result['ingredients']:
            w.writerow([r, ing['ingredient'], ing['quantity'], '', '', ''])
"
```

---

## 6. RecommendDaemon (Python)

### 6.1 Architecture

```
RecommendDaemon (D-Bus service: vn.edu.uit.FSS.RecommendDaemon)
    │
    ├── Methods:
    │   ├── GenerateShoppingList(recipe: string) → string (JSON)
    │   ├── GetAvailableRecipes() → string (JSON)
    │   ├── GetShoppingList() → string (JSON)
    │   └── MarkItemPurchased(food_id: string) → string (JSON)
    │
    ├── Internal Flow:
    │   1. GenerateShoppingList('Gỏi trộn')
    │      ├── RecipeAnalyzerEngine.generate_fss_request('Gỏi trộn')
    │      ├── DBDaemon.GetInventory() via D-Bus
    │      └── Bù Trừ → {'available': [...], 'missing': [...], 'need': [...]}
    │
    └── Database: FSS-Recommend.db
        ├── recommendation_log (per-recipe analysis snapshots)
        └── shopping_list (individual items to buy)
```

### 6.2 Test Procedure

```bash
# 1. Start daemon
source recommend_daemon/venv/bin/activate
python recommend_daemon/src/main.py

# 2. Test via dbus-send (from another terminal)
dbus-send --system --print-reply \
  --dest=vn.edu.uit.FSS.RecommendDaemon \
  /vn/edu/uit/FSS/Interface \
  vn.edu.uit.FSS.Interface.GenerateShoppingList \
  string:'Gỏi trộn khô mực'

# 3. Test GetAvailableRecipes
dbus-send --system --print-reply \
  --dest=vn.edu.uit.FSS.RecommendDaemon \
  /vn/edu/uit/FSS/Interface \
  vn.edu.uit.FSS.Interface.GetAvailableRecipes

# 4. Test via MagicMirror UI
# Open MagicMirror, click the Recommmend module
# Type recipe name, click "Tìm kiếm"
```

### 6.3 Per-Stage Artifacts & Screenshots

| Stage | What to capture | How | Thesis use |
|-------|----------------|-----|------------|
| D-Bus method call | `dbus-send --print-reply` output | `import -window root` | Proves D-Bus IPC works |
| Shopping list result | MagicMirror UI showing result table | `import -window root` | Shows user-facing output |
| Bù Trừ algorithm | JSON output with available/missing fields | `import -window root` text | Proves algorithm correctness |
| QR code download | QR overlay on screen | `import -window root` | Shows download feature |

---

## 7. MagicMirror UI (Node.js + Electron)

### 7.1 Test Procedure

```bash
# 1. Start MagicMirror
cd electron_app/magicmirror
npm start

# 2. Verify modules load
# Open Chrome DevTools: right-click → Inspect
# Console should show:
#   [MMM-FSS-Env]    Starting...
#   [MMM-FSS-Monitor] Starting...
#   [MMM-FSS-Recommend] Starting...
#   [MMM-FSS-Inventory] Starting...
#   [MMM-FSS-LivePreview] Starting...

# 3. Test Recipe Search via keyboard
# Keyboard shortcut or click search input
# Type "gỏi" → recipe chips should appear
# Type full name → press Enter → result appears

# 4. Test QR code
# After search result → click "📱 Tải về"
# QR code overlay should appear
```

### 7.2 Screenshot Checklist for Thesis

| # | Screenshot | How to capture | Module |
|---|-----------|----------------|--------|
| 1 | Environment sensor display | `import -window root env_panel.png` | MMM-FSS-Env |
| 2 | Monitor panel (door/distance) | `import -window root monitor_panel.png` | MMM-FSS-Monitor |
| 3 | Shopping list result | `import -window root shopping_list.png` | MMM-FSS-Recommend |
| 4 | Recipe chips suggestions | `import -window root recipe_chips.png` | MMM-FSS-Recommend |
| 5 | QR code overlay | `import -window root qr_overlay.png` | MMM-FSS-Recommend |
| 6 | Live preview (camera) | `import -window root live_preview.png` | MMM-FSS-LivePreview |
| 7 | Inventory list | `import -window root inventory.png` | MMM-FSS-Inventory |
| 8 | Full MagicMirror desktop | `import -window root full_desktop.png` | All |

### 7.3 Automated Screenshot Script

```bash
# Use the thesis screenshot script
bash docs/thesis/capture_thesis_screenshots_auto.sh
```

---

## 8. One-Command Pipeline Test (All Components)

### Full System Smoke Test

```bash
# Run this after making changes to verify nothing is broken
echo "=== FSS SMOKE TEST ==="

# 1. Test SensorDaemon binary exists
test -x sensor_daemon/build/sensor_daemon_exec && echo "✓ SensorDaemon binary" || echo "✗ SensorDaemon"

# 2. Test DBDaemon can import
source db_daemon/venv/bin/activate
python3 -c "from DbDaemonMain import DbDaemonMain; print('✓ DBDaemon import')"

# 3. Test FRT pipeline import
source frt_app/py_ai_core/venv/bin/activate
python3 -c "from YoloPipeline import YoloPipeline; print('✓ YoloPipeline import')"

# 4. Test Recommend Engine import
source recommend_daemon/venv/bin/activate
python3 -c "from RecommendEngine import RecommendEngine; print('✓ RecommendEngine import')"

# 5. Test Recipe Extractor import
source recipe_extractor/venv/bin/activate
python3 -c "from RecipeAnalyzerAPI import RecipeAnalyzerEngine; print('✓ RecipeAnalyzerEngine import')"

# 6. Test database schema
python3 -c "
import sqlite3
for db in ['fss_data.db', 'FSS_Inventory.db', 'FSS_Request.db']:
    conn = sqlite3.connect(f'/opt/fss/data/{db}')
    tables = conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()
    print(f'✓ {db}: {[t[0] for t in tables]}')
    conn.close()
"

# 7. Test unit tests
pytest tests/recipe_extractor/test_recipe_analyzer.py -v --tb=no 2>&1 | tail -5
pytest tests/recommend_daemon/test_recommend_engine.py -v --tb=no 2>&1 | tail -5
python3 tests/run_phase1_tests.py 2>&1 | tail -5
```

---

## 9. Thesis Evidence Summary Checklist

| # | Evidence | Source | How to capture | Status |
|---|----------|--------|----------------|--------|
| 1 | Camera raw frame | `stage1_sample_frame.jpg` | `python3 -c "import cv2; ..."` | ⬜ |
| 2 | MOG2 foreground mask | `stage2_mog2_mask.jpg` | `scripts/frt_pipeline_demo.sh` | ⬜ |
| 3 | MOG2 heatmap | `stage2_mog2_heatmap.jpg` | `scripts/frt_pipeline_demo.sh` | ⬜ |
| 4 | Preprocessed letterbox | `stage3_letterbox.jpg` | `scripts/frt_pipeline_demo.sh` | ⬜ |
| 5 | YOLO inference table | `inference_table.csv` | `run_frt_full_test.sh --mode comprehensive` | ⬜ |
| 6 | NMS stats | `nms_stats.json` | Generated automatically after comprehensive test | ⬜ |
| 7 | ByteTrack trajectories | `track_trajectories.json` | Generated automatically | ⬜ |
| 8 | Boundary events | `boundary_events.json` | Generated automatically | ⬜ |
| 9 | Annotated detection | `annotated_result.jpg` | `scripts/frt_pipeline_demo.sh` | ⬜ |
| 10 | Sensor env display | `env_panel.png` | `import -window root` | ⬜ |
| 11 | Monitor panel | `monitor_panel.png` | `import -window root` | ⬜ |
| 12 | Shopping list UI | `shopping_list.png` | `import -window root` | ⬜ |
| 13 | Recipe chips | `recipe_chips.png` | `import -window root` | ⬜ |
| 14 | QR code overlay | `qr_overlay.png` | `import -window root` | ⬜ |
| 15 | Live preview | `live_preview.png` | `import -window root` | ⬜ |
| 16 | Pipeline grid | `pipeline_comparison_grid.jpg` | Python grid script (section 4.4) | ⬜ |
| 17 | Recipe comparison table | `recipe_comparison.csv` | Python script (section 5.5) | ⬜ |
| 18 | Sensor anomaly test | `temp_anomaly.png` | D-Bus signal + screenshot | ⬜ |
| 19 | NLP extract output | Terminal JSON | `python3 -c "..."` | ⬜ |
| 20 | D-Bus signal monitor | Terminal output | `dbus-monitor` | ⬜ |

> **Instructions**: Check each box (⬜→✅) after capturing the evidence. The evidence files go into `docs/thesis/figures/` for easy reference when writing the thesis.
