# FSS Agent Instructions

**Fridge Supervisor System (FSS)**: A Linux Embedded smart fridge manager with polyglot architecture (C++/Python/Node.js), real-time sensor data acquisition, YOLOv11-based food recognition, and D-Bus IPC. Target: Raspberry Pi 4B with systemd integration.

**Key Expertise Areas**: Linux Embedded systems, D-Bus architecture, real-time I/O (I2C/GPIO), V4L2 video capture, Python ML/NLP pipelines, Electron UI, POSIX Shared Memory.

---

## 🏗️ Architecture Overview

### Component Boundaries (Polyglot By Design)

| Component | Language | Purpose | Key Responsibility |
|-----------|----------|---------|-------------------|
| **SensorDaemon** | C++ | Hardware I/O layer | I2C/GPIO polling (SHT3x temp/humidity, MC-38 door, VL53L0x distance). Kernel ioctl via libgpiod. Broadcasts via D-Bus. |
| **FRTApp** | C++ (camera) + Python (AI) | Food recognition | V4L2 video frame capture → POSIX SHM; NumPy preprocessing; tflite-runtime inference (INT8/FP32/FP16); ByteTrack persistence. |
| **DBDaemon** | Python | Data controller | SQLite (3 DBs: data, inventory, requests). D-Bus listener & state machine. File I/O to `/opt/fss/`. POSIX SHM reader for FRTApp video. |
| **Recommend System** | Python | NLP/Recipe Analysis (library) | CRF-based NER (BIO-tagged ingredients/quantities). Loads 250 recipes. Imported by RecommendDaemon. |
| **RecommendDaemon** | Python | Business logic orchestrator | Calls Recommend System NLP, compares against inventory via DBDaemon D-Bus (Bù Trừ method), persists shopping list to FSS-Recommend.db. Own D-Bus service `vn.edu.uit.FSS.RecommendDaemon`. |
| **MagicMirror UI** | Node.js (Electron) + Python | User interface | Electron + HTML/CSS/JS rendering. Python bridge processes listen D-Bus events, format JSON for UI. |

### IPC Architecture

- **D-Bus** (primary): Service bus for daemon-to-daemon communication
  - Service names: `vn.edu.uit.FSS.{SensorDaemon,DBDaemon,FRTApp,RecommendDaemon}`
  - Signals: Async broadcasts (async data flow)
  - Methods: Sync D-Bus calls (request/response)
  - Watch for: sdbus-python errors (Python); sdbus-c++ lifecycle (C++)

- **POSIX Shared Memory**: `/fss_video_frame` (FRTApp → DBDaemon)
  - 2 MB JPEG buffer
  - Read via `PosixShmReader` class in DBDaemon

- **File-based**: `/opt/fss/` (tmpfs mount for images, logs, state)

---

## 🔨 Build & Development

### Full System Setup
```bash
# Automatic build + Python venv setup for all components
bash setup.sh
```

### Component-Specific Build

**C++ Components** (SensorDaemon, FRTApp Camera Core):
```bash
cd sensor_daemon && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4
./sensor_daemon_exec

# OR for FRTApp camera core
cd frt_app/cpp_camera_core && mkdir -p build && cd build
cmake .. && make -j4
```

**Python Components** (DBDaemon, FRTApp AI, Recommend System):
```bash
# Each component has isolated venv
cd COMPONENT_NAME
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py  # or designated entry point
```

**Node.js** (MagicMirror):
```bash
cd electron_app/magicmirror
npm install
npm run start:x11  # Or use systemd service
```

### Key CMake Flags
- Language: **C++17** standard
- Optimization: **-O2** (production), -g (debug symbols)
- Common libs: `sdbus-c++`, `libgpiod`, `libsmbus2` (C++); `pip` managed (Python)

---

## ✅ Testing & Validation

