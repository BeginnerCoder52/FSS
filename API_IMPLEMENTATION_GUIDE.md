# API Specifications - Structured Implementation Format

## Class: SensorDaemonMain

### Private Member Variables
```
current_state: str
├── Purpose: Trạng thái hiện tại của daemon (INIT, IDLE, ERROR)
├── Initial Value: "INIT"
└── Valid States: ["INIT", "IDLE", "ERROR"]

is_running: bool
├── Purpose: Cờ duy trì vòng lặp tiến trình chính
├── Initial Value: false
└── Updated By: start_app(), stop_app()

loop_interval_ms: int
├── Purpose: Thời gian trễ (sleep) giữa các chu kỳ lặp để tránh chiếm dụng 100% tài nguyên CPU
├── Default Value: ~100-500 ms (depends on configuration)
└── Constraint: Must be > 0

polling_rate_env_ms: int
├── Purpose: Tần suất đọc nhiệt độ/độ ẩm (VD: 5000 ms)
├── Default Value: 5000
└── Constraint: Must be > 0

polling_rate_dist_ms: int
├── Purpose: Tần suất đo khoảng cách (VD: 500 ms)
├── Default Value: 500
└── Constraint: Must be > 0

input_processor: InputProcessor
├── Purpose: Object gói gọn toàn bộ logic thu thập dữ liệu cảm biến
├── Lifecycle: Created in init_app(), destroyed in stop_app()
└── Lifetime: Entire daemon lifetime

output_processor: OutputProcessor
├── Purpose: Object gói gọn toàn bộ logic xuất tín hiệu ra IPC
├── Lifecycle: Created in init_app(), destroyed in stop_app()
└── Lifetime: Entire daemon lifetime

watchdog: SystemdWatchdog
├── Purpose: Object báo cáo sinh tồn cho hệ điều hành OS
├── Lifecycle: Created in init_app(), destroyed in stop_app()
└── Lifetime: Entire daemon lifetime
```

### Public Methods

#### Method 1: init_app()
```
Signature: bool init_app()
Return Type: bool
Parameters: None

Pseudocode:
  1. Initialize SystemWatchdog
     - Call watchdog.init_driver()
     - If failed: return false

  2. Initialize InputProcessor
     - Create input_processor instance
     - Call input_processor.init_sensors()
     - If failed: return false

  3. Initialize OutputProcessor
     - Create output_processor instance
     - Call output_processor.init_ipc()
     - If failed: return false

  4. Load configuration (polling rates, etc.)
     - Set polling_rate_env_ms from config
     - Set polling_rate_dist_ms from config
     - Set loop_interval_ms from config

  5. State management
     - Set current_state = "IDLE"
     - Return true

Error Cases:
  - Watchdog initialization fails
  - InputProcessor.init_sensors() fails
  - OutputProcessor.init_ipc() fails
  - Configuration file not found/invalid

Success Condition: All components initialized, current_state == "IDLE"
```

#### Method 2: start_app()
```
Signature: bool start_app()
Return Type: bool
Parameters: None

Pseudocode:
  1. Pre-flight checks
     - Verify current_state == "IDLE"
     - Verify input_processor != nullptr
     - Verify output_processor != nullptr
     - If any check fails: return false

  2. Enable main loop flag
     - Set is_running = true

  3. Notify systemd
     - Call watchdog.notify_ready()

  4. Enter main loop
     - Call run_main_loop()

  5. Post-loop cleanup
     - Set is_running = false
     - Return true

Error Cases:
  - current_state != "IDLE"
  - Null pointer dereference
  - watchdog.notify_ready() fails

Success Condition: run_main_loop() executes with is_running == true
```

#### Method 3: stop_app()
```
Signature: void stop_app()
Return Type: void
Parameters: None

Pseudocode:
  1. Signal stopping
     - Set is_running = false
     - Call watchdog.notify_stopping()

  2. Shutdown output processor
     - If output_processor != nullptr:
       - Gracefully close D-Bus connections

  3. Shutdown input processor
     - If input_processor != nullptr:
       - Release I2C/GPIO resources
       - Close all sensor connections

  4. Shutdown watchdog
     - If watchdog != nullptr:
       - Cleanup sdnotify

  5. Final state
     - Set current_state = "STOPPED"

Exception Handling: All cleanup should proceed even if individual components fail
```

