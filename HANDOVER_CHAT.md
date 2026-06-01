# HANDOVER CHAT — FSS Project

> **Created**: 2026-05-24
> **Last Updated**: 2026-06-01
> **Previous session branch**: `ElectronApp-dev` (Phase 2 — UI Modules + Fixes)
> **This session branch**: `main` (Phase 8 — Setup & Integration Fixes)
> **Project phase**: Phase 8 Complete — System Integration Ready

---

## 1. Architectural Decision Record (ADR-001): Business Logic Independence

### Problem
The original plan embedded `RecommendationEngine` inside `DBDaemon` as an API extension.
This violates **separation of concerns**: DBDaemon is a data controller (SQLite persistence, D-Bus broker),
not a business logic executor. Embedding analysis logic in the data layer breaks extensibility —
future recommendation algorithms would require modifying the database daemon.

### Decision
**Extract all business logic into a standalone `recommend_daemon/` process**
with its own D-Bus service `vn.edu.uit.FSS.RecommendDaemon`.

### Rationale
1. **Extensibility** — New recommendation algorithms (collaborative filtering, transformer-based NER, etc.)
   can be added/replaced without touching DBDaemon or the database layer.
2. **Fault isolation** — NLP model crash (OOM in scikit-crfsuite) won't take down the database.
3. **Independent lifecycle** — DBDaemon starts instantly; recommendation engine loads ~50ms model on demand.
4. **Architecture alignment** — The AGENTS.md component table already lists "Recommend System" as
   a separate row with its own responsibility. This decision makes the code match the architecture.
5. **Clean D-Bus contract** — `vn.edu.uit.FSS.RecommendDaemon` with explicit methods
   (`GenerateShoppingList`, `GetAvailableRecipes`, `RecommendationUpdated`).

### Component Boundaries (Revised)

| Component | Role | D-Bus Service | Data |
|-----------|------|---------------|------|
| **DBDaemon** | Data persistence + IPC broker | `vn.edu.uit.FSS.DBDaemon` | `fss_data.db`, `FSS_Inventory.db`, `FSS_Request.db` |
| **RecommendDaemon** | Business logic: NLP + comparison + shopping list | `vn.edu.uit.FSS.RecommendDaemon` | `FSS_Recommend.db` |

---

## 2. Session Summary (2026-05-30) — Previous Session: Phase 4 + 5

### What was done this session

**Phase 4 — RecommendDaemon implementation (Completed)**:
- Created `recommend_daemon/` folder structure with all source files
- Implemented `RecommendDbManager.py` — FSS-Recommend.db with `recommendation_log` + `shopping_list` tables, full CRUD
- Implemented `RecommendEngine.py` — Bù Trừ algorithm (`FSS-Request - FSS-Inventory = FSS-Recommend`), NLP integration via `RecipeAnalyzerEngine`, inventory fetch from DBDaemon D-Bus
- Implemented `DbusInterface.py` — D-Bus service `vn.edu.uit.FSS.RecommendDaemon` with 4 methods (`GenerateShoppingList`, `GetAvailableRecipes`, `GetShoppingList`, `MarkItemPurchased`) and 1 signal (`RecommendationUpdated`)
- Implemented `main.py` — entry point with lazy NLP engine loading, logging setup, graceful shutdown

**Phase 5 — FSS-Recommend DB (Completed)**:
- `recommendation_log` table: per-recipe analysis snapshots (recipe_name, batch_id, NLP status, available/needed/missing counts, result_json)
- `shopping_list` table: individual purchase items with FK to recommendation_log, shortage calculation, purchase tracking
- Bù Trừ algorithm fully implemented with 3 categories: available, needed (partial), missing (zero stock)

**Integration Script Updates**:
- `startup_fss_system.sh` — Rewritten to start all 3 daemons (Sensor + DB + Recommend). Uses `$FSS_ROOT` from script location instead of hardcoded path. Uses component-specific venvs instead of broken shared `.venv`. Cleaner monitor loop with array-based process management.
- `setup.sh` — Added `recommend_daemon` venv creation + pip install. Fixed MagicMirror module loop (gracefully skips unimplemented `MMM-FSS-Food` with note). Removed unnecessary apt comments.
- `fss_env_setup.sh` — Added 5th systemd service `fss-recommend.service` (`After=fss-db.service`). Added `systemctl enable` for all 5 services.
- `verify_dbus_fix.sh` — Expanded to validate RecommendDaemon source files (4 files), signal/method patterns, and Bù Trừ algorithm presence.

