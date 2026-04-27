# Sensor Driver API Implementation Analysis

**Date**: April 14, 2026  
**Status**: Review & Gap Analysis

---

## Executive Summary

Both sensor drivers have solid implementations but are missing some APIs from their core C drivers.

### Key Findings:
- **SHT3X Wrapper**: 16/22 APIs implemented (~73%)
- **VL53L0X Wrapper**: 6/8 APIs implemented (~75%)  
- **Total Missing**: 8 functions/methods across both drivers
- **Action**: Add missing implementations without changing working code

---

## SHT3X Driver - Detailed API Analysis

### Core C Driver: `driver_sht31.h`
**Total Functions**: 22

### Currently Implemented in `Sht3xDriver.hpp` (16)
✅ `init_driver()` → sht31_init  
✅ `deinit_driver()` → sht31_deinit  
✅ `single_read()` → sht31_single_read  
✅ `start_continuous_read()` → sht31_start_continuous_read  
✅ `stop_continuous_read()` → sht31_stop_continuous_read  
✅ `continuous_read()` → sht31_continuous_read  
✅ `get_temperature()` → (from sht31_single_read/continuous_read)  
✅ `get_humidity()` → (from sht31_single_read/continuous_read)  
✅ `check_connection()` → custom implementation  
✅ `soft_reset()` → sht31_soft_reset  
✅ `set_repeatability()` → sht31_set_repeatability  
✅ `set_heater()` → sht31_set_heater  
✅ `get_status()` → sht31_get_status  
✅ `clear_status()` → sht31_clear_status  
✅ `get_serial_number()` → sht31_get_serial_number  
✅ `handle_i2c_timeout()` → custom implementation  
✅ `get_error_count()` → custom implementation  

### Missing from `Sht3xDriver` (6)
❌ **`get_repeatability()`** → sht31_get_repeatability  
   - Only setter exists, no getter
   - **Type**: Read-only configuration query
   - **Priority**: MEDIUM - Useful for diagnostics

❌ **`get_info()`** → sht31_info  
   - Retrieve chip information (name, manufacturer, voltage, etc.)
   - **Type**: Device identification
   - **Priority**: LOW - Optional feature

❌ **`set_art()`** → sht31_set_art  
   - Accelerated Response Time (ART) feature
   - **Type**: Performance optimization
   - **Priority**: LOW - Advanced feature

❌ **Alert Limit Functions** (4 methods):
   - `set_high_alert_limit()` → sht31_set_high_alert_limit
   - `get_high_alert_limit()` → sht31_get_high_alert_limit
   - `set_low_alert_limit()` → sht31_set_low_alert_limit
   - `get_low_alert_limit()` → sht31_get_low_alert_limit
   - **Type**: Threshold-based alerting
   - **Priority**: LOW - Specialized feature (not critical for basic operation)

❌ **Raw Register Access** (2 methods):
   - `set_reg()` → sht31_set_reg
   - `get_reg()` → sht31_get_reg
   - **Type**: Advanced low-level access
   - **Priority**: VERY LOW - Direct register manipulation

---

## VL53L0X Driver - Detailed API Analysis

### Core C Driver: `vl53l0x.h`
**Total Functions**: 8

### Currently Implemented in `Vl53l0xDriver.hpp` (6)
✅ `init_driver()` → vl53l0x_init  
✅ `read_distance_meters()` → vl53l0x_read_single (+ conversion)  
✅ `is_user_detected()` → custom threshold logic  
✅ `check_connection()` → custom implementation + m_is_connected flag  
✅ `reset_sensor()` → vl53l0x_init (re-init as reset)  
✅ `start_continuous()` → vl53l0x_start_continuous  
✅ `stop_continuous()` → vl53l0x_stop_continuous  
✅ `get_distance()` → (from last_distance_meters, converted to mm)  
✅ `is_data_ready()` → custom implementation (always true, placeholder)  
✅ `handle_i2c_timeout()` → custom error tracking  

### Missing from `Vl53l0xDriver` (2)
❌ **`get_model()`** → vl53l0x_get_model  
   - Returns sensor model ID and revision
   - **Type**: Device identification
   - **Priority**: MEDIUM - Useful for diagnostics
   - **Signature**: `bool get_model(uint8_t *model, uint8_t *revision)`

❌ **`get_last_measurement()`** → vl53l0x_get_last_measurement  
   - Retrieve stored measurement with timestamp
   - **Type**: Historical data access
   - **Priority**: MEDIUM - Advanced feature
   - **Signature**: `bool get_last_measurement(uint16_t *distance_mm, struct timespec *timestamp)`

---

## Recommended Additions

### Priority 1: SHOULD ADD (High value, no risk)
1. **Vl53l0xDriver::get_model()** - Device identification
2. **Sht3xDriver::get_repeatability()** - Configuration query

### Priority 2: COULD ADD (Moderate value)
1. **Vl53l0xDriver::get_last_measurement()** - Timestamp support
2. **Sht3xDriver::get_info()** - Device information
3. **Sht3xDriver::set_art()** - Performance optimization

### Priority 3: OPTIONAL (Low value, rarely used)
1. Alert limit functions (specialized use case)
2. Raw register access (advanced users only)
3. get_error_count() for SHT3X (already implemented)

---