#### Method 4: run_main_loop()
```
Signature: void run_main_loop()
Return Type: void
Parameters: None

Pseudocode:
  WHILE is_running == true:
    1. Watchdog check
       - Check if (current_time - last_watchdog_time) > watchdog.interval_ms
       - If yes: Call watchdog.ping()

    2. Input acquisition (periodically)
       - If time_since_last_env_poll >= polling_rate_env_ms:
         - Call input_processor.poll_all_data()
         - Update last_poll_timestamp
         - Extract temp, humidity, distance, door_status

       - If time_since_last_dist_poll >= polling_rate_dist_ms:
         - Call input_processor.get_distance_data()

    3. Output broadcasting
       - Call output_processor.broadcast_env_data(temp, humidity)
       - Call output_processor.broadcast_distance_data(distance)
       - Call output_processor.broadcast_door_status(door_status)

    4. System event processing
       - Call output_processor.broadcast_system_events(sensor_map)

    5. Rate limiting
       - Sleep for loop_interval_ms

    6. Error handling
       - If any step raises exception:
         - Call recover_from_fault()
         - Update current_state = "ERROR"
         - Attempt recovery

Timing Guarantees:
  - Watchdog heartbeat: Every watchdog.interval_ms
  - Environment polling: Every polling_rate_env_ms
  - Distance polling: Every polling_rate_dist_ms
  - Loop iteration: Every loop_interval_ms
```

#### Method 5: recover_from_fault()
```
Signature: bool recover_from_fault()
Return Type: bool
Parameters: None

Pseudocode:
  1. Log error
     - Write current error to log file
     - Increment error_count

  2. Report to systemd
     - Call watchdog.report_error_status("Recovery in progress")

  3. Attempt recovery steps
     - Try: Reconnect D-Bus
       - Call output_processor.sdbus_interface.reconnect_bus()
     
     - Try: Reinitialize failed sensors
       - If sensor_x failed:
         - Call input_processor.init_sensors()

     - Try: Reset state machine
       - Set current_state = "IDLE"

  4. Validation
     - Run basic connectivity checks
     - If all checks pass:
       - Set current_state = "IDLE"
       - Return true
     - Else:
       - Set current_state = "ERROR"
       - Return false

Max Recovery Attempts: 3 (before giving up)
Backoff Strategy: Exponential (1s, 2s, 4s)
```

#### Method 6: log_system_status()
```
Signature: void log_system_status()
Return Type: void
Parameters: None

Pseudocode:
  1. Collect system metrics
     - Get current RAM usage (bytes)
     - Get CPU usage percentage
     - Get process uptime (seconds)
     - Count errors occurred

  2. Format log entry
     - Timestamp: ISO 8601
     - Format: "{timestamp} | state={state} | ram={ram_mb}MB | cpu={cpu_pct}% | uptime={uptime}s | errors={error_count}"

  3. Write to log file
     - Path: /var/log/sensor_daemon.log (or /opt/fss/logs/daemon.log)
     - Mode: APPEND

Frequency: Called every 60 seconds (or configurable)
Log Rotation: Handle file size limits (max 10MB before rotation)
```

#### Method 7: process_environment_data()
```
Signature: void process_environment_data()
Return Type: void
Parameters: None

Pseudocode:
  1. Read from input processor
     - Call input_processor.poll_all_data()
     - Extract: temperature, humidity, distance, door_status

  2. Prepare broadcast data
     - Package data with timestamp: {"temp": T, "hum": H, "dist": D, "door": S, "ts": TS}

  3. Emit D-Bus signals
     - Call output_processor.broadcast_env_data(T, H)
     - Call output_processor.broadcast_distance_data(D)
     - Call output_processor.broadcast_door_status(S)

  4. Alternative: Emit consolidated event
     - Call output_processor.broadcast_system_events(data_map)

Frequency: Determined by polling_rate_env_ms
Error Handling: Log failed emissions, don't abort loop
```

---

## Class: InputProcessor