### Unit Tests
```bash
# Phase 1 schema validation (unittest framework)
python tests/run_phase1_tests.py

# Recommend system NLP validation
pytest recommend_system/tests/test_recipe_analyzer.py -v
```

### Integration Tests
```bash
# FRTApp inference benchmark (all quantization models)
cd fss-test && bash test-cases.sh

# Single model benchmark
python fss-test/test-inference.py \
  --model models/model_int8.tflite \
  --image-dir test-images/ \
  --benchmark-num-threads 1,2,4
```

### System Startup
```bash
# Integrated startup (all daemons + systemd watchdog + PM2 management)
bash startup_fss_system.sh

# Individual daemon startup (for debugging)
# SensorDaemon
./sensor_daemon/build/sensor_daemon_exec

# DBDaemon
source db_daemon/venv/bin/activate
python db_daemon/src/main.py

# FRTApp AI core
source frt_app/py_ai_core/venv/bin/activate
python frt_app/py_ai_core/src/main.py

# RecommendDaemon
source recommend_daemon/venv/bin/activate
python recommend_daemon/src/main.py
```

---

## 📋 D-Bus Usage Patterns

### Core Pattern (Listen + Broadcast)

**C++** (sdbus-c++):
```cpp
// Define service interface
auto obj = sdbus::createObject("vn.edu.uit.FSS.DBDaemon");
obj->registerSignal("UIUpdateRequired")
  .onInterface("vn.edu.uit.FSS.Interface");

// Emit signal
connection->emit(obj)
  .onInterface("vn.edu.uit.FSS.Interface")
  .signal("UIUpdateRequired")
  .withArguments(json_payload);
```

**Python** (sdbus):
```python
from sdbus import DbusInterfaceCommon, dbus_method, dbus_signal
from sdbus.sd_bus_internals import SdBus

class DbDbusInterface:
    UI_UPDATE_REQUIRED = dbus_signal(
        "a{ss}", relation_to_object=DbusRelationToObject.NEW_SEPARATE
    )
    
    def __init__(self):
        self.bus = SdBus(bus_type=BusType.SYSTEM)
    
    def emit_ui_update(self, data: dict):
        self.UI_UPDATE_REQUIRED.emit(data)
```

### D-Bus Connection Gotchas
- **System vs Session Bus**: FSS uses **System Bus** (better for system daemons)
- **Service Registration**: Only one service name per daemon; wait for bus readiness
- **Signal Ordering**: Signals are fire-and-forget (no guarantee of delivery)
- **Error Handling**: Always check connection state before emitting; implement retry logic
- **Testing**: Use `dbus-send` CLI or mock D-Bus in tests

```bash
# Debug D-Bus on system
dbus-send --system --print-reply --dest=vn.edu.uit.FSS.DBDaemon /vn/edu/uit/FSS/Interface \
  org.freedesktop.DBus.Properties.GetAll string:"vn.edu.uit.FSS.Interface"
```

---

## 📁 Directory & Naming Conventions

### Folder Structure Pattern
```
component_name/
├── CMakeLists.txt           (C++: build config)
├── requirements.txt         (Python: pip dependencies)
├── include/                 (C++: *.hpp headers)
├── src/
│   ├── __init__.py          (Python: package marker)
│   ├── main.py              (Python: entry point)
│   └── *.cpp / *.py         (Implementation files)
├── tests/
│   ├── __init__.py
│   └── test_*.py            (unittest/pytest style)
├── models/                  (Pre-trained weights, DB schemas)
└── py_bridge/               (Node.js integration only)
    ├── requirements.txt
    └── *_listener.py        (D-Bus → JSON bridge)
```

### Naming Conventions