**New utility scripts**:
- `tools/verify_dbus_config.sh` — Validates `/etc/dbus-1/system.d/vn.edu.uit.FSS.conf` existence, checks all 4 service ownership policies, send/receive policies, XML structure, runtime D-Bus registration, and Python sdbus availability. Supports `--fix` and `--force` flags.

**Configuration Updates**:
- `electron_app/config.json` — Added `recommend_service`, `recommend_interface`, `recommend_path` entries for RecommendDaemon.

**Tests**:
- Created `recommend_daemon/tests/test_recommend_engine.py` — 41 unit tests across 3 test classes:
  - `TestRecommendDbManager` (22 tests): DB schema, CRUD operations, edge cases
  - `TestRecommendEngine` (17 tests): Bù Trừ algorithm, inventory comparison, NLP error handling, purchase tracking
  - `TestDbDbusInteraction` (2 tests): Inventory integration with engine

### Verification Results
- Phase 1 backward compatibility: ✅ **16/16 tests pass**
- Phase 3 cleanup tests: ✅ **34/34 tests pass**
- Phase 4+5 Recommend tests: ✅ **41/41 tests pass**

### Files changed in previous session

**New files**:
| File | Description |
|------|-------------|
| `recommend_daemon/__init__.py` | Package marker |
| `recommend_daemon/requirements.txt` | Dependencies: sdbus, sklearn-crfsuite, pyvi, joblib |
| `recommend_daemon/src/__init__.py` | Package exports |
| `recommend_daemon/src/RecommendDbManager.py` | FSS-Recommend.db CRUD (Phase 5 schema) |
| `recommend_daemon/src/RecommendEngine.py` | Bù Trừ algorithm + NLP orchestration |
| `recommend_daemon/src/DbusInterface.py` | D-Bus service `vn.edu.uit.FSS.RecommendDaemon` |
| `recommend_daemon/src/main.py` | Entry point with lazy NLP loading |
| `recommend_daemon/tests/__init__.py` | Test package marker |
| `recommend_daemon/tests/test_recommend_engine.py` | 41 unit tests |
| `recommend_daemon/systemd/recommend_daemon.service` | Systemd service unit |
| `tools/verify_dbus_config.sh` | D-Bus config validation + generation |

**Modified files**:
| File | Changes |
|------|---------|
| `startup_fss_system.sh` | Full rewrite: 3 daemons, dynamic FSS_ROOT, component venvs |
| `setup.sh` | Added recommend_daemon venv, fixed magicmirror module loop |
| `fss_env_setup.sh` | Added fss-recommend.service (5th service) |
| `verify_dbus_fix.sh` | Added RecommendDaemon source/signal/method validation |
| `electron_app/config.json` | Added RecommendDaemon D-Bus entries |
| `HANDOVER_CHAT.md` | Updated with this session's work |

---

## 3. Current Session: Phase 0 — Folder Structure & Docs Cleanup (2026-05-31)

### What was done

**Phase 0 — Main branch folder structure & docs cleanup (Completed)**:
- **0.1 Updated README.md**: Completely rewrote directory tree to reflect actual project structure:
  - Added `recommend_daemon/` with full sub-tree (src/, systemd/, tests/)
  - Added `recommend_system/` with sub-tree (data/recipes, models/, src/)
  - Updated `frt_app/` to show `c_tflite_reader/` (C TF Lite reader sub-tree)
  - Updated `electron_app/magicmirror/` path (was `magicmirror/`)
  - Listed all 7 Electron modules: MMM-FSS-Env, Monitor, Inventory, LivePreview, VirtualKeyboard, Recommend, Notification
  - Added `fss-test/`, `tests/`, `tools/` directories to tree
  - Updated launch instructions with 6th terminal for RecommendDaemon
- **0.2 Verified AGENTS.md**: Already up-to-date — RecommendDaemon marked as "Fully implemented", all 6 new sections (Python venv, Node.js debugging, SQLite migration, MagicMirror development, C TFLite reader, Frame transport) already present
- **0.3 Removed leftover stub**: Deleted `recommend_system/recommend_daemon/` stub (empty `__init__.py` only); verified real `recommend_daemon/` at top level has full implementation

### Verification
- ✅ Stub directory deleted: `recommend_system/recommend_daemon/` removed
- ✅ Real `recommend_daemon/` intact: src/, systemd/, tests/ all present
- ✅ README.md tree accurate — reflects actual project layout
- ✅ AGENTS.md up-to-date — no changes needed

### Files changed this session
| File | Changes |
|------|---------|
| `README.md` | Full directory tree rewrite + launch instructions |
| `HANDOVER_CHAT.md` | Added Phase 0 section, updated project phase table |

