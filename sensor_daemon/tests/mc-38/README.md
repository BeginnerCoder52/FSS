# MC-38 Door Sensor Driver Tests

## Overview
Comprehensive test suite for the MC-38 magnetic door sensor driver (DoorSensorDriver class). Tests all public APIs including initialization, state reading, GPIO diagnostics, and convenience methods.

## Hardware Setup
- **MC-38 Terminal 1**: GPIO26 (Physical Pin 37)
- **MC-38 Terminal 2**: Ground (Physical Pin 39)
- **GPIO Chip**: /dev/gpiochip0

## Prerequisites
- libgpiod development library: `sudo apt install libgpiod-dev`
- C++ compiler with C++17 support
- Root privileges (required for GPIO access)

## Building

### Option 1: Using Make
```bash
cd /home/richardmelvin52/FSS/sensor_daemon/tests/mc-38
make
```

### Option 2: Manual Compilation
```bash
g++ -std=c++17 -Wall -Wextra -O2 \
    -I../../include \
    -I../../include/gc-38 \
    -o test_mc38_driver \
    test_main.cpp DoorSensorTest.cpp \
    ../../src/DoorSensorDriver.cpp \
    ../../drivers/sensor/mc-38/src/MC38.cpp \
    -lgpiod
```

### Option 3: CMake (From tests directory)
```bash
cd /home/richardmelvin52/FSS/sensor_daemon/tests
cmake .
make
```

## Running the Tests

### Basic Execution
```bash
sudo ./test_mc38_driver
```

### With Custom GPIO Offset
```bash
sudo ./test_mc38_driver --gpio 26
```

### Help
```bash
./test_mc38_driver --help
```

## Test Suite Description

The test suite runs 7 comprehensive tests:

### 1. **Initialization Test**
- Verifies DoorSensorDriver can initialize with GPIO26
- Checks /dev/gpiochip0 access
- Confirms MC38 driver instantiation

### 2. **Read State API Test**
- Tests `read_state()` method
- Verifies it returns "OPEN" or "CLOSED"
- Checks state consistency

### 3. **is_open() Method Test**
- Tests convenience method `is_open()`
- Compares with `read_state()` for consistency
- Validates boolean return value

### 4. **is_closed() Method Test**
- Tests convenience method `is_closed()`
- Compares with `read_state()` for consistency
- Validates mutual exclusivity with is_open()

### 5. **GPIO Diagnosis Test**
- Tests `diagnose_gpio_line()` API
- Verifies GPIO connection status
- Checks for resource conflicts

### 6. **Clear Interrupt Flags Test**
- Tests `clear_interrupt_flags()` API
- Validates method executes without errors
- For MC-38 (simple GPIO), this is a no-op

### 7. **Continuous Monitoring Test**
- Monitors sensor for 5 seconds
- Detects state changes in real-time
- Useful for validating debounce and responsiveness

## Expected Output

### Successful Run
```
════════════════════════════════════════════════════════
Running MC-38 Door Sensor Tests
════════════════════════════════════════════════════════

[TEST 1: Initialization]
  GPIO Pin: GPIO26 (Pin 37)
  GPIO Chip: /dev/gpiochip0
Initialization Test                                      [PASS]

[TEST 2: Read State API]
  Current State: CLOSED
Read State Test                                          [PASS]
[... more tests ...]

Test Summary:
  Passed: 7
  Failed: 0
════════════════════════════════════════════════════════
```

### Door State Readings

When magnet is near the sensor (door closed):
```
Current State: CLOSED
is_closed(): true
is_open(): false
```

When magnet is far from the sensor (door open):
```
Current State: OPEN
is_closed(): false
is_open(): true
```

## Troubleshooting

### GPIO Access Denied
- Run with sudo: `sudo ./test_mc38_driver`
- Verify /dev/gpiochip0 permissions

### Initialization Failed
- Check MC-38 is physically connected to GPIO26 (Pin 37) and GND (Pin 39)
- Run `pinctrl` to verify GPIO26 status
- Ensure no other application is using GPIO26

### Incorrect Readings
- Verify sensor is not bouncing excessively
- Check physical connection quality
- Test with actual magnet to confirm behavior
- Review debounce settings if integrated into larger system

### libgpiod Not Found
- Install: `sudo apt install libgpiod-dev`
- Verify: `pkg-config --modversion libgpiod`

## API Reference

### DoorSensorDriver Public Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `bool init_driver()` | Initialize GPIO and sensor | Success status |
| `std::string read_state()` | Read current door state | "OPEN" or "CLOSED" |
| `bool is_open()` | Check if door is open | true/false |
| `bool is_closed()` | Check if door is closed | true/false |
| `bool diagnose_gpio_line()` | Verify GPIO connection | Connection status |
| `void clear_interrupt_flags()` | Clear interrupt buffer | void |

## Implementation Details

### Driver Architecture
- **DoorSensorDriver**: High-level wrapper providing state management
- **MC38**: Low-level libgpiod wrapper using line requests
- **GpioHandler**: Shared GPIO resource management

### GPIO Configuration
- Direction: Input
- Bias: Pull-up (internal)
- Active Logic: Low = CLOSED, High = OPEN
- Update Rate: Configurable (default 500ms in tests)

## Integration with Main Sensor Daemon

To build as part of the complete sensor_daemon:
1. Ensure MC38.hpp/cpp are in `/drivers/sensor/mc-38/`
2. Ensure DoorSensorDriver.hpp/cpp are in `/sensor_daemon/include/` and `/sensor_daemon/src/`
3. Update CMakeLists.txt to include MC-38 sources
4. Link against libgpiod: `-lgpiod`

## References
- [libgpiod Documentation](https://libgpiod.readthedocs.io/)
- [Raspberry Pi GPIO Pinout](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- [README_PINOUT.md](../../README_PINOUT.md) - Hardware pinout for all sensors