### Private Member Variables
```
m_i2c_main: std::shared_ptr<I2cHandler>
├── Purpose: Con trỏ quản lý bus I2C chính (/dev/i2c-1)
├── Default Device: /dev/i2c-1
├── Baud Rate: 100 kHz (standard I2C)
└── Lifetime: From init_sensors() to daemon shutdown

m_i2c_ext: std::shared_ptr<I2cHandler>
├── Purpose: Con trỏ quản lý bus I2C phụ (VD: /dev/i2c-6)
├── Default Device: /dev/i2c-6 (or configurable)
├── Baud Rate: 100 kHz (standard I2C)
└── Optional: May not be used if only single I2C bus available

m_gpio_handler: std::shared_ptr<GpioHandler>
├── Purpose: Con trỏ quản lý chip GPIO (VD: gpiochip4)
├── Default Chip: gpiochip4 (Raspberry Pi GPIO)
├── Library: libgpiod
└── Lifetime: From init_sensors() to daemon shutdown

sht3x: std::unique_ptr<Sht3xDriver>
├── Purpose: Đối tượng điều khiển cảm biến môi trường
├── I2C Address: 0x44 (or 0x45 depending on pin config)
├── I2C Bus: m_i2c_main
├── Measurement Range: Temp [-40°C to +125°C], Humidity [0% to 100%]
└── Polling Strategy: Single-shot or continuous mode

vl53l0x: std::unique_ptr<Vl53l0xDriver>
├── Purpose: Đối tượng điều khiển cảm biến khoảng cách
├── I2C Address: 0x29
├── I2C Bus: m_i2c_main
├── Measurement Range: 0-2000 mm (outdoor 0-400 mm)
├── Output Unit: meters (converted in driver)
└── Polling Strategy: Single measurement or continuous

door_sensor: std::unique_ptr<DoorSensorDriver>
├── Purpose: Đối tượng điều khiển cảm biến cửa
├── GPIO Chip: gpiochip4
├── GPIO Pin: Configurable (e.g., pin 27)
├── Sensor Type: Reed Switch (magnetic contact)
└── Debounce Time: ~20ms (hardware + software)

last_poll_timestamp: float
├── Purpose: Lưu trữ Unix timestamp chính xác tại thời điểm gọi lệnh quét cảm biến để đồng bộ
├── Type: UNIX timestamp (seconds since epoch, with millisecond precision)
├── Updated By: poll_all_data() method
└── Used For: Data synchronization across components
```

### Public Methods

#### Method 1: init_sensors()
```
Signature: bool init_sensors()
Return Type: bool
Parameters: None

Pseudocode:
  1. Initialize I2C buses
     - Create m_i2c_main (device: /dev/i2c-1)
       - If fails: log error, return false
     - Create m_i2c_ext (device: /dev/i2c-6) - optional
       - If fails: log warning, continue (not critical)

  2. Initialize GPIO handler
     - Create m_gpio_handler (chip: gpiochip4)
       - Request GPIO lines for door sensor
       - If fails: log error, return false

  3. Initialize SHT3x driver
     - Create sht3x driver instance
     - Inject I2C bus reference (m_i2c_main)
     - Call sht3x.init_driver()
       - If fails: log error, return false
     - Set polling rate from config

  4. Initialize VL53L0x driver
     - Create vl53l0x driver instance
     - Inject I2C bus reference (m_i2c_main)
     - Call vl53l0x.init_driver()
       - If fails: log error, return false
     - Set threshold distance from config

  5. Initialize Door sensor driver
     - Create door_sensor driver instance
     - Inject GPIO handler reference
     - Call door_sensor.init_driver()
       - If fails: log error, return false
     - Configure debounce time

  6. Verify all sensors
     - For each sensor: call sensor.check_connection()
     - If connection check fails: log warning (may recover later)

  7. Success
     - Return true

Initialization Order:
  1. I2C buses (all sensors depend on this)
  2. GPIO handler (door sensor depends on this)
  3. Individual sensor drivers

Error Recovery:
  - If any critical initialization fails: return false
  - Non-critical failures (like secondary I2C bus) logged as warnings
  - Calling code (SensorDaemonMain.init_app) should handle false return
```

#### Method 2: poll_all_data()
```
Signature: std::map<std::string, float> poll_all_data()
Return Type: std::map<std::string, float>
Parameters: None

Pseudocode:
  1. Update timestamp
     - Set last_poll_timestamp = current_unix_timestamp()
     - This timestamp will be synced across all components

  2. Read SHT3x (Environment)
     - temp, humidity = sht3x.read_data()
     - If error: temp = -999.0, humidity = -999.0
     - Log error but continue

  3. Read VL53L0x (Distance)
     - distance = vl53l0x.read_distance_meters()
     - If error: distance = -1.0
     - Log error but continue

  4. Read Door Sensor
     - door_state = door_sensor.read_state()
     - Convert to numeric: 1.0 if open, 0.0 if closed

  5. Package results
     - Create map:
     {
       "temperature": temp,
       "humidity": humidity,
       "distance": distance,
       "door_status": door_state,
       "timestamp": last_poll_timestamp,
       "sensor_quality": quality_flags
     }

  6. Return map
     - Return packed map

Map Keys and Types:
  "temperature"    : float (-999.0 on error)
  "humidity"       : float (-999.0 on error)
  "distance"       : float (-1.0 on error, in meters)
  "door_status"    : float (1.0 = open, 0.0 = closed)
  "timestamp"      : float (UNIX timestamp)
  "sensor_quality" : float (bitmask: bit0=temp_ok, bit1=humidity_ok, bit2=distance_ok, bit3=door_ok)
```