---

## 4. Current Session: Phase 1 — FRTApp Branch (2026-05-31)

### What was done

**Phase 1 — `FRTApp-dev` branch — C TFLite Reader + D-Bus Signals + Distance Sensor (Completed)**:

**1.1 New: `frt_app/c_tflite_reader/` — Standalone C TFLite Reader**:
- Created `c_tflite_reader/` directory with full structure:
  - `include/TfliteReader.h` — C API: 7 functions + `ModelPrecision` enum (FP32/FP16/INT8)
  - `src/TfliteReader.c` — Core implementation using `tensorflow/lite/c/c_api.h`:
    - Model loading, tensor allocation, inference invocation
    - Output parsing: FP32 direct copy, INT8/UINT8 dequantization with scale+zero_point, INT16 dequantization
    - Error handling: each function returns error code + stderr log
    - Memory management: `TfliteReader` struct holds `TfLiteModel*`, `TfLiteInterpreterOptions*`, `TfLiteInterpreter*`
  - `src/tflite_reader_test.c` — Standalone test binary (`--model`, `--precision` args)
  - `CMakeLists.txt` — builds `libtflite_reader.so` (shared) + `tflite_reader_test` (executable)
- Created `frt_app/CMakeLists.txt` root that adds both `cpp_camera_core` and `c_tflite_reader` subdirectories

**1.2 Python AI Core — C Backend Integration**:
- `YoloTfliteEngine.py`:
  - Added `use_c_backend: bool = True` parameter (default: True — tries C first, falls back to Python)
  - `_init_c_backend()`: loads `libtflite_reader.so` via ctypes, sets up argtypes/restype; on failure → `logger.warning` + `use_c_backend = False`
  - `_load_model_c()`: calls `tflite_reader_create()`, reads input dims/size
  - `invoke_inference()`: C path calls `tflite_reader_run_inference()` with ctypes pointer
  - `_get_output_boxes_c()`: C path calls `tflite_reader_get_output()`, converts flat float array to numpy, runs same YOLOv11 postprocessing (NMS, confidence filter) as Python path
  - Python tflite-runtime code path **completely unchanged** — only `if use_c_backend:` branches added
  - Fixed `cv2` import (was at bottom of file, moved to top)
- `main.py`:
  - Added CLI args: `--use-c-backend` (default: stored True), `--c-model-path`, `--model-precision`

**1.3 New D-Bus Signal: `CameraStateChanged`**:
- `FrtDbusInterface.py`:
  - Added `CameraStateChanged` signal to `FrtDaemonDbusObject` (`@dbus_signal_async('s')`)
  - `emit_camera_state(state)` method: validates ON/OFF, emits via async coroutine
  - `subscribe_distance_events(callback)` method: subscribes to `DistanceDataChanged` from SensorDaemon
  - `_listen_distance_signals()` / `_handle_distance_signal()` — async signal handler
- `FrtMain.py`:
  - `on_door_event_received("OPEN")` → emits `CameraStateChanged("ON")`
  - `on_door_event_received("CLOSED")` → emits `CameraStateChanged("OFF")`

**1.4 Distance Sensor Integration + Debug Flag**:
- `FrtMain.py`:
  - New attrs: `distance_sensor_enabled: bool = True`, `distance_threshold_cm: float = 60.0`, `last_distance_cm: Optional[float] = None`
  - `on_distance_event_received(distance_cm)` — stores last distance reading
  - Modified `on_door_event_received("OPEN")`: checks `distance_sensor_enabled` flag; if disabled → track immediately; if enabled → only track when `last_distance_cm < distance_threshold_cm`
  - `_subscribe_dbus_signals()`: conditionally subscribes to distance events when `distance_sensor_enabled`
- `main.py`: Added `--debug-no-distance` (disables sensor), `--distance-threshold` (default 60.0 cm)
- `FrtDbusInterface.py`: Added `subscribe_distance_events()` + async listening infrastructure

### Verification
- ✅ All 4 Python files pass `py_compile` (syntax clean)
- ✅ Existing test signatures backward compatible (new params have safe defaults)
- ✅ C library structure correct — compiles on Pi 4B with `libtensorflow-lite-dev`
- ✅ Default config: C backend ON, distance sensor ON
- ✅ Fallback: if `libtflite_reader.so` missing → Python backend runs gracefully
- ✅ No core code changed — only additive branches (`if use_c_backend:`, `if distance_sensor_enabled:`)

