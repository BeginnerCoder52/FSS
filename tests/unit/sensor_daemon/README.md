# Sensor Daemon Unit Tests

## Overview

This directory contains comprehensive unit tests for the **Sensor Daemon** module of the FSS (SMART_MIRROR) project. The tests follow **ASPICE (Automotive SPICE) principles** ensuring:

- **Clean Code**: Well-structured, readable, and maintainable test code
- **Complete Coverage**: All APIs and critical paths are tested
- **Integration Testing**: Component interactions within `SensorDaemonMain` are validated
- **Error Handling**: Fault scenarios and recovery mechanisms are thoroughly tested
- **State Management**: Daemon lifecycle and state transitions are verified

## Test Architecture

### Directory Structure

```
tests/
├── CMakeLists.txt                         # Global test build configuration
└── unit/
    └── sensor_daemon/
        ├── CMakeLists.txt                 # Sensor daemon test build config
        ├── README.md                      # This file
        ├── SensorDaemonMainTest.cpp       # Main orchestrator tests
        ├── InputProcessorTest.cpp         # Sensor data acquisition tests
        ├── OutputProcessorTest.cpp        # IPC broadcasting tests
        ├── SystemWatchdogTest.cpp         # Health monitoring tests
        ├── Sht3xDriverTest.cpp            # SHT31 temperature/humidity sensor tests
        ├── Vl53l0xDriverTest.cpp          # VL53L0X distance sensor tests
        ├── DoorSensorDriverTest.cpp       # MC-38 door sensor tests
        └── SensorDbusInterfaceTest.cpp    # D-Bus communication tests
```

## Test Modules

### 1. **SensorDaemonMainTest.cpp**

**Purpose**: Integration tests for the main application orchestrator

**Key Test Cases**:

- Initialization sequence validation
- Application lifecycle management (INIT → IDLE → RUNNING → STOPPED)
- Main loop execution and polling intervals
- Environmental data processing pipeline
- Distance data broadcasting workflow
- Error recovery mechanism (3 retry attempts with exponential backoff)
- Watchdog heartbeat coordination
- System status logging

**Tested APIs**:

- `init_app()` - Validates component initialization order
- `start_app()` - Verifies state transitions and readiness notification
- `stop_app()` - Tests graceful shutdown sequence
- `run_main_loop()` - Validates polling rates and timing
- `process_environment_data()` - Tests data pipeline end-to-end
- `recover_from_fault()` - Validates 3-attempt recovery with backoff
- `log_system_status()` - Tests logging and system metrics collection

### 2. **InputProcessorTest.cpp**

**Purpose**: Tests sensor data acquisition and aggregation

**Key Test Cases**:

- Sensor initialization for SHT31, VL53L0X, and MC-38
- Environmental data polling (temperature, humidity)
- Distance measurement acquisition (in mm)
- Door status reading (OPEN/CLOSED)
- Poll timestamp accuracy (Unix time precision)
- Data aggregation into sensor map
- I2C and GPIO handler integration

**Tested APIs**:

- `init_sensors()` - Validates all sensor initialization
- `poll_all_data()` - Tests complete sensor sweep
- `get_env_data()` - Validates temperature/humidity extraction
- `get_distance_data()` - Tests distance measurement
- `get_door_status()` - Tests door state interpretation

### 3. **OutputProcessorTest.cpp**

**Purpose**: Tests IPC broadcasting and event distribution

**Key Test Cases**:

- D-Bus interface initialization
- Environmental data broadcasting (temperature, humidity)
- Distance data emission to subscribers
- Door status signal propagation
- System event analysis and routing
- Data validation before broadcast
- Error handling for failed emissions

**Tested APIs**:

- `init_ipc()` - Validates D-Bus connection establishment
- `broadcast_env_data()` - Tests temperature/humidity signals
- `broadcast_distance_data()` - Tests distance signal emission
- `broadcast_door_status()` - Tests door state signals
- `broadcast_system_events()` - Tests event routing logic

### 4. **SystemWatchdogTest.cpp**

**Purpose**: Tests health monitoring and system reporting

**Key Test Cases**:

