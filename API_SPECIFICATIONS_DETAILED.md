# FSS API Specifications - Detailed Design Document

## Source: FSS_SoftwareDetailedDesign_v1.1.0.xlsx
**Package:** SensorDaemon

---

## 1. SensorDaemonMain

### Overview
Main application class that orchestrates the entire sensor daemon system. Manages initialization, lifecycle, main event loop, and coordination between InputProcessor and OutputProcessor.

### Private Member Variables

| Variable Name | Type | Purpose |
|---|---|---|
| `current_state` | `str` | Trạng thái hiện tại của daemon (INIT, IDLE, ERROR). |
| `is_running` | `bool` | Cờ duy trì vòng lặp tiến trình chính. |
| `loop_interval_ms` | `int` | Thời gian trễ (sleep) giữa các chu kỳ lặp để tránh chiếm dụng 100% tài nguyên CPU. |
| `polling_rate_env_ms` | `int` | Tần suất đọc nhiệt độ/độ ẩm (VD: 5000 ms). |
| `polling_rate_dist_ms` | `int` | Tần suất đo khoảng cách (VD: 500 ms). |
| `input_processor` | `InputProcessor` | Object gói gọn toàn bộ logic thu thập dữ liệu cảm biến. |
| `output_processor` | `OutputProcessor` | Object gói gọn toàn bộ logic xuất tín hiệu ra IPC. |
| `watchdog` | `SystemdWatchdog` | Object báo cáo sinh tồn cho hệ điều hành OS. |

### Public Methods

#### 1. `init_app()`
- **Signature:** `init_app()`
- **Return Type:** `bool`
- **Description:** Khởi tạo Processor, Handler và nạp cấu hình.
- **Purpose:** Initialize all components, load configuration, and prepare system for startup

#### 2. `start_app()`
- **Signature:** `start_app()`
- **Return Type:** `bool`
- **Description:** Đưa hệ thống vào trạng thái IDLE và kích hoạt vòng lặp chính.
- **Purpose:** Transition system to IDLE state and activate main event loop

#### 3. `stop_app()`
- **Signature:** `stop_app()`
- **Return Type:** `void`
- **Description:** Dọn dẹp tài nguyên và tắt tiến trình an toàn.
- **Purpose:** Gracefully shutdown all resources and terminate the process

#### 4. `run_main_loop()`
- **Signature:** `run_main_loop()`
- **Return Type:** `void`
- **Description:** Vòng lặp chính, điều phối input_processor và output_processor.
- **Purpose:** Main event loop that orchestrates InputProcessor and OutputProcessor execution

#### 5. `recover_from_fault()`
- **Signature:** `recover_from_fault()`
- **Return Type:** `bool`
- **Description:** [XỬ LÝ LỖI] Cố gắng khôi phục hệ thống nếu có ngoại lệ.
- **Purpose:** Error handling - attempt system recovery from faults/exceptions

#### 6. `log_system_status()`
- **Signature:** `log_system_status()`
- **Return Type:** `void`
- **Description:** [DEBUG] Ghi log file lưu trạng thái RAM/CPU của Daemon.
- **Purpose:** Debug utility - log current RAM/CPU status to file

#### 7. `process_environment_data()`
- **Signature:** `process_environment_data()`
- **Return Type:** `void`
- **Description:** Gọi đọc I2C và phát D-Bus/ZMQ theo định kỳ.
- **Purpose:** Periodic processing of environment sensor data, read I2C and broadcast via D-Bus/ZMQ

---

## 2. InputProcessor

### Overview
Manages all sensor data acquisition. Contains driver instances for SHT3x (environment), VL53L0x (distance), and Door sensor. Handles I2C communication and GPIO operations.

### Private Member Variables

| Variable Name | Type | Purpose |
|---|---|---|
| `m_i2c_main` | `shared_ptr` | Con trỏ quản lý bus I2C chính (/dev/i2c-1). |
| `m_i2c_ext` | `shared_ptr` | Con trỏ quản lý bus I2C phụ (VD: /dev/i2c-6). |
| `m_gpio_handler` | `shared_ptr` | Con trỏ quản lý chip GPIO (VD: gpiochip4). |
| `sht3x` | `unique_ptr<Sht3xDriver>` | Đối tượng điều khiển cảm biến môi trường. |
| `vl53l0x` | `unique_ptr<Vl53l0xDriver>` | Đối tượng điều khiển cảm biến khoảng cách. |
| `door_sensor` | `unique_ptr<DoorSensorDriver>` | Đối tượng điều khiển cảm biến cửa. |
| `last_poll_timestamp` | `float` | Lưu trữ Unix timestamp chính xác tại thời điểm gọi lệnh quét cảm biến để đồng bộ. |

### Public Methods

#### 1. `init_sensors()`
- **Signature:** `init_sensors()`
- **Return Type:** `bool`
- **Description:** Gọi lệnh khởi tạo đồng loạt cho cả 3 sensor.
- **Purpose:** Initialize all three sensors (SHT3x, VL53L0x, Door sensor) simultaneously

