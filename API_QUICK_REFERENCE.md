# FSS API Quick Reference - Method Signatures

## 1. SensorDaemonMain - Method Signatures

```cpp
// Lifecycle Methods
bool init_app();
bool start_app();
void stop_app();

// Main Event Loop
void run_main_loop();

// Error Handling
bool recover_from_fault();

// Debugging
void log_system_status();
void process_environment_data();
```

### Member Variables
```cpp
std::string current_state;           // INIT, IDLE, ERROR
bool is_running;                     // Main loop flag
int loop_interval_ms;                // Sleep interval (ms)
int polling_rate_env_ms;             // Temperature/humidity polling (ms)
int polling_rate_dist_ms;            // Distance polling (ms)
InputProcessor* input_processor;     // Sensor data input handler
OutputProcessor* output_processor;   // IPC output handler
SystemdWatchdog* watchdog;          // OS watchdog reporting
```

---

## 2. InputProcessor - Method Signatures

```cpp
// Sensor Initialization
bool init_sensors();

// Data Acquisition
std::map<std::string, float> poll_all_data();
void get_env_data(float& temp, float& hum);
uint16_t get_distance_data();
bool get_door_status();
```

### Member Variables
```cpp
std::shared_ptr<I2cHandler> m_i2c_main;          // Primary I2C bus (/dev/i2c-1)
std::shared_ptr<I2cHandler> m_i2c_ext;           // Secondary I2C bus (/dev/i2c-6)
std::shared_ptr<GpioHandler> m_gpio_handler;     // GPIO chip handler
std::unique_ptr<Sht3xDriver> sht3x;              // Environment sensor driver
std::unique_ptr<Vl53l0xDriver> vl53l0x;          // Distance sensor driver
std::unique_ptr<DoorSensorDriver> door_sensor;   // Door sensor driver
float last_poll_timestamp;                        // Unix timestamp of last poll
```

---

## 3. OutputProcessor - Method Signatures

```cpp
// IPC Initialization
bool init_ipc();

// Signal Broadcasting
void broadcast_env_data(float temp, float hum);
void broadcast_distance_data(uint16_t distance);
void broadcast_door_status(bool is_open);
void broadcast_system_events(std::map<std::string, std::any> data);
```

### Member Variables
```cpp
SensorDbusInterface* sdbus_interface;  // D-Bus connection handler
```

---

## 4. SensorDbusInterface - Method Signatures

```cpp
// D-Bus Connection Management
bool init_interface();

// Signal Emission
void emit_env_signal(std::map<std::string, float> data_map);
void emit_door_signal(std::string state);
void emit_presence_signal(bool user);

// Error Recovery
bool reconnect_bus();

// Debugging
void log_bus_error(std::string error_msg);
```

### Member Variables
```cpp
void* system_bus;                  // Linux system D-Bus connection
std::string interface_name;        // Interface name (e.g., vn.edu.uit.FSS.Sensor)
bool is_connected;                 // Connection status flag
int dropped_messages_count;        // Failed message counter
```

### Signal Names (D-Bus)
- `EnvDataUpdated` - Environment data signal
- `DoorStateChanged` - Door state change signal
- `UserPresenceDetected` - User presence detection signal

---

## 5. SystemWatchdog - Method Signatures

```cpp
// Initialization
bool init_driver();

// Heartbeat and Status Reporting
void ping();                           // Send WATCHDOG=1
void notify_ready();                   // Send READY=1
void notify_stopping();                // Send STOPPING=1
void report_error_status(std::string err);
```

### Member Variables
```cpp
int interval_ms;                   // Watchdog interval (ms)
float last_ping_ts;                // Timestamp of last ping
```

### Systemd Notification Codes
- `WATCHDOG=1` - Watchdog heartbeat
- `READY=1` - Service is ready
- `STOPPING=1` - Service is stopping
- `STATUS=<message>` - Status message

---

## Integration Points

### Main Loop Flow (SensorDaemonMain)
```
run_main_loop():
  1. Check watchdog timeout
  2. Poll InputProcessor.poll_all_data()
  3. Extract individual sensor values
  4. Call OutputProcessor.broadcast_*() for each sensor
  5. Update SystemWatchdog.ping()
  6. Sleep for loop_interval_ms
  7. Repeat until is_running = false
```

### Error Recovery Flow
```
recover_from_fault():
  1. Log error state
  2. Attempt SystemWatchdog.report_error_status()
  3. Try OutputProcessor.sdbus_interface.reconnect_bus()
  4. Reinitialize failed components
  5. Return success/failure status
```

### Initialization Flow
```
init_app():
  1. SystemWatchdog.init_driver()
  2. InputProcessor.init_sensors()
  3. OutputProcessor.init_ipc()
  4. Set current_state = IDLE
  5. Return success/failure

start_app():
  1. Set is_running = true
  2. SystemWatchdog.notify_ready()
  3. Call run_main_loop()
```

---

## D-Bus Interface Details

### Service Name (SensorDaemon)
- `vn.edu.uit.FSS.Sensor`

### Signal Definitions

#### EnvDataUpdated
- **Emitter:** SensorDbusInterface
- **Payload:** JSON map with keys: `temp`, `humidity`, `timestamp`
- **Called By:** OutputProcessor.broadcast_env_data()

#### DoorStateChanged
- **Emitter:** SensorDbusInterface
- **Payload:** String ("OPEN" or "CLOSED")
- **Called By:** OutputProcessor.broadcast_door_status()

#### UserPresenceDetected
- **Emitter:** SensorDbusInterface
- **Payload:** Boolean (true = present, false = absent)
- **Called By:** OutputProcessor.broadcast_distance_data() (after threshold check)

---

## Type Conventions

| Type | Description | Example |
|---|---|---|
| `float` | Temperature (°C), Humidity (%), Distance (meters) | 23.5, 65.2, 0.75 |
| `uint16_t` | Raw distance sensor value | 1234 |
| `bool` | Boolean state | true/false |
| `int` | Time intervals, error counts | 5000, 42 |
| `string` | State names, error messages | "OPEN", "I2C_TIMEOUT" |
| `map<string, float>` | Multi-value sensor data | {"temp": 23.5, "humidity": 65.2} |

---

## Error Handling Priorities

1. **High Priority:** I2C bus failures, GPIO access denied, D-Bus connection lost
2. **Medium Priority:** Individual sensor read failures, watchdog timeout
3. **Low Priority:** Debug logging failures, message dropping

---

## Threading Considerations

- All methods are assumed to run in a single main thread
- D-Bus signals may be received asynchronously (from SystemWatchdog perspective)
- OutputProcessor must be thread-safe if signals are emitted from different thread contexts
- I2C and GPIO operations are blocking and should be completed before next loop iteration

---

## Testing Checklist

- [ ] SensorDaemonMain state transitions work correctly
- [ ] InputProcessor sensor initialization sequence
- [ ] OutputProcessor D-Bus signal emission without errors
- [ ] SensorDbusInterface reconnection logic
- [ ] SystemWatchdog heartbeat timing
- [ ] Error recovery without crashing
- [ ] Memory cleanup in stop_app()
- [ ] Timestamp synchronization across all components