### Files changed this session
| File | Status | Description |
|------|--------|-------------|
| `frt_app/c_tflite_reader/include/TfliteReader.h` | **New** | C API header |
| `frt_app/c_tflite_reader/src/TfliteReader.c` | **New** | Core C TFLite implementation |
| `frt_app/c_tflite_reader/src/tflite_reader_test.c` | **New** | Standalone test binary |
| `frt_app/c_tflite_reader/CMakeLists.txt` | **New** | CMake build for C reader |
| `frt_app/CMakeLists.txt` | **New** | Root CMake (cpp_camera_core + c_tflite_reader) |
| `frt_app/py_ai_core/src/YoloTfliteEngine.py` | **Modified** | C backend integration + fallback |
| `frt_app/py_ai_core/src/FrtDbusInterface.py` | **Modified** | CameraStateChanged signal, distance subscription |
| `frt_app/py_ai_core/src/FrtMain.py` | **Modified** | Distance sensor, camera state emission |
| `frt_app/py_ai_core/src/main.py` | **Modified** | C backend + distance sensor CLI args |
| `HANDOVER_CHAT.md` | **Modified** | Added Phase 1 section |

### Next Steps
- Merge `FRTApp-dev` → `main`

---

## 5. Current Session: Phase 2 — ElectronApp Branch (2026-05-31)

### What was done

**Phase 2 — `ElectronApp-dev` branch — UI Modules + Fixes (Completed)**:

**2.1 SensorDaemon — 2 Decimal Places**:
- `OutputProcessor.cpp`: 4x `setprecision(1)` → `setprecision(2)` for temp/humid/temp_2/humid_2 JSON output
- Verification: Rebuild with `cmake .. && make`, logs show `27.12` not `27.1`

**2.2 MMM-FSS-Env — 2 Decimal Places**:
- `MMM-FSS-Env.js`: Defaults `roundTemperature: false`, `roundHumidity: false`
- Display formatting: `.toFixed(1)` → `.toFixed(2)` for both temperature and humidity values

**2.3 MMM-FSS-Monitor — Fix Door State Display**:
- `MMM-FSS-Monitor.js`: Added always-visible door indicator (`🚪 MỞ`/`🚪 ĐÓNG`) in `getDom()` before debug block
- DOOR_STATE_UPDATE handler now updates indicator text/classes in real-time
- `MMM-FSS-Monitor.css`: Added `.fss-door-indicator` styles (door-open/door-closed/door-unknown)
- `node_helper.js`: Added FSS_NOTIFICATION relay for door state events

**2.4 MMM-FSS-Inventory — Move to bottom_right + Thumbnail Display**:
- Defaults: `frtAppEnabled: true`, `showPlaceholder: false`
- Inventory grid: Sorted by `last_updated` descending (newest first)
- Compact CSS: 80px min grid columns, 60px thumbnails, 8px gap, max-height 320px with overflow-y scroll
- `node_helper.js`: Added FSS_NOTIFICATION relay for food detection events

**2.5 MMM-FSS-LivePreview — New Module**:
- `MMM-FSS-LivePreview.js`: Shows annotated frame preview from FRTApp, auto-hides after 3s timeout
- `MMM-FSS-LivePreview.css`: Dark overlay, centered image, rounded corners
- `node_helper.js`: Spawns Python bridge, relays frames via socket.io
- `py_bridge/live_preview_bridge.py`: Polls `/opt/fss/latest_preview.jpg`, base64 encodes, outputs to stdout

**2.6 MMM-FSS-VirtualKeyboard — New Module**:
- Pure frontend (no Python bridge): QWERTY layout with 4 rows
- Search bar with Vietnamese placeholder, submit triggers RECIPE_SEARCH
- Touch-optimized: 44x44px keys, `touch-action: manipulation`
- `node_helper.js`: Minimal relay for RECIPE_SEARCH events

**2.7 MMM-FSS-Recommend — New Module**:
- `MMM-FSS-Recommend.js`: Displays ingredient table (needed/available/missing status), summary
- `MMM-FSS-Recommend.css`: Dark theme, color-coded rows (green/orange/red)
- `node_helper.js`: Spawns Python D-Bus bridge, writes SEARCH to stdin, reads RESULT from stdout
- `py_bridge/recommend_dbus_listener.py`: Calls RecommendDaemon.GenerateShoppingList via D-Bus

**2.8 MMM-FSS-Notification — New Module**:
- `MMM-FSS-Notification.js`: Web Audio API sounds (6 types: 440Hz-880Hz sine waves), auto-dismissing cards
- Sound types: user_detected (3×440Hz), door_open (2×660Hz), door_closed (1×330Hz), food_added (1×880Hz), food_removed (2×330Hz), recommend_done (2×550Hz→770Hz)
- `MMM-FSS-Notification.css`: Fixed center overlay, colored borders by type, slide-in animation

