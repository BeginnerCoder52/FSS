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
| **RecommendDaemon** | Python | Business logic orchestrator | Calls Recommend System NLP, compares against inventory via DBDaemon D-Bus (Bù Trừ method), persists shopping list to FSS-Recommend.db. Own D-Bus service `vn.edu.uit.FSS.RecommendDaemon`. Fully implemented with 4 D-Bus methods + 1 signal. |
| **FRTApp C Reader** | C | Performance layer | Standalone C library (`c_tflite_reader/`) using TensorFlow Lite C API for FP32/FP16/INT8 inference. Optional backend; Python tflite-runtime is fallback. |
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

**C++ Components** (SensorDaemon, FRTApp Camera Core, C TFLite Reader):
```bash
cd sensor_daemon && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4
./sensor_daemon_exec

# OR for FRTApp camera core + C tflite reader (both built together)
cd frt_app && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# Verify C tflite reader library
ls libtflite_reader.so
./c_tflite_reader/tflite_reader_test --model ../models/yolov11n.tflite --precision int8
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
- [recommend_daemon/src/main.py](recommend_daemon/src/main.py)
- [recommend_daemon/src/RecommendEngine.py](recommend_daemon/src/RecommendEngine.py)
- [recommend_daemon/src/DbusInterface.py](recommend_daemon/src/DbusInterface.py)
- [recommend_daemon/src/RecommendDbManager.py](recommend_daemon/src/RecommendDbManager.py)

### MagicMirror UI (Node.js + Python)

**Node.js** (Electron):
- Modules: `MMM-FSS-Env`, `MMM-FSS-Monitor`, `MMM-FSS-Inventory`,
  `MMM-FSS-LivePreview`, `MMM-FSS-VirtualKeyboard`, `MMM-FSS-Recommend`,
  `MMM-FSS-Notification`
- HTML/CSS rendering, JS event handling

**Python Bridges** (py_bridge/):
- `env_dbus_listener.py`: D-Bus → JSON → stdout for environment sensor data
- `monitor_dbus_listener.py`: D-Bus → JSON → stdout for distance/door sensors
- `inventory_dbus_listener.py`: D-Bus → JSON → stdout for food inventory
- `live_preview_bridge.py`: Polls `/opt/fss/latest_preview.jpg` → base64 → stdout
- `recommend_dbus_listener.py`: Sends recipe search to RecommendDaemon via D-Bus
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

## 🚀 Full Setup Guide (Corrected & Complete)

Execute these in order:

### Step 1: System Dependencies
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake pkg-config \
    libi2c-dev i2c-tools libv4l-dev v4l-utils \
    libsystemd-dev libsdbus-c++-dev libdbus-1-dev \
    libzmq3-dev libsqlite3-dev libopencv-dev \
    libtensorflow-lite-dev \
    python3-venv python3-dev python3-sdbus python3-systemd \
    nodejs npm
```

### Step 2: Create Runtime Directory
```bash
sudo mkdir -p /opt/fss/{images,logs,data,models}
sudo chown -R "$USER:$USER" /opt/fss

# Create FRTApp log file with user ownership
sudo touch /var/log/frt_app.log
sudo chown "$USER:$USER" /var/log/frt_app.log
```

### Step 3: Install D-Bus Configuration
```bash
# Copy D-Bus policy to system (allows FSS services on system bus)
sudo mkdir -p /etc/dbus-1/system.d
sudo cp dbus_config/vn.edu.uit.FSS.conf /etc/dbus-1/system.d/
```

### Step 4: Build C++ Components
```bash
# SensorDaemon
mkdir -p sensor_daemon/build && cd sensor_daemon/build
cmake .. -DCMAKE_BUILD_TYPE=Release && make -j4
cd ../..

# FRTApp (camera core + C TFLite reader)
mkdir -p frt_app/build && cd frt_app/build
cmake .. -DCMAKE_BUILD_TYPE=Release && make -j4
cd ../..

# Install libtflite_reader.so to system library path
sudo cp frt_app/build/c_tflite_reader/libtflite_reader.so /usr/local/lib/
sudo ldconfig
```

