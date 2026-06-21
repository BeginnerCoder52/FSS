# Chapter 3 — TemperatureMonitor: Giám sát Nhiệt độ và Phát hiện Bất thường

## 3.x Bộ Giám sát Nhiệt độ (TemperatureMonitor)

### 3.x.1 Vai trò

TemperatureMonitor là thành phần trong SensorDaemon chịu trách nhiệm giám sát nhiệt độ tủ lạnh theo thời gian thực, phát hiện các bất thường và cảnh báo người dùng qua D-Bus.

### 3.x.2 Kiến trúc

```
[SHT3x Sensor] ──I2C──→ [Sht3xDriver] ──→ [InputProcessor]
                                                │
                                          (poll 5000ms)
                                                │
                                           [TemperatureMonitor]
                                                │
                                    ┌───────────┼───────────┐
                                    │           │           │
                               Temperature   Anomaly    Status
                               Reading      Detection  Reporting
                                    │           │           │
                                    └───────────┼───────────┘
                                                │
                                           [OutputProcessor]
                                                │
                                          D-Bus Signal
```

### 3.x.3 Luồng xử lý

```
1. InputProcessor.poll_sensors()
   └─ Gọi Sht3xDriver.single_read() mỗi 5000ms
      ├─ Đọc nhiệt độ (°C)
      └─ Đọc độ ẩm (%)

2. TemperatureMonitor.evaluate()
   ├─ So sánh với ngưỡng (thresholds)
   ├─ Ghi log environment_log
   └─ Nếu bất thường → emit cảnh báo

3. OutputProcessor.emit_sensor_data()
   ├─ Broadcast EnvironmentDataUpdated (bình thường)
   └─ Broadcast TemperatureAnomaly (nếu có bất thường)
```

### 3.x.4 Quy tắc Phát hiện Bất thường (Anomaly Rules)

| # | Điều kiện | Mức độ | Hành động |
|---|-----------|--------|-----------|
| 1 | Nhiệt độ > 8°C | Cảnh báo (WARNING) | Ghi log + Broadcast `TemperatureAnomaly` với `severity=warning` |
| 2 | Nhiệt độ > 12°C | Nguy hiểm (CRITICAL) | Ghi log + Broadcast `TemperatureAnomaly` với `severity=critical` |
| 3 | Nhiệt độ < 0°C | Cảnh báo (WARNING) | Ghi log + Broadcast `TemperatureAnomaly` với `severity=warning` |
| 4 | Nhiệt độ tăng > 3°C trong 30s | Bất thường (UNUSUAL) | Ghi log + Broadcast `TemperatureAnomaly` với `severity=unusual` |
| 5 | Sai số đọc > 3 lần liên tiếp | Lỗi cảm biến (ERROR) | Ghi log + Broadcast `SensorError` |
| 6 | Độ ẩm > 80% kèm nhiệt độ > 6°C | Cảnh báo môi trường | Ghi log + Broadcast `EnvironmentWarning` |

**Ngưỡng mặc định**:
- Nhiệt độ lý tưởng: 2°C – 6°C (tủ lạnh)
- Chu kỳ đọc: 5000 ms
- Cửa sổ phát hiện tăng đột biến: 30 giây (6 mẫu)

### 3.x.5 D-Bus Signal Specification

#### Signal: `EnvironmentDataUpdated`

Broadcast khi có dữ liệu cảm biến mới (bao gồm cả bình thường và bất thường).

```xml
<signal name="EnvironmentDataUpdated">
    <arg name="payload" type="s" direction="out"/>
    <!-- JSON payload:
    {
        "type": "EnvironmentDataUpdated",
        "temperature": 4.5,
        "humidity": 65.2,
        "is_anomaly": false,
        "anomaly_type": null,
        "severity": null,
        "timestamp": "2026-06-21T10:30:00Z"
    }
    -->
</signal>
```

#### Signal: `TemperatureAnomaly`

Broadcast khi phát hiện bất thường nhiệt độ.

```xml
<signal name="TemperatureAnomaly">
    <arg name="payload" type="s" direction="out"/>
    <!-- JSON payload:
    {
        "type": "TemperatureAnomaly",
        "temperature": 11.2,
        "humidity": 72.1,
        "threshold": 8.0,
        "severity": "critical",
        "rule_id": 2,
        "rule_description": "Temperature exceeds CRITICAL threshold (12°C)",
        "timestamp": "2026-06-21T10:30:00Z"
    }
    -->
</signal>
```

#### Signal: `SensorError`

Broadcast khi cảm biến lỗi (không đọc được, timeout, mất kết nối).

```xml
<signal name="SensorError">
    <arg name="payload" type="s" direction="out"/>
    <!-- JSON payload:
    {
        "type": "SensorError",
        "sensor": "SHT3x",
        "error_code": 5,
        "error_type": "i2c_timeout",
        "consecutive_failures": 4,
        "timestamp": "2026-06-21T10:30:00Z"
    }
    -->
</signal>
```

### 3.x.6 Cấu hình (Config)

Các ngưỡng và tham số được định nghĩa trong hằng số C++ tại `SensorDaemon`:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `TEMP_WARNING_LOW` | 0.0°C | Ngưỡng cảnh báo thấp |
| `TEMP_WARNING_HIGH` | 8.0°C | Ngưỡng cảnh báo cao |
| `TEMP_CRITICAL_HIGH` | 12.0°C | Ngưỡng nguy hiểm cao |
| `TEMP_SPIKE_DELTA` | 3.0°C | Ngưỡng tăng đột biến |
| `TEMP_SPIKE_WINDOW_MS` | 30000 ms | Cửa sổ phát hiện đột biến |
| `HUMIDITY_WARNING` | 80.0% | Ngưỡng cảnh báo độ ẩm |
| `MAX_CONSECUTIVE_ERRORS` | 3 | Số lần lỗi liên tiếp tối đa |
| `POLLING_RATE_ENV_MS` | 5000 ms | Chu kỳ đọc cảm biến môi trường |

### 3.x.7 D-Bus Monitor (Debug)

```bash
# Monitor tất cả signals từ SensorDaemon
dbus-monitor --system "interface=vn.edu.uit.FSS.Interface"

# Lọc signal cụ thể
dbus-monitor --system "member=TemperatureAnomaly"
dbus-monitor --system "member=EnvironmentDataUpdated"

# Kiểm tra service đã đăng ký
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep SensorDaemon
```