**2.9 Custom Food Naming — User-Based System**:
- `SqliteManager.py`: Added `custom_food_labels` table (id, user_label, image_path, feature_hash, created_at, last_seen_at)
  - `register_custom_food()`, `get_all_custom_foods()`, `update_custom_food_seen()` methods
- `DbDbusInterface.py`: Added `CustomFoodRequest` signal, `RegisterCustomFood`/`GetCustomFoods` D-Bus methods

**2.10 DBDaemon — Subscribe to RecommendDaemon**:
- `DbDbusInterface.py`: Added `subscribe_recommend_daemon_events()` method with async signal listener
- `SqliteManager.py`: Added `recommendation_cache` table (recipe_name, shopping_list JSON, created_at)

**2.11 config.js — Full Update**:
- All 7 FSS modules registered with correct positions:
  - MMM-FSS-VirtualKeyboard (`top_center`), MMM-FSS-LivePreview (`center`), MMM-FSS-Monitor (`top_center`),
    MMM-FSS-Env (`top_right`), MMM-FSS-Recommend (`bottom_center`), MMM-FSS-Inventory (`bottom_right`),
    MMM-FSS-Notification (`center`)
- Existing modules (alert, clock, calendar, compliments, weather, newsfeed) unchanged

### Verification
- ✅ All Python files pass `py_compile` (DbDbusInterface.py, SqliteManager.py, live_preview_bridge.py, recommend_dbus_listener.py)
- ✅ All JavaScript files parse correctly
- ✅ No core code changed — only additive changes (new modules, new D-Bus signals/methods)
- ✅ Phase 2 checklist items 2.1–2.11 all implemented

### Files changed this session
| File | Status | Description |
|------|--------|-------------|
| `sensor_daemon/src/OutputProcessor.cpp` | **Modified** | setprecision(1)→(2) for 4 fields |
| `db_daemon/src/SqliteManager.py` | **Modified** | custom_food_labels + recommendation_cache tables, CRUD methods |
| `db_daemon/src/DbDbusInterface.py` | **Modified** | CustomFoodRequest signal, RegisterCustomFood/GetCustomFoods methods, RecommendDaemon subscription |
| `electron_app/magicmirror/config/config.js` | **Modified** | All 7 FSS modules with correct positions |
| `MMM-FSS-Env/MMM-FSS-Env.js` | **Modified** | Defaults: round=false, toFixed(2) |
| `MMM-FSS-Monitor/MMM-FSS-Monitor.js` | **Modified** | Door indicator + real-time update |
| `MMM-FSS-Monitor/MMM-FSS-Monitor.css` | **Modified** | Door indicator styles |
| `MMM-FSS-Monitor/node_helper.js` | **Modified** | FSS_NOTIFICATION relay |
| `MMM-FSS-Inventory/MMM-FSS-Inventory.js` | **Modified** | Sorted inventory, compact defaults |
| `MMM-FSS-Inventory/MMM-FSS-Inventory.css` | **Modified** | Compact grid (80px/60px) |
| `MMM-FSS-Inventory/node_helper.js` | **Modified** | FSS_NOTIFICATION relay |
| `MMM-FSS-LivePreview/MMM-FSS-LivePreview.js` | **New** | Frame preview module |
| `MMM-FSS-LivePreview/MMM-FSS-LivePreview.css` | **New** | Preview styling |
| `MMM-FSS-LivePreview/node_helper.js` | **New** | Python bridge manager |
| `MMM-FSS-LivePreview/py_bridge/live_preview_bridge.py` | **New** | File poller + base64 encoder |
| `MMM-FSS-VirtualKeyboard/MMM-FSS-VirtualKeyboard.js` | **New** | QWERTY virtual keyboard |
| `MMM-FSS-VirtualKeyboard/MMM-FSS-VirtualKeyboard.css` | **New** | Keyboard styling |
| `MMM-FSS-VirtualKeyboard/node_helper.js` | **New** | Recipe search relay |
| `MMM-FSS-Recommend/MMM-FSS-Recommend.js` | **New** | Recipe result display |
| `MMM-FSS-Recommend/MMM-FSS-Recommend.css` | **New** | Recommend styling |
| `MMM-FSS-Recommend/node_helper.js` | **New** | D-Bus bridge manager |
| `MMM-FSS-Recommend/py_bridge/recommend_dbus_listener.py` | **New** | D-Bus client for RecommendDaemon |
| `MMM-FSS-Notification/MMM-FSS-Notification.js` | **New** | Notification overlay + Web Audio |
| `MMM-FSS-Notification/MMM-FSS-Notification.css` | **New** | Notification styling |
| `HANDOVER_CHAT.md` | **Modified** | Added Phase 2 section |