#### 2. `poll_all_data()`
- **Signature:** `poll_all_data()`
- **Return Type:** `map<string, float>`
- **Description:** Đóng gói dữ liệu từ các Driver thành Dictionary (Map) kèm nhãn thời gian.
- **Purpose:** Aggregate data from all drivers into a structured map with timestamp

#### 3. `get_env_data()`
- **Signature:** `get_env_data(temp: float&, hum: float&)`
- **Return Type:** `void`
- **Parameters:** 
  - `temp: float&` - Reference to temperature variable
  - `hum: float&` - Reference to humidity variable
- **Description:** Hàm lấy riêng giá trị nhiệt độ và độ ẩm hiện tại.
- **Purpose:** Retrieve current temperature and humidity values (output parameters)

#### 4. `get_distance_data()`
- **Signature:** `get_distance_data()`
- **Return Type:** `uint16_t`
- **Description:** Hàm lấy riêng giá trị khoảng cách giá trị thô.
- **Purpose:** Get raw distance value from VL53L0x sensor

#### 5. `get_door_status()`
- **Signature:** `get_door_status()`
- **Return Type:** `bool`
- **Description:** Hàm kiểm tra trạng thái cửa (true = open).
- **Purpose:** Check current door state (true indicates open, false indicates closed)

---

## 3. OutputProcessor

### Overview
Handles all inter-process communication and signal broadcasting. Uses D-Bus to emit sensor data updates and system events to other components (DBDaemon, UI).

### Private Member Variables

| Variable Name | Type | Purpose |
|---|---|---|
| `sdbus_interface` | `SensorDbusInterface` | Đối tượng quản lý kết nối D-Bus. |

### Public Methods

#### 1. `init_ipc()`
- **Signature:** `init_ipc()`
- **Return Type:** `bool`
- **Description:** Khởi tạo các kênh truyền thông liên tiến trình.
- **Purpose:** Initialize inter-process communication channels (D-Bus connections)

#### 2. `broadcast_env_data()`
- **Signature:** `broadcast_env_data(temp: float, hum: float)`
- **Return Type:** `void`
- **Parameters:**
  - `temp: float` - Temperature value in Celsius
  - `hum: float` - Humidity value in percentage
- **Description:** Phát tín hiệu dữ liệu môi trường.
- **Purpose:** Broadcast environment sensor data (temperature and humidity) via D-Bus

#### 3. `broadcast_distance_data()`
- **Signature:** `broadcast_distance_data(distance: uint16_t)`
- **Return Type:** `void`
- **Parameters:**
  - `distance: uint16_t` - Distance measurement value
- **Description:** Phát tín hiệu dữ liệu khoảng cách đo được.
- **Purpose:** Broadcast distance sensor data via D-Bus

#### 4. `broadcast_door_status()`
- **Signature:** `broadcast_door_status(is_open: bool)`
- **Return Type:** `void`
- **Parameters:**
  - `is_open: bool` - Door status (true = open, false = closed)
- **Description:** Phát tín hiệu đóng/mở cửa hiện tại.
- **Purpose:** Broadcast door state changes via D-Bus

#### 5. `broadcast_system_events()`
- **Signature:** `broadcast_system_events(data: map)`
- **Return Type:** `void`
- **Parameters:**
  - `data: map` - Map of system event data
- **Description:** Phân tích Map data từ InputProcessor và kích hoạt các hàm emit tương ứng.
- **Purpose:** Analyze system event map and trigger appropriate signal emissions

---

## 4. SensorDbusInterface (SdbusInterface)

### Overview
Manages D-Bus system bus connection for the SensorDaemon. Handles signal emission, error recovery, and bus lifecycle management.

### Private Member Variables

| Variable Name | Type | Purpose |
|---|---|---|
| `system_bus` | `object` | Kết nối System D-Bus nội bộ của Linux. |
| `interface_name` | `str` | Tên Interface (VD: vn.edu.uit.FSS.Sensor). |
| `is_connected` | `bool` | Cờ trạng thái kết nối Bus. |
| `dropped_messages_count` | `int` | Số tin nhắn gửi thất bại do lỗi mạng D-Bus. |

### Public Methods

#### 1. `init_interface()`
- **Signature:** `init_interface()`
- **Return Type:** `bool`
- **Description:** Mở kết nối socket lên D-Bus.
- **Purpose:** Initialize and establish connection to system D-Bus

#### 2. `emit_env_signal()`
- **Signature:** `emit_env_signal(data_map: map)`
- **Return Type:** `void`
- **Parameters:**
  - `data_map: map` - Map containing environment data
- **Description:** Phát JSON tín hiệu EnvDataUpdated.
- **Purpose:** Emit EnvDataUpdated signal with environment data as JSON

#### 3. `emit_door_signal()`
- **Signature:** `emit_door_signal(state: str)`
- **Return Type:** `void`
- **Parameters:**
  - `state: str` - Door state string ("OPEN" or "CLOSED")
