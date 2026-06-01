# FSS FINAL UPGRADE — 30/05/2026

**Execution timeline: 1 day**  
**Strategy:** Sequential by branch — FRTApp first, then ElectronApp, each on their own branches. Merge `FRTApp-dev` → `main`, then `ElectronApp-dev` → `main`. After each change, verify functionality.

> ⚠️ **CRITICAL NOTE**: After EACH implementation step, stop and verify:
> - The component compiles/starts without errors
> - D-Bus signals/methods work correctly
> - Existing tests still pass (`pytest`, `npm test`)
> - The change integrates properly with dependent components
> - RAM/CPU usage is within Pi 4B limits
> - Logs show expected behavior
>
> Never batch multiple untested changes together.

---

## TABLE OF CONTENTS

1. [PHASE 0: MAIN BRANCH — Folder Structure & Docs Cleanup](#phase-0-main-branch--folder-structure--docs-cleanup)
2. [PHASE 1: FRTApp BRANCH — C TFLite Reader + D-Bus Signals](#phase-1-frtapp-branch--c-tflite-reader--dbus-signals)
3. [PHASE 2: ElectronApp BRANCH — UI Modules + Fixes](#phase-2-electronapp-branch--ui-modules--fixes)
4. [New Libraries & Dependencies](#new-libraries--dependencies)
5. [AGENTS.md Update Plan](#agentsmd-update-plan)
6. [Appendix: Sound Design for Notification](#appendix-sound-design-for-notification)

---

## PHASE 0: MAIN BRANCH — Folder Structure & Docs Cleanup

### 0.1 Update README.md
Align directory tree in README.md with actual merged code:
- Add `recommend_daemon/` to tree (fully implemented — was missing)
- Correct `frt_app/` sub-tree to show `c_tflite_reader/` (post-upgrade)
- List all Electron modules (7 FSS modules after upgrade):
  - Existing: `MMM-FSS-Env`, `MMM-FSS-Monitor`, `MMM-FSS-Inventory`
  - New: `MMM-FSS-LivePreview`, `MMM-FSS-VirtualKeyboard`, `MMM-FSS-Recommend`, `MMM-FSS-Notification`
- Remove `recommend_system/recommend_daemon/` stub from tree

### 0.2 Update AGENTS.md
- Architecture table: mark RecommendDaemon as **Implemented** (was "planned")
- Update directory listing
- Add 6 new sections (detailed in [AGENTS.md Update Plan](#agentsmd-update-plan))

### 0.3 Remove leftover stubs
- Delete `recommend_system/recommend_daemon/` (only `__init__.py` files)
- Verify `recommend_daemon/` at top level is the real one (it is)

---

## PHASE 1: FRTApp BRANCH (`FRTApp-dev`)

### 1.1 New: `frt_app/c_tflite_reader/` — Standalone C TF Lite Reader

**Purpose:** Performance-optimized C library for loading/running `.tflite` inference on Pi 4B. Python tflite-runtime stays as primary backend; C reader is an optional `--use-c-backend` flag. If C reader fails to load at runtime, Python backend runs as fallback.

**Folder structure:**
```
frt_app/
├── c_tflite_reader/
│   ├── CMakeLists.txt
│   ├── include/
│   │   └── TfliteReader.h          # C API header
│   └── src/
│       ├── TfliteReader.c          # Core impl using TF Lite C API
│       └── tflite_reader_test.c    # Standalone test binary
├── cpp_camera_core/                # unchanged
├── py_ai_core/                     # see 1.2
└── CMakeLists.txt                  # updated to build both
```

#### TfliteReader.h API:
```c
#include <stddef.h>

typedef enum {
    TFLITE_FP32 = 0,
    TFLITE_FP16 = 1,
    TFLITE_INT8 = 2
} ModelPrecision;

typedef struct TfliteReader TfliteReader;

// Create reader instance, load model. Returns NULL on failure.
TfliteReader* tflite_reader_create(const char* model_path, ModelPrecision precision);

// Get input tensor dimensions. dims_out filled with [batch, height, width, channels].
// Returns number of dims written, or -1 on error.
int tflite_reader_get_input_dims(TfliteReader* reader, int* dims_out, int max_dims);

// Get total input tensor size in bytes.
int tflite_reader_get_input_size(TfliteReader* reader);

// Run inference synchronously. input_data must be input_size bytes.
// Returns 0 on success, -1 on error.
int tflite_reader_run_inference(TfliteReader* reader, const void* input_data, size_t input_size);

// Get output tensor as float array. num_detections_out receives count.
// Returns pointer to internal buffer (do not free). NULL on error.
const float* tflite_reader_get_output(TfliteReader* reader, int* num_detections_out);

// Get model precision that was loaded.
ModelPrecision tflite_reader_get_precision(TfliteReader* reader);

// Destroy the reader and free resources.
void tflite_reader_destroy(TfliteReader* reader);
```

#### TfliteReader.c implementation outline:
- Uses `#include "tensorflow/lite/c/c_api.h"`
- Error handling: each function returns error code and logs to stderr
- Memory: `TfliteReader` struct holds `TfLiteModel*`, `TfLiteInterpreterOptions*`, `TfLiteInterpreter*`
- Input type detection: `TfLiteTensorType` → if INT8, quantize float input; if FP32/FP16, copy as float
- Output parsing: all outputs converted to float array regardless of model type
- Test binary: loads a model, runs dummy inference, prints output dims

#### CMakeLists.txt (`c_tflite_reader/`):
```cmake
cmake_minimum_required(VERSION 3.10)
project(tflite_reader C)

set(CMAKE_C_STANDARD 11)

find_package(TensorFlowLite REQUIRED)

add_library(tflite_reader SHARED
    src/TfliteReader.c
)

target_include_directories(tflite_reader
    PUBLIC include
    PRIVATE ${TensorFlowLite_INCLUDE_DIRS}
)

target_link_libraries(tflite_reader
    PRIVATE ${TensorFlowLite_LIBRARIES}
)

# Test binary
add_executable(tflite_reader_test src/tflite_reader_test.c)
target_link_libraries(tflite_reader_test tflite_reader)
```

#### Root CMakeLists.txt (`frt_app/`) — add:
```cmake
add_subdirectory(c_tflite_reader)
```

#### Build verification:
```bash
cd frt_app && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4
# Verify library exists
ls libtflite_reader.so
# Run test
./c_tflite_reader/tflite_reader_test --model ../models/yolov11n.tflite --precision fp32
```

### 1.2 Python AI Core — Integrate C Reader as Optional Backend

**File:** `frt_app/py_ai_core/src/YoloTfliteEngine.py`

**Changes:**
- Add `use_c_backend: bool = False` to `__init__`
- When `True`:
  ```python
  import ctypes
  self._c_lib = ctypes.CDLL("libtflite_reader.so")
  self._c_reader = self._c_lib.tflite_reader_create(model_path.encode(), precision_enum)
  ```
- `load_model_mmap()` → calls `tflite_reader_create()`
- `invoke_inference()` → `tflite_reader_run_inference()` then `tflite_reader_get_output()`
- `get_output_boxes()` → parses C output (same format as Python backend)
- Error: if `ctypes.CDLL` fails → `logger.warning("C backend unavailable, falling back to Python")` → sets `use_c_backend = False`
- Python tflite-runtime code path is **completely unchanged** — only the new `if use_c_backend:` branches are added

**CLI args in `main.py`:**
```python
parser.add_argument('--use-c-backend', action='store_true',
                    help='Use C TFLite reader for inference (faster on Pi 4B)')
parser.add_argument('--c-model-path', default='/opt/fss/models/yolov11n.tflite',
                    help='Model path for C reader')
parser.add_argument('--model-precision', choices=['fp32','fp16','int8'], default='int8',
                    help='Model quantization precision')
```

### 1.3 New D-Bus Signal: `CameraStateChanged`

**File:** `frt_app/py_ai_core/src/FrtDbusInterface.py`

**Add to `FrtDaemonDbusObject`:**
```python
@dbus_signal_async('s')
def CameraStateChanged(self, state: str) -> None:
    """Signal: Camera on/off state. Payload: 'ON' | 'OFF'."""
    pass
```

**Emit method in `FrtDbusInterface`:**
```python
def emit_camera_state(self, state: str) -> None:
    if not self.is_connected or not self.bus_connection:
        return
    asyncio.run_coroutine_threadsafe(
        self._async_emit_camera_state(state), self._loop
    )

async def _async_emit_camera_state(self, state: str):
    self.bus_connection.CameraStateChanged(state)
```

**Emit triggers in `FrtMain.py`:**
- `on_door_event_received("OPEN")` → camera starts → `self.dbus_interface.emit_camera_state("ON")`
- `on_door_event_received("CLOSED")` → camera stops → `self.dbus_interface.emit_camera_state("OFF")`

### 1.4 Distance Sensor Integration + Debug Flag

**File:** `frt_app/py_ai_core/src/FrtMain.py`

**New attributes:**
```python
self.distance_sensor_enabled: bool = True   # set False via --debug-no-distance
self.distance_threshold_cm: float = 60.0     # default 60cm
self.last_distance_cm: Optional[float] = None
```

**New method — distance callback:**
```python
def on_distance_event_received(self, distance_cm: float) -> None:
    self.last_distance_cm = distance_cm
    logger.debug(f"Distance updated: {distance_cm:.1f}cm")
```

**Modified `on_door_event_received("OPEN")`:**
```python
if door_state.upper() == "OPEN":
    can_track = False
    if not self.distance_sensor_enabled:
        can_track = True  # debug mode — ignore distance
    elif self.last_distance_cm is not None and self.last_distance_cm < self.distance_threshold_cm:
        can_track = True  # user close enough
    
    if can_track and self.current_state != AppState.TRACKING.value:
        logger.info("Transitioning to TRACKING state")
        self.current_state = AppState.TRACKING.value
        self.dbus_interface.emit_camera_state("ON")
        # ... rest of camera init
```

**Modified `on_door_event_received("CLOSED")`:**
```python
elif door_state.upper() == "CLOSED":
    if self.current_state == AppState.TRACKING.value:
        logger.info("Transitioning to IDLE state")
        self.current_state = AppState.IDLE.value
        self.dbus_interface.emit_camera_state("OFF")
        # ... rest of cleanup
```

**Subscribe to distance in `_subscribe_dbus_signals()`:**
```python
if self.dbus_interface:
    self.dbus_interface.subscribe_door_events(self.on_door_event_received)
    if self.distance_sensor_enabled:
        self.dbus_interface.subscribe_distance_events(self.on_distance_event_received)
```

**New subscribe method in `FrtDbusInterface`:**
```python
def subscribe_distance_events(self, callback: Callable) -> None:
    """Subscribe to DistanceDataChanged from SensorDaemon."""
    if not self.is_connected:
        return
    self.distance_callback = callback
    asyncio.run_coroutine_threadsafe(
        self._subscribe_to_distance_async(), self._loop
    )
```

**New CLI args in `main.py`:**
```python
parser.add_argument('--debug-no-distance', action='store_true',
                    help='Disable distance sensor dependency — camera activates on door open alone')
parser.add_argument('--distance-threshold', type=float, default=60.0,
                    help='Distance threshold in cm (default: 60.0)')
```

**Performance verification checklist:**
- [ ] C library compiles with `cmake .. && make`
- [ ] `python src/main.py --use-c-backend` runs without error
- [ ] `python src/main.py` (no flag) uses Python backend as before
- [ ] If `libtflite_reader.so` deleted, Python code falls back gracefully
- [ ] `CameraStateChanged` visible in `dbus-monitor`
- [ ] `--debug-no-distance` allows camera on door open without VL53L0x

---

## PHASE 2: ElectronApp BRANCH (`ElectronApp-dev`)

### 2.1 SensorDaemon — 2 Decimal Places

**File:** `sensor_daemon/src/OutputProcessor.cpp`

| Line | Current | Change to |
|------|---------|-----------|
| 80 | `std::fixed << std::setprecision(1) << data.at("temp")` | `std::fixed << std::setprecision(2) << data.at("temp")` |
| 87 | `std::fixed << std::setprecision(1) << data.at("humid")` | `std::fixed << std::setprecision(2) << data.at("humid")` |
| 94 | `std::fixed << std::setprecision(1) << data.at("temp_2")` | `std::fixed << std::setprecision(2) << data.at("temp_2")` |
| 101 | `std::fixed << std::setprecision(1) << data.at("humid_2")` | `std::fixed << std::setprecision(2) << data.at("humid_2")` |

**Verification:**
- Rebuild: `cd sensor_daemon/build && cmake .. && make -j4`
- Run: `./sensor_daemon_exec` → check logs show `27.12` not `27.1`
- Check D-Bus: `dbus-monitor --system "interface=vn.edu.uit.FSS.Sensor"` → payload shows 2 decimals

### 2.2 MMM-FSS-Env — 2 Decimal Places

**File:** `electron_app/magicmirror/modules/MMM-FSS-Env/MMM-FSS-Env.js`

**Default config (lines 22-27):**
```js
defaults: {
    roundTemperature: false,     // was true
    roundHumidity: false,        // was true
    // ... rest unchanged
}
```

**Display formatting (lines 137, 159):**
```js
// Line 137 (was .toFixed(1)):
data.temperature.toFixed(2)

// Line 159 (was .toFixed(1)):
data.humidity.toFixed(2)
```

**Verification:**
- Restart MagicMirror
- Check MMM-FSS-Env module shows `27.12°C` not `27°C` or `27.1°C`
- Check stale detection still works

### 2.3 MMM-FSS-Monitor — Fix Door State Display

**Root cause:** Module stores `doorState` internally but only shows it inside `if (this.config.showDebugInfo)` block. Normal users see nothing.

**Fixes:**

**`MMM-FSS-Monitor.js`:**
- Add to `getDom()` before the debug block:
```javascript
// Door state indicator (always visible)
const doorIndicator = document.createElement("div");
doorIndicator.id = "fss-door-indicator";
doorIndicator.classList.add("fss-door-indicator");

if (this.state.doorState) {
    const isOpen = this.state.doorState === "OPEN";
    doorIndicator.textContent = isOpen ? "🚪 MỞ" : "🚪 ĐÓNG";
    doorIndicator.classList.toggle("door-open", isOpen);
    doorIndicator.classList.toggle("door-closed", !isOpen);
} else {
    doorIndicator.textContent = "🚪 --";
    doorIndicator.classList.add("door-unknown");
}
wrapper.appendChild(doorIndicator);
```

- Update `socketNotificationReceived("DOOR_STATE_UPDATE")` to update door indicator text/classes
- Set `showDebugInfo: false` as default in `defaults`

**`MMM-FSS-Monitor.css`:**
```css
.fss-door-indicator {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    text-align: center;
    transition: all 0.3s ease;
}
.fss-door-indicator.door-open {
    background: #e74c3c;
    color: white;
}
.fss-door-indicator.door-closed {
    background: #2ecc71;
    color: white;
}
.fss-door-indicator.door-unknown {
    background: #95a5a6;
    color: white;
}
```

**Verification:**
- Restart MagicMirror
- Send fake D-Bus signal: `dbus-send --system /vn/edu/uit/FSS/DBDaemon vn.edu.uit.FSS.DBDaemon.DoorStateUpdate string:"OPEN" double:$(date +%s)`
- Verify door indicator turns red with "🚪 MỞ"
- Door CLOSED → green with "🚪 ĐÓNG"

### 2.4 MMM-FSS-Inventory — Move to bottom_right + Thumbnail Display

**`config.js` change:**
```js
{
    module: "MMM-FSS-Inventory",
    position: "bottom_right",    // was bottom_center
    config: {
        frtAppEnabled: true,     // was false
        showPlaceholder: false   // was true
    }
}
```

**`MMM-FSS-Inventory.js` changes:**
- Keep existing notification queue (it works)
- Ensure inventory grid shows: **latest thumbnail + class name + quantity**
- Sort items by `last_updated` descending
- Show custom-labeled foods with their user label instead of "unknown"
- The existing code already handles FRT_UPDATE and INVENTORY_UPDATE — just ensure image_path is used

**`MMM-FSS-Inventory.css` changes:**
```css
.mmm-fss-inventory-grid {
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 8px;
    max-height: 320px;
    overflow-y: auto;
}
.mmm-fss-inventory-item img {
    width: 60px;
    height: 60px;
    border-radius: 8px;
    object-fit: cover;
}
.mmm-fss-inventory-item .item-name {
    font-size: 11px;
    text-align: center;
    margin-top: 4px;
}
.mmm-fss-inventory-item .item-qty {
    font-size: 10px;
    color: #95a5a6;
    text-align: center;
}
```

**Verification:**
- Restart MagicMirror
- Check Inventory is now at bottom_right
- Check thumbnails appear when food is detected
- Check scrolling works with many items

### 2.5 MMM-FSS-LivePreview — Video Preview from SHM

**Key design:** No 2nd YOLO instance. FRTApp main pipeline writes annotated frames to `/opt/fss/latest_preview.jpg` every 3rd iteration (~10 FPS output). LivePreview bridge polls this file.

**Module structure:**
```
MMM-FSS-LivePreview/
├── MMM-FSS-LivePreview.js
├── MMM-FSS-LivePreview.css
├── node_helper.js
└── py_bridge/
    ├── requirements.txt       # Pillow (or just use opencv in frt_app)
    └── live_preview_bridge.py
```

**`MMM-FSS-LivePreview.js`:**
```javascript
Module.register("MMM-FSS-LivePreview", {
    defaults: {
        previewFps: 10,
        timeoutAfterStable: 3000,  // ms after stable detection before closing
        maxWidth: 640,
        maxHeight: 480
    },
    start() {
        this.isVisible = false;
        this.currentFrame = null;
        this.stableTimer = null;
        this.sendSocketNotification("LIVE_PREVIEW_START", {});
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-live-preview";
        wrapper.style.display = this.isVisible ? "block" : "none";
        
        const video = document.createElement("img");
        video.id = "fss-live-preview-img";
        video.style.maxWidth = this.config.maxWidth + "px";
        video.style.maxHeight = this.config.maxHeight + "px";
        wrapper.appendChild(video);
        
        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "LIVE_PREVIEW_FRAME") {
            this.showPreview(payload.frame);
        } else if (notification === "LIVE_PREVIEW_DONE") {
            this.hidePreview();
        } else if (notification === "LIVE_PREVIEW_SHOW") {
            this.isVisible = true;
            this.updateDom();
        }
    },
    showPreview(base64Frame) {
        this.isVisible = true;
        document.getElementById("fss-live-preview-img").src = "data:image/jpeg;base64," + base64Frame;
        this.updateDom();
        
        // Auto-hide after stability timeout
        if (this.stableTimer) clearTimeout(this.stableTimer);
        this.stableTimer = setTimeout(() => {
            this.hidePreview();
        }, this.config.timeoutAfterStable);
    },
    hidePreview() {
        this.isVisible = false;
        this.updateDom();
    }
});
```

**`MMM-FSS-LivePreview.css`:**
```css
#fss-live-preview {
    position: relative;
    display: flex;
    justify-content: center;
    align-items: center;
    background: rgba(0,0,0,0.8);
    border-radius: 12px;
    padding: 8px;
    margin: 8px auto;
    max-width: 660px;
    transition: opacity 0.5s ease;
}
#fss-live-preview img {
    border-radius: 8px;
    width: 100%;
    height: auto;
}
```

**`live_preview_bridge.py`:**
```python
#!/usr/bin/env python3
"""Read /opt/fss/latest_preview.jpg and output base64 JSON to stdout."""
import json, sys, time, base64, os

PREVIEW_PATH = "/opt/fss/latest_preview.jpg"
POLL_INTERVAL = 0.1  # 100ms = 10 FPS
last_mtime = 0

print(json.dumps({"type": "STATUS", "message": "Started"}), flush=True)

try:
    while True:
        if os.path.exists(PREVIEW_PATH):
            mtime = os.path.getmtime(PREVIEW_PATH)
            if mtime != last_mtime:
                last_mtime = mtime
                with open(PREVIEW_PATH, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    print(json.dumps({"type": "FRAME", "data": b64}), flush=True)
        time.sleep(POLL_INTERVAL)
except KeyboardInterrupt:
    pass
```

**`node_helper.js`:**
```javascript
const NodeHelper = require("node_helper");
const { spawn } = require("child_process");

module.exports = NodeHelper.create({
    start() {
        this.pythonProcess = null;
        this.started = false;
    },
    socketNotificationReceived(notification) {
        if (notification === "LIVE_PREVIEW_START" && !this.started) {
            this.startBridge();
        }
    },
    startBridge() {
        const script = require("path").join(__dirname, "py_bridge", "live_preview_bridge.py");
        this.pythonProcess = spawn("/usr/bin/python3", [script]);
        
        let buffer = "";
        this.pythonProcess.stdout.on("data", (data) => {
            buffer += data.toString();
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep incomplete line
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const msg = JSON.parse(line);
                    if (msg.type === "FRAME") {
                        this.sendSocketNotification("LIVE_PREVIEW_FRAME", { frame: msg.data });
                    }
                } catch(e) {}
            }
        });
        this.started = true;
    },
    stop() {
        if (this.pythonProcess) this.pythonProcess.kill();
    }
});
```

**FRTApp integration — in `FrtMain.py` inference loop:**
Every 3rd frame after successful inference:
```python
if frame_count % 3 == 0 and tracked:
    self._save_preview_frame(frame, tracked)

def _save_preview_frame(self, frame, detections):
    """Draw detections on frame and save for LivePreview."""
    annotated = frame.copy()
    for det in detections:
        x, y, w, h = det.get("bbox", [0,0,0,0])
        label = det.get("class_name", "?")
        conf = det.get("confidence", 0)
        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0,255,0), 2)
        cv2.putText(annotated, f"{label} {conf:.2f}", (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    cv2.imwrite("/opt/fss/latest_preview.jpg", annotated,
                [cv2.IMWRITE_JPEG_QUALITY, 70])
```

**config.js addition:**
```js
{
    module: "MMM-FSS-LivePreview",
    position: "center",
    config: {
        previewFps: 10,
        timeoutAfterStable: 3000
    }
}
```

**RAM note:** Single JPEG file (~50KB) on tmpfs. No 2nd model. No FFmpeg subprocess. ~1MB RSS for Python bridge polling loop.

### 2.6 Custom Food Naming — User-Based System

**Data flow:**
1. FRTApp detects object with confidence < threshold OR class not in {5 known classes}
2. Instead of `FoodDetected`, emit `UnknownFoodDetected(frame_crop_base64, timestamp)`
3. DBDaemon receives → stores temp crop at `/opt/fss/custom_pending.jpg` → emits `CustomFoodRequest` signal
4. MMM-FSS-Notification shows dialog with:
   - `[Add as Custom]` — opens MMM-FSS-VirtualKeyboard in modal mode
   - `[Cancel]` — dismisses, deletes temp crop
5. User types name → sent to DBDaemon via `RegisterCustomFood(name, image_path)` D-Bus call
6. DBDaemon: stores in `FSS_Inventory.db` (`custom_food_labels` table) + adds to `current_inventory` with qty=1
7. Next detection: FRTApp compares histogram of detected crop vs saved custom foods
   - If match > threshold → show **Custom Food Menu** with saved name as option + "Add New"
   - User taps name → logged as that food, quantity incremented

**DBDaemon — new table in `SqliteManager.py`:**
```python
CREATE TABLE IF NOT EXISTS custom_food_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_label TEXT NOT NULL,
    image_path TEXT,
    feature_hash TEXT,            -- HSV histogram as base64 JSON
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT DEFAULT (datetime('now'))
)
```

**DBDaemon — new D-Bus signals/methods:**
```python
# In DbDaemonDbusObject:
@dbus_signal_async('ss')
def CustomFoodRequest(self, temp_image_path: str, frame_crop_b64: str) -> None:
    """Signal: Unknown food detected, ask user to name it."""
    pass

@dbus_method_async('ss', 'b')
async def RegisterCustomFood(self, food_name: str, image_path: str) -> bool:
    """Method: Register a user-named custom food."""
    pass

@dbus_method_async('', 's')
async def GetCustomFoods(self) -> str:
    """Method: Get all previously registered custom foods (JSON)."""
    pass
```

**FRTApp — `FrtDbusInterface.py`:**
```python
@dbus_signal_async('ss')
def UnknownFoodDetected(self, crop_b64: str, timestamp: str) -> None:
    """Signal: Unknown food detected, payload is base64 crop + timestamp."""
    pass
```

**Similarity matching for "next time"** (in `DBDaemon` or a utility):
```python
import cv2, numpy as np, json, base64

def compute_histogram(image_path: str) -> str:
    img = cv2.imread(image_path)
    if img is None: return ""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0,1], None, [50,60], [0,180,0,256])
    cv2.normalize(hist, hist)
    return json.dumps(hist.tolist())

def histogram_similarity(h1_json: str, h2_json: str) -> float:
    h1 = np.array(json.loads(h1_json), dtype=np.float32)
    h2 = np.array(json.loads(h2_json), dtype=np.float32)
    return cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
```

**Verification:**
- [ ] FRTApp detects unknown → `UnknownFoodDetected` emitted
- [ ] Electron shows "Add as Custom / Cancel" dialog
- [ ] User types name → name stored in DB
- [ ] Next detection of same food → Custom Food Menu appears
- [ ] User taps existing name → quantity incremented

### 2.7 New Module: MMM-FSS-VirtualKeyboard

**Pure frontend** — no Python bridge. Uses HTML/CSS/JS only.

**File: `MMM-FSS-VirtualKeyboard.js`:**
```javascript
Module.register("MMM-FSS-VirtualKeyboard", {
    defaults: {
        layout: "qwerty",
        showSearchBar: true,
        placeholderText: "Nhập tên món ăn...",
        submitOnEnter: true
    },
    start() {
        this.query = "";
        this.isVisible = true;
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-vk-container";
        
        // Search bar
        if (this.config.showSearchBar) {
            const bar = document.createElement("div");
            bar.id = "fss-vk-search-bar";
            const input = document.createElement("input");
            input.id = "fss-vk-input";
            input.type = "text";
            input.placeholder = this.config.placeholderText;
            input.value = this.query;
            input.addEventListener("input", (e) => { this.query = e.target.value; });
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") this.submit();
            });
            bar.appendChild(input);
            
            const searchBtn = document.createElement("button");
            searchBtn.id = "fss-vk-search-btn";
            searchBtn.textContent = "🔍";
            searchBtn.addEventListener("click", () => this.submit());
            bar.appendChild(searchBtn);
            wrapper.appendChild(bar);
        }
        
        // Keyboard rows
        const rows = [
            ["q","w","e","r","t","y","u","i","o","p"],
            ["a","s","d","f","g","h","j","k","l"],
            ["⇧","z","x","c","v","b","n","m","⌫"],
            ["123","🇻🇳","␣","␣","␣","␣","␣","↵"]
        ];
        
        rows.forEach((row, ri) => {
            const rowDiv = document.createElement("div");
            rowDiv.className = "fss-vk-row";
            row.forEach(key => {
                const btn = document.createElement("button");
                btn.className = "fss-vk-key";
                btn.textContent = key;
                btn.dataset.key = key;
                btn.addEventListener("click", () => this.onKeyPress(key));
                if (key === "␣") btn.classList.add("fss-vk-space");
                if (key === "↵") btn.classList.add("fss-vk-enter");
                if (key === "⌫") btn.classList.add("fss-vk-backspace");
                rowDiv.appendChild(btn);
            });
            wrapper.appendChild(rowDiv);
        });
        
        return wrapper;
    },
    onKeyPress(key) {
        const input = document.getElementById("fss-vk-input");
        if (!input) return;
        
        if (key === "⌫") {
            this.query = this.query.slice(0, -1);
        } else if (key === "↵") {
            this.submit();
        } else if (key === "⇧") {
            // Toggle shift — implement caps
        } else if (key === "123") {
            // Toggle numpad — implement later
        } else {
            this.query += key;
        }
        input.value = this.query;
    },
    submit() {
        if (this.query.trim()) {
            this.sendSocketNotification("RECIPE_SEARCH", { recipe: this.query.trim() });
        }
    },
    setQuery(text) {
        this.query = text;
        const input = document.getElementById("fss-vk-input");
        if (input) input.value = text;
    }
});
```

**`MMM-FSS-VirtualKeyboard.css`:**
```css
#fss-vk-container {
    background: rgba(30,30,30,0.95);
    border-radius: 16px;
    padding: 12px;
    max-width: 600px;
    margin: 0 auto;
}
#fss-vk-search-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
}
#fss-vk-input {
    flex: 1;
    padding: 10px 16px;
    border-radius: 24px;
    border: 1px solid #555;
    background: #222;
    color: white;
    font-size: 18px;
    outline: none;
}
#fss-vk-search-btn {
    padding: 8px 16px;
    border-radius: 24px;
    border: none;
    background: #3498db;
    color: white;
    cursor: pointer;
    font-size: 18px;
}
.fss-vk-row {
    display: flex;
    justify-content: center;
    gap: 4px;
    margin: 2px 0;
}
.fss-vk-key {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    border: 1px solid #444;
    background: #333;
    color: white;
    font-size: 16px;
    cursor: pointer;
    touch-action: manipulation;
    transition: background 0.1s;
}
.fss-vk-key:active { background: #555; }
.fss-vk-space { width: 180px; }
.fss-vk-enter { background: #27ae60; width: 88px; }
.fss-vk-backspace { color: #e74c3c; }
```

**`node_helper.js`:** Minimal relay — forward any `RECIPE_SEARCH` events to MMM-FSS-Recommend.

**config.js:**
```js
{ module: "MMM-FSS-VirtualKeyboard", position: "top_center" }
```

### 2.8 New Module: MMM-FSS-Recommend

**Structure:**
```
MMM-FSS-Recommend/
├── MMM-FSS-Recommend.js
├── MMM-FSS-Recommend.css
├── node_helper.js
└── py_bridge/
    ├── requirements.txt
    └── recommend_dbus_listener.py
```

**`MMM-FSS-Recommend.js`:**
```javascript
Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    start() {
        this.result = null;
        this.loading = false;
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-recommend-container";
        
        if (this.loading) {
            wrapper.innerHTML = '<div class="fss-recommend-loading">Đang phân tích...</div>';
            return wrapper;
        }
        
        if (!this.result) {
            wrapper.innerHTML = '<div class="fss-recommend-empty">Nhập tên món ăn để tìm kiếm</div>';
            return wrapper;
        }
        
        // Recipe name header
        const header = document.createElement("div");
        header.className = "fss-recommend-header";
        header.textContent = `📋 ${this.result.recipe_name}`;
        wrapper.appendChild(header);
        
        // Ingredient table
        const table = document.createElement("table");
        table.className = "fss-recommend-table";
        table.innerHTML = `
            <tr><th>Nguyên liệu</th><th>Cần</th><th>Có</th><th></th></tr>
            ${this.result.ingredients.map(ing => `
                <tr class="fss-recommend-${ing.status}">
                    <td>${ing.name}</td>
                    <td>${ing.required}</td>
                    <td>${ing.available}</td>
                    <td>${ing.status === 'available' ? '✅' : ing.status === 'needed' ? '⚠️' : '❌'}</td>
                </tr>
            `).join('')}
        `;
        wrapper.appendChild(table);
        
        // Summary
        const summary = document.createElement("div");
        summary.className = "fss-recommend-summary";
        const missing = this.result.ingredients.filter(i => i.status === 'missing').length;
        summary.textContent = missing > 0 
            ? `❌ Còn thiếu ${missing} nguyên liệu`
            : '✅ Đã có đủ nguyên liệu!';
        wrapper.appendChild(summary);
        
        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "RECOMMEND_RESULT") {
            this.result = payload;
            this.loading = false;
            this.updateDom();
        } else if (notification === "RECOMMEND_LOADING") {
            this.loading = true;
            this.result = null;
            this.updateDom();
        }
    }
});
```

**`recommend_dbus_listener.py`:**
```python
#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecommendDaemon D-Bus, relay results."""
import sys, json, asyncio, uuid
from sdbus import DbusInterfaceCommon, dbus_method

class RecommendDaemonInterface(DbusInterfaceCommon,
                               interface_name="vn.edu.uit.FSS.RecommendDaemon"):
    @dbus_method('ss', 's')
    def GenerateShoppingList(self, recipe_name: str, batch_id: str) -> str:
        pass

proxy = RecommendDaemonInterface.new_proxy(
    "vn.edu.uit.FSS.RecommendDaemon",
    "/vn/edu/uit/FSS/RecommendDaemon"
)

for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        msg = json.loads(line)
        if msg.get("type") == "SEARCH":
            recipe = msg["recipe"]
            batch_id = str(uuid.uuid4())
            result = proxy.GenerateShoppingList(recipe, batch_id)
            print(json.dumps({"type": "RESULT", "data": json.loads(result)}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
```

**`node_helper.js`:** Spawns `recommend_dbus_listener.py`, writes `RECIPE_SEARCH` to its stdin, reads `RECOMMEND_RESULT` from stdout.

**config.js:**
```js
{
    module: "MMM-FSS-Recommend",
    position: "bottom_center",
    config: {}
}
```

### 2.9 New Module: MMM-FSS-Notification

**Structure:**
```
MMM-FSS-Notification/
├── MMM-FSS-Notification.js
├── MMM-FSS-Notification.css
└── node_helper.js
```

**Sound design:** Use **Web Audio API** (OscillatorNode) — no sound files needed, no npm packages. Different frequencies for different notification types:

| Type | Frequency | Duration | Pattern | Description |
|------|-----------|----------|---------|-------------|
| Monitor (user detected) | 440 Hz | 200ms | 3 rapid beeps | Alert tone |
| Monitor (door) | 660 Hz | 150ms | 2 beeps | Transition tone |
| Food (added) | 880 Hz | 100ms | 1 short beep | Positive chime |
| Food (removed) | 330 Hz | 200ms | 2 slow beeps | Negative tone |
| Recommend | 550 Hz | 150ms | 1 beep + 1 higher | Informational |

**Sound implementation (`MMM-FSS-Notification.js`):**
```javascript
playNotificationSound(type) {
    // Web Audio API — no files needed
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const soundMap = {
            "user_detected":  { freq: 440, dur: 200, count: 3, gap: 80 },
            "door_open":      { freq: 660, dur: 150, count: 2, gap: 100 },
            "door_closed":    { freq: 330, dur: 150, count: 1, gap: 0 },
            "food_added":     { freq: 880, dur: 100, count: 1, gap: 0 },
            "food_removed":   { freq: 330, dur: 200, count: 2, gap: 150 },
            "recommend_done": { freq: 550, dur: 150, count: 2, gap: 100, freq2: 770 }
        };
        
        const s = soundMap[type] || { freq: 500, dur: 100, count: 1, gap: 0 };
        
        let startTime = ctx.currentTime;
        for (let i = 0; i < s.count; i++) {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.frequency.value = s.freq2 && i === 1 ? s.freq2 : s.freq;
            osc.type = "sine";
            
            gain.gain.setValueAtTime(0.3, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + s.dur / 1000);
            
            osc.start(startTime);
            osc.stop(startTime + s.dur / 1000);
            startTime += (s.dur + s.gap) / 1000;
        }
    } catch(e) {
        // Audio not available — silently ignore
    }
}
```

**`MMM-FSS-Notification.js` — main logic:**
```javascript
Module.register("MMM-FSS-Notification", {
    defaults: {
        displayDuration: 5000,   // 5 seconds
        maxVisible: 5,
        animationDuration: 300
    },
    start() {
        this.notifications = [];
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-notification-overlay";
        
        this.notifications.forEach((n, i) => {
            const card = document.createElement("div");
            card.className = `fss-notification-card fss-notif-${n.type}`;
            
            const msg = document.createElement("div");
            msg.className = "fss-notif-message";
            msg.textContent = n.message;
            card.appendChild(msg);
            
            const timer = document.createElement("div");
            timer.className = "fss-notif-timer";
            card.appendChild(timer);
            
            wrapper.appendChild(card);
        });
        
        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "FSS_NOTIFICATION") {
            this.playNotificationSound(payload.type);
            this.addNotification(payload);
        }
    },
    addNotification(data) {
        this.notifications.unshift({
            id: Date.now(),
            type: data.type,
            message: data.message,
            timestamp: Date.now()
        });
        
        if (this.notifications.length > this.config.maxVisible) {
            this.notifications.pop();
        }
        
        this.updateDom();
        
        // Auto-dismiss
        setTimeout(() => {
            this.notifications = this.notifications.filter(n => n.id !== data.id);
            this.updateDom();
        }, this.config.displayDuration);
    }
});
```

**`MMM-FSS-Notification.css`:**
```css
#fss-notification-overlay {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
    max-width: 500px;
    width: 100%;
}
.fss-notification-card {
    background: rgba(20,20,30,0.92);
    border-radius: 12px;
    padding: 12px 16px;
    border-left: 4px solid #ccc;
    backdrop-filter: blur(8px);
    animation: fssNotifSlideIn 0.3s ease;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.fss-notif-monitor   { border-left-color: #3498db; }
.fss-notif-food      { border-left-color: #2ecc71; }
.fss-notif-recommend { border-left-color: #e67e22; }
.fss-notif-custom    { border-left-color: #9b59b6; }
.fss-notif-message {
    color: white;
    font-size: 14px;
    line-height: 1.4;
}
.fss-notif-timer {
    height: 2px;
    background: rgba(255,255,255,0.2);
    margin-top: 8px;
    border-radius: 1px;
    animation: fssNotifTimer 5s linear;
}
@keyframes fssNotifSlideIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes fssNotifTimer {
    from { width: 100%; }
    to { width: 0%; }
}
```

**How other modules send notifications:** Each module's `node_helper.js` duplicates relevant data to `MMM-FSS-Notification`:

```javascript
// In MMM-FSS-Monitor/node_helper.js — after receiving door state:
this.sendSocketNotification("FSS_NOTIFICATION", {
    type: "monitor",
    message: `🚪 DOOR ${doorState}. Opening/Turning off USB Camera…`
});

// In MMM-FSS-Inventory/node_helper.js — on FRT_UPDATE:
this.sendSocketNotification("FSS_NOTIFICATION", {
    type: "food",
    message: `📦 ${action} ${quantity} ${foodClass} ${action === 'Added' ? 'to' : 'from'} the fridge`
});

// In MMM-FSS-Recommend/node_helper.js — on RECOMMEND_RESULT:
this.sendSocketNotification("FSS_NOTIFICATION", {
    type: "recommend",
    message: `🔍 You searched for "${recipeName}". Missing ${missingCount} ingredient(s).`
});
```

**config.js addition:**
```js
{
    module: "MMM-FSS-Notification",
    position: "center"        // Fixed overlay — position not grid-sensitive
}
```

### 2.10 config.js — Full Update

Merged config with all 7 FSS modules correctly positioned:

```js
modules: [
    // ... default modules (clock, calendar, compliments, weather, newsfeed) unchanged ...
    
    // FSS Modules:
    {
        module: "MMM-FSS-VirtualKeyboard",
        position: "top_center"
    },
    {
        module: "MMM-FSS-LivePreview",
        position: "center",
        config: { previewFps: 10, timeoutAfterStable: 3000 }
    },
    {
        module: "MMM-FSS-Monitor",
        position: "top_center",
        config: { distanceThreshold: 0.6, showDebugInfo: false }
    },
    {
        module: "MMM-FSS-Env",
        position: "top_right",
        config: {
            updateInterval: 2000,
            roundTemperature: false,
            roundHumidity: false,
            displayUnits: true
        }
    },
    {
        module: "MMM-FSS-Recommend",
        position: "bottom_center"
    },
    {
        module: "MMM-FSS-Inventory",
        position: "bottom_right",
        config: { frtAppEnabled: true, showPlaceholder: false }
    },
    {
        module: "MMM-FSS-Notification",
        position: "center"
    }
]
```

### 2.11 DBDaemon — Subscribe to RecommendDaemon

**File:** `db_daemon/src/DbDbusInterface.py`

**New subscription method:**
```python
def subscribe_recommend_daemon_events(self, callback: Callable) -> None:
    """Subscribe to RecommendationUpdated from RecommendDaemon."""

    class RecInterface(DbusInterfaceCommonAsync,
                       interface_name="vn.edu.uit.FSS.RecommendDaemon"):
        @dbus_signal_async('ss')
        def RecommendationUpdated(self, recipe_name: str, shopping_list: str):
            pass

    proxy = RecInterface.new_proxy(
        "vn.edu.uit.FSS.RecommendDaemon",
        "/vn/edu/uit/FSS/RecommendDaemon"
    )
    asyncio.create_task(self._listen_recommendations(proxy, callback))
```

**New table in `SqliteManager.py`:**
```python
CREATE TABLE IF NOT EXISTS recommendation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_name TEXT NOT NULL,
    shopping_list TEXT NOT NULL,     -- JSON
    created_at TEXT DEFAULT (datetime('now'))
)
```

**Relay to UI:** After storing, emit `UIUpdateRequired` with a special flag so MMM-FSS-Notification can pick it up.

---

## NEW LIBRARIES & DEPENDENCIES

| Library | Component | Install | Size | Purpose |
|---------|-----------|---------|------|---------|
| `libtensorflow-lite-dev` | `c_tflite_reader` | `apt` | ~15MB | C API for .tflite inference |
| `Pillow`(≥10.0) | LivePreview bridge | `pip` | ~1MB | (may already exist) |
| `opencv-python-headless`(≥4.8) | FRTApp preview save | `pip` | ~20MB | Drawing bboxes on frames |
| `numpy`(≥1.24) | FRTApp + preview | `pip` | ~10MB | (already exists) |

**Existing deps unchanged:** `sdbus>=0.14.0`, `sklearn-crfsuite`, `pyvi`, `joblib`, `tflite-runtime`

**No new npm packages** — Web Audio API handles sounds natively in Electron/Chromium.

---

## AGENTS.md UPDATE PLAN

Add these 6 new sections after the existing "Component Deep Dives":

### A. Python venv Management Workflow
```markdown
### Python venv Management

**Standard setup per component:**
```bash
cd COMPONENT_NAME
python3 -m venv venv
source venv/bin/activate
pip install --upgrade setuptools pip
pip install -r requirements.txt
```

**Cross-component imports** (e.g., RecommendDaemon imports recommend_system):
- Add `sys.path.append(os.path.join(os.path.dirname(__file__), '../../recommend_system/src'))`
- Or install as editable: `pip install -e ../../recommend_system/`

**Common issues:**
- `ModuleNotFoundError`: Check `sys.path`, venv activation, pip install
- `pip install sdbus` fails: Need system deps `libsystemd-dev`, `pkg-config`
- Freeze: `pip freeze > requirements.txt` after adding new deps
```

### B. Node.js / Electron Debugging
```markdown
### Node.js / Electron Debugging

**Chrome DevTools for Electron renderer:**
```bash
# Start with dev flags
npm run start:x11:dev
# Then open chrome://inspect in Chromium browser
```

**Node.js inspector for main process:**
```bash
# Add --inspect flag
DISPLAY=:0 electron js/electron.js --inspect=9229
```

**PM2 process management:**
```bash
pm2 list                    # List all processes
pm2 logs magicmirror        # View logs
pm2 restart magicmirror     # Restart
pm2 save                    # Save process list
```

**socket.io debugging:**
```javascript
// In browser console (DevTools)
localStorage.debug = 'socket.io:*';
// Reload module to see socket events
```

**Module lifecycle hooks:**
- `start()` — called once on module load
- `getDom()` — called on each `updateDom()`, returns DOM element
- `socketNotificationReceived(noti, payload)` — receives socket events from node_helper
- `notificationReceived(noti, payload, sender)` — receives MagicMirror internal events
```

### C. SQLite Schema Migration Patterns
```markdown
### SQLite Schema Migration Patterns

**Adding a new column:**
```sql
ALTER TABLE table_name ADD COLUMN new_column TEXT DEFAULT NULL;
```

**Adding a new table:**
```python
# In SqliteManager.init_tables_if_not_exists()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS new_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
```

**Version tracking:**
```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);
```

**Rollback:** Re-create table from backup:
```python
cursor.execute("CREATE TABLE backup AS SELECT * FROM table_to_migrate")
cursor.execute("DROP TABLE table_to_migrate")
cursor.execute("CREATE TABLE table_to_migrate (...new schema...)")
cursor.execute("INSERT INTO table_to_migrate SELECT * FROM backup")
cursor.execute("DROP TABLE backup")
```

**FSS databases:**
| File | Location | Tables |
|------|----------|--------|
| `fss_data.db` | `/opt/fss/data/` | `environment_log`, `door_event_log`, `distance_sensor_log`, `presence_sensor_log` |
| `FSS_Inventory.db` | `/opt/fss/data/` | `current_inventory`, `food_history`, `custom_food_labels` |
| `FSS_Request.db` | `/opt/fss/data/` | `recipe_requests` |
| `FSS-Recommend.db` | `/opt/fss/data/` | `recommendation_log`, `shopping_list` |
```

### D. MagicMirror Module Development Workflow
```markdown
### MagicMirror Module Development Workflow

**Module template (3-file structure):**
```
MMM-FSS-<Name>/
├── MMM-FSS-<Name>.js        # Frontend: DOM rendering, socket listeners
├── MMM-FSS-<Name>.css       # Styling (dark theme, touch-friendly)
└── node_helper.js            # Backend: spawns subprocess, relays socket.io
└── py_bridge/                # (optional) Python D-Bus listener
    ├── requirements.txt
    └── <name>_listener.py    # Reads D-Bus, outputs JSON to stdout
```

**Data flow:** `Python bridge → stdout JSON → node_helper.js → socket.io → Frontend`

**JSON protocol (stdout):**
```json
{"type": "EVENT_NAME", "field1": "value1", "field2": 123}
```

**node_helper.js pattern:**
```javascript
const NodeHelper = require('node_helper');
const { spawn } = require('child_process');

module.exports = NodeHelper.create({
    start() { this.process = null; },
    socketNotificationReceived(noti, payload) {
        if (noti === "START") this.startBridge();
    },
    startBridge() {
        this.process = spawn('python3', [__dirname + '/py_bridge/listener.py']);
        let buf = '';
        this.process.stdout.on('data', d => {
            buf += d.toString();
            let lines = buf.split('\n');
            buf = lines.pop();
            lines.filter(l => l.trim()).forEach(l => {
                try {
                    const msg = JSON.parse(l);
                    this.sendSocketNotification(msg.type, msg);
                } catch(e) {}
            });
        });
    },
    stop() { if (this.process) this.process.kill(); }
});
```

**Position reference:**
| Position | CSS Mapping | Best for |
|----------|-------------|----------|
| `top_bar` | `.region.top.bar` | Status bar items |
| `top_left` | `.region.top.left` | Clock, calendar |
| `top_center` | `.region.top.center` | Search bars, keyboard |
| `top_right` | `.region.top.right` | Sensor data |
| `center` | `.region.middle.center` | Video, overlays |
| `bottom_center` | `.region.bottom.center` | Recommendations |
| `bottom_right` | `.region.bottom.right` | Compact inventory |

**Touchscreen optimization:**
- Buttons: min 44×44px
- Touch ripple/scale on press (not hover)
- `touch-action: manipulation` CSS
- Avoid right-click, drag, or hover-only interactions
```

### E. C TFLite Reader Development
```markdown
### C TFLite Reader Development

**API reference:** `#include "tensorflow/lite/c/c_api.h"`

**Key functions:**
```c
TfLiteModel* model = TfLiteModelCreateFromFile(model_path);
TfLiteInterpreterOptions* options = TfLiteInterpreterOptionsCreate();
TfLiteInterpreter* interpreter = TfLiteInterpreterCreate(model, options);

// Input
TfLiteTensor* input = TfLiteInterpreterGetInputTensor(interpreter, 0);
TfLiteTensorCopyFromBuffer(input, input_data, input_size);

// Run
TfLiteInterpreterInvoke(interpreter);

// Output
const TfLiteTensor* output = TfLiteInterpreterGetOutputTensor(interpreter, 0);
TfLiteTensorCopyToBuffer(output, output_buffer, output_size);
```

**Building for ARM64 (Raspberry Pi 4B):**
```bash
# Native build on Pi
sudo apt install libtensorflow-lite-dev
# Or cross-compile:
aarch64-linux-gnu-gcc -I/usr/aarch64-linux-gnu/include -c src/TfliteReader.c
```

**ctypes integration (Python → C):**
```python
import ctypes
lib = ctypes.CDLL("./libtflite_reader.so")
lib.tflite_reader_create.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.tflite_reader_create.restype = ctypes.c_void_p
reader = lib.tflite_reader_create(b"/path/to/model.tflite", 2)  # 2=INT8
```

**FP32/FP16/INT8 handling:**
| Enum | Precision | Input type | Output conversion |
|------|-----------|------------|-------------------|
| `TFLITE_FP32` | 32-bit float | `float` | Direct |
| `TFLITE_FP16` | 16-bit float | `float` (converted) | Convert to float |
| `TFLITE_INT8` | 8-bit integer | `uint8_t` (quantized) | Dequantize with scale+zero |

**Error handling pattern:**
```c
if (!reader) { fprintf(stderr, "TfliteReader: create failed\n"); return NULL; }
if (TfLiteInterpreterGetInputTensorCount(reader->interpreter) < 1) {
    fprintf(stderr, "TfliteReader: no input tensors\n");
    tflite_reader_destroy(reader);
    return NULL;
}
```
```

### F. FFmpeg / SHM Frame Transport
```markdown
### Frame Transport Mechanisms

**POSIX Shared Memory** (`/dev/shm/fss_video_frame`):
- Writer (C++): `shm_open`, `ftruncate`, `mmap`, `memcpy`
- Reader (Python): `PosixShmReader` — `mmap`, read, `munmap`
- Size: 2MB JPEG buffer
- Permission: `chmod 666 /dev/shm/fss_video_frame`

**File-based polling** (`/opt/fss/latest_preview.jpg`):
- Writer: `cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])`
- Reader: Poll via `os.path.getmtime()`, read if changed
- Best for: LivePreview bridge (simple, no 2nd inference)

**Frame rate control:**
```python
# Writer side — write every Nth frame
if frame_count % 3 == 0:  # ~10 FPS from 30 FPS input
    save_preview(frame)

# Reader side — poll at interval
import time
while True:
    if file_updated():
        send_frame()
    time.sleep(0.1)  # 10 FPS polling
```

**JPEG quality vs bandwidth:**
| Quality | Size | Use case |
|---------|------|----------|
| 95 | ~150KB | Archival |
| 70 | ~40-60KB | Live preview (good balance) |
| 50 | ~20-30KB | Low bandwidth / RAM constraint |
```
---

## APPENDIX: SOUND DESIGN FOR NOTIFICATIONS

### Web Audio API — Built-in, Zero Dependencies

MagicMirror runs on Electron which includes Chromium's Web Audio API. No sound files needed.

**Sound mapping:**

| Notification Type | Sound | Purpose |
|------------------|-------|---------|
| `user_detected` | 440Hz × 3 rapid beeps 👤 | Alert — user near fridge |
| `door_open` | 660Hz × 2 beeps 🚪 | Transition — camera starting |
| `door_closed` | 330Hz × 1 beep 🔒 | Transition — camera stopping |
| `food_added` | 880Hz × 1 short chime ✅ | Positive — item added |
| `food_removed` | 330Hz × 2 slow beeps ➖ | Informational — item removed |
| `recommend_done` | 550Hz → 770Hz × 2 🔍 | Informational — analysis complete |

**Implementation:** `new AudioContext()` → `OscillatorNode` with sine wave → `GainNode` for envelope → `ctx.destination`

**Why Web Audio:**
- No npm packages to download
- No sound files to store
- Minimal CPU/RAM (oscillator uses ~0.1% CPU)
- Works offline (no network needed)
- Differentiate types by frequency instead of loading multiple files

---

## EXECUTION CHECKLIST (1-Day Sprint)

### FRTApp Branch (FRTApp-dev)
- [ ] 1.1 Create `c_tflite_reader/` with all API functions → test build
- [ ] 1.2 Update `frt_app/CMakeLists.txt` → build both sub-folders
- [ ] 1.3 Python AI Core integration (optional C backend) → test both paths
- [ ] 1.4 `CameraStateChanged` D-Bus signal → verify with `dbus-monitor`
- [ ] 1.5 Distance sensor subscription + `--debug-no-distance` flag → test
- [ ] **Merge FRTApp-dev → main**

### ElectronApp Branch (ElectronApp-dev)
- [ ] 2.1 SensorDaemon: `setprecision(1)` → `setprecision(2)` → rebuild & verify
- [ ] 2.2 MMM-FSS-Env: disable rounding, `toFixed(2)` → restart & verify
- [ ] 2.3 MMM-FSS-Monitor: door state indicator → test with fake signal
- [ ] 2.4 MMM-FSS-Inventory: move to bottom_right + thumbnails → verify
- [ ] 2.5 MMM-FSS-LivePreview: new module → test with SHM/file
- [ ] 2.6 MMM-FSS-VirtualKeyboard: new module → test key presses
- [ ] 2.7 MMM-FSS-Recommend: new module → test with recipe search
- [ ] 2.8 MMM-FSS-Notification: new module with Web Audio sounds → test each type
- [ ] 2.9 Custom Food Naming: dialog → store → recall → verify DB
- [ ] 2.10 DBDaemon: subscribe to `RecommendationUpdated` → verify relay
- [ ] 2.11 config.js: update with all modules + positions → restart & verify
- [ ] **Merge ElectronApp-dev → main**

### Post-Merge
- [ ] Full integration test: SensorDaemon → DBDaemon → FRTApp → RecommendDaemon → UI
- [ ] README.md directory tree updated
- [ ] AGENTS.md 6 new sections added
- [ ] Stub `recommend_system/recommend_daemon/` deleted

---
# FSS FINAL UPGRADE — 30/05/2026
Updated Implementation Plan (Aligned with FINAL_UPGRADE_3005)
1. recommend_system Output Format — Already Satisfied
The friend's concern is already addressed by the current codebase:
- RecipeAnalyzerEngine.generate_fss_request() (recommend_system/src/RecipeAnalyzerAPI.py:392) returns a Dict — specifically {"status": "SUCCESS", "dish": str, "ingredients": [{...}], "processing_time_ms": float}. No .db writes at the NLP library level.
- RecommendEngine.generate_shopping_list() (recommend_daemon/src/RecommendEngine.py:29) also returns a Dict[str, Any] — the Bù Trừ result with available/needed/missing lists.
- The D-Bus method GenerateShoppingList (DbusInterface.py:194) serializes this dict to JSON string and returns it to the caller.
- The .db persistence is an optional side effect inside generate_shopping_list() (lines 120-132) — only runs if self.db_manager is set, and does NOT replace the dict return value.
No code changes needed. The plan already had this right. The FINAL_UPGRADE_3005.md section on RecommendDaemon confirms this: "Returns JSON FSS-Request for RecommendDaemon consumption."
2. Alignment with FINAL_UPGRADE_3005.md
All existing sections of FINAL_UPGRADE_3005.md describe the current implemented state (Phases 0-2 from HANDOVER_CHAT.md). Our additions are:
FINAL_UPGRADE_3005 Section	Our Change	Alignment
Architecture Overview (Recommend System + RecommendDaemon)	Add standalone recommend_system D-Bus service vn.edu.uit.FSS.RecommendSystem	Extension — new service, existing architecture unchanged
Sound Design (Appendix, recommend_done: 550Hz→770Hz × 2)	MMM-FSS-Recommend self-contained sound will reuse the exact same frequency pattern	Direct reuse — matches spec exactly
Execution Checklist (Phase 2.6: MMM-FSS-VirtualKeyboard, 2.7: MMM-FSS-Recommend, 2.8: MMM-FSS-Notification)	Replace VirtualKeyboard with MMM-Keyboard from GitHub; MMM-FSS-Recommend gets own sound (decoupled from Notification module)	Deviation — VirtualKeyboard replaced, Recommend gets self-contained notification
DbDaemon D-Bus Methods (existing InsertRequest etc.)	Add new GetRequestList(recipe_name) method	Extension — new method, existing D-Bus interface unchanged
AGENTS.md (already has 6 new sections from FINAL_UPGRADE_3005)	Add new sections documenting Recommend System D-Bus, MMM-Keyboard, notification changes	Preservation — keep existing, append new
D-Bus Config (dbus_config/vn.edu.uit.FSS.conf)	Add policy for vn.edu.uit.FSS.RecommendSystem	Extension — new service policy, existing policies unchanged
3. Implementation Tasks (In Order)
Task A: format_result_for_ui() in RecommendEngine
- File: recommend_daemon/src/RecommendEngine.py
- Add method that transforms the internal Bù Trừ dict into UI-friendly format:
- Normalizes ingredient rows with status field (available/needed/missing)
- Adds summary field ("Còn thiếu X nguyên liệu!" / "Đã có đủ nguyên liệu!")
- Returns backward-compatible dict (keeps existing fields, adds ingredients[] flattened array)
- Called by _handle_generate_shopping_list() in main.py before returning
Task B: Wire RECOMMEND_LOADING in node_helper.js
- File: electron_app/magicmirror/modules/MMM-FSS-Recommend/node_helper.js
- Before writing SEARCH to Python bridge stdin, emit this.sendSocketNotification("RECOMMEND_LOADING", {})
- Frontend (MMM-FSS-Recommend.js:68) already handles this — just needs the backend send
Task C: Standalone Recommend System D-Bus Service
- New files in recommend_system/src/:
- dbus_service.py — Service vn.edu.uit.FSS.RecommendSystem, object path /vn/edu/uit/FSS/RecommendSystem
- Method ExtractAndPersistRecipe(recipe_name: str) -> str:
1. Calls RecipeAnalyzerEngine.generate_fss_request(recipe_name) (NLP)
2. Calls DbDaemon.InsertRequest(recipe_name, ingredients_json, batch_id) via D-Bus proxy
3. Returns JSON: {"status": "SUCCESS", "dish": str, "ingredients": [...], "batch_id": str}
- main.py — Entry point: lazy-loads engine, registers D-Bus, enters main loop
- D-Bus proxy pattern: Copy existing pattern from recommend_daemon/src/DbusInterface.py (sdbus async, thread with event loop)
Task D: GetRequestList D-Bus Method on DbDaemon
- File: db_daemon/src/DbDbusInterface.py
- Add to DbDaemonDbusObject:
@dbus_method_async('s', 's')
async def GetRequestList(self, recipe_name: str) -> str:
    # Queries FSS_Request.db via callback
    # Returns JSON array of matching requests
- Add callback setter set_requests_by_recipe_callback() in DbDbusInterface
- Add handler in DbDaemonMain.py that calls SqliteManager.get_requests_by_recipe()
- SqliteManager already has get_requests_by_recipe() — no change needed
Task E: Replace MMM-FSS-VirtualKeyboard with MMM-Keyboard
- Clone: git clone https://github.com/lavolp3/MMM-Keyboard.git into electron_app/magicmirror/modules/
- npm: cd MMM-Keyboard && npm install (depends on simple-keyboard)
- config.js: Replace MMM-FSS-VirtualKeyboard entry with:
{
    module: "MMM-Keyboard",
    position: "fullscreen_above",
    config: {
        startWithNumbers: false,
        startUppercase: false,
        debug: false
    }
}
- MMM-Keyboard protocol:
- Open: this.sendNotification("KEYBOARD", {key: "recommendSearch", style: "default", data: {}})
- Receive: Listen for KEYBOARD_INPUT with {key: "recommendSearch", message: "thịt kho, trứng chiên", data: {}}
Task F: Wire MMM-Keyboard → MMM-FSS-Recommend Input Flow
- File: MMM-FSS-Recommend.js
- Modify getDom(): Add "Tìm kiếm" button at top of module header
- Button click → this.sendNotification("KEYBOARD", {key: "recommendSearch", ...})
- Add handler in notificationReceived():
if (notification === "KEYBOARD_INPUT" && payload.key === "recommendSearch") {
    const recipes = payload.message.split(",").map(s => s.trim()).filter(s => s);
    this.loading = true;
    this.result = null;
    this.accumulatedResults = [];
    this.pendingCount = recipes.length;
    this.updateDom();
    recipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", {recipe: r}));
}
- Add handler in socketNotificationReceived():
if (notification === "RECOMMEND_RESULT") {
    this.accumulatedResults.push(payload);
    this.pendingCount--;
    if (this.pendingCount <= 0) {
        this.result = this.mergeResults(this.accumulatedResults);
        this.loading = false;
        this.updateDom();
        this.playNotificationSound("recommend_done");
    }
}
- Add mergeResults() method: Combines multiple recipe results into one composite display (merged ingredient lists, aggregated counts)
- File: node_helper.js — Add batch tracking (optional; frontend already tracks via pendingCount)
- File: py_bridge/recommend_dbus_listener.py — No changes needed; already handles individual SEARCH calls
Task G: Self-Contained Notification + Sound in MMM-FSS-Recommend
- File: MMM-FSS-Recommend.js
- Add Web Audio API sound functions (pattern from MMM-FSS-Notification.js:77-115):
initAudio() { /* resume AudioContext on user gesture */ }
playNotificationSound(type) {
    // Same 550Hz→770Hz × 2 beep from FINAL_UPGRADE_3005 Sound Design appendix
}
- Add inline toast notification:
showToast(message, type) {
    // Create <div class="fss-recommend-toast">, append to wrapper
    // Auto-dismiss after 3s via setTimeout
}
- File: MMM-FSS-Recommend.css — Add .fss-recommend-toast styles (similar to MMM-FSS-Notification card styles but in this module's namespace)
Task H: Update D-Bus Config
- File: dbus_config/vn.edu.uit.FSS.conf
- Add policy block for vn.edu.uit.FSS.RecommendSystem:
<policy context="default">
    <allow send_destination="vn.edu.uit.FSS.RecommendSystem"/>
    <allow receive_sender="vn.edu.uit.FSS.RecommendSystem"/>
</policy>
<policy user="fss">
    <allow own="vn.edu.uit.FSS.RecommendSystem"/>
    <allow send_destination="vn.edu.uit.FSS.RecommendSystem"/>
    <allow receive_sender="vn.edu.uit.FSS.RecommendSystem"/>
</policy>
Task I: Update AGENTS.md
Add new sections (keep all existing content):
- Recommend System D-Bus Service: Document service name, method, flow, files
- MMM-Keyboard Integration: Installation, notification protocol, config.js entry
- MMM-FSS-Recommend Self-Contained Notification: Sound design, inline toast, merge logic
Task J: Documentation Addition to FINAL_UPGRADE_3005.md
Append to FINAL_UPGRADE_3005.md (preserving all existing content):
- New subsection under Architecture: "Recommend System D-Bus Expansion"
- New checklist items in Execution Checklist for Phase 9
- Updated module table reflecting MMM-Keyboard replacement
4. Data Flow Diagram (Updated)
[MMM-Keyboard] --KEYBOARD_INPUT--> [MMM-FSS-Recommend.js]
    parse comma-separated: "thịt kho, trứng chiên"
    |
    v  (for each recipe, via socket)
[node_helper.js] --stdin--> [recommend_dbus_listener.py]
    |
    v  (calls D-Bus)
[RecommendDaemon.GenerateShoppingList()]
    |
    ├── [RecommendEngine._ensure_nlp_engine()] → load recommend_system NLP
    ├── [RecommendEngine.generate_shopping_list()]
    │       ├── NLP extraction (dict return)
    │       ├── Inventory query via DbDaemon.GetInventory() D-Bus
    │       ├── Bù Trừ comparison (dict return)
    │       └── Optional .db persistence
    └── [format_result_for_ui()] → UI-friendly dict
    |
    v  (JSON string via D-Bus return)
[recommend_dbus_listener.py] --stdout--> [node_helper.js]
    |
    v  (socket notification)
[MMM-FSS-Recommend.js]
    ├── mergeResults() for multi-recipe
    ├── showToast() + playNotificationSound()
    └── updateDom()
Alternative path (standalone Recommend System D-Bus):
[Any D-Bus client]
    |
    v
[RecommendSystem.ExtractAndPersistRecipe()] (new service)
    ├── NLP extraction (RecipeAnalyzerEngine)
    ├── calls DbDaemon.InsertRequest() via D-Bus proxy
    └── returns dict as JSON
5. Files Changed/New
File	Action  Task
recommend_daemon/src/RecommendEngine.py	Edit: add format_result_for_ui()  A  
electron_app/.../MMM-FSS-Recommend/node_helper.js	Edit: emit RECOMMEND_LOADING    B
recommend_system/src/dbus_service.py	New C
recommend_system/src/main.py	New C
db_daemon/src/DbDbusInterface.py	Edit: add GetRequestList method + callback  D
db_daemon/src/DbDaemonMain.py	Edit: add handler for GetRequestList    D
electron_app/magicmirror/config/config.js	Edit: replace VirtualKeyboard with MMM-Keyboard E
electron_app/.../MMM-FSS-Recommend/MMM-FSS-Recommend.js	Edit: add KEYBOARD_INPUT handler, mergeResults, sound, toast    F,G
electron_app/.../MMM-FSS-Recommend/MMM-FSS-Recommend.css	Edit: add toast styles  G
dbus_config/vn.edu.uit.FSS.conf	Edit: add RecommendSystem policy  H
AGENTS.md	Edit: append new sections   I
FINAL_UPGRADE_3005.md	Edit: append Phase 9 section    J
(new module) electron_app/magicmirror/modules/MMM-Keyboard/	New (git clone https://github.com/lavolp3/MMM-Keyboard.git) E 
6. Backward Compatibility
- format_result_for_ui() is additive — the existing return format from generate_shopping_list() is unchanged; format_result_for_ui() is called as a post-processing step
- Existing Python bridge recommend_dbus_listener.py needs no changes — it already handles individual SEARCH calls
- MMM-FSS-Recommend still handles RECIPE_SEARCH notification (for backward compat with any other module that might send it)
- The new D-Bus service vn.edu.uit.FSS.RecommendSystem is additive — doesn't conflict with existing services
- MMM-FSS-VirtualKeyboard can be left in place (not deleted) — just removed from config.js

---

## 7. Implementation Status (01/06/2026)

All Tasks A-J from the Updated Implementation Plan have been implemented:

| Task | Status | Key Changes |
|------|--------|-------------|
| **A** | ✅ Done | `format_result_for_ui()` in RecommendEngine.py — transforms Bù Trừ dict into UI-friendly format with `ingredients[]` array + `summary` field |
| **B** | ✅ Done | `RECOMMEND_LOADING` emitted from node_helper.js before each SEARCH write to Python bridge stdin |
| **C** | ✅ Done | New `recommend_system/src/dbus_service.py` + `main.py` — standalone D-Bus service `vn.edu.uit.FSS.RecommendSystem` with `ExtractAndPersistRecipe` method |
| **D** | ✅ Done | `GetRequestList(recipe_name)` D-Bus method added to DbDaemon — queries via SqliteManager.get_requests_by_recipe() |
| **E** | ✅ Done | `config.js`: replaced MMM-FSS-VirtualKeyboard with [MMM-Keyboard](https://github.com/lavolp3/MMM-Keyboard) at `fullscreen_above` position |
| **F** | ✅ Done | MMM-FSS-Recommend.js: "Tìm kiếm" button → `sendNotification("KEYBOARD", ...)` → `KEYBOARD_INPUT` handler → comma-split multi-recipe → `mergeResults()` |
| **G** | ✅ Done | Self-contained Web Audio sound (`recommend_done`: 550Hz→770Hz × 2) in MMM-FSS-Recommend.js |
| **H** | ✅ Done | D-Bus config updated with `vn.edu.uit.FSS.RecommendSystem` policies for richardmelvin52, root, and default contexts |
| **I** | ✅ Done | AGENTS.md: 3 new sections — Recommend System D-Bus, MMM-Keyboard Integration, MMM-FSS-Recommend Notification |
| **J** | ✅ Done | This section appended to FINAL_UPGRADE_3005.md |

### Files Changed / Created
| File | Action | Task |
|------|--------|------|
| `recommend_daemon/src/RecommendEngine.py` | Edit: add `format_result_for_ui()` | A |
| `recommend_daemon/src/main.py` | Edit: call `format_result_for_ui()` before returning | A |
| `electron_app/.../MMM-FSS-Recommend/node_helper.js` | Edit: emit `RECOMMEND_LOADING` | B |
| `recommend_system/src/dbus_service.py` | **New** | C |
| `recommend_system/src/main.py` | **New** | C |
| `db_daemon/src/DbDbusInterface.py` | Edit: add `GetRequestList` + callback | D |
| `db_daemon/src/DbDaemonMain.py` | Edit: add `_handle_get_requests_by_recipe()` | D |
| `dbus_config/vn.edu.uit.FSS.conf` | Edit: add `RecommendSystem` policy | H |
| `electron_app/magicmirror/config/config.js` | Edit: replace VirtualKeyboard with MMM-Keyboard | E |
| `electron_app/.../MMM-FSS-Recommend/MMM-FSS-Recommend.js` | Edit: KEYBOARD_INPUT, mergeResults, sounds | F,G |
| `electron_app/.../MMM-FSS-Recommend/MMM-FSS-Recommend.css` | Edit: search button styles | F,G |
| `AGENTS.md` | Edit: append 3 new sections | I |
| `FINAL_UPGRADE_3005.md` | Edit: append this status section | J |

### Execution Checklist (Updated)
- [x] Task A: `format_result_for_ui()` in RecommendEngine
- [x] Task B: `RECOMMEND_LOADING` in node_helper.js
- [x] Task C: Standalone Recommend System D-Bus Service
- [x] Task D: `GetRequestList` D-Bus method on DbDaemon
- [x] Task E: Replace VirtualKeyboard with MMM-Keyboard in config.js
- [x] Task F: Wire MMM-Keyboard → MMM-FSS-Recommend input flow
- [x] Task G: Self-contained notification + sound in MMM-FSS-Recommend
- [x] Task H: Update D-Bus config for RecommendSystem
- [x] Task I: Update AGENTS.md with new sections
- [x] Task J: Documentation addition to FINAL_UPGRADE_3005.md


*End of FINAL_UPGRADE_3005.md*