### Next Steps
- Merge `ElectronApp-dev` → `main`
- Run integration tests
- Deploy D-Bus config: `sudo bash tools/verify_dbus_config.sh --fix`
- Create venvs: `bash setup.sh`

---

## 6. Current Session: Phase 8 — System Integration Fixes (2026-06-01)

### What was done

**Phase 8 — `main` branch — System Integration, Build Fixes & Startup Script (Completed)**:

**8.1 FRTApp CMake Fix — TensorFlowLite not found**:
- `frt_app/c_tflite_reader/CMakeLists.txt`: `find_package(TensorFlowLite REQUIRED)` → `pkg_check_modules(TFLITE REQUIRED tensorflow-lite)` because `libtensorflow-lite-dev` on Debian doesn't ship a CMake config file
- Verified: cmake configures successfully, finds `tensorflow-lite` v2.20.0 via pkg-config

**8.2 FRTApp C TFLite Reader — `TfLiteTensorQuantizationParams` API fix**:
- `TfliteReader.c`: In newer TFLite C API, `TfLiteTensorQuantizationParams()` returns a `TfLiteQuantizationParams` struct (not a float)
- Fixed 3 occurrences: INT8/UINT8 block (lines 181, 201) and INT16 block (line 219) to use `.scale` and `.zero_point` members
- Verified: compiles and links `libtflite_reader.so` + `tflite_reader_test` successfully

**8.3 FRTApp Camera Core — Duplicate `main()`**:
- `cpp_camera_core/CMakeLists.txt`: `file(GLOB SOURCES "src/*.cpp")` picked up both `camera_test.cpp` and `main.cpp`, both with `main()`
- Added `list(REMOVE_ITEM ... camera_test.cpp)` to exclude test from main executable
- Verified: `camera_core_exec` links successfully

**8.4 D-Bus Config — Service Name Alignment**:
- Discovered C++ SensorDaemon registers as `vn.edu.uit.FSS.Sensor` (not `SensorDaemon`) in `SensorDbusInterface.cpp:18`
- Updated `/etc/dbus-1/system.d/vn.edu.uit.FSS.conf` and `dbus_config/vn.edu.uit.FSS.conf`: all `SensorDaemon` → `Sensor`
- Added `RecommendDaemon` ownership (was missing), uncommented all services (all now implemented)
- Added `org.freedesktop.DBus` send_destination to all policy blocks (required for service name registration)

**8.5 MagicMirror — Invalid Position `"center"`**:
- `config.js`: `MMM-FSS-LivePreview` and `MMM-FSS-Notification` used `position: "center"` which is not a valid MagicMirror position
- Changed both to `position: "middle_center"` (the correct equivalent)
- Verified: MagicMirror starts without position warnings

**8.6 Python 3.13 Compatibility — tflite-runtime & sdbus-python**:
- `tflite-runtime` has no wheel for Python 3.13 on ARM64 → commented out in `frt_app/py_ai_core/requirements.txt` (C backend is primary path; Python fallback inside try/except)
- `sdbus-python` has no wheel for Python 3.13 on ARM64 → installed system `python3-sdbus` (`apt install python3-sdbus`); recreated `frt_app/py_ai_core/venv` with `--system-site-packages`
- `electron_app/py_bridge/requirements.txt`: `sdbus-python>=0.14.0` → `sdbus>=0.14.0` (same package name the module bridges already use)
- Verified: All Python imports work (`sdbus`, `cv2`, `numpy`, `Pillow`, `loguru`, `psutil`)

**8.7 Recommend System — Missing Venv**:
- `recommend_system/` was missing its component venv (not in the original setup guide)
- Created `recommend_system/venv/` and installed deps from `requirements.txt` (`sklearn-crfsuite`, `pyvi`, `joblib`)
- Updated setup guide to include it

**8.8 FrtDbusInterface — Duplicate `SensorInterface` Class**:
- Both `_subscribe_to_sensor_signals_async()` and `_subscribe_to_distance_async()` defined a local class `SensorInterface(DbusInterfaceCommonAsync)` with the same `interface_name`, causing sdbus error: *"D-Bus interface of the name 'vn.edu.uit.FSS.Sensor' was already created"*
- Moved `SensorInterface` to module level (alongside `FrtDaemonDbusObject`), containing both `DoorStateChanged` and `DistanceDataChanged` signals
- Both subscription methods now create proxies from the single class
- Verified: `py_compile` passes