| Entity | Convention | Examples |
|--------|-----------|----------|
| D-Bus Services | Reverse domain: `vn.edu.uit.FSS.<Component>` | `vn.edu.uit.FSS.SensorDaemon` |
| D-Bus Methods/Signals | snake_case | `get_sensor_data()`, `UIUpdateRequired` |
| C++ Classes | PascalCase | `SensorDaemonMain`, `I2cHandler` |
| C++ Methods | snake_case | `init_app()`, `poll_sensors()` |
| C++ Members | `m_<name>` prefix + snake_case | `m_i2c_main`, `m_fd` |
| C++ Constants | UPPER_CASE | `DEFAULT_I2C_ADDR`, `SHT3X_CMD_READ_STATUS` |
| Python Classes | PascalCase | `DbDaemonMain`, `SqliteManager` |
| Python Methods | snake_case | `insert_environment_log()`, `get_inventory()` |
| DB Tables | snake_case | `environment_log`, `current_inventory`, `food_history` |
| File Names | Executables: snake_case; Data: CamelCase | `sensor_daemon_exec`, `FSS_Inventory.db` |

---

## 🔍 Component Deep Dives

### SensorDaemon (C++)

**Main Class**: `SensorDaemonMain` → manages `InputProcessor` + `OutputProcessor`

**I/O Handlers**:
- `I2cHandler`: Wraps libsmbus2 ioctl for I2C reads from SHT3x (temp/humidity)
- `GpioHandler`: Wraps libgpiod for GPIO reads (MC-38 door sensor)
- Polling: Env sensors (5000 ms), distance (500 ms)

**D-Bus**:
- Service: `vn.edu.uit.FSS.SensorDaemon`
- Broadcasts: `DOOR_OPEN`, `DOOR_CLOSE`, `EnvironmentDataUpdated`

**Key Files**:
- [include/SensorDaemonMain.hpp](sensor_daemon/include/SensorDaemonMain.hpp)
- [src/SensorDaemonMain.cpp](sensor_daemon/src/SensorDaemonMain.cpp)
- [src/InputProcessor.cpp](sensor_daemon/src/InputProcessor.cpp)

### DBDaemon (Python)

**Main Class**: `DbDaemonMain` (state machine + asyncio event loop)

**Managers**:
- `SqliteManager`: CRUD operations on 3 DBs (data, inventory, requests)
- `PosixShmReader`: Reads JPEG frames from `/fss_video_frame` (triggered by FRTApp)
- `DiskFileManager`: Saves images to `/opt/fss/`
- `DbDbusInterface`: Listens to D-Bus signals, emits `UIUpdateRequired`

**Database Schema**:
- `fss_data.db`: `environment_log`, `door_event_log`
- `FSS_Inventory.db`: `current_inventory`, `food_history`
- `FSS_Request.db`: `recipe_requests` (ingested by RecommendDaemon)

**Role**: Pure data controller + IPC broker. No business logic (orchestration lives in RecommendDaemon).

**Key Files**:
- [db_daemon/src/DbDaemonMain.py](db_daemon/src/DbDaemonMain.py)
- [db_daemon/src/SqliteManager.py](db_daemon/src/SqliteManager.py)

### FRTApp (C++ + Python)

**C++ Camera Core** (`cpp_camera_core/`):
- Reads `/dev/video0` via V4L2 API
- Writes raw frames to `/fss_video_frame` POSIX SHM
- Main: [cpp_camera_core/src/main.cpp](frt_app/cpp_camera_core/src/main.cpp)

**Python AI Core** (`py_ai_core/`):
- Loads model from `models/` (tflite format: INT8/FP32/FP16)
- Reads frames from SHM, preprocesses with NumPy
- Runs tflite-runtime inference
- ByteTrack for persistence (track objects across frames)
- D-Bus: Listens `DOOR_OPEN`, broadcasts `FoodDetected`

**Key Files**:
- [frt_app/py_ai_core/src/YoloPipeline.py](frt_app/py_ai_core/src/YoloPipeline.py)
- [frt_app/py_ai_core/src/SdbusInterface.py](frt_app/py_ai_core/src/SdbusInterface.py)

### Recommend System (Python)

