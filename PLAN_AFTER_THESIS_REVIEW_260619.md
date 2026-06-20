# Plan After Thesis Review — 26/06/19

> Based on teacher feedback on the graduation thesis (Khóa luận tốt nghiệp).
> Project: **DEVELOPMENT OF AN AI-INTEGRATED APPLICATION TO SUPPORT FOOD MANAGEMENT AND REFRIGERATOR ENVIRONMENT MONITORING**

---

## Table of Contents

1. [Branch Strategy & Test Plan](#0-branch-strategy--test-plan)
2. [NLP Pipeline — Replace CRF NER with Filter + Sort](#1-nlp-pipeline--replace-crf-ner-with-filter--sort)
3. [Sensor Daemon — Temperature Anomaly Detection](#2-sensor-daemon--temperature-anomaly-detection)
4. [MagicMirror — Clickable Recipe Suggestion Chips](#3-magicmirror--clickable-recipe-suggestion-chips)
5. [Recipe Download via QR Code](#4-recipe-download-via-qr-code)
6. [Thesis Documentation Updates](#5-thesis-documentation-updates)
7. [YOLO/FRT Pipeline — Friend's Tasks](#6-yolofrt-pipeline--friends-tasks)
8. [Teacher Feedback Cross-Reference](#7-teacher-feedback-cross-reference)

---

## 0. Branch Strategy & Test Plan

### Existing Branch Map

| Local Branch | Purpose | Status |
|---|---|---|
| `main` | Stable release | Inactive |
| `ui-dev` | Active UI/MagicMirror development | **Active** |
| `folder_restructure` | Consolidate folder layout (pulled from `ui-dev`) | **Current** |
| `DBDaemon-dev` | DBDaemon development | Stale |
| `ElectronApp-dev` | Electron/MagicMirror development | Stale |
| `FRTApp-dev` | FRTApp (C++ camera + Python AI) | Stale |
| `recommend_daemon` | RecommendDaemon development | Stale |
| `recommend_system` | Recommend System (recipe_extractor) | Stale |
| `recommend_system-dev` | Recommend System dev work | Stale |
| `FSS_Deploy` | Deployment configuration | Stale |

| Remote Branch | Purpose |
|---|---|
| `DBDaemon-test` | DBDaemon unit/integration tests |
| `SensorDaemon-dev` | SensorDaemon development |
| `SensorDaemon-test` | SensorDaemon tests |
| `test/deploy-model` | Model deployment testing |
| `test/frtapp-phase1` | FRTApp Phase 1 tests |
| `refactor` | Code refactoring |

### Observation

- Each major component has its own `-dev` branch → pattern confirms **feature-per-branch** approach
- Separate `-test` branches exist for `DBDaemon` and `SensorDaemon` on remote → prior precedent for **dedicated test branches**
- The test folder has been consolidated into `/tests/` on `folder_restructure`, meaning tests now live alongside source in the same repo layout

### Recommendation: Hybrid Approach

**For sections with code changes (Sections 1-4, 6):**

| Section | Code Branch | Rationale |
|---|---|---|
| **§1 — NLP Filter+Sort** | `recommend_system` (or new `feat/nlp-filter-sort`) | Isolated to `recipe_extractor/` + `recommend_daemon/` |
| **§2 — TemperatureMonitor** | New branch from `main`: `feat/temperature-monitor` (or reuse `SensorDaemon-dev`) | Only touches `sensor_daemon/` |
| **§3 — Recipe Chips** | `ui-dev` (already active) | Only MagicMirror JS/CSS in `electron_app/` |
| **§4 — QR Code** | `ui-dev` (same branch as §3) | Same module `MMM-FSS-Recommend` — avoid merge conflicts by stacking on same branch |
| **§6 — FRT Pipeline** | `FRTApp-dev` | Friend's task, separate component |

**For testing:**

| Approach | Option | Pros | Cons |
|---|---|---|---|
| **A** — Inline tests on feature branch | Tests live beside code changes | No merge overhead; CI runs tests with code | Branch becomes larger |
| **B** — Dedicated `test/<feature>` branch | Clean separation | Extra branch management; tests may drift from code |
| **C** — Single `test/post-thesis` branch | One branch for all tests post-implementation | Simple; run all tests once | Tests can't be written before code |

**Recommendation: Option A** — Write unit tests for each feature **within its own feature branch**, since:
1. Test files are already consolidated under `/tests/` → no structural change needed
2. Each feature branch already isolates scope
3. Avoids test/code drift (Option B risk)
4. The 10-day timeline is short — branching overhead hurts more than helps

Only create a **separate integration test branch** (`test/thesis-integration`) at the end if cross-component integration verification is needed.

### Test coverage gap analysis (current vs. required)

| Component | Existing Tests | Coverage | Gap |
|---|---|---|---|
| `recipe_extractor/` | CRF model + BIO tags + feature extraction | Good for CRF, **must rewrite** for filter+sort | Full rewrite needed |
| `recommend_daemon/` | RecommendEngine + RecommendDbManager + integration | **Good** (500+ lines of tests) | Only needs `original_ingredients` parsing update |
| `db_daemon/` | Schema validation + backward compat + new methods | **Good** | Minimal changes expected |
| `sensor_daemon/` | HW driver tests (MC38, SHT3x, VL53L0x) | HW-level only | **No unit tests** — need TemperatureMonitor tests |
| `electron_app/` | MagicMirror built-in tests only | Core MM, not FSS modules | **No tests** for MMM-FSS-* modules |
| `integration/` | Extractor↔Recommend, Extractor↔DBD, Extractor↔Electron | **Good cross-component** | Needs update for new NLP output format |

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
| `tests/recipe_extractor/test_recipe_analyzer.py` | **Rewrite** | Remove CRF-specific tests (BIO schema, word2features, sent2features, model loading). Add tests for filter+parse+sort logic |
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

### Existing tests that will break

These tests import or depend on the CRF model and **must be rewritten**:
- `tests/recipe_extractor/test_recipe_analyzer.py` — full rewrite (see above)
- `tests/recipe_extractor/test_recipe_extractor_main.py` — check imports
- `tests/recipe_extractor/test_recipe_extractor_service.py` — check D-Bus service tests
- `tests/integration/test_extractor_recommend_integration.py` — line 113: `@unittest.skipIf(True, ...)` already skips CRF import; the mock `MockRecipeAnalyzerEngine` needs its output format updated to include `original_ingredients`
- `tests/integration/test_extractor_dbd_integration.py` — check format dependency
- `tests/integration/test_extractor_electron_integration.py` — check format dependency

### Tests to write (filter+parse+sort)

| Test class | Description |
|---|---|
| `TestRecipeFilter` | Recipe name lookup: exact match, case-insensitive match, not found, empty name |
| `TestIngredientParser` | Split `" : "` delimiter, no delimiter fallback, trailing whitespace, empty string |
| `TestRecipeSorter` | Alphabetical sort, Vietnamese diacritic order |
| `TestFullRecipeOutput` | Verify all fields returned (serving, times, difficulty, process, cook, usage, tips) |
| `TestRecommendEngineNewFormat` | Test `original_ingredients` parsing in `generate_shopping_list()` |

### Pipeline Verification: Step-by-Step Real Results

Beyond unit tests, the NLP pipeline must produce **concrete evidence at every stage** so the thesis can show that each transformation is correct.

| Step | Input | Processing | Expected Output | Evidence |
|------|-------|------------|----------------|---------|
| **1. Load recipe DB** | Path to `recipe_extractor/data/recipes/` | Scan all JSON files, build `{name → data}` dict | 2470 recipes loaded, < 0.5s | Terminal log: `Loaded 2470 recipes in 0.32s` |
| **2. Filter** | `"gỏi trộn khô mực"` | Normalize + hash lookup (case-insensitive, diacritic-insensitive) | `recipe_data: {name, ingredients, spices, ...}` | Printed recipe name match |
| **3. Parse ingredients** | `["Bưởi : 1 trái", "Mực khô : 1 con (50g)"]` | Split on `" : "`, strip whitespace | `[{"ingredient": "Bưởi", "quantity": "1 trái"}, ...]` | Terminal table of parsed pairs |
| **4. Sort** | Parsed ingredient list | Alphabetical by ingredient name | `["Bưởi", "Cà rốt", "Đậu phộng", ...]` | Printed sorted list |
| **5. Build full output** | All recipe fields + parsed ingredients | Combine into JSON FSS-Request | Full recipe JSON with `original_ingredients`, `process`, `cook`, etc. | Saved `recipe_output.json` |
| **6. RecommendDaemon parse** | `original_ingredients` from NLP | Split on `" : "` → feed to Bù Trừ | Shopping list with available/needed/missing | Comparison table |
| **7. Edge case: not found** | `"bún bò huế không tồn tại"` | Hash miss → NOT_FOUND | `status: "NOT_FOUND", message: "..."` | Suggestion list |

### User Script: `scripts/nlp_pipeline_demo.sh`

A step-by-step CLI script that the user runs to demonstrate the pipeline:

```bash
#!/usr/bin/env bash
# nlp_pipeline_demo.sh — Step-by-step NLP pipeline demonstration
# Usage: bash scripts/nlp_pipeline_demo.sh
# Output: prints each step, pauses for user confirmation, saves artifacts

RECIPE_NAME="${1:-Gỏi Trộn Khô Mực}"
RECIPE_DB="recipe_extractor/data/recipes"
OUTPUT_DIR="system_results/nlp_demo_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUTPUT_DIR"

echo "╔══════════════════════════════════════════════════════╗"
echo "║     NLP PIPELINE DEMO — Filter + Parse + Sort       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Recipe: $RECIPE_NAME"
echo "Output: $OUTPUT_DIR/"
echo ""

# --- STEP 1: Load Recipe Database ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1: Load Recipe Database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Scanning: $RECIPE_DB/"
START=$(date +%s%N)
RECIPE_COUNT=$(find "$RECIPE_DB" -name "*.json" | wc -l)
python3 -c "
import json, os, time
start = time.time()
db = {}
for f in os.listdir('$RECIPE_DB'):
    if f.endswith('.json'):
        with open(os.path.join('$RECIPE_DB', f)) as fp:
            data = json.load(fp)
            db[data.get('recipe_name', '').lower().strip()] = data
elapsed = (time.time() - start) * 1000
print(f'  ✅ Loaded {len(db)} recipes in {elapsed:.2f}ms')
print(f'  First 3: {list(db.keys())[:3]}')
"
echo ""

# --- STEP 2: Filter Recipe ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 2: Filter — Look up '$RECIPE_NAME'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import json, os
db = {}
for f in os.listdir('$RECIPE_DB'):
    if f.endswith('.json'):
        with open(os.path.join('$RECIPE_DB', f)) as fp:
            data = json.load(fp)
            db[data.get('recipe_name', '').lower().strip()] = data
key = '$RECIPE_NAME'.lower().strip()
if key in db:
    print(f'  ✅ Found: \"{db[key][\"recipe_name\"]}\"')
    print(f'     Serving: {db[key].get(\"serving\",\"N/A\")}')
    print(f'     Time:    {db[key].get(\"times\",\"N/A\")}')
    print(f'     Difficulty: {db[key].get(\"difficulty\",\"N/A\")}')
else:
    suggestions = [k for k in db if key in k or any(w in k for w in key.split())]
    print(f'  ❌ Not found. Suggestions: {suggestions[:5]}')
"
echo "Press Enter to continue..."
read -r

# --- STEP 3: Parse Ingredients ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 3: Parse ingredients (split on ' : ')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import json, os
db = {}
for f in os.listdir('$RECIPE_DB'):
    if f.endswith('.json'):
        with open(os.path.join('$RECIPE_DB', f)) as fp:
            data = json.load(fp)
            db[data.get('recipe_name', '').lower().strip()] = data
key = '$RECIPE_NAME'.lower().strip()
if key in db:
    raw = db[key].get('normal_ingredients', [])
    print(f'  Raw strings ({len(raw)} items):')
    for s in raw:
        print(f'    \"{s}\"')
    print()
    parsed = []
    for s in raw:
        parts = s.split(' : ', 1)
        name = parts[0].strip()
        qty = parts[1].strip() if len(parts) > 1 else '1'
        parsed.append({'ingredient': name, 'quantity': qty})
    print(f'  Parsed into:')
    for p in parsed:
        print(f'    {p[\"ingredient\"]:20s} → qty: {p[\"quantity\"]}')
"
echo "Press Enter to continue..."
read -r

# --- STEP 4: Sort Alphabetically ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 4: Sort ingredients alphabetically"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import json, os
db = {}
for f in os.listdir('$RECIPE_DB'):
    if f.endswith('.json'):
        with open(os.path.join('$RECIPE_DB', f)) as fp:
            data = json.load(fp)
            db[data.get('recipe_name', '').lower().strip()] = data
key = '$RECIPE_NAME'.lower().strip()
if key in db:
    raw = db[key].get('normal_ingredients', [])
    parsed = []
    for s in raw:
        parts = s.split(' : ', 1)
        name = parts[0].strip()
        qty = parts[1].strip() if len(parts) > 1 else '1'
        parsed.append({'ingredient': name, 'quantity': qty})
    sorted_parsed = sorted(parsed, key=lambda x: x['ingredient'])
    print(f'  Sorted ({len(sorted_parsed)} items):')
    for i, p in enumerate(sorted_parsed, 1):
        print(f'    {i:2d}. {p[\"ingredient\"]:20s} → {p[\"quantity\"]}')
"
echo ""

# --- STEP 5: Full Output ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 5: Full Recipe Output (saved to JSON)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import json, os
db = {}
for f in os.listdir('$RECIPE_DB'):
    if f.endswith('.json'):
        with open(os.path.join('$RECIPE_DB', f)) as fp:
            data = json.load(fp)
            db[data.get('recipe_name', '').lower().strip()] = data
key = '$RECIPE_NAME'.lower().strip()
if key in db:
    output = {
        'status': 'SUCCESS',
        'dish': db[key].get('recipe_name', key),
        'original_ingredients': db[key].get('normal_ingredients', []),
        'original_spices': db[key].get('spices', []),
        'serving': db[key].get('serving', ''),
        'times': db[key].get('times', ''),
        'difficulty': db[key].get('difficulty', ''),
        'process': db[key].get('process', db[key].get('step', [])),
        'cook': db[key].get('cook', []),
        'usage': db[key].get('usage', []),
        'tips': db[key].get('tips', []),
        'processing_time_ms': 0.01
    }
    output_path = '$OUTPUT_DIR/recipe_output.json'
    with open(output_path, 'w', encoding='utf-8') as fp:
        json.dump(output, fp, ensure_ascii=False, indent=2)
    print(f'  ✅ Full recipe saved to: {output_path}')
    print(f'  Fields: {list(output.keys())}')
    print(f'  Ingredients: {len(output[\"original_ingredients\"])}')
    print(f'  Process steps: {len(output[\"process\"])}')
    print(f'  Cook steps: {len(output[\"cook\"])}')
"
echo ""
echo "✅ NLP PIPELINE DEMO COMPLETE — Results in $OUTPUT_DIR/"
```

### Branch: `recommend_system` (or `feat/nlp-filter-sort`)

This is a self-contained change to `recipe_extractor/` + `recommend_daemon/src/RecommendEngine.py`. Work on this branch, write tests inline.

---

## 2. Sensor Daemon — Temperature Anomaly Detection

### Teacher feedback

> *"Chưa nêu ra được chi tiết tính năng giám sát môi trường cụ thể là giám sát những gì mà mới chỉ thực hiện hiển thị số liệu thôi. Có thể giám sát nhiệt độ bất thường do bỏ nhiều đồ, hoặc là thất thoát nhiệt do cửa mở..."*

### Problem

The current SensorDaemon reads sensor values (temperature, humidity, distance, door state) and broadcasts them via D-Bus, but performs **zero analysis** on the data. It is a data acquisition pipeline, not a monitoring system.

What exists: raw data display only.
What's missing: any form of anomaly detection, threshold alerts, or event detection.

### Friend's comment (critical review)

> *"luồng chưa rõ => chỉ xây class detect là không đủ => phải có giải pháp, ví dụ: (1) đẩy thông báo lên màn hình tủ lạnh => ko có ý nghĩa khi người dùng đang không có ở đó (2) đẩy thông báo lên điện thoại người dùng => phức tạp"*

**Analysis**: The friend is correct. The original plan only described **detection** (how to detect anomalies) but not **notification delivery** (how the user actually gets informed). The two options have different trade-offs:

| Option | Pros | Cons |
|---|---|---|
| **(1) Fridge screen notification** | Simple (D-Bus → UI signal); already have MMM-FSS-Notification module | Useless if user is away |
| **(2) Push to phone** | User gets real-time alerts anywhere | Requires mobile app + push notification infrastructure (FCM/APNs) + internet |

**Recommendation**: Implement **both** — use (1) as the primary delivery (within 10-day scope) and document (2) as future work in the thesis "Hướng phát triển" section. The anomaly data is already on D-Bus; the MMM-FSS-Notification module can subscribe to `TemperatureAnomaly` signals with minimal effort.

### Updated Solution (implement in 10 days)

Create a `TemperatureMonitor` class that:
1. Analyzes temperature readings in real-time (sliding window)
2. Emits D-Bus `TemperatureAnomaly` signals
3. Integrates with existing `MMM-FSS-Notification` module for on-screen display

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

### Notification delivery (NEW — addresses friend's feedback)

**Primary (in-scope)**: MMM-FSS-Notification subscribes to `TemperatureAnomaly` events
- `MMM-FSS-Notification.js` listens on D-Bus for `TemperatureAnomaly` (via node_helper.py)
- Displays as a dismissible alert banner on the MagicMirror screen
- Color-coded: yellow (LOAD_WARM_FOOD), red (FRIDGE_OVERHEATING), blue (FREEZER_WARNING)
- Auto-dismisses after 30 seconds for LOAD_WARM_FOOD; persistent until acknowledged for others

**Future work (thesis only)**: Push notification via mobile
- Propose FCM (Firebase Cloud Messaging) or a simple WebSocket gateway
- Requires a lightweight companion app or Telegram Bot API integration
- Out of 10-day scope

### Files to create/modify

| File | Action | Description |
|------|--------|-------------|
| `sensor_daemon/include/TemperatureMonitor.hpp` | Create | Header: `TemperatureMonitor` class with rolling buffer, threshold constants, state machine (NORMAL / WARNING / CRITICAL) |
| `sensor_daemon/src/TemperatureMonitor.cpp` | Create | Implementation: sliding window analysis, rate-of-change computation, state transition logic |
| `sensor_daemon/include/SensorDaemonMain.hpp` | Modify | Add `unique_ptr<TemperatureMonitor>` member, add `anomaly_check_rate_ms` config |
| `sensor_daemon/src/SensorDaemonMain.cpp` | Modify | In `process_environment_data()`: after polling, feed data to TemperatureMonitor |
| `sensor_daemon/include/OutputProcessor.hpp` | Modify | Add `broadcast_temperature_anomaly(type, details)` |
| `sensor_daemon/src/OutputProcessor.cpp` | Modify | Implement: format JSON string, call D-Bus interface |
| `sensor_daemon/include/SensorDbusInterface.hpp` | Modify | Add `emit_temperature_anomaly(json_string)` |
| `sensor_daemon/src/SensorDbusInterface.cpp` | Modify | Register `TemperatureAnomaly` signal with string payload |
| `sensor_daemon/CMakeLists.txt` | Modify | Add `TemperatureMonitor.cpp` to `add_executable` sources |
| `electron_app/magicmirror/modules/MMM-FSS-Notification/MMM-FSS-Notification.js` | **Modify** | NEW: Add `TemperatureAnomaly` handler — listen for signal, render colored alert banner |
| `electron_app/magicmirror/modules/MMM-FSS-Notification/MMM-FSS-Notification.css` | **Modify** | NEW: Add `.fss-anomaly-alert`, `.fss-anomaly-warning`, `.fss-anomaly-critical` styles |
| `electron_app/magicmirror/modules/MMM-FSS-Notification/node_helper.js` | **Modify** | NEW: Add Python subprocess for `TemperatureAnomaly` D-Bus listener (or extend existing) |
| `electron_app/magicmirror/modules/MMM-FSS-Notification/py_bridge/anomaly_dbus_listener.py` | **Create** | NEW: Listen for `TemperatureAnomaly` signal, parse JSON, output to stdout |
| `tests/sensor_daemon/CMakeLists.txt` | **Create** | NEW: Add test build target for TemperatureMonitor |
| `tests/sensor_daemon/test_temperature_monitor.cpp` | **Create** | NEW: Unit tests for TemperatureMonitor — rolling buffer, rate-of-change computation, state transitions, no false positives |
| `tests/sensor_daemon/README.md` | Modify | Update with TemperatureMonitor test instructions |

### TemperatureMonitor tests

| Test | Description |
|---|---|
| `test_rolling_buffer_append` | Buffer correctly stores and evicts old values |
| `test_normal_no_alert` | Stable temperature → no alert emitted |
| `test_load_warm_food_detection` | ΔT > +2°C → LOAD_WARM_FOOD |
| `test_fridge_overheating_detection` | 3 consecutive samples > 8°C → FRIDGE_OVERHEATING |
| `test_freezer_warning_detection` | Secondary sensor > -15°C → FREEZER_WARNING |
| `test_state_transition_suppression` | Alert only emitted on transition, not every poll |
| `test_recovery_after_anomaly` | Temperature returns to normal → alert clears |
| `test_empty_buffer` | No crash with < 3 samples |

### Branch: New branch from `main`: `feat/temperature-monitor` (or reuse `SensorDaemon-dev`)

Reason: Isolated to `sensor_daemon/` (C++) + `electron_app/` (UI notification). No overlap with other sections.

---

## 3. MagicMirror — Clickable Recipe Suggestion Chips

### Teacher feedback

> *"Tính năng đề xuất nguyên liệu chưa đủ tính bất ngờ... cần đặt vấn đề nếu có một món ăn ở ngoài cái database của em thì người dùng sẽ thêm món ăn đó vào ra làm sao?"*

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

### Things to consider

- What if `availableRecipes[]` has < 5 recipes? Show all available.
- "Xem thêm" cycles infinitely through the recipe list.
- Clicking a chip does NOT close the keyboard (if open) — user can continue typing.

### Files to modify

| File | Action | Description |
|------|--------|-------------|
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.js` | Modify | Add `this.suggestedRecipes` array, shuffle logic, chip rendering in `getDom()`, click handler to trigger search |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.css` | Modify | Add `.fss-chip-grid`, `.fss-chip` CSS classes (rounded pills, dark bg, hover/active states, max 5 per row) |

### No backend changes needed

The `availableRecipes` list is already populated on module startup via the existing `GET_RECIPES` → `RECIPES` socket flow.

### Branch: `ui-dev` (same as §4)

Both §3 and §4 modify the same module (`MMM-FSS-Recommend`). Work on a single branch to avoid merge conflicts.

---

## 4. Recipe Download via QR Code

### Teacher feedback

> *"giải pháp nhóm đặt ra chưa mang tính thực tiễn, chưa gắn với end-user"*

### Problem

The system runs on a Raspberry Pi with a MagicMirror display. After searching a recipe, the user sees the ingredient list on screen but has no way to take it with them (e.g., to go grocery shopping). Writing it down manually is impractical.

### Friend's comment (critical review)

> *"qr do python code này generate ra chỉ có thể giữ text ở trong cửa sổ hiển thị tạm thời sẽ mất khi người dùng chuyển cửa sổ hoặc là tắt máy (tùy vào hãng điện thoại). vấn đề lưu trữ => cần một cái app hoặc là web để lưu trữ thông báo và đảm bảo rằng sẽ không bị mất khi người dùng tắt đi."*

**Analysis**: The friend raises a valid point. On many Android phones, the built-in QR scanner shows the decoded text in a temporary overlay that disappears when the user taps away or switches apps. This means:
- User scans QR → sees recipe text → taps screen → text is gone
- No persistent storage of the scanned recipe

**Recommendation**: Update the approach so that the QR code links to a **locally-hosted HTTP page** (served by the Raspberry Pi) instead of encoding the full recipe as raw text. This gives:
- The phone browser **stores the page in history**
- User can bookmark, screenshot, or copy-paste
- No app installation needed
- Works on any phone with a browser

### Updated Solution (implement in 10 days)

Replace raw-text QR codes with **URL-based QR codes** pointing to a lightweight local HTTP server on the Raspberry Pi.

### Updated flow

```
Search result displayed
  → "📱 Tải về" button appears below shopping list
  → On click: 
      1. Flask/SimpleHTTPServer endpoint: POST /generate-recipe
      2. Server generates an HTML page at http://<rpi-ip>:8080/recipe/<id>
      3. QR code encodes this URL (not raw text)
      4. QR displayed on screen
  → User scans QR → phone opens browser → recipe page renders
  → Page is responsive (no zooming needed), dark-themed
  → User can bookmark / screenshot / copy text
```

### QR code specs

| Parameter | NEW Value | Old Value | Reason |
|---|---|---|---|
| Content | URL: `http://<hostname>.local:8080/r/<id>` | Plain text | Persistent in browser history |
| Library | `python-qrcode` + `Flask` | `python-qrcode` only | Need HTTP server for serving pages |
| Error correction | M (~15%) | M (~15%) | Unchanged |
| Box size | 10 | 10 | Unchanged |

### Local HTTP server

- **Framework**: Flask (lightweight, already compatible with Python-based system)
- **Port**: 8080 (unlikely to conflict with MagicMirror on 8080 — MM uses port 8080 for its server; use 8081 instead)
- **Routes**:
  - `GET /r/<recipe_id>` — renders recipe page (HTML template)
  - `POST /api/recipe` — accepts recipe data, returns QR URL
- **Storage**: In-memory dict (recipes are ephemeral; survive until daemon restart)
- **Template**: Single HTML page with dark theme, responsive, print-friendly

| Method | Network needed? | Setup complexity | User friction | Persistence |
|--------|----------------|------------------|---------------|-------------|
| QR Code (raw text) | No | Low | Scan → read → lost | ❌ Lost on dismiss |
| **QR Code (URL)** | **Yes (LAN only)** | **Medium (Flask)** | **Scan → browser opens** | **✅ In browser history** |
| WiFi Hotspot + HTTP | Yes (RPi as AP) | High | Connect to WiFi | ✅ |
| Bluetooth | No | Medium | Pair devices | ❌ |
| Email | Yes | High | Enter email | ✅ |

The URL approach adds a minor setup (Flask server) but solves the persistence problem completely.

### Files to create/modify

| File | Action | Description |
|------|--------|-------------|
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.js` | Modify | Replace "📱 Tải về" button: now calls `GET_RECIPE_DETAIL` → receives URL → generates QR from URL |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.css` | Modify | Unchanged QR overlay styles |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/py_bridge/qr_generator.py` | Create | Utility: takes URL string → generates QR code → returns base64 PNG |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/py_bridge/recipe_http_server.py` | **Create** | NEW: Flask server with `/r/<id>` and `/api/recipe` endpoints |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/py_bridge/requirements.txt` | Modify | Add `flask`, `qrcode[pil]` |
| `electron_app/magicmirror/modules/MMM-FSS-Recommend/node_helper.js` | Modify | Update handler for `GENERATE_QR`: spawn HTTP server if not running, call API endpoint |
| `recommend_daemon/py_bridge/recommend_dbus_listener.py` | Modify | Add `GET_RECIPE_DETAIL` command: returns full recipe data from database |

### Branch: `ui-dev` (same as §3)

Same MagicMirror module. Stacking §3 and §4 on `ui-dev` avoids merge conflicts.

---

## 5. Thesis Documentation Updates

### Teacher feedback cross-reference

| # | Feedback | Thesis section to update | Type |
|---|---|---|---|
| 1 | Bỏ qua yêu cầu về cơ khí | Add "Yêu cầu về phần cứng" section | **Improvement** (design only) |
| 2 | Thay ảnh minh họa thuật toán bằng ảnh sản phẩm thật | All chapters: replace generic diagrams with screenshots | **Implement** in 10 days |
| 3 | NLP dùng công nghệ quá lớn | Chapter 3 (NLP): rewrite as filter+sort | **Implement** in 10 days |
| 4 | Độ chính xác mô hình nhận diện không tốt | Chapter 3 (FRT): add accuracy metrics table | Friend's task |
| 5 | Thiếu minh chứng cho mô hình xử lý ảnh và đề xuất nguyên liệu | Chapter 4 (Evaluation): add comparison table & images | **Implement** in 10 days |
| 6 | Đề xuất nguyên liệu chưa đủ bất ngờ | Section "Hướng phát triển": add LLM API proposal | **Improvement** (future work) |
| 7 | Giám sát môi trường chỉ hiển thị số liệu | Chapter 3 (Sensor): add anomaly detection | **Implement** in 10 days |
| 8 | Tính bảo mật chủ quan | Section "Bảo mật": rewrite with realistic scenarios | **Improvement** (future work) |

### Friend's correction on item 8 (security)

> *"Mục 5 - phần 6c => không phải kiểu bảo mật hệ thống mà là hình ảnh thực phẩm trong tủ của người dùng có được phép truyền lên cloud để xử lý không"*

**Correction**: The friend is right. Item 6c (security) is not about system-level security (AppArmor, SELinux, firewalls). It is about **user privacy** — specifically whether food images captured inside the user's fridge can be transmitted to cloud services for processing (e.g., LLM API for recipe suggestions, or cloud-based YOLO inference).

**Thesis rewrite for "Bảo mật" section**:

| Old framing (incorrect) | New framing (correct) |
|---|---|
| "Distributed system security with AppArmor, SELinux, firewall rules" | "User privacy: are food images allowed to be uploaded to cloud for processing?" |
| "Encrypted storage for keys, secure boot" | "Data sovereignty: user's food images stay on-device by default; cloud processing is opt-in" |
| "API key encryption, HTTPS, rate limiting" | "Transparency: system must inform user when data leaves the device" |

**Key points for thesis**:

1. **Current design**: All processing runs on-device (RPi 4B). No images leave the system. This is a **privacy-by-design** advantage.
2. **Cloud LLM proposal** (6a): If implemented, user must explicitly opt-in. Images should be anonymized (no EXIF, no identifiable metadata) before transmission.
3. **Future consideration**: If adopting cloud YOLO inference (NVIDIA Jetson or cloud API), the same privacy rules apply.

This reframing actually makes the thesis stronger — the current architecture **already** addresses privacy by keeping everything offline.

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

**Privacy considerations** (updated per friend's feedback):
- Recipe names only are sent to LLM (no images, no personal data)
- API call is opt-in — user must confirm before data leaves device
- All LLM responses are logged locally for audit

**Why not implement now**: Requires API key management, internet connectivity handling, error handling for API failures, and user confirmation UI — too large for 10 days.

#### 6b. Proactive recommendation engine

**Problem**: The current Bù Trừ algorithm is purely reactive — it only responds when the user explicitly searches for a recipe. It cannot suggest "what can I cook with what I have."

**Proposal**: Invert the algorithm. Scan the current inventory and find all recipes that can be made with available ingredients. Sort by coverage percentage (e.g., 80%+ ingredients available). Present as "Bạn có thể nấu các món sau với nguyên liệu hiện có."

**Why not implement now**: Requires indexing recipes by ingredient (inverted index), scoring algorithm, and UI for displaying suggestions — medium complexity but low priority for thesis defense.

#### 6c. Privacy: on-device vs cloud processing (REVISED per friend's feedback)

**Problem**: The original plan framed this as "system security" (AppArmor, firewalls). The actual concern is **whether user's food images can be uploaded to cloud for processing**.

**Current state**: All processing is on-device (RPi 4B). No images or data leave the system. This is a **privacy-by-design** advantage that should be highlighted in the thesis.

**Proposal for future**: If cloud processing is added (e.g., cloud YOLO, LLM API):
- **Opt-in only**: User must explicitly enable cloud processing
- **Anonymization**: Strip EXIF, metadata, and any identifying information before upload
- **Transparency**: Show user exactly what data is being sent and to which service
- **Data retention policy**: Define how long cloud providers retain the data
- **Local fallback**: If cloud is unavailable or user opts out, fall back to on-device processing (even if less accurate)

**Why not implement now**: The current system is fully offline. Cloud integration requires network stack, user consent UI, and privacy policy documentation — beyond 10-day scope.

---

## 6. YOLO/FRT Pipeline — Friend's Tasks

### Teacher feedback

> *"Độ chính xác của mô hình nhận diện không được tốt => Cần nêu rõ quá trình cải thiện mô hình."*
> *"Còn thiếu các minh chứng cho mô hình xử lý ảnh"*

### Pipeline Stages & Per-Step Verification

The FRT pipeline has 7 distinct stages. Each stage must produce **concrete output artifacts** that prove the stage works correctly. These artifacts go into the thesis as evidence.

| # | Stage | Input | Processing | Output Artifact | Thesis Evidence |
|---|-------|-------|------------|----------------|-----------------|
| **1** | Camera Capture | USB camera `/dev/video0` | V4L2: `open()` → `ioctl` → `mmap` → `dequeue` | `sample_frame.jpg` (first raw frame) | Shows camera is working at expected resolution |
| **2** | MOG2 Motion Detection | Raw BGR frame | `cv2.createBackgroundSubtractorMOG2()` → foreground mask | `mog2_foreground_mask.jpg` + `mog2_heatmap.jpg` | Proves motion filter removes empty frames |
| **3** | Image Preprocessing | BGR frame | BGR→RGB, letterbox resize to 640×640, normalize to [0,1] | `preprocess_rgb.jpg` + `preprocess_letterbox.jpg` | Shows input tensor preparation is correct |
| **4** | YOLO Inference | 640×640×3 float32 tensor | TFLite interpreter → NMS → output boxes | `inference_table.csv` (all detections with confidence) | Raw model output before any filtering |
| **5** | NMS Filtering | Raw YOLO boxes | IoU threshold 0.45, confidence threshold 0.25 → deduplicated boxes | `nms_stats.json` (before/after box counts per frame) | Proves NMS removes duplicates |
| **6** | ByteTrack Tracking | NMS-filtered boxes across frames | IoU matching → Kalman filter → track ID assignment | `track_trajectories.json` + `boundary_events.json` | Shows persistent ID assignment |
| **7** | Annotated Output | Frame + final boxes | `cv2.rectangle()` + label + virtual boundary line | `annotated_result.jpg` + per-frame `frame_{n}_annotated.jpg` | Final visual result for thesis |

### Startup Timer: Camera Countdown Notification

The user needs a **visible countdown in the terminal** before the camera pipeline starts, so they can prepare their test object.

```
╔══════════════════════════════════════════════════════════════╗
║           FRT PIPELINE — CAMERA STARTING IN...             ║
╚══════════════════════════════════════════════════════════════╝

  Preparing camera: /dev/video0
  Using model:      YOLOv11n_260518_best_int8.tflite
  Duration:         30 seconds

  5... (check: camera free? ✓)
  4... (check: SHM ready? ✓)
  3... (check: model loaded? ✓)
  2... (check: MOG2 initialized? ✓)
  1... PIPELINE STARTED!

  ╔══════════════════════════════════════════════════════════╗
  ║  Camera is LIVE — Pipeline running at 10 FPS             ║
  ║                                                          ║
  ║  HOW TO TEST CHECK-IN:                                   ║
  ║  1. Hold an object (fruit, can, bottle) in front of      ║
  ║     the camera at the TOP of the frame                   ║
  ║  2. Slowly move it DOWNWARD across the middle line       ║
  ║  3. Watch terminal for: ✅ CHECK_IN — track_id=3         ║
  ║                                                          ║
  ║  HOW TO TEST CHECK-OUT:                                  ║
  ║  1. Hold an object at the BOTTOM of the frame            ║
  ║  2. Slowly move it UPWARD across the middle line         ║
  ║  3. Watch terminal for: ✅ CHECK_OUT — track_id=3        ║
  ║                                                          ║
  ║  Press Ctrl+C to stop the test early                     ║
  ╚══════════════════════════════════════════════════════════╝
```

**Implementation**: Add a `--countdown SECONDS` flag to `run_frt_full_test.sh`. Default: 5 seconds. The countdown runs prerequisite checks (camera device, model file, SHM) in parallel and prints a green checkmark for each.

### Live Terminal Dashboard (during pipeline run)

While the pipeline runs, the terminal should display a live-updating status panel:

```
┌──────────────────────────────────────────────────────────────┐
│  FRT PIPELINE — LIVE DASHBOARD           Elapsed: 12s / 30s │
├──────────────────────────────────────────────────────────────┤
│  Camera FPS:        9.8                                       │
│  Pipeline FPS:      8.2                                       │
│                                                              │
│  MOG2:    ████████████░░░░░░░  65% motion (last 10 frames)  │
│  YOLO:    ████████████████░░  82ms avg inference              │
│  NMS:     before=42 → after=3  (92.9% suppression)           │
│  ByteTrack:  3 active tracks                                  │
│                                                              │
│  Boundary Events:  CHECK_IN ×2   CHECK_OUT ×1               │
│  ─────────────────────────────────────────────────────────── │
│  [00:05] Track #2: CHECK_IN  → add "apple" to inventory     │
│  [00:09] Track #3: CHECK_OUT → remove "carrot" from inv.    │
│  [00:12] Track #4: CHECK_IN  → add "bottle" to inventory    │
│                                                              │
│  Latest detection: apple (99.2%) @ center=(320, 240)        │
└──────────────────────────────────────────────────────────────┘
```

This dashboard updates in-place every second using ANSI escape codes (`\033[<N>A`, `\033[J`). Already partially supported via the loguru output; the enhancement is to consolidate key metrics into a single compact panel.

### User Script: `scripts/frt_pipeline_demo.sh`

A step-by-step script that:
1. Shows a 5-second countdown with camera/model checks
2. Runs the pipeline for a configurable duration
3. Prints per-stage results as they complete
4. Saves all artifacts to `system_results/frt_demo_<timestamp>/`

```bash
#!/usr/bin/env bash
# frt_pipeline_demo.sh — Step-by-step FRT pipeline demonstration
# Usage: bash scripts/frt_pipeline_demo.sh [--duration 30] [--countdown 5]
# Output: Terminal dashboard + artifacts in system_results/frt_demo_*/

CAMERA="${CAMERA_DEVICE:-/dev/video0}"
MODEL="${MODEL_PATH:-/opt/fss/models/YOLOv11n_260518_best_int8.tflite}"
DURATION=30
COUNTDOWN=5
OUTPUT_DIR="system_results/frt_demo_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUTPUT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     FRT PIPELINE DEMO — Camera → MOG2 → YOLO → ByteTrack   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Camera:   $CAMERA"
echo "Model:    $MODEL"
echo "Duration: ${DURATION}s"
echo "Output:   $OUTPUT_DIR/"
echo ""

# ──────── Countdown with prerequisite checks ────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           PIPELINE STARTING IN ${COUNTDOWN}s...                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
for ((i=COUNTDOWN; i>=1; i--)); do
    case $i in
        5)  CHECK1="Camera $CAMERA: $( [[ -c "$CAMERA" ]] && echo '✓ AVAILABLE' || echo '✗ NOT FOUND' )" ;;
        4)  CHECK2="Model $(basename $MODEL): $( [[ -f "$MODEL" ]] && echo '✓ FOUND' || echo '✗ MISSING' )" ;;
        3)  CHECK3="SHM /dev/shm/fss_video_frame: $( [[ -f /dev/shm/fss_video_frame ]] && echo '✓ READY' || echo '⚠ NOT FOUND (will create)' )" ;;
        2)  CHECK4="MOG2 initializing... ✓" ;;
    esac
    echo -e "\033[1m  $i...\033[0m"
    [[ -n "$CHECK1" ]] && echo "    $CHECK1" && unset CHECK1
    [[ -n "$CHECK2" ]] && echo "    $CHECK2" && unset CHECK2
    [[ -n "$CHECK3" ]] && echo "    $CHECK3" && unset CHECK3
    [[ -n "$CHECK4" ]] && echo "    $CHECK4" && unset CHECK4
    sleep 1
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🎥 PIPELINE IS NOW RUNNING                                 ║"
echo "║                                                             ║"
echo "║  CHECK-IN:  Move object TOP → BOTTOM (cross middle line)    ║"
echo "║  CHECK-OUT: Move object BOTTOM → TOP (cross middle line)    ║"
echo "║                                                             ║"
echo "║  Press Ctrl+C to stop                                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ──────── Run pipeline (uses existing comprehensive test) ────────
source frt_app/py_ai_core/venv/bin/activate
python tests/frt_app/"[FRT-MAIN]-test_comprehensive_frt.py" \
    --camera "$CAMERA" \
    --model "$MODEL" \
    --output-dir "$OUTPUT_DIR" \
    --duration "$DURATION" \
    2>&1 | tee "$OUTPUT_DIR/full_log.txt"

# ──────── Print per-stage results summary ────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     PIPELINE RESULTS — Per-Stage Artifacts                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Stage 1: Camera
if [[ -f "$OUTPUT_DIR/sample_frame.jpg" ]]; then
    echo "  ✅ [Stage 1] Camera Capture: sample_frame.jpg ($(du -h "$OUTPUT_DIR/sample_frame.jpg" | cut -f1))"
else
    echo "  ❌ [Stage 1] Camera Capture: NO FRAME"
fi

# Stage 2: MOG2
if [[ -f "$OUTPUT_DIR/mog2_foreground_mask.jpg" ]]; then
    echo "  ✅ [Stage 2] MOG2 Motion: mog2_foreground_mask.jpg"
    echo "     → mog2_heatmap.jpg"
else
    echo "  ❌ [Stage 2] MOG2 Motion: NO MASK"
fi

# Stage 3: Preprocessing
if [[ -f "$OUTPUT_DIR/preprocess_letterbox.jpg" ]]; then
    echo "  ✅ [Stage 3] Preprocessing: preprocess_rgb.jpg + preprocess_letterbox.jpg"
else
    echo "  ❌ [Stage 3] Preprocessing: NO OUTPUT"
fi

# Stage 4: YOLO Inference
if [[ -f "$OUTPUT_DIR/inference_table.csv" ]]; then
    LINE_COUNT=$(wc -l < "$OUTPUT_DIR/inference_table.csv")
    echo "  ✅ [Stage 4] YOLO Inference: inference_table.csv ($((LINE_COUNT-1)) detections)"
else
    echo "  ❌ [Stage 4] YOLO Inference: NO TABLE"
fi

# Stage 5: NMS
if [[ -f "$OUTPUT_DIR/nms_stats.json" ]]; then
    echo "  ✅ [Stage 5] NMS: nms_stats.json"
    python3 -c "
import json
with open('$OUTPUT_DIR/nms_stats.json') as f:
    nms = json.load(f)
s = nms.get('summary', {})
print(f'     → Avg boxes before NMS: {s.get(\"boxes_before_nms_avg\",\"?\")} \
→ after: {s.get(\"boxes_after_nms_avg\",\"?\")} \
(suppression: {s.get(\"suppression_rate_avg\",\"?\")}%)')
"
else
    echo "  ❌ [Stage 5] NMS: NO STATS"
fi

# Stage 6: ByteTrack
if [[ -f "$OUTPUT_DIR/boundary_events.json" ]]; then
    EVENTS=$(python3 -c "import json; e=json.load(open('$OUTPUT_DIR/boundary_events.json')); print(len(e))" 2>/dev/null || echo "0")
    echo "  ✅ [Stage 6] ByteTrack: boundary_events.json ($EVENTS events)"
    python3 -c "
import json
events = json.load(open('$OUTPUT_DIR/boundary_events.json'))
ci = sum(1 for e in events if 'CHECK_IN' in e.get('event',''))
co = sum(1 for e in events if 'CHECK_OUT' in e.get('event',''))
print(f'     → CHECK_IN: {ci} | CHECK_OUT: {co}')
# Print last 3 events
for e in events[-3:]:
    print(f'     → [{e.get(\"timestamp\",\"?\")}] Track {e.get(\"track_id\",\"?\")}: {e.get(\"event\",\"?\")}')
" 2>/dev/null
else
    echo "  ❌ [Stage 6] ByteTrack: NO EVENTS"
fi

# Stage 7: Final annotation
if [[ -f "$OUTPUT_DIR/annotated_result.jpg" ]]; then
    echo "  ✅ [Stage 7] Annotated Output: annotated_result.jpg ($(du -h "$OUTPUT_DIR/annotated_result.jpg" | cut -f1))"
    ls "$OUTPUT_DIR"/latest_frames/frame_*_annotated.jpg 2>/dev/null && \
        echo "     → Per-frame annotated: $(ls "$OUTPUT_DIR"/latest_frames/frame_*_annotated.jpg 2>/dev/null | wc -l) frames"
else
    echo "  ❌ [Stage 7] Annotated Output: NO IMAGE"
fi

echo ""
echo "  📁 Full results: $OUTPUT_DIR/"
echo "  📄 Pipeline report: $OUTPUT_DIR/pipeline_report.json"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     FRT PIPELINE DEMO COMPLETE                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
```

### Tasks for friend

| Task | Description | Effort |
|------|-------------|--------|
| **Accuracy benchmark** | Run all 5 YOLOv11n quantization variants on a labeled test set. Generate mAP, precision, recall, F1 table | 2 days |
| **Fix ByteTrack** | Debug why `total_events: 0` across all sessions (likely virtual line calibration or confidence threshold). Annotate tracking results | 2 days |
| **Improvement log** | Document: base model → fine-tuning → improved model. Show before/after metrics with annotated images | 1 day |
| **Evidence collection** | Select best annotated frames from `system_results/`, create comparison grids (ground truth vs detection) | 1 day |
| **Replace diagrams** | Replace YOLO architecture diagrams in thesis with actual `annotated_result.jpg` images from real sessions | 1 day |
| **Startup timer** | Add `--countdown` flag to `run_frt_full_test.sh` with 5-second timer + prerequisite checks | 0.5 day |
| **Live dashboard** | Enhance terminal output with ANSI-based live status panel (FPS, detections, boundary events) | 1 day |
| **Pipeline demo script** | Create `scripts/frt_pipeline_demo.sh` with 7-stage results summary | 0.5 day |

### What goes in "Improvement" section

- Fine-tuning YOLO on a custom fridge-food dataset (currently using COCO-pretrained weights)
- Experimenting with YOLOv26n variants for better speed-accuracy tradeoff
- Deploying on NVIDIA Jetson or TPU for real-time inference

### Branch: `FRTApp-dev`

Friend works on `FRTApp-dev`. Tests live in `tests/frt_app/` which already exist.

---

## 7. Teacher Feedback Cross-Reference

| # | Feedback | Solution | Section | Timeline | Branch |
|---|---|---|---|---|---|
| 1 | Bỏ qua yêu cầu cơ khí | Add hardware requirement section to thesis | **§5 — Thesis docs** | Improvement | `ui-dev` (docs only) |
| 2 | Thay ảnh minh họa bằng ảnh thật | Capture 10+ screenshots from system_results/ and UI | **§5 — Thesis all chapters** | 10 days | `ui-dev` (screenshots) |
| 3 | NLP công nghệ quá lớn | Remove CRF, replace with filter+sort | **§1 — NLP Pipeline** | 10 days | `recommend_system` |
| 4 | Độ chính xác FRT không tốt | Run benchmarks, document improvement process | **§6 — Friend's task** | 10 days | `FRTApp-dev` |
| 5 | Thiếu minh chứng | Recipe comparison table + FRT accuracy table | **§5 — Thesis docs** + Friend | 10 days | `ui-dev` + `FRTApp-dev` |
| 6 | Đề xuất chưa bất ngờ | LLM API proposal + proactive recipe suggestion | **§5 §6a/b — Improvement** | Improvement | `ui-dev` (docs only) |
| 7 | Giám sát chỉ hiển thị số liệu | TemperatureMonitor with 3 anomaly rules + UI notification | **§2 — Sensor Daemon** | 10 days | `feat/temperature-monitor` |
| 8 | Bảo mật chủ quan → Privacy | Reframe as user privacy (food images on cloud?) | **§5 §6c — Improvement** | Improvement | `ui-dev` (docs only) |

### Legend

| Label | Meaning |
|---|---|
| **10 days** | Can be implemented within the 10-day window |
| **Improvement** | Proposed in thesis "Hướng phát triển" section only |
| **Friend's task** | Assigned to team member working on FRT/YOLO pipeline |

---

## Summary: Branch Strategy

```
main (stable)
├── ui-dev (ACTIVE) ───────────────────── §3 (chips), §4 (QR), §5 (docs/screenshots)
├── folder_restructure (CURRENT) ──────── Just folder layout (merge to ui-dev when done)
├── feat/temperature-monitor (NEW) ────── §2 (TemperatureMonitor C++ + UI notification)
├── recommend_system ──────────────────── §1 (NLP filter+sort rewrite)
└── FRTApp-dev ────────────────────────── §6 (Friend's YOLO tasks)

For testing:
  └─ Write tests inline on each feature branch (Option A)
  └─ If cross-component integration needed → create test/thesis-integration (optional)
```

No single branch for everything — use **feature-per-branch** consistent with existing pattern.