- **Description:** Phát tín hiệu DoorStateChanged.
- **Purpose:** Emit DoorStateChanged signal with current door state

#### 4. `emit_presence_signal()`
- **Signature:** `emit_presence_signal(user: bool)`
- **Return Type:** `void`
- **Parameters:**
  - `user: bool` - User presence status (true = present, false = absent)
- **Description:** Phát tín hiệu UserPresenceDetected.
- **Purpose:** Emit UserPresenceDetected signal indicating user presence

#### 5. `reconnect_bus()`
- **Signature:** `reconnect_bus()`
- **Return Type:** `bool`
- **Description:** [XỬ LÝ LỖI] Khôi phục kết nối IPC nếu dbus-daemon bị khởi động lại.
- **Purpose:** Error handling - recover D-Bus connection if daemon restarts

#### 6. `log_bus_error()`
- **Signature:** `log_bus_error(error_msg: str)`
- **Return Type:** `void`
- **Parameters:**
  - `error_msg: str` - Error message to log
- **Description:** [DEBUG] Ghi nhận các lỗi truyền tải tín hiệu D-Bus.
- **Purpose:** Debug logging for D-Bus signal transmission errors

---

## 5. SystemWatchdog

### Overview
Manages systemd watchdog functionality to report daemon health status to the OS. Sends periodic "heartbeat" signals to prevent process termination.

### Private Member Variables

| Variable Name | Type | Purpose |
|---|---|---|
| `interval_ms` | `int` | Chu kỳ gửi tín hiệu sống lên OS. |
| `last_ping_ts` | `float` | Thời điểm ping gần nhất. |

### Public Methods

#### 1. `init_driver()`
- **Signature:** `init_driver()`
- **Return Type:** `bool`
- **Description:** Khởi tạo thư viện sdnotify.
- **Purpose:** Initialize systemd notification library

#### 2. `ping()`
- **Signature:** `ping()`
- **Return Type:** `void`
- **Description:** Báo cáo WATCHDOG=1.
- **Purpose:** Send WATCHDOG=1 heartbeat signal to systemd

#### 3. `notify_ready()`
- **Signature:** `notify_ready()`
- **Return Type:** `void`
- **Description:** Báo cáo READY=1.
- **Purpose:** Notify systemd that daemon is ready (READY=1)

#### 4. `notify_stopping()`
- **Signature:** `notify_stopping()`
- **Return Type:** `void`
- **Description:** Báo cáo STOPPING=1 trước khi tắt.
- **Purpose:** Notify systemd that daemon is stopping (STOPPING=1)

#### 5. `report_error_status()`
- **Signature:** `report_error_status(err: str)`
- **Return Type:** `void`
- **Parameters:**
  - `err: str` - Error message/status description
- **Description:** [DEBUG/LỖI] Đẩy lỗi trực tiếp vào log của Systemctl status.
- **Purpose:** Report error status directly to systemd status output

---

## Key Requirements and Constraints

### SensorDaemonMain
- Must maintain state machine: INIT → IDLE → RUNNING → ERROR/STOPPED
- `loop_interval_ms` should prevent 100% CPU usage
- Must properly coordinate InputProcessor and OutputProcessor timing
- `recover_from_fault()` must handle unexpected exceptions gracefully

### InputProcessor
- `last_poll_timestamp` must be set synchronously with `poll_all_data()` call
- All three sensors must be initialized before daemon enters IDLE state
- Reference parameters (`temp&, hum&`) must be properly handled for `get_env_data()`
- Distance data returned as raw value from sensor (not converted to meters at this level)

### OutputProcessor
- All broadcast methods must handle D-Bus connection failures
- `broadcast_system_events()` must parse map structure and call appropriate emit methods
- Error recovery should be attempted via `sdbus_interface.reconnect_bus()`

### SensorDbusInterface (SdbusInterface)
- Interface name should follow pattern: `vn.edu.uit.FSS.Sensor`
- Must track dropped messages count for debugging
- `reconnect_bus()` should implement exponential backoff for retry logic
- All signal emissions should include timestamp

### SystemWatchdog
- `interval_ms` should match systemd WatchdogSec configuration
- `ping()` must be called before interval_ms timeout
- Must use sdnotify library for OS communication
- Error reporting should not block main event loop

---

## Data Flow Notes

1. **Sensor Data Path:**
   InputProcessor.poll_all_data() → map of sensor values → OutputProcessor.broadcast_*() → D-Bus signals

2. **Error Reporting:**
   Any component error → SensorDaemonMain.recover_from_fault() → SystemWatchdog.report_error_status()

3. **Initialization Sequence:**
   init_app() → InputProcessor.init_sensors() → OutputProcessor.init_ipc() → SystemWatchdog.init_driver() → start_app()

---

## Implementation Notes

- All classes should handle D-Bus connection failures gracefully
- Sensor polling should respect timing intervals to avoid race conditions
- State transitions must be atomic and thread-safe where applicable
- All error conditions should be logged before recovery attempts