### Step 5: Create Python Virtual Environments
```bash
# Helper function
setup_venv() {
    local dir="$1"
    local flags="${2:-}"
    python3 -m venv $flags "$dir/venv"
    "$dir/venv/bin/pip" install --upgrade pip setuptools
    if [ -f "$dir/requirements.txt" ]; then
        "$dir/venv/bin/pip" install -r "$dir/requirements.txt"
    fi
}

# Core daemon venvs
setup_venv "db_daemon"
setup_venv "recommend_daemon"

# FRTApp AI core (needs --system-site-packages for sdbus)
setup_venv "frt_app/py_ai_core" "--system-site-packages"

# Electron bridge venv
setup_venv "electron_app/py_bridge"

# MagicMirror module bridges
for module in MMM-FSS-Env MMM-FSS-Inventory MMM-FSS-Monitor MMM-FSS-LivePreview MMM-FSS-Recommend; do
    if [ -d "electron_app/magicmirror/modules/$module/py_bridge" ]; then
        setup_venv "electron_app/magicmirror/modules/$module/py_bridge"
    fi
done

# Recommend System (library for NLP)
setup_venv "recommend_system"
```

### Step 6: Install Node.js / MagicMirror
```bash
cd electron_app/magicmirror
npm install
cd ../..
```

### Step 7: Verify the Installation
```bash
# Check C++ binaries
ls -la sensor_daemon/build/sensor_daemon_exec
ls -la frt_app/build/c_tflite_reader/libtflite_reader.so
ls -la frt_app/build/cpp_camera_core/camera_core_exec

# Check Python venvs
for dir in db_daemon recommend_daemon recommend_system frt_app/py_ai_core electron_app/py_bridge; do
    [ -f "$dir/venv/bin/python" ] && echo "✓ $dir" || echo "✗ $dir"
done

# Check npm
[ -d electron_app/magicmirror/node_modules ] && echo "✓ magicmirror" || echo "✗ magicmirror"

# Validate D-Bus config
bash tools/verify_dbus_config.sh
```

### Step 8: Start the System
Choose method:

A) **Manual testing** (individual terminals):
```bash
# Terminal 1: SensorDaemon (C++ hardware I/O)
sudo ./sensor_daemon/build/sensor_daemon_exec

# Terminal 2: FRTApp Camera Core (C++ V4L2 -> POSIX SHM)
sudo ./frt_app/build/cpp_camera_core/camera_core_exec

# Terminal 3: DBDaemon (Python data controller)
source db_daemon/venv/bin/activate && python db_daemon/src/main.py

# Terminal 4: FRTApp AI Core (Python YOLO inference on SHM frames)
source frt_app/py_ai_core/venv/bin/activate && \
  python frt_app/py_ai_core/src/main.py --use-c-backend

# Terminal 5: RecommendDaemon (Python business logic)
source recommend_daemon/venv/bin/activate && python recommend_daemon/src/main.py

# Terminal 6: MagicMirror (Electron UI)
cd electron_app/magicmirror && npm start
```

B) **Startup script** (manages all daemons):
```bash
bash startup_fss_system.sh
```

C) **Systemd services** (for RPi production):
```bash
bash fss_env_setup.sh
sudo systemctl start fss-sensor fss-camera fss-ai fss-db fss-recommend
```

### Step 9: Run Tests
```bash
# Phase 1 schema validation
python tests/run_phase1_tests.py

# Recommend system NLP (use its own venv)
source recommend_system/venv/bin/activate
pytest recommend_system/tests/test_recipe_analyzer.py -v

# Recommend daemon
source recommend_daemon/venv/bin/activate
pytest recommend_daemon/tests/test_recommend_engine.py -v
```

---

## 🐍 Python venv Management

### Standard Setup Per Component
```bash
cd COMPONENT_NAME
python3 -m venv venv
source venv/bin/activate
pip install --upgrade setuptools pip
pip install -r requirements.txt
```

### Cross-Component Imports
When one component needs to import another (e.g., RecommendDaemon imports recommend_system):
```python
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../recommend_system/src'))
```
Or install as editable:
```bash
pip install -e ../../recommend_system/
```

### Common Issues
- `ModuleNotFoundError`: Check `sys.path`, venv activation, and that `pip install` ran
- `pip install sdbus` fails: Need system deps — `sudo apt install libsystemd-dev pkg-config`
- After adding new deps: `pip freeze | grep -v "^#" > requirements.txt`
- Freeze full env: `pip freeze -l > requirements.txt` (only local packages)

---

## ⚡ Node.js / Electron Debugging

### Chrome DevTools for Electron Renderer
```bash
# Start with dev flags
cd electron_app/magicmirror
npm run start:x11:dev
# Then open chrome://inspect in a Chromium browser
```

### Node.js Inspector for Main Process
```bash
DISPLAY=:0 node_modules/.bin/electron js/electron.js --inspect=9229
```

### PM2 Process Management
```bash
pm2 list              # List all processes
pm2 logs magicmirror  # View real-time logs
pm2 restart mm        # Restart MagicMirror
pm2 save              # Save process list for reboot
```

### socket.io Debugging
```javascript
// In browser DevTools console — enables verbose socket.io logging
localStorage.debug = 'socket.io:*';
// Reload the module to see all socket events in console
```

