# MC-38 Door Sensor Tests

## Overview
This directory contains test programs for the MC-38 magnetic door sensor driver configured to use **GPIO26** (Pin 37) and **Ground** (Pin 39).

## Building the Test

### Prerequisites
- libgpiod development library: `sudo apt install libgpiod-dev`
- C++ compiler with C++17 support (e.g., g++ or clang++)

### Build Command
```bash
cd /home/richardmelvin52/FSS/drivers/sensor/mc-38/tests
g++ -std=c++17 -o test_mc38 test_mc38.cpp ../src/MC38.cpp \
    -I../include -lgpiod
```

### Alternative: Using CMake
If you're building as part of the larger project with CMake, add this to your CMakeLists.txt:
```cmake
add_executable(test_mc38 tests/test_mc38.cpp src/MC38.cpp)
target_include_directories(test_mc38 PRIVATE include)
target_link_libraries(test_mc38 gpiod)
```

## Running the Test

```bash
# Run with root privileges (required for GPIO access)
sudo ./test_mc38
```

## Test Suite Description

The test program runs 4 tests:

1. **Initialization Test**: Verifies the MC38 sensor can be properly initialized on GPIO26
2. **Single Status Read**: Reads the door status once to verify operation
3. **Helper Methods Test**: Tests the `isDoorOpen()` and `isDoorClosed()` convenience methods
4. **Continuous Monitoring**: Monitors the sensor for 10 seconds, detecting any state changes

## Hardware Configuration

| Component | Pin | GPIO | Notes |
|-----------|-----|------|-------|
| MC-38 Terminal 1 | 37 | GPIO 26 | Connected via internal pull-up |
| MC-38 Terminal 2 | 39 | Ground | Ground reference |

## Expected Output

When the magnet is near the sensor (door closed):
```
Status: CLOSED     | [●] MAGNET DETECTED - Door is CLOSED
```

When the magnet is far from the sensor (door open):
```
Status: OPEN       | [○] NO MAGNET - Door is OPEN
```

## Troubleshooting

### GPIO Access Denied
- Run the test with `sudo`
- Ensure libgpiod is installed: `sudo apt install libgpiod-dev`

### GPIO26 Not Found
- Verify the GPIO pin is available and not in use by other processes
- Check `/proc/device-tree/gpio/` or use `gpioinfo` from libgpiod2 package

### Incorrect Sensor Readings
- Verify the sensor hardware is properly connected to GPIO26 (Pin 37) and Ground (Pin 39)
- Test with a magnet to ensure physical connection is correct
- Check for proper pull-up resistor configuration

## References
- [libgpiod Documentation](https://libgpiod.readthedocs.io/)
- [Raspberry Pi GPIO Pinout](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- MC-38 Datasheet (typically a simple magnetic reed switch)
