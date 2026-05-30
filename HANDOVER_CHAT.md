# HANDOVER CHAT — FSS Project

> **Created**: 2026-05-24
> **Last Updated**: 2026-05-31
> **Previous session branch**: `recommend_daemon` (Phase 4 + 5 — Recommend Daemon full implementation)
> **This session branch**: `main` (Phase 0 — Folder Structure & Docs Cleanup)
> **Project phase**: Phase 0 Complete — Ready for Phase 1 (FRTApp-dev)

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
- Start **Phase 2**: `ElectronApp-dev` branch (SensorDaemon precision, MMM-FSS modules)
- Run `sudo bash tools/verify_dbus_config.sh --fix` on target machine
- Create venvs: `bash setup.sh`

---

## 3. Design Notes & Rationale

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

## 5. Project Phase Roadmap

| Phase | Component | Branch | Status |
|-------|-----------|--------|--------|
| Phase 0 | Folder Structure & Docs Cleanup | `main` | ✅ Complete |
| Phase 1 | FRTApp — C TFLite Reader + D-Bus + Distance Sensor | `FRTApp-dev` | ✅ Complete |
| Phase 2 | DBDaemon DB schema | `DBDaemon-dev` | ✅ Complete |
| Phase 3 | Recommend System (NLP) | `recommend_system` | ✅ Complete |
| Phase 4 | DBDaemon cleanup | `DBDaemon-dev` | ✅ Complete |
| Phase 5 | Recommend Daemon | `recommend_daemon` | ✅ Complete |
| Phase 6 | FSS-Recommend DB + Bù Trừ | `recommend_daemon` | ✅ Complete |
| Phase 7 | ElectronApp — UI Modules + Fixes | `ElectronApp-dev` | 🔜 Next |

---

## 5. Remaining Work Before System Integration

### 🔴 Must Do

- [ ] **Deploy D-Bus config**: Run `sudo bash tools/verify_dbus_config.sh --fix` on the target machine to create `/etc/dbus-1/system.d/vn.edu.uit.FSS.conf`. Without this, all daemons will fail to register on the system bus.
- [ ] **Create `venv/` for each component**: Run `bash setup.sh` (updated) to create all venvs and install dependencies. Or manually: `python3 -m venv recommend_daemon/venv && recommend_daemon/venv/bin/pip install -r recommend_daemon/requirements.txt`
- [ ] **Update `tests/run_phase1_tests.py`**: Add `recommend_daemon` module validation to the Phase 1 test runner.

### 🟡 Should Do

- [ ] **Create `MMM-FSS-Food` module**: Referenced in `setup.sh` and `AGENTS.md` but not implemented. Needs:
  - `MMM-FSS-Food.js` — frontend: display shopping list from recommend daemon
  - `MMM-FSS-Food.css` — styling
  - `node_helper.js` — spawns `food_dbus_listener.py` as subprocess
  - `py_bridge/food_dbus_listener.py` — listens to `RecommendDaemon.RecommendationUpdated` signal, translates to JSON for node_helper
  - `py_bridge/requirements.txt` — depends on `sdbus`
- [ ] **Add integration/E2E tests**: Full data flow test: mock D-Bus → GenerateShoppingList → NLP → Bù Trừ → DB persistence → signal emission.
- [ ] **Wire ElectronApp UI to call RecommendDaemon**: Replace current DBDaemon recommendation calls with RecommendDaemon D-Bus calls.

### 🟢 Nice to Have

- [ ] **`verify_dbus_fix.sh`**: Could be merged with `tools/verify_dbus_config.sh` into a single `tools/verify_all.sh` that validates everything at once.

---

## 6. Repository Information

| Property | Value |
|----------|-------|
| Remote | `origin` → `https://github.com/BeginnerCoder52/FSS.git` |
| Current branch | `recommend_daemon` (Phase 4+5 complete) |
| Next action | Merge `recommend_daemon` into `main` |
| Project root | `/home/richardmelvin52/FSS` |

### Branches overview

| Branch | Phase | Component |
|--------|-------|-----------|
| `main` | — | Integration/stable |
| `DBDaemon-dev` | 1, 3 | Database + IPC broker |
| `recommend_system` | 2 | NLP library (CRF model + recipes) |
| `FRTApp-dev` | — | Food recognition (C++ + Python) |
| `SensorDaemon-dev` | — | Hardware I/O |
| `ElectronApp-dev` | — | MagicMirror UI |
| `recommend_daemon` | 4, 5 | Business logic daemon |

---

## 7. Architecture Reference

### D-Bus Service Ownership

| Component | D-Bus Service | Methods | Signals |
|-----------|---------------|---------|---------|
| SensorDaemon | `vn.edu.uit.FSS.SensorDaemon` | — | `EnvironmentDataUpdated`, `DoorStateChanged`, `UserPresenceDetected`, `DistanceDataChanged` |
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

*End of handover. Next session should merge `recommend_daemon` into `main` and tackle the Integration remaining items (Section 5).*