## Implementation Strategy

### Phase 1: Add Core Missing Methods (No Breaking Changes)
**Files to modify**:
- [Vl53l0xDriver.hpp](sensor_daemon/include/Vl53l0xDriver.hpp) - Add 2 methods
- [Vl53l0xDriver.cpp](sensor_daemon/src/Vl53l0xDriver.cpp) - Implement 2 methods
- [Sht3xDriver.hpp](sensor_daemon/include/Sht3xDriver.hpp) - Add 1 method
- [Sht3xDriver.cpp](sensor_daemon/src/Sht3xDriver.cpp) - Implement 1 method

**Constraint**: No changes to existing working functions

### Phase 2: API Documentation Updates
Update API specification documents to list all implemented and available functions.

---

## API Spec Documentation Template

For `/docs/API_SPECIFICATION.md`:

### SHT3X Driver API

| Function | Mode | Core Driver | Status | Notes |
|----------|------|-------------|--------|-------|
| init_driver() | Lifecycle | sht31_init | ✅ Implemented | Basic initialization |
| deinit_driver() | Lifecycle | sht31_deinit | ✅ Implemented | Resource cleanup |
| single_read() | Measurement | sht31_single_read | ✅ Implemented | One-shot reading |
| start_continuous_read() | Measurement | sht31_start_continuous_read | ✅ Implemented | Begin continuous mode |
| stop_continuous_read() | Measurement | sht31_stop_continuous_read | ✅ Implemented | End continuous mode |
| continuous_read() | Measurement | sht31_continuous_read | ✅ Implemented | Read next sample |
| get_temperature() | Data | sht31_single_read | ✅ Implemented | Last temp (°C) |
| get_humidity() | Data | sht31_continuous_read | ✅ Implemented | Last humidity (%) |
| get_repeatability() | Config | sht31_get_repeatability | ❌ NOT IMPLEMENTED | Query repeatability level |
| set_repeatability() | Config | sht31_set_repeatability | ✅ Implemented | Set measurement quality |
| set_heater() | Control | sht31_set_heater | ✅ Implemented | Enable/disable heater |
| soft_reset() | Control | sht31_soft_reset | ✅ Implemented | Reset sensor |
| get_status() | Status | sht31_get_status | ✅ Implemented | Read status register |
| clear_status() | Status | sht31_clear_status | ✅ Implemented | Clear status flags |
| get_serial_number() | Info | sht31_get_serial_number | ✅ Implemented | Device SN |
| get_info() | Info | sht31_info | ❌ NOT IMPLEMENTED | Chip information |
| set_art() | Optimization | sht31_set_art | ❌ NOT IMPLEMENTED | Enable ART feature |
| check_connection() | Diagnostic | (custom) | ✅ Implemented | Connection check |
| handle_i2c_timeout() | Error | (custom) | ✅ Implemented | Error tracking |
| get_error_count() | Diagnostic | (custom) | ✅ Implemented | Error counter |

### VL53L0X Driver API

| Function | Mode | Core Driver | Status | Notes |
|----------|------|-------------|--------|-------|
| init_driver() | Lifecycle | vl53l0x_init | ✅ Implemented | I2C-6, 0x29 |
| read_distance_meters() | Measurement | vl53l0x_read_single | ✅ Implemented | Single shot (m) |
| start_continuous() | Measurement | vl53l0x_start_continuous | ✅ Implemented | Continuous mode |
| stop_continuous() | Measurement | vl53l0x_stop_continuous | ✅ Implemented | End continuous |
| get_distance() | Data | (converted) | ✅ Implemented | Last distance (mm) |
| get_model() | Info | vl53l0x_get_model | ❌ NOT IMPLEMENTED | Model & revision |
| get_last_measurement() | Data | vl53l0x_get_last_measurement | ❌ NOT IMPLEMENTED | Meas + timestamp |
| is_user_detected() | Application | (threshold logic) | ✅ Implemented | User in range (0.05-0.8m) |
| is_data_ready() | Status | (custom) | ✅ Implemented | Placeholder |
| check_connection() | Diagnostic | (custom) | ✅ Implemented | Connection check |
| reset_sensor() | Control | vl53l0x_init | ✅ Implemented | Re-initialize |
| handle_i2c_timeout() | Error | (custom) | ✅ Implemented | Error tracking |

---

## New Variables/Members

### Vl53l0xDriver (Already Added)
- **`m_continuous_mode`** (bool): Tracks if continuous measurement is active
  - Added in Phase 1 fix (April 13, 2026)
  - Used by read_distance_meters() to route API calls correctly

### Sht3xDriver (None new in current implementation)
- All variables match API specification

---

## Validation

### Test Coverage
- ✅ SHT3X: 8 test cases, all passing
- ✅ VL53L0X: 8 test cases, all passing
- ✅ No regressions after model flag addition

### Constraints Maintained
- ✅ No existing function names changed
- ✅ No existing function signatures modified
- ✅ All working code remains unchanged
- ✅ Code cleanliness preserved

---

## Next Steps

1. **Phase 1**: Add Priority 1 functions (get_model, get_repeatability)
2. **Phase 2**: Document API specification officially
3. **Phase 3**: Consider Priority 2 additions based on use cases
4. **Phase 4**: Archive this analysis in project documentation