**Algorithm**: CRF (Conditional Random Fields) for Named Entity Recognition (NER) with BIO tagging

**Model**: `fss_ner_crf_optimized.joblib` (0.09 MB, ~250 Vietnamese recipes trained)

**Main Class**: `RecipeAnalyzerEngine`
- Loads model at startup
- Normalizes ingredient quantities (default "1" unit)
- Returns JSON FSS-Request for RecommendDaemon consumption

**Performance**: F1-Score 95.03%, latency ~3.2ms (Pi 4B)

**Key Files**:
- [recommend_system/src/RecipeAnalyzerAPI.py](recommend_system/src/RecipeAnalyzerAPI.py)
- [recommend_system/src/RecipeProcessor.py](recommend_system/src/RecipeProcessor.py)
- Full inventory: [/memories/repo/recommend_system_inventory.md](/memories/repo/recommend_system_inventory.md)

### RecommendDaemon (Python)

**Main Class**: `RecommendDaemonMain` (orchestrator, own D-Bus service)

**Algorithm**: Bù Trừ (Comparison) — `FSS-Request - FSS-Inventory = FSS-Recommend`

**Data Flow**:
1. User enters recipe in UI → D-Bus call to `RecommendDaemon.GenerateShoppingList(recipe)`
2. Calls `RecipeAnalyzerEngine` from `recommend_system/` to extract ingredients (NLP)
3. Queries DBDaemon `GetInventory()` via D-Bus for current stock
4. Runs Bù Trừ comparison: each ingredient → available/in-stock/missing
5. Persists result to `FSS-Recommend.db` (own database)
6. Emits `RecommendationUpdated` signal for UI consumption

**Database Schema** (`FSS-Recommend.db`):
- `recommendation_log`: Per-recipe analysis snapshots (recipe_name, batch_id, counts, status, result_json)
- `shopping_list`: Individual items to buy (food_id, shortfall quantity, purchase tracking)

**D-Bus**:
- Service: `vn.edu.uit.FSS.RecommendDaemon`
- Methods: `GenerateShoppingList`, `GetAvailableRecipes`, `GetShoppingList`, `MarkItemPurchased`

**Key Files**:
- [recommend_daemon/src/main.py](recommend_daemon/src/main.py) (planned)
- [recommend_daemon/src/RecommendEngine.py](recommend_daemon/src/RecommendEngine.py) (planned)
- [recommend_daemon/src/DbusInterface.py](recommend_daemon/src/DbusInterface.py) (planned)
- [recommend_daemon/src/RecommendDbManager.py](recommend_daemon/src/RecommendDbManager.py) (planned)

### MagicMirror UI (Node.js + Python)

**Node.js** (Electron):
- Modules: `MMM-FSS-Food`, `MMM-FSS-Env`
- HTML/CSS rendering, JS event handling

**Python Bridges** (py_bridge/):
- `food_dbus_listener.py`: Translates D-Bus signals → JSON → stdout (consumed by node_helper.js)
- `env_zmq_client.py`: (Alternative: ZMQ listener for env sensor data)
- node_helper.js spawns Python subprocess and handles lifecycle

---

## ⚠️ Common Pitfalls & Debugging

| Issue | Cause | Solution |
|-------|-------|----------|
| D-Bus service not found | Bus not ready or service not registered | Check `dbus-daemon` running; ensure service name matches; add 2s startup delay |
| POSIX SHM permission denied | `/fss_video_frame` mounted with restrictive perms | Run `chmod 666 /dev/shm/fss_video_frame` or set `umask 0` in FRTApp |
| I2C device not found | GPIO/I2C not enabled or wrong `/dev/i2c-*` | Use `i2cdetect -l` to list; check device tree overlay; verify address (0x44 for SHT3x) |
| tflite model inference timeout | Model too large or thread count wrong | Try INT8 model; reduce input image size; tune `tflite_runtime` thread count |
| Python venv activation fails | Module import after source fails | Run `pip install --upgrade setuptools` before `pip install -r requirements.txt` |
| systemd service fails to start | Missing venv or permission error | Check service ExecStart path; ensure User=fss has correct permissions |
| D-Bus signal not received | Listener registered after sender broadcasts | Start all daemons in order (SensorDaemon → FRTApp → DBDaemon → RecommendDaemon); add async retry logic |