#### Method 3: get_env_data()
```
Signature: void get_env_data(float& temp, float& hum)
Return Type: void
Parameters:
  - temp: float& (reference to temperature output variable)
  - hum: float& (reference to humidity output variable)

Pseudocode:
  1. Read from SHT3x
     - Call sht3x.get_temperature()
     - Call sht3x.get_humidity()

  2. Assign output parameters
     - temp = sht3x.get_temperature()
     - hum = sht3x.get_humidity()

  3. Error handling
     - If sht3x not initialized: temp = 0.0, hum = 0.0
     - If read failed: temp = -999.0, hum = -999.0

Note: This method returns cached values, not fresh reads
      For fresh reads, call poll_all_data() first
```

#### Method 4: get_distance_data()
```
Signature: uint16_t get_distance_data()
Return Type: uint16_t
Parameters: None

Pseudocode:
  1. Read from VL53L0x
     - Call vl53l0x.read_distance_raw()

  2. Return value
     - If error: return 0xFFFF (65535, max uint16_t)
     - Else: return raw distance value in mm

Range: 0-2000 mm (0-2 meters)
Note: Returns raw value, NOT converted to meters
      Conversion to meters happens in OutputProcessor
```

#### Method 5: get_door_status()
```
Signature: bool get_door_status()
Return Type: bool
Parameters: None

Pseudocode:
  1. Read from door sensor
     - Call door_sensor.read_state()

  2. Parse result
     - If door_sensor.current_state == "OPEN":
       - Return true
     - Else if door_sensor.current_state == "CLOSED":
       - Return false
     - Else:
       - Log error
       - Return false (default to closed)

  3. Return value
     - true: Door is open
     - false: Door is closed
```

---

## Class: OutputProcessor

### Private Member Variables
```
sdbus_interface: SensorDbusInterface
├── Purpose: Đối tượng quản lý kết nối D-Bus
├── Ownership: Unique ownership (managed by OutputProcessor)
├── Lifetime: From init_ipc() to daemon shutdown
└── Initialization: Lazy initialization in init_ipc()
```

### Public Methods

#### Method 1: init_ipc()
```
Signature: bool init_ipc()
Return Type: bool
Parameters: None

Pseudocode:
  1. Create D-Bus interface
     - Create sdbus_interface instance

  2. Initialize D-Bus connection
     - Call sdbus_interface.init_interface()
     - If fails: log error, return false

  3. Verify connection
     - Check if sdbus_interface.is_connected == true
     - If fails: log error, return false

  4. Setup signal handlers
     - Prepare to emit: EnvDataUpdated, DoorStateChanged, UserPresenceDetected

  5. Success
     - Return true

Error Handling:
  - If D-Bus system not available: return false
  - If service name already registered: return false
  - Retry logic: Auto-reconnect will be handled in broadcast methods
```

#### Method 2: broadcast_env_data()
```
Signature: void broadcast_env_data(float temp, float hum)
Return Type: void
Parameters:
  - temp: float (Temperature in Celsius)
  - hum: float (Humidity in percentage)

Pseudocode:
  1. Prepare data
     - Create map: data_map = {"temperature": temp, "humidity": hum, "timestamp": now()}

  2. Emit signal
     - Call sdbus_interface.emit_env_signal(data_map)

  3. Error handling
     - If signal emission fails:
       - Log error to dropped_messages_count
       - Attempt: sdbus_interface.reconnect_bus()
       - Don't throw exception (don't abort main loop)

  4. Complete
     - Return (void)

Signal Name: EnvDataUpdated
D-Bus Path: /vn/edu/uit/FSS/Sensor
Signal Payload: {"temperature": float, "humidity": float, "timestamp": float}
```