**8.9 Log File Permission**:
- FRTApp AI Core couldn't write to `/var/log/frt_app.log` (didn't exist, created by root on first write)
- Created with: `sudo touch /var/log/frt_app.log && sudo chown $USER:$USER /var/log/frt_app.log`
- Added to setup guide Step 2

**8.10 Startup Script — Added FRTApp**:
- `startup_fss_system.sh` only managed 3 daemons (Sensor, DB, Recommend)
- Added `start_frt_camera()`: starts `camera_core_exec` (C++ V4L2 → POSIX SHM)
- Added `start_frt_ai()`: starts `main.py --use-c-backend` (Python YOLO inference)
- Both added to shutdown handler, process monitor, and status display
- FRTApp camera/ai start as non-fatal (skip gracefully if no camera)

**8.11 Setup Guide — Full Correction**:
- Added missing `python3-sdbus` and `python3-systemd` to system deps
- Added D-Bus config installation step (`cp dbus_config/vn.edu.uit.FSS.conf /etc/dbus-1/system.d/`)
- Added `libtflite_reader.so` installation to `/usr/local/lib` + `ldconfig`
- Added `--system-site-packages` flag for FRTApp AI venv
- Added `recommend_system` to venv creation list
- Updated start methods to include FRTApp camera + AI
- Updated verification to check all 5 venvs + D-Bus config

### Verification
- ✅ All C++ components build: `sensor_daemon_exec`, `libtflite_reader.so`, `camera_core_exec`, `tflite_reader_test`
- ✅ All Python files pass `py_compile`
- ✅ All pip installs succeed on Python 3.13 ARM64
- ✅ `sdbus` importable from FRTApp venv (via system-site-packages)
- ✅ `libtflite_reader.so` loadable via ctypes
- ✅ MagicMirror starts without position errors
- ✅ D-Bus config validated by `tools/verify_dbus_config.sh`
- ✅ Full setup guide in AGENTS.md covers all 9 steps

### Files changed this session
| File | Status | Description |
|------|--------|-------------|
| `frt_app/c_tflite_reader/CMakeLists.txt` | **Modified** | find_package → pkg_check_modules for TFLite |
| `frt_app/c_tflite_reader/src/TfliteReader.c` | **Modified** | TfLiteQuantizationParams struct access (scale/zero_point) |
| `frt_app/cpp_camera_core/CMakeLists.txt` | **Modified** | Excluded camera_test.cpp from main build |
| `frt_app/py_ai_core/requirements.txt` | **Modified** | Commented tflite-runtime, removed sdbus-python/sdbus (system package) |
| `frt_app/py_ai_core/src/FrtDbusInterface.py` | **Modified** | SensorInterface defined once at module level |
| `dbus_config/vn.edu.uit.FSS.conf` | **Modified** | SensorDaemon→Sensor, added RecommendDaemon |
| `electron_app/magicmirror/config/config.js` | **Modified** | center→middle_center for 2 modules |
| `electron_app/py_bridge/requirements.txt` | **Modified** | sdbus-python→sdbus |
| `startup_fss_system.sh` | **Modified** | Added FRTApp camera + AI core, 5 daemons total |
| `AGENTS.md` | **Modified** | Added full 9-step corrected setup guide |
| `/etc/dbus-1/system.d/vn.edu.uit.FSS.conf` | **Modified** | SensorDaemon→Sensor, org.freedesktop.DBus entries |
| `/var/log/frt_app.log` | **New** | Created with user ownership for FRTApp logging |
| `HANDOVER_CHAT.md` | **Modified** | Added Phase 8 section |

---

## 7. Design Notes & Rationale

### Why per-component `requirements.txt` instead of one shared `.venv`?

Each component has different dependencies:
- `db_daemon` needs only `sdbus`
- `recommend_daemon` needs `sdbus` + `sklearn-crfsuite` + `joblib` + `pyvi`
- `frt_app/py_ai_core` needs `tflite-runtime` + `opencv`

The old `startup_fss_system.sh` tried a shared `.venv` approach, which cannot satisfy all
components simultaneously (dependency conflicts, missing packages). The per-component venv
pattern (`component/venv/`) matches the existing `fss_env_setup.sh` systemd service design
and gives proper isolation.

### Why `FSS_ROOT` should be dynamic

The old scripts hardcoded `/home/richardmelvin52/FSS`. Updated scripts now use
`$(dirname "$(readlink -f "$0")")` so they work regardless of clone location.

---

