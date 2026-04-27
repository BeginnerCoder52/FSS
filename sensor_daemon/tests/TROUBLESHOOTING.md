## SHT31 Test Troubleshooting Guide

### Current Status
✅ **Tests: 10/10 PASSING** on `/dev/i2c-1` at address `0x44`

```
Initialization Test         [PASS]
Connection Check Test       [PASS]
Single Read Test            [PASS] - Temp: 32.13°C, Humidity: 62.32%
Continuous Read Test        [PASS]
Set Repeatability Test      [PASS]
Set Heater Test             [PASS]
Soft Reset Test             [PASS]
Status Register Test        [PASS]
Serial Number Test          [PASS] - 0x87ccbeb0
Error Handling Test         [PASS]
```

### Problem: Initialization Failed on `/dev/i2c-0`

**Root Cause**: Wrong I2C bus device

### I2C Bus Assignment (Per Hardware)

| Sensor | Bus | GPIO Pins | Device Path |
|--------|-----|-----------|-------------|
| **SHT31** (Temperature/Humidity) | 1 | SDA=GPIO2, SCL=GPIO3 | `/dev/i2c-1` |
| **VL53L0X** (Distance) | 6 | SDA=GPIO22, SCL=GPIO23 | `/dev/i2c-6` |
| **MC-38** (Door) | GPIO | GPIO26 | N/A |

### How to Verify Sensor Connection

```bash
# 1. List available I2C busses
ls /dev/i2c-*

# 2. Scan I2C bus 1 for devices
i2cdetect -y 1

# Expected output:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:                         -- -- -- -- -- -- -- -- 
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 40: -- -- -- -- 44 -- -- -- -- -- -- -- -- -- -- --  <- SHT31 at 0x44
# 50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 70: -- -- -- -- -- -- -- --

# 3. If sensor is at address 0x45 (ADDR pin to VCC), use:
./sht3x_test -b /dev/i2c-1 -a 0x45
```

### Test Command Reference

```bash
# Default (I2C-1, Address 0x44)
./sht3x_test

# Explicit addresses
./sht3x_test -b /dev/i2c-1 -a 0x44  # ADDR pin -> GND
./sht3x_test -b /dev/i2c-1 -a 0x45  # ADDR pin -> VCC

# Custom I2C bus
./sht3x_test -b /dev/i2c-6 -a 0x44

# Show help
./sht3x_test --help
```

### Pinout Verification Checklist

- [ ] SHT31 **VCC** (power) connected to **3.3V** (Pin 1)
- [ ] SHT31 **GND** (ground) connected to **GND** (Pin 9)
- [ ] SHT31 **SDA** (data) connected to **GPIO2** (Pin 3)
- [ ] SHT31 **SCL** (clock) connected to **GPIO3** (Pin 5)
- [ ] Pullup resistors (~4.7kΩ) on SDA and SCL lines
- [ ] ADDR pin setup matches address (GND→0x44, VCC→0x45)

### Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| **"I2C device not found"** | Check device exists: `ls /dev/i2c-1` |
| **"Initialization failed"** | Run `i2cdetect -y 1` to verify sensor present |
| **No 0x44/0x45 in scan** | Check power (VCC/GND) and SDA/SCL connections |
| **I2C-6 not found** | Enable in `/boot/config.txt`: `dtoverlay=i2c6,pins_22_23` |
| **Permission denied** | Add user to i2c group: `sudo usermod -aG i2c $USER` |

### Reading Test Output Format

```
[PASS] - Green - Test succeeded
[FAIL] - Red - Test failed

Single Read Test            [PASS]
  Temperature: 32.13°C      <- Last measured value
  Humidity: 62.32%          <- Last measured value

Serial Number Test          [PASS]
  Serial Number: 0x87ccbeb0 <- Device unique ID
```

### Next Steps

1. ✅ **Verify hardware**: Check I2C connections and address
2. ✅ **Run diagnostics**: `i2cdetect -y 1`
3. ✅ **Run tests**: `./sht3x_test -b /dev/i2c-1 -a 0x44`
4. ✅ **Monitor output**: Temperature and humidity readings
5. ✅ **Integrate to daemon**: sensor_daemon will use working driver

### Real-time Monitoring

After confirming tests pass, monitor sensor in real-time:

```bash
# Read once per second
while true; do
  /dev/i2c-1 ./read_sht31 0x44
  sleep 1
done
```

### Support

- Check `/home/richardmelvin52/FSS/drivers/sensor/README_PINOUT.md` for pinout diagram
- Review `SHT3X_QUICK_REFERENCE.md` for API usage
- Check test source: `sensor_daemon/tests/sht3x/Sht3xTest.cpp`