#### Method 3: broadcast_distance_data()
```
Signature: void broadcast_distance_data(uint16_t distance)
Return Type: void
Parameters:
  - distance: uint16_t (Raw distance in millimeters)

Pseudocode:
  1. Convert to meters
     - distance_m = distance / 1000.0

  2. Detect presence
     - threshold_m = 0.8 (configurable, typically 80cm)
     - user_present = (distance_m < threshold_m)

  3. Emit presence signal
     - Call sdbus_interface.emit_presence_signal(user_present)

  4. Alternative: Emit distance signal (for debugging)
     - Create map: data_map = {"distance_mm": distance, "distance_m": distance_m, "timestamp": now()}
     - Call sdbus_interface.emit_distance_signal(data_map)

  5. Error handling
     - If signal emission fails:
       - Log error
       - Attempt reconnection
       - Don't abort

  6. Complete
     - Return (void)

Signal Names:
  - UserPresenceDetected (primary)
  - DistanceUpdated (optional, for debugging)
```

#### Method 4: broadcast_door_status()
```
Signature: void broadcast_door_status(bool is_open)
Return Type: void
Parameters:
  - is_open: bool (true = open, false = closed)

Pseudocode:
  1. Convert to string
     - state_str = is_open ? "OPEN" : "CLOSED"

  2. Emit signal
     - Call sdbus_interface.emit_door_signal(state_str)

  3. Error handling
     - If signal emission fails:
       - Log error
       - Attempt reconnection
       - Don't abort

  4. Complete
     - Return (void)

Signal Name: DoorStateChanged
Signal Payload: "OPEN" or "CLOSED"
```

#### Method 5: broadcast_system_events()
```
Signature: void broadcast_system_events(std::map<std::string, std::any> data)
Return Type: void
Parameters:
  - data: std::map<std::string, std::any> (Sensor data map from InputProcessor.poll_all_data())

Pseudocode:
  1. Extract values from map
     - temp = data["temperature"]
     - hum = data["humidity"]
     - distance = data["distance"]
     - door_status = data["door_status"]
     - timestamp = data["timestamp"]

  2. Emit consolidated event
     - Create comprehensive_map = {
         "env": {"temperature": temp, "humidity": hum},
         "presence": {"distance": distance, "threshold": 0.8, "detected": distance < 0.8},
         "door": {"status": door_status ? "OPEN" : "CLOSED"},
         "timestamp": timestamp
       }
     - Call sdbus_interface.emit_system_event(comprehensive_map)

  3. Alternative: Emit individual signals
     - If updated: Call broadcast_env_data(temp, hum)
     - If updated: Call broadcast_distance_data((uint16_t)(distance * 1000))
     - If updated: Call broadcast_door_status(door_status == 1.0)

  4. Error handling
     - Graceful degradation: emit what succeeds, log what fails

  5. Complete
     - Return (void)

Purpose: Centralized event broadcasting for system-wide consistency
```

---

## Class: SensorDbusInterface

### Private Member Variables
```
system_bus: void* (or DBusConnection*)
├── Purpose: Kết nối System D-Bus nội bộ của Linux
├── Type: Opaque pointer (library-specific implementation)
├── Lifetime: From init_interface() to daemon shutdown
└── Thread Safety: Must protect with mutex if accessed from multiple threads

interface_name: std::string
├── Purpose: Tên Interface (VD: vn.edu.uit.FSS.Sensor)
├── Default Value: "vn.edu.uit.FSS.Sensor"
├── Immutable: Set during initialization
└── Used For: D-Bus signal routing

is_connected: bool
├── Purpose: Cờ trạng thái kết nối Bus
├── Initial Value: false
├── Updated By: init_interface(), reconnect_bus()
└── Checked By: broadcast methods before signal emission

dropped_messages_count: int
├── Purpose: Số tin nhắn gửi thất bại do lỗi mạng D-Bus
├── Initial Value: 0
├── Incremented: Each failed signal emission
└── Used For: Debug statistics
```

### Public Methods

#### Method 1: init_interface()
```
Signature: bool init_interface()
Return Type: bool
Parameters: None

Pseudocode:
  1. Get system bus
     - system_bus = dbus_bus_get(DBUS_BUS_SYSTEM, &error)
     - If error: log error, return false

  2. Verify connection
     - If system_bus == NULL: return false

  3. Request service name
     - service_name = "vn.edu.uit.FSS.Sensor"
     - Call dbus_bus_request_name(system_bus, service_name, flags, &error)
     - If failed (name already taken): log warning, return false

  4. Register object path
     - object_path = "/vn/edu/uit/FSS/Sensor"
     - Register path to handle signals
     - If failed: log error, return false

  5. Setup signal handlers
     - Register handler for incoming signals (if applicable)

  6. State update
     - Set is_connected = true

  7. Success
     - Return true

D-Bus Configuration:
  Service Name: vn.edu.uit.FSS.Sensor
  Object Path: /vn/edu/uit/FSS/Sensor
  Bus Type: System Bus (requires proper permissions in /etc/dbus-1/system.d/)
  Flags: DBUS_NAME_FLAG_REPLACE_EXISTING
```