### Debug Commands
```bash
# Check D-Bus services registered
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames

# Monitor D-Bus traffic
dbus-monitor --system "interface=vn.edu.uit.FSS.Interface"

# Check shared memory
ls -la /dev/shm/ | grep fss

# Verify I2C device
i2cdetect -y 1  # Bus 1 for SHT3x

# Check systemd watchdog
systemctl status sensor_daemon
journalctl -u sensor_daemon -n 50 --no-pager

# Python import debug
python -c "import sdbus; print(sdbus.__file__)"
```

---

## 📚 Related Documentation

- **System Architecture**: [docs/FSS_SoftwareDetailedDesign_v1.1.0.txt](docs/FSS_SoftwareDetailedDesign_v1.1.0.txt)
- **Test Reports**: [tests/PHASE1_TEST_REPORT.md](tests/PHASE1_TEST_REPORT.md)
- **Sensor Pinouts**: [drivers/sensor/README_PINOUT.md](drivers/sensor/README_PINOUT.md)
- **Recommend System Details**: [/memories/repo/recommend_system_inventory.md](/memories/repo/recommend_system_inventory.md)
- **Handover Notes**: [HANDOVER_CHAT.md](HANDOVER_CHAT.md)

---

## 🎯 Quick Workflow

**Add a new sensor to SensorDaemon**:
1. Implement driver in `sensor_daemon/src/` (e.g., `NewSensorDriver.cpp`)
2. Register in `InputProcessor::poll_sensors()` with polling interval
3. Emit D-Bus signal in `OutputProcessor::emit_sensor_data()`
4. Update test in `sensor_daemon/tests/`

**Add UI logic to MagicMirror**:
1. Create module in `electron_app/magicmirror/modules/MMM-FSS-<NewModule>/`
2. Write `node_helper.js` to spawn Python bridge subprocess
3. Create `py_bridge/<feature>_listener.py` (D-Bus reader or ZMQ client)
4. Render data via HTML/CSS/JS in module template

**Modify DBDaemon schema**:
1. Create migration in `db_daemon/src/SqliteManager.py`
2. Update `SqliteManager.init_databases()` with new table schema
3. Run `tests/run_phase1_tests.py` to validate schema
4. Update FRT callback to populate new fields

**Add recommendation logic to RecommendDaemon**:
1. Implement Bù Trừ algorithm in `recommend_daemon/src/RecommendEngine.py`
2. Register D-Bus methods in `recommend_daemon/src/DbusInterface.py` (`GenerateShoppingList`, `GetAvailableRecipes`, etc.)
3. Add `FSS-Recommend.db` schema in `recommend_daemon/src/RecommendDbManager.py`
4. Wire in `recommend_daemon/src/main.py` with lazy NLP engine loading from `recommend_system/`
5. Test: `pytest recommend_daemon/tests/test_recommend_engine.py -v`

---

## 📞 Agent Activation Hints

Use this AGENTS.md when:
- Implementing new D-Bus signals or methods
- Debugging IPC/hardware communication
- Adding sensors or UI components
- Optimizing inference pipeline (FRTApp)
- Modifying database schema
- Troubleshooting systemd service startup

---

## CONSTRAINTS:
DO NOT CHANGE THE CORE CODE
USE CLEAN CODE AND DETAILED CLEAN COMMENT
ALWAYS CHECK THE FUNCTIONALITY AFTER INPLEMENTATION
FOLLOW ITS LANGUAGE CODE, AND ASPICE PRINCIPLE.