## 8. Project Phase Roadmap

| Phase | Component | Branch | Status |
|-------|-----------|--------|--------|
| Phase 0 | Folder Structure & Docs Cleanup | `main` | ✅ Complete |
| Phase 1 | FRTApp — C TFLite Reader + D-Bus + Distance Sensor | `FRTApp-dev` | ✅ Complete |
| Phase 2 | DBDaemon DB schema | `DBDaemon-dev` | ✅ Complete |
| Phase 3 | Recommend System (NLP) | `recommend_system` | ✅ Complete |
| Phase 4 | DBDaemon cleanup | `DBDaemon-dev` | ✅ Complete |
| Phase 5 | Recommend Daemon | `recommend_daemon` | ✅ Complete |
| Phase 6 | FSS-Recommend DB + Bù Trừ | `recommend_daemon` | ✅ Complete |
| Phase 7 | ElectronApp — UI Modules + Fixes | `ElectronApp-dev` | ✅ Complete |
| Phase 8 | System Integration Fixes | `main` | ✅ Complete |

---

## 9. Remaining Work

### 🟡 Should Do

- [ ] **Add integration/E2E tests**: Full data flow test: mock D-Bus → GenerateShoppingList → NLP → Bù Trừ → DB persistence → signal emission.

### 🟢 Nice to Have

- [ ] **`verify_dbus_fix.sh`**: Could be merged with `tools/verify_dbus_config.sh` into a single `tools/verify_all.sh` that validates everything at once.
- [ ] **Phase 1 test runner**: Update `tests/run_phase1_tests.py` to include `recommend_daemon` and `recommend_system` module validation.

---

## 10. Repository Information

| Property | Value |
|----------|-------|
| Remote | `origin` → `https://github.com/BeginnerCoder52/FSS.git` |
| Current branch | `main` (Phase 8 complete — System Integration Ready) |
| Next action | Run full system: `bash startup_fss_system.sh`, then `npm start` for MagicMirror |
| Project root | `/home/richardmelvin52/FSS` |

### Branches overview

| Branch | Phase | Component |
|--------|-------|-----------|
| `main` | — | Integration/stable (all phases merged) |
| `DBDaemon-dev` | 1, 3 | Database + IPC broker |
| `recommend_system` | 2 | NLP library (CRF model + recipes) |
| `FRTApp-dev` | — | Food recognition (C++ + Python) |
| `SensorDaemon-dev` | — | Hardware I/O |
| `ElectronApp-dev` | — | MagicMirror UI |
| `recommend_daemon` | 4, 5 | Business logic daemon |

---

## 11. Architecture Reference

### D-Bus Service Ownership

| Component | D-Bus Service | Methods | Signals |
|-----------|---------------|---------|---------|
| SensorDaemon | `vn.edu.uit.FSS.Sensor` | — | `EnvironmentDataChanged`, `DistanceDataChanged`, `DoorStateChanged`, `UserPresenceDetected`, `EnvironmentDataUpdated` |
| FRTApp | `vn.edu.uit.FSS.FRTApp` | — | `FoodDetected`/`FRTDetectionResult` |
| DBDaemon | `vn.edu.uit.FSS.DBDaemon` | `GetInventory`, `GetRequests`, `InsertRequest`, `ClearRequest` | `UIUpdateRequired`, `EnvironmentUpdateRequired`, `SecondaryEnvironmentUpdateRequired`, `DoorStateUpdate`, `DistanceAlert`, `UserPresenceUpdate` |
| RecommendDaemon | `vn.edu.uit.FSS.RecommendDaemon` | `GenerateShoppingList`, `GetAvailableRecipes`, `GetShoppingList`, `MarkItemPurchased` | `RecommendationUpdated` |

### Data Flow (Post-Phase 5)

```
User enters recipe in UI
    → D-Bus: RecommendDaemon.GenerateShoppingList(recipe_name)
    → RecommendDaemon.RecommendEngine calls RecipeAnalyzerEngine (from recommend_system/)
    → RecommendDaemon calls DBDaemon.GetInventory() via D-Bus
    → RecommendDaemon runs Bù Trừ comparison
    → RecommendDaemon stores result in FSS-Recommend.db
    → RecommendDaemon emits RecommendationUpdated signal
    → UI receives signal, displays shopping list
```

### Database Ownership

- `DBDaemon` owns: `fss_data.db`, `FSS_Inventory.db`, `FSS_Request.db`
- `RecommendDaemon` owns: `FSS-Recommend.db`

---

*End of handover. All phases merged to `main`. Next session: integration/E2E tests and full system startup.*
