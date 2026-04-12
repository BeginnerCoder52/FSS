# SHT3x Driver - Quick Reference

## Quick Start

### Basic Usage

```cpp
#include "Sht3xDriver.hpp"
#include "I2cHandler.hpp"
#include <memory>

// Create I2C handler and driver
auto i2c = std::make_shared<I2cHandler>("/dev/i2c-1");
Sht3xDriver sht3x(i2c, 0x44);  // Address can be 0x44 or 0x45

// Initialize
if (!sht3x.init_driver()) {
    // Handle initialization error
    return;
}

// Single read (one-shot measurement)
if (sht3x.single_read(true)) {
    float temp = sht3x.get_temperature();  // °C
    float humid = sht3x.get_humidity();    // 0-100%
    printf("Temp: %.2f°C, Humidity: %.1f%%\n", temp, humid);
}

// Cleanup
sht3x.deinit_driver();
```

### Continuous Mode

```cpp
// Start continuous measurements at 1 Hz
sht3x.start_continuous_read(1.0f);

// Read samples periodically (once per second in this case)
for (int i = 0; i < 10; ++i) {
    if (sht3x.continuous_read()) {
        printf("T=%.1f°C, H=%.1f%%\n", 
               sht3x.get_temperature(), 
               sht3x.get_humidity());
    }
    sleep(1);
}

// Stop continuous mode
sht3x.stop_continuous_read();
```

## API Reference

### Initialization & Cleanup
| Method | Purpose | Returns |
|--------|---------|---------|
| `init_driver()` | Initialize sensor | `bool` - success |
| `deinit_driver()` | Clean shutdown | `bool` - success |
| `check_connection()` | Verify sensor online | `bool` - connected |

### Single Measurement
| Method | Purpose | Returns |
|--------|---------|---------|
| `single_read(bool)` | One-shot measurement | `bool` - success |
| `get_temperature()` | Last temp (°C) | `float` |
| `get_humidity()` | Last humidity (%) | `float` |

### Continuous Measurement
| Method | Purpose | Returns |
|--------|---------|---------|
| `start_continuous_read(float rate)` | Begin continuous mode | `bool` - success |
| `continuous_read()` | Read next sample | `bool` - success |
| `stop_continuous_read()` | End continuous mode | `bool` - success |

**Supported Rates**: 0.5, 1, 2, 4, 10 Hz

### Configuration
| Method | Purpose | Parameters |
|--------|---------|------------|
| `set_repeatability(r)` | Measurement quality | 0=high, 1=med, 2=low |
| `set_heater(bool)` | Enable heater | `true`/`false` |
| `soft_reset()` | Reset sensor | N/A |

### Status & Diagnostics
| Method | Purpose | Returns |
|--------|---------|---------|
| `get_status()` | Status register | `uint16_t` flags |
| `clear_status()` | Clear status flags | `bool` - success |
| `get_serial_number(sn[4])` | Device SN | `bool` - success |
| `get_error_count()` | Error counter | `int` |
| `handle_i2c_timeout()` | Record error | void |

## Configuration Examples

### High Precision
```cpp
sht3x.init_driver();
sht3x.set_repeatability(0);  // High
sht3x.single_read(true);     // Clock stretching
```

### Fast Response
```cpp
sht3x.set_repeatability(2);  // Low
sht3x.single_read(false);    // No stretching
```

### Continuous Polling
```cpp
sht3x.start_continuous_read(10.0f);  // 10 Hz
// Call continuous_read() as needed
```

### Heater On (Condensation Prevention)
```cpp
sht3x.set_heater(true);
sht3x.single_read(true);
sht3x.set_heater(false);
```

## Error Handling

```cpp
if (!sht3x.check_connection()) {
    std::cerr << "Sensor not connected\n";
    return;
}

if (!sht3x.single_read(true)) {
    std::cerr << "Read failed\n";
    if (sht3x.get_error_count() > 5) {
        sht3x.soft_reset();
    }
}
```

## Integration into sensor_daemon

Edit `InputProcessor.cpp`:
```cpp
// In InputProcessor::poll_all_data()
if (sht3x->single_read(true)) {
    data["temp"] = sht3x->get_temperature();
    data["humid"] = sht3x->get_humidity();
}
```

## I2C Address Selection

### Determine Your Address

```cpp
// Check which address your sensor responds to:
for (uint8_t addr : {0x44, 0x45}) {
    Sht3xDriver test_driver(i2c, addr);
    if (test_driver.init_driver()) {
        printf("Found sensor at 0x%02x\n", addr);
        test_driver.deinit_driver();
    }
}
```

### Hardware Configuration

| ADDR Pin | Address | Use Case |
|----------|---------|----------|
| GND | 0x44 | Default, most common |
| VCC | 0x45 | Multiple sensors on same bus |

## Testing

```bash
# Build tests
cd /home/richardmelvin52/FSS/sensor_daemon/tests/build
cmake .. && make

# Run tests with hardware
./sht3x_test -b /dev/i2c-1 -a 0x44

# Run with custom I2C bus
./sht3x_test --bus /dev/i2c-6 --address 0x45
```

## Known Limitations

- Measurement delay: ~15ms (built-in SHT31 requirement)
- Max continuous rate: 10 Hz
- Serial number retrieval success rate varies
- Long-term stability requires periodic soft resets

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Init fails | Verify I2C bus, power, address |
| Read fails repeatedly | Call `soft_reset()` |
| Connection drops | Check wire connectors, pull-ups |
| Humidity seems stuck | Verify I2C clock speed |
| High error count | Enable heater, reduce rate |

## Performance Tips

1. **Use continuous mode** for high-frequency data (> 1 Hz)
2. **Low repeatability** for power-sensitive applications
3. **Single read** for infrequent measurements
4. **Regular status** checks to detect issues early

## Support

For detailed API documentation, see:
- `sensor_daemon/include/Sht3xDriver.hpp`
- `sensor_daemon/tests/sht3x/Sht3xTest.cpp` (examples)
- LibDriver original docs in `drivers/sensor/sht3x/`