#### Method 2: emit_env_signal()
```
Signature: void emit_env_signal(std::map<std::string, float> data_map)
Return Type: void
Parameters:
  - data_map: std::map<std::string, float> (Contains: "temperature", "humidity", "timestamp")

Pseudocode:
  1. Check connection
     - If !is_connected: attempt reconnect, if fails return void

  2. Create signal message
     - signal = dbus_message_new_signal(
         "/vn/edu/uit/FSS/Sensor",
         "vn.edu.uit.FSS.Sensor",
         "EnvDataUpdated"
       )
     - If NULL: log error, return

  3. Append data
     - dbus_message_append_args(signal,
         DBUS_TYPE_DOUBLE, &data_map["temperature"],
         DBUS_TYPE_DOUBLE, &data_map["humidity"],
         DBUS_TYPE_DOUBLE, &data_map["timestamp"],
         DBUS_TYPE_INVALID
       )

  4. Send signal
     - dbus_connection_send(system_bus, signal, NULL)
     - dbus_connection_flush(system_bus)

  5. Cleanup
     - dbus_message_unref(signal)

  6. Error handling
     - If send failed: increment dropped_messages_count, log error

  7. Return (void)

Signal Name: EnvDataUpdated
Signal Parameters:
  1. temperature: double (°C)
  2. humidity: double (%)
  3. timestamp: double (UNIX timestamp)
```

#### Method 3: emit_door_signal()
```
Signature: void emit_door_signal(std::string state)
Return Type: void
Parameters:
  - state: std::string ("OPEN" or "CLOSED")

Pseudocode:
  1. Check connection
     - If !is_connected: return

  2. Create signal message
     - signal = dbus_message_new_signal(
         "/vn/edu/uit/FSS/Sensor",
         "vn.edu.uit.FSS.Sensor",
         "DoorStateChanged"
       )

  3. Append state string
     - state_ptr = state.c_str()
     - dbus_message_append_args(signal,
         DBUS_TYPE_STRING, &state_ptr,
         DBUS_TYPE_INVALID
       )

  4. Send signal
     - dbus_connection_send(system_bus, signal, NULL)
     - dbus_connection_flush(system_bus)

  5. Cleanup
     - dbus_message_unref(signal)

  6. Error handling
     - If send failed: increment dropped_messages_count

  7. Return (void)

Signal Name: DoorStateChanged
Signal Parameters:
  1. state: string ("OPEN" or "CLOSED")
```

#### Method 4: emit_presence_signal()
```
Signature: void emit_presence_signal(bool user)
Return Type: void
Parameters:
  - user: bool (true = present, false = absent)

Pseudocode:
  1. Check connection
     - If !is_connected: return

  2. Create signal message
     - signal = dbus_message_new_signal(
         "/vn/edu/uit/FSS/Sensor",
         "vn.edu.uit.FSS.Sensor",
         "UserPresenceDetected"
       )

  3. Append boolean
     - dbus_bool_t presence = user ? TRUE : FALSE
     - dbus_message_append_args(signal,
         DBUS_TYPE_BOOLEAN, &presence,
         DBUS_TYPE_INVALID
       )

  4. Send signal
     - dbus_connection_send(system_bus, signal, NULL)
     - dbus_connection_flush(system_bus)

  5. Cleanup
     - dbus_message_unref(signal)

  6. Error handling
     - If send failed: increment dropped_messages_count

  7. Return (void)

Signal Name: UserPresenceDetected
Signal Parameters:
  1. presence: boolean (true = user present, false = no user)
```

