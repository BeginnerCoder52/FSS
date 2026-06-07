/**
 * @file InputProcessor.cpp
 * @brief Implementation of the InputProcessor class for real data polling.
 */

#include "InputProcessor.hpp"
#include "Sht3xDriver.hpp"
#include "Vl53l0xDriver.hpp"
#include "DoorSensorDriver.hpp"
#include "I2cHandler.hpp"
#include "GpioHandler.hpp"
#include <ctime>
#include <iostream>
#include <signal.h>
#include <setjmp.h>
#include <cstring>
#include <pthread.h>

/* ------------------------------------------------------------------
 * Signal-level crash recovery for unsafe C driver calls.
 * A crash (SIGSEGV/SIGBUS/SIGFPE/SIGILL) in the C drivers jumps back
 * to a sigsetjmp recovery point instead of killing the process.
 * ------------------------------------------------------------------ */
static sigjmp_buf g_sensor_crash_buf;

static void sensor_fault_handler(int sig)
{
    siglongjmp(g_sensor_crash_buf, sig);
}

static bool g_fault_handlers_installed = false;

static void ensure_fault_handlers()
{
    if (g_fault_handlers_installed) return;

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sensor_fault_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_NODEFER; /* allow catching repeated crashes */

    /* Attempt to install; failures are non-fatal */
    sigaction(SIGSEGV, &sa, nullptr);
    sigaction(SIGBUS,  &sa, nullptr);
    sigaction(SIGFPE,  &sa, nullptr);
    sigaction(SIGILL,  &sa, nullptr);

    g_fault_handlers_installed = true;
}

/*
 * After a siglongjmp recovery from a SHT3x crash, the driver's
 * pthread mutex may still be locked.  This helper resets it so
 * subsequent operations don't deadlock.
 */
extern void sht3x_recover_mutex(); /* defined in Sht3xDriver.cpp */

InputProcessor::InputProcessor()
    : last_poll_timestamp(0.0f)
{
    m_i2c_main = std::make_shared<I2cHandler>("/dev/i2c-1");
    m_i2c_ext = std::make_shared<I2cHandler>("/dev/i2c-6");
    m_i2c_env2 = std::make_shared<I2cHandler>("/dev/i2c-5"); // Add the new I2C-5 bus
    m_gpio_handler = std::make_shared<GpioHandler>("gpiochip4");

    // Both sensors use default address 0x44, separated by physical bus
    sht3x = std::make_unique<Sht3xDriver>(m_i2c_main, 0x44);   // Ngăn mát (Bus 1)
    sht3x_2 = std::make_unique<Sht3xDriver>(m_i2c_env2, 0x44); // Ngăn đông (Bus 5)
    vl53l0x = std::make_unique<Vl53l0xDriver>(m_i2c_ext, 0x29);
    door_sensor = std::make_unique<DoorSensorDriver>(m_gpio_handler, 26); // MC-38 (GPIO 26)
}

InputProcessor::~InputProcessor()
{
}

bool InputProcessor::init_sensors()
{
    ensure_fault_handlers();

    bool success = true;
    try {
        // Initialize First SHT3x environmental sensor (Ngan mat)
        if (sht3x && !sht3x->check_connection()) {
            if (!sht3x->init_driver()) {
                std::cerr << "Failed to initialize SHT3x environmental sensor" << std::endl;
                success = false;
            }
        }

        // Initialize Secondary SHT3x environmental sensor (Ngan dong)
        if (sht3x_2 && !sht3x_2->check_connection()) {
            if (!sht3x_2->init_driver()) {
                std::cerr << "Failed to initialize Secondary SHT3x sensor on I2C-5" << std::endl;
                success = false;
            }
        }

        // Initialize VL53L0x distance sensor
        if (!vl53l0x || !vl53l0x->init_driver())
        {
            std::cerr << "Failed to initialize VL53L0x distance sensor" << std::endl;
            success = false;
        }

        // Initialize Door sensor
        if (!door_sensor || !door_sensor->init_driver())
        {
            std::cerr << "Failed to initialize Door sensor" << std::endl;
            success = false;
        }

    } catch (const std::exception& e) {
        std::cerr << "InputProcessor init_sensors exception: " << e.what() << std::endl;
        success = false;
    } catch (...) {
        std::cerr << "InputProcessor init_sensors unknown exception" << std::endl;
        success = false;
    }

    return success;
}

/* ------------------------------------------------------------------
 * Per-sensor guarded read macro.
 * Wraps a sensor operation with:
 *   1. sigsetjmp/siglongjmp – recover from C-level signals (SEGV/BUS/FPE/ILL)
 *   2. try/catch – recover from C++ exceptions
 * Ensures one failing sensor never takes down the entire process.
 * ------------------------------------------------------------------ */
