# RecipeExtractor Test Plan

## Overview

RecipeExtractor is a standalone D-Bus service (`vn.edu.uit.FSS.RecipeExtractor`) that:
- Receives recipe names via D-Bus method `ExtractAndPersistRecipe(recipe_name)`
- Runs CRF-based NLP inference (`RecipeAnalyzerEngine`) to extract ingredients
- Persists results to DBDaemon via D-Bus `InsertRequest()`
- Returns structured JSON ingredient list

## 1. Standalone Unit Tests

### 1.1 RecipeExtractorDbusService

| Test | Description | Expected |
|------|-------------|----------|
| `test_init_without_nlp` | Create service without NLP engine | Service created, nlp_engine=None, logger initialized |
| `test_init_with_nlp` | Create service with mock NLP engine | Engine stored, SDBUS_AVAILABLE flag checked |
| `test_set_nlp_engine` | Set NLP engine after construction | Engine stored, accessible via nlp_engine |
| `test_setup_bus_without_sdbus` | Call setup_bus_service when sdbus unavailable | Returns False, logged warning |
| `test_extract_and_persist_no_loop` | Call extract_and_persist without event loop running | Returns JSON error: "Event loop not running" |
| `test_handle_extract_no_nlp` | Internal handler without NLP engine | Returns JSON error: "NLP engine not initialized" |
| `test_handle_extract_success` | Mock NLP returns valid ingredients | Returns JSON with SUCCESS, ingredients, persisted flag |
| `test_handle_extract_nlp_error` | NLP returns ERROR status | Returns JSON with error status propagated |
| `test_handle_extract_nlp_not_found` | NLP returns NOT_FOUND with suggestions | Returns JSON with NOT_FOUND, suggestions included |
| `test_stop_service` | Stop the service when loop running | Loop stopped, event thread joined, is_connected=False |

### 1.2 RecipeExtractorMain

| Test | Description | Expected |
|------|-------------|----------|
| `test_init` | Create main instance | RecipeExtractorMain created, RecipeExtractorDbusService initialized |
| `test_init_service_no_sdbus` | init_service when sdbus unavailable | Returns False (service setup fails) |
| `test_start_stop` | Start then stop service | is_running transitions true→false |
| `test_ensure_nlp_engine_loaded` | Lazy load NLP engine on first call | NLP engine loaded and set on D-Bus service |
| `test_ensure_nlp_engine_no_model` | Lazy load fails gracefully without model | Returns False, no exception raised |

### 1.3 Bridge Data Transformation (`recommend_dbus_listener.py`)

| Test | Description | Expected |
|------|-------------|----------|
| `test_transform_ingredients_empty` | Empty ingredients list | Returns empty items, counts = 0 |
| `test_transform_ingredients_single` | Single ingredient | name=ingredient, required=quantity, available=0, status="missing" |
| `test_transform_ingredients_multiple` | Multiple ingredients | All transformed correctly, missing_count = len(items) |
| `test_transform_no_quantity` | Ingredient without quantity | required defaults to "1" |

## 2. Integration Test Plans

### 2.1 recipe_extractor ↔ electron_app (via bridge)

**Data Flow**: 
```
MMM-FSS-Recommend.js → node_helper.js → recommend_dbus_listener.py 
    → D-Bus → RecipeExtractor.ExtractAndPersistRecipe()
    ← JSON response ← D-Bus ←
    → transform_ingredients() → stdout JSON → node_helper.js → socket → MMM-FSS-Recommend.js
```

**Test Scenarios**:
1. Bridge receives SEARCH message → calls RecipeExtractor → returns transformed result
2. Bridge receives SEARCH for unknown recipe → RecipeExtractor returns NOT_FOUND → bridge returns ERROR
3. Bridge handles D-Bus timeout → returns ERROR
4. Bridge handles RecipeExtractor returning malformed JSON → returns ERROR
5. Sequential searches (multiple foods) → each returns independently
6. Mock mode (recipe="test"/"dev") → returns hardcoded mock data

**Test Approach**: 
- Unit test `transform_ingredients()` function in isolation
- Integration: Mock D-Bus proxy, feed SEARCH messages to stdin, capture stdout JSON

### 2.2 recipe_extractor ↔ db_daemon

**Data Flow**:
```
RecipeExtractor._handle_extract_and_persist()
    → NLP extraction (success)
    → D-Bus call: DBDaemon.InsertRequest(recipe_name, ingredients_json, batch_id)
    ← D-Bus response: bool
```

**Test Scenarios**:
1. `_call_dbus_insert_request` with valid data → returns True
2. `_call_dbus_insert_request` when DBDaemon unavailable → returns False
3. `_handle_extract_and_persist` with persist success → JSON includes `persisted: true`
4. `_handle_extract_and_persist` with persist failure → JSON includes `persisted: false`
5. NLP extraction fails → InsertRequest NOT called

**Test Approach**:
- Unit test: Mock `_call_dbus_insert_request` via async mocking
- Verify it's called with correct parameters
- Verify error handling when DBDaemon D-Bus is down

### 2.3 recipe_extractor ↔ recommend_daemon

**Data Flow**:
```
recommend_daemon/main.py → imports recipe_extractor.src.RecipeAnalyzerAPI
    → Uses RecipeAnalyzerEngine for NLP extraction
    → RecipeAnalyzerEngine.generate_fss_request(recipe_name)
```

**Test Scenarios**:
1. recommend_daemon can import RecipeAnalyzerEngine from recipe_extractor
2. Both components use the same model and recipe paths (verification)
3. Consistent ingredient format across both components

**Test Approach**:
- Verify import path: `from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine`
- Run same recipe through both components, verify identical output format
- End-to-end: recipe_extractor extracts → recommend_daemon consumes

## 3. Implementation Priority

1. ✅ **`tests/test_recipe_extractor_service.py`** — Unit tests for D-Bus service logic (no D-Bus required)
2. ✅ **`tests/test_recipe_extractor_main.py`** — Unit tests for main lifecycle
3. ✅ **Bridge transformation tests** — Included in test_recipe_extractor_service.py
4. ⬜ **Integration tests** — Require running D-Bus or mock bus