#### Method 5: reconnect_bus()
```
Signature: bool reconnect_bus()
Return Type: bool
Parameters: None

Pseudocode:
  1. Check current state
     - If is_connected == true:
       - Return true (already connected)

  2. Cleanup old connection
     - If system_bus != NULL:
       - dbus_connection_close(system_bus)
       - dbus_connection_unref(system_bus)
       - system_bus = NULL

  3. Reconnection loop
     - FOR attempt IN 0..max_retries (3 retries):
       - Try: init_interface()
       - If success: return true
       - Else:
         - Sleep(exponential_backoff(attempt))
         - Continue

  4. Failure
     - Set is_connected = false
     - Log error: "Failed to reconnect to D-Bus after N attempts"
     - Return false

Backoff Strategy:
  - Attempt 0: Sleep 1 second
  - Attempt 1: Sleep 2 seconds
  - Attempt 2: Sleep 4 seconds
  - Max Retries: 3

Recovery Conditions:
  - dbus-daemon crashed and restarted
  - Temporary socket connectivity issue
  - Signal emission failed due to transient error
```

#### Method 6: log_bus_error()
```
Signature: void log_bus_error(std::string error_msg)
Return Type: void
Parameters:
  - error_msg: std::string (Error message to log)

Pseudocode:
  1. Prepare log entry
     - timestamp = ISO8601_now()
     - formatted_msg = "[{timestamp}] D-Bus Error: {error_msg}"

  2. Write to log
     - Path: /var/log/fss_sensor_dbus.log
     - Mode: APPEND
     - Include:
       - Timestamp
       - Error message
       - Severity: ERROR
       - dropped_messages_count

  3. Optional: Send alert
     - If error_critical:
       - Report via systemd journal
       - Log.Err("Critical D-Bus error: {error_msg}")

  4. Return (void)

Log Rotation:
  - Max file size: 10 MB
  - Keep backups: 5 files
  - Auto-rotate when exceeded

Critical Errors:
  - Service name conflict
  - Object path registration failed
  - System bus unavailable
```

---

## Class: SystemWatchdog

### Private Member Variables
```
interval_ms: int
├── Purpose: Chu kỳ gửi tín hiệu sống lên OS
├── Default Value: 5000 (5 seconds)
├── Config Source: From systemd WatchdogSec directive
├── Actual: Must be < (WatchdogSec / 2) for reliability
└── Range: 1000-60000 ms recommended

last_ping_ts: float
├── Purpose: Thời điểm ping gần nhất
├── Type: UNIX timestamp (seconds with millisecond precision)
├── Updated By: ping() method
└── Used For: Interval violation detection
```

### Public Methods

#### Method 1: init_driver()
```
Signature: bool init_driver()
Return Type: bool
Parameters: None

Pseudocode:
  1. Load sdnotify library
     - Try: Link to systemd notification library (libsystemd)
     - If unavailable: log warning, return false (optional feature)

  2. Get WatchdogSec from systemd
     - Call sd_watchdog_enabled(0)
     - If returns -1: service doesn't have watchdog enabled, return true (not an error)
     - If returns > 0: watchdog_usec = returned value
       - Convert to milliseconds: interval_ms = watchdog_usec / 1000

  3. Verify watchdog enabled
     - If interval_ms == 0: watchdog disabled, return true

  4. Set initial ping timestamp
     - last_ping_ts = current_unix_timestamp()

  5. Success
     - Log: "Watchdog initialized with interval {interval_ms}ms"
     - Return true

Systemd Configuration:
  In /etc/systemd/system/sensor_daemon.service:
    [Service]
    Type=notify
    WatchdogSec=10s
    ExecStart=/path/to/sensor_daemon
```

#### Method 2: ping()
```
Signature: void ping()
Return Type: void
Parameters: None

Pseudocode:
  1. Check if watchdog enabled
     - If interval_ms == 0: return (watchdog disabled)

  2. Update timestamp
     - last_ping_ts = current_unix_timestamp()

  3. Send heartbeat
     - Call sd_notify(0, "WATCHDOG=1")
     - If failed: log warning (non-critical)

  4. Return (void)

Timing Requirement:
  - Must be called at least every (interval_ms) milliseconds
  - Typical: Called from SensorDaemonMain.run_main_loop() every loop iteration
  - If missed: systemd will kill the process after timeout

Signal Code:
  WATCHDOG=1 tells systemd: "I'm still alive and healthy"
```

#### Method 3: notify_ready()
```
Signature: void notify_ready()
Return Type: void
Parameters: None

Pseudocode:
  1. Send ready notification
     - Call sd_notify(0, "READY=1")

  2. Log
     - Log: "Service marked as READY to systemd"

  3. Return (void)

Timing:
  - Should be called after all initialization complete
  - Called from SensorDaemonMain.start_app() before run_main_loop()
  - Signals to systemd: Service is ready to accept requests

Systemd Behavior:
  - If Type=notify in service file: systemd waits for READY=1
  - Without READY=1: systemd assumes timeout (default 90s)
  - Essential for proper service startup sequencing
```