- Watchdog driver initialization
- Periodic ping mechanism (every 4 seconds)
- Ready state notification (at startup)
- Stopping state notification (at shutdown)
- Error status reporting to systemd
- Last ping timestamp tracking
- Timeout interval configuration

**Tested APIs**:

- `init_driver()` - Validates watchdog setup
- `ping()` - Tests heartbeat mechanism
- `notify_ready()` - Tests startup notification
- `notify_stopping()` - Tests shutdown notification
- `report_error_status()` - Tests error message propagation

### 5. **Sht3xDriverTest.cpp**

**Purpose**: Tests SHT31 temperature and humidity sensor

**Key Test Cases**:

- Driver initialization and I2C communication
- Single-shot measurement mode
- Continuous measurement mode at various rates (0.5, 1, 2, 4, 10 Hz)
- Temperature and humidity value retrieval
- Clock stretching configuration
- Sensor deinitialization
- Error handling for I2C failures

**Tested APIs**:

- `init_driver()` - Validates sensor setup
- `single_read()` - Tests one-time measurement
- `start_continuous_read()` - Tests continuous mode with rates
- `continuous_read()` - Tests continuous polling
- `get_temperature()` - Tests temperature retrieval
- `get_humidity()` - Tests humidity retrieval (if available)
- `stop_continuous_read()` - Tests mode termination
- `deinit_driver()` - Tests cleanup

### 6. **Vl53l0xDriverTest.cpp**

**Purpose**: Tests VL53L0X Time-of-Flight distance sensor

**Key Test Cases**:

- Driver initialization and I2C setup
- Distance measurement in meters
- User detection based on distance threshold
- Continuous measurement mode
- Hardware connection verification
- Sensor reset functionality
- I2C timeout handling
- Distance-to-meter conversion accuracy

**Tested APIs**:

- `init_driver()` - Validates sensor initialization
- `read_distance_meters()` - Tests distance conversion
- `is_user_detected()` - Tests presence detection logic
- `check_connection()` - Tests I2C connectivity
- `reset_sensor()` - Tests reset mechanism
- `start_continuous()` - Tests continuous mode
- `stop_continuous()` - Tests mode termination
- `handle_i2c_timeout()` - Tests timeout recovery

### 7. **DoorSensorDriverTest.cpp**

**Purpose**: Tests MC-38 magnetic door sensor

**Key Test Cases**:

- GPIO line initialization and ownership
- Door state reading (OPEN/CLOSED)
- State string formatting
- Interrupt flag clearing
- GPIO line availability diagnosis
- Debounce time handling
- Connection status management

**Tested APIs**:

- `init_driver()` - Validates GPIO setup
- `read_state()` - Tests state string retrieval
- `is_open()` - Tests open state detection
- `is_closed()` - Tests closed state detection
- `clear_interrupt_flags()` - Tests buffer overflow handling
- `diagnose_gpio_line()` - Tests GPIO availability check

### 8. **SensorDbusInterfaceTest.cpp**

**Purpose**: Tests D-Bus communication interface

**Key Test Cases**:

- D-Bus connection establishment
- Environmental signal emission (data map format)
- Door signal emission (OPEN/CLOSED strings)
- User presence signal emission
- Bus reconnection after daemon restart
- Signal parameter validation
- Connection error handling

**Tested APIs**:

- `init_interface()` - Validates D-Bus setup
- `emit_env_signal()` - Tests environmental data signals
- `emit_door_signal()` - Tests door state signals
- `emit_presence_signal()` - Tests user detection signals
- `reconnect_bus()` - Tests connection recovery

## Component Interaction Flow (Integration)

The following diagram shows how components interact within `SensorDaemonMain`:

```
┌─────────────────────────────────────────────────────────┐
│         SensorDaemonMain::run_main_loop()               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Every 5000ms:     Every 500ms:      Every 4000ms:      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Environmental│  │   Distance   │  │  Watchdog    │  │
│  │ polling cycle│  │  polling     │  │  heartbeat   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│         v                  v                  v          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ InputProcessor::poll_all_data()                     │ │
│  │ ├─ Sht3xDriver::continuous_read()                  │ │
│  │ ├─ Vl53l0xDriver::read_distance_meters()           │ │
│  │ └─ DoorSensorDriver::read_state()                  │ │
│  └─────────────────┬───────────────────────────────────┘ │
│                    │                                       │
│                    v                                       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ OutputProcessor::broadcast_system_events()         │ │
│  │ ├─ SensorDbusInterface::emit_env_signal()          │ │
│  │ ├─ SensorDbusInterface::emit_presence_signal()     │ │
│  │ └─ SensorDbusInterface::emit_door_signal()         │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  SystemWatchdog::ping() ──────────────────────────────▶  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Building Tests

### Prerequisites

```bash
# Install Google Test
sudo apt-get install libgtest-dev