### Module Lifecycle Hooks (MagicMirror)
- `start()` — called once on module load (initialize state, send start notification)
- `getDom()` — called on each `updateDom()`, returns the DOM element to render
- `socketNotificationReceived(notification, payload)` — receives events from node_helper.js
- `notificationReceived(notification, payload, sender)` — receives MagicMirror internal notifications
- `stop()` — called when module is removed (cleanup timers, kill subprocesses)

---

## 🗄️ SQLite Schema Migration Patterns

### Adding a New Column
```sql
ALTER TABLE table_name ADD COLUMN new_column TEXT DEFAULT NULL;
```

### Adding a New Table
Always use `IF NOT EXISTS` for idempotent migrations:
```python
# In SqliteManager.init_tables_if_not_exists()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS new_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        value REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
```

### Schema Version Tracking
```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);
```

### Rollback Procedure
```python
# Step 1: Backup
cursor.execute("CREATE TABLE backup AS SELECT * FROM table_to_migrate")
# Step 2: Drop old
cursor.execute("DROP TABLE table_to_migrate")
# Step 3: Create new schema
cursor.execute("CREATE TABLE table_to_migrate (...new schema...)")
# Step 4: Restore data (with default for new columns)
cursor.execute("INSERT INTO table_to_migrate SELECT *, NULL FROM backup")
# Step 5: Cleanup
cursor.execute("DROP TABLE backup")
```

### FSS Databases Reference
| File | Location | Tables |
|------|----------|--------|
| `fss_data.db` | `/opt/fss/data/` | `environment_log`, `door_event_log`, `distance_sensor_log`, `presence_sensor_log` |
| `FSS_Inventory.db` | `/opt/fss/data/` | `current_inventory`, `food_history`, `custom_food_labels` |
| `FSS_Request.db` | `/opt/fss/data/` | `recipe_requests` |
| `FSS-Recommend.db` | `/opt/fss/data/` | `recommendation_log`, `shopping_list` |

---

## 🧩 MagicMirror Module Development Workflow

### Module Template (3-File + Optional Bridge)
```
MMM-FSS-<Name>/
├── MMM-FSS-<Name>.js        # Frontend: DOM rendering, socket listeners
├── MMM-FSS-<Name>.css       # Styling (dark theme, touch-friendly)
├── node_helper.js            # Backend: spawns subprocess, relays socket.io
└── py_bridge/                # (optional) Python D-Bus listener
    ├── requirements.txt
    └── <name>_listener.py    # Reads D-Bus, outputs JSON to stdout
```

### Data Flow
```
Python bridge → stdout JSON → node_helper.js → socket.io → Frontend JS → DOM
```

### JSON Protocol (stdout line-delimited)
All Python bridges output one JSON object per line:
```json
{"type": "EVENT_NAME", "key1": "value1", "key2": 123}
```

### node_helper.js Pattern
```javascript
const NodeHelper = require('node_helper');
const { spawn } = require('child_process');

module.exports = NodeHelper.create({
    start() {
        this.process = null;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "START") {
            this.startBridge();
        }
    },
    startBridge() {
        const script = __dirname + '/py_bridge/listener.py';
        this.process = spawn('python3', [script]);
        let buffer = '';
        this.process.stdout.on('data', (data) => {
            buffer += data.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const msg = JSON.parse(line);
                    this.sendSocketNotification(msg.type, msg);
                } catch (e) {}
            }
        });
        this.process.stderr.on('data', (data) => {
            console.error(`[${this.name}] ${data.toString().trim()}`);
        });
    },
    stop() {
        if (this.process) this.process.kill();
    }
});
```

### MagicMirror Position Reference
| Position | CSS Mapping | Best For |
|----------|-------------|----------|
| `top_bar` | `.region.top.bar` | Status bar items |
| `top_left` | `.region.top.left` | Clock, calendar |
| `top_center` | `.region.top.center` | Search bars, virtual keyboard |
| `top_right` | `.region.top.right` | Sensor data (env, monitor) |
| `center` | `.region.middle.center` | Video preview, notifications |
| `bottom_center` | `.region.bottom.center` | Recommendations |
| `bottom_right` | `.region.bottom.right` | Compact inventory |

### Touchscreen Optimization Tips
- Buttons: min 44×44px tap target
- Use `:active` (not `:hover`) for press feedback
- CSS: `touch-action: manipulation` prevents double-tap zoom
- Avoid right-click, drag, or hover-only interactions
- Use `pointer-events: none` on overlays that shouldn't block touches

---

## ⚙️ C TFLite Reader Development