#### Method 4: notify_stopping()
```
Signature: void notify_stopping()
Return Type: void
Parameters: None

Pseudocode:
  1. Send stopping notification
     - Call sd_notify(0, "STOPPING=1")

  2. Log
     - Log: "Service marked as STOPPING to systemd"

  3. Return (void)

Timing:
  - Should be called as first step in SensorDaemonMain.stop_app()
  - Gives systemd immediate notice before cleanup begins
  - Systemd then waits for process exit (or timeout)

Systemd Behavior:
  - If STOPPING=1 sent: systemd gives grace period before SIGKILL
  - Default: 90 seconds grace period (configurable)
  - Allows clean resource shutdown before forceful termination
```

#### Method 5: report_error_status()
```
Signature: void report_error_status(std::string err)
Return Type: void
Parameters:
  - err: std::string (Error message/status description)

Pseudocode:
  1. Format status message
     - status_msg = "STATUS=" + err
     - Example: "STATUS=Recovering from I2C timeout"

  2. Send to systemd
     - Call sd_notify(0, status_msg.c_str())

  3. Log to file
     - Write to /var/log/fss_sensor_daemon.log
     - Format: "[{timestamp}] ERROR: {err}"

  4. Optional: Increase error counter
     - error_count++
     - If error_count > threshold:
       - Log critical alert
       - Potential trigger for recovery routine

  5. Return (void)

Status Message Format:
  STATUS=<message> (max 100 chars typically)
  Example: "STATUS=I2C bus timeout, reconnecting..."

Systemd Display:
  When you run: systemctl status sensor_daemon
  The error message will appear in the "Active" line

Maximum Length:
  Typically 1024 bytes total for sd_notify message
  Keep status message concise
```

---

## Integration Workflow

### Initialization Sequence
```
main()
├─ SensorDaemonMain.init_app()
│  ├─ SystemWatchdog.init_driver()
│  │  └─ sd_watchdog_enabled() → get interval
│  ├─ InputProcessor.init_sensors()
│  │  ├─ I2cHandler creation (m_i2c_main)
│  │  ├─ GpioHandler creation (m_gpio_handler)
│  │  ├─ Sht3xDriver.init_driver()
│  │  ├─ Vl53l0xDriver.init_driver()
│  │  └─ DoorSensorDriver.init_driver()
│  └─ OutputProcessor.init_ipc()
│     └─ SensorDbusInterface.init_interface()
│        ├─ dbus_bus_get(DBUS_BUS_SYSTEM)
│        └─ dbus_bus_request_name()
│
└─ SensorDaemonMain.start_app()
   ├─ SystemWatchdog.notify_ready()
   │  └─ sd_notify(0, "READY=1")
   └─ SensorDaemonMain.run_main_loop()
      └─ Loop:
         ├─ Check watchdog interval
         ├─ SystemWatchdog.ping() if time elapsed
         │  └─ sd_notify(0, "WATCHDOG=1")
         ├─ InputProcessor.poll_all_data()
         ├─ OutputProcessor.broadcast_*()
         │  └─ SensorDbusInterface.emit_*_signal()
         └─ Sleep(loop_interval_ms)
```

### Error Recovery Sequence
```
Any error occurs in run_main_loop()
│
├─ SensorDaemonMain.recover_from_fault()
│  ├─ SystemWatchdog.report_error_status("Error description")
│  ├─ Attempt:
│  │  └─ SensorDbusInterface.reconnect_bus()
│  │     ├─ Close old connection
│  │     └─ Loop:
│  │        ├─ SensorDbusInterface.init_interface()
│  │        └─ Exponential backoff
│  └─ Return success/failure
│
└─ Continue or exit based on recovery result
```

### Shutdown Sequence
```
Systemd sends SIGTERM or manual stop command
│
├─ SensorDaemonMain.stop_app()
│  ├─ Set is_running = false
│  ├─ SystemWatchdog.notify_stopping()
│  │  └─ sd_notify(0, "STOPPING=1")
│  ├─ Close OutputProcessor
│  │  └─ SensorDbusInterface cleanup
│  │     └─ dbus_connection_close()
│  ├─ Close InputProcessor
│  │  ├─ Sht3xDriver cleanup
│  │  ├─ Vl53l0xDriver cleanup
│  │  ├─ DoorSensorDriver cleanup
│  │  └─ I2C/GPIO resource cleanup
│  └─ Return
│
└─ main() exits
```