# Install required dependencies
sudo apt-get install libsdbus-c++-dev libzmq3-dev libgpiod-dev
```

### Build Commands

```bash
# Create build directory
cd tests
mkdir -p build
cd build

# Configure CMake (Debug mode with coverage)
cmake -DCMAKE_BUILD_TYPE=Debug ..

# Build all tests
cmake --build . -j$(nproc)
```

## Running Tests

### Run All Tests

```bash
# From build directory
ctest -V
```

### Run Specific Test Module

```bash
# Test sensor daemon main integration
ctest -R SensorDaemonMain -V

# Test input processor
ctest -R InputProcessor -V

# Test output processor
ctest -R OutputProcessor -V

# Test system watchdog
ctest -R SystemWatchdog -V

# Test all sensor drivers
ctest -R "Driver" -V
```

### Generate Coverage Report

```bash
# After running tests, generate coverage report
gcovr --print-summary
gcovr --html coverage.html
```

## Test Code Style Guidelines

All test files adhere to the following principles:

### 1. **ASPICE Compliance**

- Clear test objectives and documentation
- Each test validates a single behavior
- Proper setup/teardown with fixtures
- Mock objects isolate units under test

### 2. **Clean Code**

- Descriptive test names using `TEST(Suite, TestName)` format
- Clear assertions with meaningful messages
- Minimal test code complexity
- No hardcoded magic numbers (use constants)

### 3. **Documentation**

- Header comments explain test purpose
- Inline comments clarify non-obvious logic
- Test cases grouped logically by functionality

### 4. **Mock Objects**

Each test file provides mocks for dependencies:

- `MockI2cHandler` - Simulates I2C communication
- `MockGpioHandler` - Simulates GPIO operations
- `MockSensorDbusInterface` - Simulates D-Bus signals
- `MockWatchdog` - Simulates watchdog notifications

## Test Fixtures

Each test module uses Google Test fixtures for consistent setup:

```cpp
class SensorDaemonTest : public ::testing::Test {
protected:
    virtual void SetUp() {
        // Initialize test environment
    }

    virtual void TearDown() {
        // Cleanup resources
    }
};
```

## Integration Points

Tests validate the following integration scenarios:

1. **Initialization Pipeline**: Watchdog → InputProcessor → OutputProcessor
2. **Main Loop Orchestration**: Sensor polling → Data processing → Broadcasting
3. **Error Recovery**: Exception → Recovery attempt → State restoration
4. **Graceful Shutdown**: Stop signal → Watchdog notification → Resource cleanup

## Debugging Tests

```bash
# Run single test with full output
ctest -R "SensorDaemonMain.*Initialization" -VVV

# Run with GDB for debugging
gdb ./unit/sensor_daemon/test_sensor_daemon_main

# Inside GDB: run with arguments
(gdb) run --gtest_filter="SensorDaemonTest.InitializationSuccess"
```

## Performance Benchmarks

Tests include timing validation for:

- Environmental polling: 5000ms ± 100ms tolerance
- Distance polling: 500ms ± 50ms tolerance
- Watchdog heartbeat: 4000ms ± 200ms tolerance
- Loop interval: 100ms sleep precision

## Future Extensions

- Add stress tests for long-running operations
- Add performance profiling for sensor reading latency
- Add hardware-in-the-loop tests (HIL)
- Add continuous integration (CI) automation

## Contact & Support

For questions about the test suite, refer to the main project documentation or contact the FSS Development Team.

---

**Last Updated**: 2024
**Test Framework**: Google Test (GTest)
**C++ Standard**: C++17
**Coverage Target**: >85% code coverage