### API Reference
```c
#include "tensorflow/lite/c/c_api.h"
```

### Core Usage Pattern
```c
// Load model
TfLiteModel* model = TfLiteModelCreateFromFile(model_path);
TfLiteInterpreterOptions* options = TfLiteInterpreterOptionsCreate();
TfLiteInterpreter* interpreter = TfLiteInterpreterCreate(model, options);

// Get input tensor
TfLiteTensor* input = TfLiteInterpreterGetInputTensor(interpreter, 0);
TfLiteTensorCopyFromBuffer(input, input_data, input_size);

// Run inference
TfLiteInterpreterInvoke(interpreter);

// Get output
const TfLiteTensor* output = TfLiteInterpreterGetOutputTensor(interpreter, 0);
TfLiteTensorCopyToBuffer(output, output_buffer, output_size);

// Cleanup
TfLiteInterpreterDelete(interpreter);
TfLiteInterpreterOptionsDelete(options);
TfLiteModelDelete(model);
```

### Building for ARM64 (Raspberry Pi 4B)
```bash
# Native build on Pi
sudo apt install libtensorflow-lite-dev
```

### ctypes Integration (Python → C)
```python
import ctypes
lib = ctypes.CDLL("./libtflite_reader.so")

lib.tflite_reader_create.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.tflite_reader_create.restype = ctypes.c_void_p

reader = lib.tflite_reader_create(b"/opt/fss/models/yolov11n.tflite", 2)  # 2=INT8
```

### FP32 / FP16 / INT8 Handling
| Enum Value | Precision | Input Type | Output Handling |
|-----------|-----------|------------|-----------------|
| `0` (`TFLITE_FP32`) | 32-bit float | `float` | Direct float output |
| `1` (`TFLITE_FP16`) | 16-bit float | `float` (converted) | Cast to float |
| `2` (`TFLITE_INT8`) | 8-bit integer | `uint8_t` (quantized) | Dequantize with scale + zero point |

### Error Handling Pattern
```c
TfliteReader* reader = tflite_reader_create(path, precision);
if (!reader) {
    fprintf(stderr, "TfliteReader: failed to create from %s\n", path);
    return NULL;
}
if (tflite_reader_get_input_dims(reader, dims, 4) < 0) {
    fprintf(stderr, "TfliteReader: invalid input dims\n");
    tflite_reader_destroy(reader);
    return NULL;
}
```

### FSS C TFLite Reader API
```c
TfliteReader* tflite_reader_create(const char* model_path, ModelPrecision precision);
int tflite_reader_get_input_dims(TfliteReader* reader, int* dims_out, int max_dims);
int tflite_reader_get_input_size(TfliteReader* reader);
int tflite_reader_run_inference(TfliteReader* reader, const void* input_data, size_t input_size);
const float* tflite_reader_get_output(TfliteReader* reader, int* num_detections_out);
ModelPrecision tflite_reader_get_precision(TfliteReader* reader);
void tflite_reader_destroy(TfliteReader* reader);
```

---

## 📹 Frame Transport Mechanisms

### POSIX Shared Memory (`/fss_video_frame`)
- **Writer** (C++ camera core): `shm_open()` → `ftruncate()` → `mmap()` → `memcpy()` JPEG frames
- **Reader** (Python): `PosixShmReader` class in DBDaemon — `mmap` SHM, read JPEG, `munmap`
- **Buffer size**: 2 MB (fixed-size circular buffer)
- **Permission fix**: `chmod 666 /dev/shm/fss_video_frame` or set `umask 0` in FRTApp
- **Debug**: `ls -la /dev/shm/ | grep fss`

### File-Based Polling (`/opt/fss/latest_preview.jpg`)
- **Writer** (FRTApp Python AI): `cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])`
- **Reader** (LivePreview bridge): Poll using `os.path.getmtime()`, read when file changes
- **Use case**: Low-FPS preview for UI (no 2nd inference needed)
- **RAM**: Single ~50KB JPEG on tmpfs — negligible overhead

### Frame Rate Control
```python
# Writer side — only write every Nth frame
if frame_count % 3 == 0:   # ~10 FPS from 30 FPS source
    cv2.imwrite("/opt/fss/latest_preview.jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])

# Reader side — poll at matching interval
while True:
    if os.path.getmtime(PATH) != last_mtime:
        send_frame()
    time.sleep(0.1)  # 10 FPS polling
```

### JPEG Quality vs Bandwidth Tradeoff
| Quality | ~Size | Use Case |
|---------|-------|----------|
| 95 | 150KB | Archival / high-quality capture |
| 70 | 40-60KB | Live preview (good balance) |
| 50 | 20-30KB | Low-RAM / bandwidth constrained |

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