# Sensor Pinout Mapping

This document describes the physical connections between the sensors and the Raspberry Pi 4B.

## I2C Bus Configuration
- **I2C-1 (Default):** Used for the SHT3x environmental sensor.
- **I2C-6 (Extended):** Used for the VL53L0X distance sensor.

## Pinout Table

| Component | Component Pin | Pi 4B Pin (Physical) | Pi 4B Pin (BCM) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Fan** | VCC / GND | 4 / 6 | 5V / Ground | Already in use |
| **SHT3x** | VCC | 1 | 3.3V | I2C-1 (Default Bus) |
| | GND | 9 | Ground | |
| | SDA | 3 | GPIO 2 | Default I2C SDA |
| | SCL | 5 | GPIO 3 | Default I2C SCL |
| **VL53L0X** | VCC | 17 | 3.3V | I2C-6 (Extended Bus) |
| | GND | 20 | Ground | Pin 20 near pins 22/24 |
| | SDA | 22 | GPIO 22 | Extended I2C SDA |
| | SCL | 24 | GPIO 23 | Extended I2C SCL |
| **MC-38** | Terminal 1 | 37 | GPIO 26 | Magnetic Door Sensor |
| | Terminal 2 | 39 | Ground | |

## Software Configuration
Ensure that I2C-6 is enabled in `/boot/config.txt` (or `/boot/firmware/config.txt` on newer OS versions) by adding the following line:
```
dtoverlay=i2c6,pins_22_23
```