#define GUARDED_SENSOR(name_, fallback_expr_, ...)                     \
    do {                                                               \
        int _sig_ = sigsetjmp(g_sensor_crash_buf, 1);                 \
        if (_sig_ == 0) {                                              \
            try {                                                      \
                __VA_ARGS__                                            \
            } catch (const std::exception &_e_) {                      \
                std::cerr << "ERR: " << name_                          \
                          << " exception: " << _e_.what() << std::endl;\
                fallback_expr_;                                        \
            } catch (...) {                                            \
                std::cerr << "ERR: " << name_                          \
                          << " unknown exception" << std::endl;        \
                fallback_expr_;                                        \
            }                                                          \
        } else {                                                       \
            std::cerr << "CRASH: " << name_                            \
                      << " fault (signal " << _sig_ << ")" << std::endl;\
            fallback_expr_;                                            \
        }                                                              \
    } while (0)

std::map<std::string, float> InputProcessor::poll_all_data()
{
    std::map<std::string, float> data;

    // Update timestamp with current Unix time
    last_poll_timestamp = static_cast<float>(std::time(nullptr));
    data["timestamp"] = last_poll_timestamp;

    // ---- Defaults ----
    data["temp"]     = 0.0f;
    data["humid"]    = 0.0f;
    data["temp_2"]   = 0.0f;
    data["humid_2"]  = 0.0f;
    data["distance"] = 0.0f;
    data["presence"] = 0.0f;
    data["door"]     = 0.0f;

    /* -----------------------------------------------------------------
     * 1. SHT3x PRIMARY (temperature / humidity – highest priority)
     *    Auto-reconnect on disconnect, guarded against crashes.
     * -------------------------------------------------------------- */
    if (sht3x)
    {
        GUARDED_SENSOR("SHT3x-primary",
            /* fallback: leave defaults */,
            {
                if (!sht3x->check_connection()) {
                    sht3x_recover_mutex();
                    sht3x->init_driver();
                }
                if (sht3x->single_read(true)) {
                    data["temp"]  = sht3x->get_temperature();
                    data["humid"] = sht3x->get_humidity();
                }
            }
        );
    }

    /* -----------------------------------------------------------------
     * 2. SHT3x SECONDARY (temperature / humidity – highest priority)
     * -------------------------------------------------------------- */
    if (sht3x_2)
    {
        GUARDED_SENSOR("SHT3x-secondary",
            /* fallback: leave defaults */,
            {
                if (!sht3x_2->check_connection()) {
                    sht3x_recover_mutex();
                    sht3x_2->init_driver();
                }
                if (sht3x_2->single_read(true)) {
                    data["temp_2"]  = sht3x_2->get_temperature();
                    data["humid_2"] = sht3x_2->get_humidity();
                }
            }
        );
    }

    /* -----------------------------------------------------------------
     * 3. VL53L0X distance / presence sensor
     * -------------------------------------------------------------- */
    if (vl53l0x)
    {
        GUARDED_SENSOR("VL53L0X",
            /* fallback: leave defaults */,
            {
                if (!vl53l0x->check_connection()) {
                    vl53l0x->init_driver();
                }
                data["distance"] = vl53l0x->read_distance_meters();
                data["presence"] = vl53l0x->is_user_detected() ? 1.0f : 0.0f;
            }
        );
    }

    /* -----------------------------------------------------------------
     * 4. Door sensor (MC-38)
     * -------------------------------------------------------------- */
    if (door_sensor)
    {
        GUARDED_SENSOR("Door",
            /* fallback: leave defaults */,
            {
                data["door"] = door_sensor->is_open() ? 1.0f : 0.0f;
            }
        );
    }

    return data;
}

void InputProcessor::get_env_data(float &temp, float &hum)
{
    try
    {
        if (sht3x)
        {
            temp = sht3x->get_temperature();
            hum = sht3x->get_humidity();
        }
        else
        {
            temp = 0.0f;
            hum = 0.0f;
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "InputProcessor get_env_data exception: " << e.what() << std::endl;
        temp = 0.0f;
        hum = 0.0f;
    }
    catch (...)
    {
        std::cerr << "InputProcessor get_env_data unknown exception" << std::endl;
        temp = 0.0f;
        hum = 0.0f;
    }
}

uint16_t InputProcessor::get_distance_data()
{
    try
    {
        if (vl53l0x)
        {
            return vl53l0x->get_distance();
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "InputProcessor get_distance_data exception: " << e.what() << std::endl;
    }
    catch (...)
    {
        std::cerr << "InputProcessor get_distance_data unknown exception" << std::endl;
    }
    return 0;
}

bool InputProcessor::get_door_status()
{
    try
    {
        if (door_sensor)
        {
            return door_sensor->is_open();
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "InputProcessor get_door_status exception: " << e.what() << std::endl;
    }
    catch (...)
    {
        std::cerr << "InputProcessor get_door_status unknown exception" << std::endl;
    }
    return false;
}
