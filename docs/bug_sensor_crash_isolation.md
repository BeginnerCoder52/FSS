# Bug: Sensor failure crashes the entire process

## Description

When any sensor encounters a device error (I2C communication failure, hardware
timeout, or unexpected fault in the C driver layer), the entire sensor daemon
process crashes instead of gracefully degrading.

## Root Cause

Two distinct failure modes both resulted in process death:

1. **C-level signal crashes** — The C sensor drivers (`vl53l0x_init`,
   `sht31_single_read`, etc.) make raw `ioctl()` calls on I2C file descriptors.
   A bad bus state or device fault can trigger `SIGSEGV` / `SIGBUS` / `SIGFPE`.
   These signals **cannot be caught by `try`/`catch`** and previously killed the
   process immediately.

2. **Missing `catch(...)` guards** — Several call sites only caught
   `std::exception`. Any other exception type (e.g. `std::bad_alloc` or a
   non-standard throw) propagated upward uncaught and called
   `std::terminate()`, crashing the process.

Additionally, there was no reconnection mechanism: after 5 consecutive errors a
sensor was marked disconnected permanently. The daemon would either stop
entirely (after 3 failed `recover_from_fault()` attempts) or silently lose the
sensor forever.

## Changes

### 1. Signal-level crash recovery (`InputProcessor.cpp`)

Added `sigaction` handlers for `SIGSEGV`, `SIGBUS`, `SIGFPE`, `SIGILL` using
`sigsetjmp` / `siglongjmp`. Each sensor read in `poll_all_data()` is now wrapped
with:

```
GUARDED_SENSOR("SHT3x-primary", fallback, { sensor->read(...) })
```

If the C driver triggers a signal, `siglongjmp` returns to the guard point with
the signal number. The sensor defaults to 0.0f and **the process continues**
without crashing.

### 2. Recoverable mutex (`Sht3xDriver.cpp`)

Replaced `std::mutex` with `pthread_mutex_t` to allow explicit recovery after a
signal jump. A new `sht3x_recover_mutex()` function uses `trylock` to detect a
leaked lock and release it, preventing deadlock on the next poll cycle.

### 3. `catch(...)` everywhere

Added `catch(...)` to every `try` block in:
- `main.cpp` — top-level entry point
- `SensorDaemonMain.cpp` — `init_app()`, `start_app()`, `stop_app()`,
  `run_main_loop()`, `process_environment_data()`, `recover_from_fault()`,
  `log_system_status()`
- `InputProcessor.cpp` — `init_sensors()`, `get_env_data()`,
  `get_distance_data()`, `get_door_status()`, and per-sensor inside
  `poll_all_data()`

### 4. Per-sensor failure isolation (`InputProcessor.cpp`)

`poll_all_data()` was restructured from a single `try` block around all sensor
reads to **individual guarded reads** for each sensor. One sensor failing
(exception or signal) no longer discards data from the other sensors. Default
values (0.0f) are used for the failed sensor.

### 5. Auto-reconnect on disconnect

| Driver | Mechanism |
|--------|-----------|
| `Sht3xDriver` | `single_read()` / `continuous_read()` call `init_driver()` when `m_is_connected == false` |
| `Vl53l0xDriver` | `read_distance_meters()` calls `init_driver()` when `m_is_connected == false` |

Temperature/humidity sensors (SHT3x) are treated as highest priority — the
mutex is recovered and reinit is attempted every poll cycle.

### 6. Removed unreachable code (`main.cpp`)

Removed `app.run_main_loop()` after `start_app()`. `start_app()` already calls
`run_main_loop()` internally (it blocks until `is_running` becomes false), so
the second call was dead code.

## Files Modified

| File | Changes |
|------|---------|
| `src/InputProcessor.cpp` | Signal handlers, `GUARDED_SENSOR` macro, per-sensor isolation, `catch(...)` |
| `src/SensorDaemonMain.cpp` | `catch(...)` in all methods |
| `src/Sht3xDriver.cpp` | `pthread_mutex_t` + `sht3x_recover_mutex()`, auto-reconnect, `Sht3xMutexLock` RAII |
| `src/Vl53l0xDriver.cpp` | Auto-reconnect on disconnect |
| `src/main.cpp` | Top-level `catch(...)`, removed unreachable call |

## Testing

- Each modified source file compiles cleanly with `-fsyntax-only`
- No functional changes to normal (non-fault) operation — guards are
  transparent when no signal/exception occurs
- On actual hardware: a sensor I2C fault now logs `CRASH: <sensor> fault
  (signal 11)` and continues polling the remaining sensors
