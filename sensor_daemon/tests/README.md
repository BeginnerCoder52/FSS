## SHT31 Sensor Driver Tests

Comprehensive unit test suite for the Sht3xDriver wrapper class.

### Features

- **Initialization Test**: Verifies sensor startup and configuration
- **Connection Check**: Tests sensor connectivity status
- **Single Read Test**: Validates single measurement mode
- **Continuous Read Test**: Tests continuous measurement mode at various rates
- **Repeatability Configuration**: Tests high/medium/low repeatability settings
- **Heater Control**: Validates heater enable/disable functionality
- **Soft Reset**: Tests sensor reset command
- **Status Register**: Tests status read and clear operations
- **Serial Number**: Retrieves and displays sensor serial number
- **Error Handling**: Validates error counter mechanism

### Building Tests

#### From sensor_daemon directory

```bash
mkdir -p build
cd build
cmake ..
make sht3x_test
```

#### From tests directory

```bash
mkdir -p build
cd build
cmake ..
make sht3x_test
```

### Running Tests

```bash
# Using default I2C bus (/dev/i2c-1) and address (0x44)
./sht3x_test

# Specify I2C bus and address
./sht3x_test -b /dev/i2c-1 -a 0x44

# Show help
./sht3x_test --help
```

### Test Output

The test suite produces colored output:
- **GREEN [PASS]**: Test completed successfully
- **RED [FAIL]**: Test failed

A summary is displayed at the end showing total passed and failed tests.

### I2C Address Selection

The SHT31 sensor can be configured for two I2C addresses:
- **0x44**: Default (ADDR pin connected to GND)
- **0x45**: Alternative (ADDR pin connected to VCC)

Verify your hardware configuration and pass the correct address via the `-a` flag.

### Requirements

- libgpiod development headers
- Linux I2C interface (`/dev/i2c-*`)
- CMake 3.10+
- C++17 compatible compiler
- libpthread

### Sensor Hardware Requirements

- SHT31 sensor connected via I2C (SDA/SCL)
- Proper I2C pull-up resistors (typically 4.7kΩ)
- Power supply (3.3V or 5V, depending on your setup)

### Troubleshooting

**"Failed to open I2C bus"**
- Check I2C device path (`ls /dev/i2c-*`)
- Verify permissions: `sudo group i2c $USER`

**"Cannot set I2C slave address"**
- Verify correct I2C address with `i2cdetect -y 1`
- Check sensor connections

**"Initialization failed"**
- Verify sensor power supply
- Check I2C pull-up resistors
- Test with `i2cget` or similar tools

### Test Results Example

```
=====================================
  SHT31 Sensor Driver Test Suite
=====================================

Initialization Test                      [PASS]
Connection Check Test                    [PASS]
Single Read Test                         [PASS]
  Temperature: 25.47°C
  Humidity: 45.32%
Continuous Read Test                     [PASS]
Set Repeatability Test                   [PASS]
Set Heater Test                          [PASS]
Soft Reset Test                          [PASS]
Status Register Test                     [PASS]
Serial Number Test                       [PASS]
  Serial Number: 0xaabbccdd
Error Handling Test                      [PASS]

=====================================
Tests Passed: 10 | Tests Failed: 0
=====================================
```

### Integration

After building and verifying tests pass, the driver is ready for integration into sensor_daemon.
