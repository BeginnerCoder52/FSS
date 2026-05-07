/**
 * @file Sht3xDriver.cpp
 * @brief Implementation of the Sht3xDriver C++ wrapper for LibDriver SHT31.
 *
 * Bridges the C driver API to C++ and integrates with the sensor_daemon
 * I2C handler for communication.
 */

#include "Sht3xDriver.hpp"
#include "I2cHandler.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <cstring>
#include <mutex>

extern "C"
{
#include "driver_sht31.h"
}

/* Global state for C driver */
static std::mutex g_driver_mutex;
static I2cHandler* g_active_i2c = nullptr;

/* Bridge functions for LibDriver C API */
extern "C"
{
    /**
     * I2C initialization callback.
     */
    uint8_t iic_init(void)
    {
        return g_active_i2c && g_active_i2c->open_bus() ? 0 : 1;
    }

    /**
     * I2C deinitialization callback.
     */
    uint8_t iic_deinit(void)
    {
        if (g_active_i2c)
        {
            g_active_i2c->close_bus();
            return 0;
        }
        return 1;
    }

    /**
     * I2C read with 16-bit register address.
     */
    uint8_t iic_read_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
    {
        if (!g_active_i2c)
        {
            return 1;
        }

        /* Use I2cHandler's atomic 16-bit address transaction */
        if (!g_active_i2c->read_address16(addr, reg, buf, len))
        {
            return 1;
        }

        return 0;
    }

    /**
     * I2C write with 16-bit register address.
     */
    uint8_t iic_write_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
    {
        if (!g_active_i2c)
        {
            return 1;
        }

        /* Use I2cHandler's atomic 16-bit address transaction */
        if (!g_active_i2c->write_address16(addr, reg, buf, len))
        {
            return 1;
        }

        return 0;
    }

    // uint8_t iic_scl_read_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len) {
    //     if (!g_active_i2c) return 1;
    //     return g_active_i2c->read_address16(addr, reg, buf, len) ? 0 : 1;
    // }
    
    /**
     * Delay milliseconds callback.
     */
    void delay_ms(uint32_t ms)
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(ms));
    }

    /**
     * Debug print callback.
     */
    void debug_print(const char *const fmt, ...)
    {
        /* Optional - can be enabled for debugging */
    }

    /**
     * Receive callback for alerts.
     */
    void receive_callback(uint16_t type)
    {
        (void)type;
    }
}

Sht3xDriver::Sht3xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address)
    : m_i2c(i2c_handler), device_address(i2c_address), last_temperature(0.0f),
      last_humidity(0.0f), m_is_connected(false), m_error_count(0),
      m_driver_handle(nullptr)
{
    m_driver_handle = new sht31_handle_t();
    memset(m_driver_handle, 0, sizeof(sht31_handle_t));
}

Sht3xDriver::~Sht3xDriver()
{
    if (m_is_connected)
    {
        deinit_driver();
    }
    // Safely free the handle
    if (m_driver_handle != nullptr)
    {
        delete static_cast<sht31_handle_t *>(m_driver_handle);
        m_driver_handle = nullptr;
    }
}



bool Sht3xDriver::init_driver()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);

    /* CRITICAL FIX: Do not re-initialize if already running to prevent loop crashing */
    if (m_is_connected) {
        return true;
    }
    
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);
    /* Initialize handle structure */
    DRIVER_SHT31_LINK_INIT(g_sht31_handle, sht31_handle_t);

    /* Link I2C callbacks */
    DRIVER_SHT31_LINK_IIC_INIT(g_sht31_handle, iic_init);
    DRIVER_SHT31_LINK_IIC_DEINIT(g_sht31_handle, iic_deinit);
    DRIVER_SHT31_LINK_IIC_READ_ADDRESS16(g_sht31_handle, iic_read_address16);
    DRIVER_SHT31_LINK_IIC_WRITE_ADDRESS16(g_sht31_handle, iic_write_address16);

    /* Link utility callbacks */
    DRIVER_SHT31_LINK_DELAY_MS(g_sht31_handle, delay_ms);
    DRIVER_SHT31_LINK_DEBUG_PRINT(g_sht31_handle, debug_print);
    DRIVER_SHT31_LINK_RECEIVE_CALLBACK(g_sht31_handle, receive_callback);

    /* Set I2C address pin based on device address */
    sht31_address_t addr_pin = (device_address == 0x44) ? SHT31_ADDRESS_0 : SHT31_ADDRESS_1;
    /* CRITICAL FIX: Send a BREAK command to snap the sensor out of a stuck continuous loop */
    if (g_active_i2c && g_active_i2c->open_bus()) {
        g_active_i2c->write_address16(addr_pin, 0x3093, nullptr, 0); // 0x3093 is the Break command
        delay_ms(20); // Give the sensor time to halt
    }
    
    if (sht31_set_addr_pin(g_sht31_handle, addr_pin) != 0)
    {
        m_is_connected = false;
        return false;
    }

    /* Initialize driver */
    if (sht31_init(g_sht31_handle) != 0)
    {
        m_is_connected = false;
        return false;
    }

    /* Configure sensor for operation */
    delay_ms(10);

    /* Set repeatability to high */
    if (sht31_set_repeatability(g_sht31_handle, SHT31_REPEATABILITY_HIGH) != 0)
    {
        sht31_deinit(g_sht31_handle);
        m_is_connected = false;
        return false;
    }

    /* Set auto-recovered from voltage error */
    if (sht31_set_art(g_sht31_handle) != 0)
    {
        sht31_deinit(g_sht31_handle);
        m_is_connected = false;
        return false;
    }

    /* Disable heater by default */
    if (sht31_set_heater(g_sht31_handle, SHT31_BOOL_FALSE) != 0)
    {
        sht31_deinit(g_sht31_handle);
        m_is_connected = false;
        return false;
    }

    m_is_connected = true;
    m_error_count = 0;
    return true;
}

bool Sht3xDriver::deinit_driver()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return true;
    }

    if (sht31_deinit(g_sht31_handle) == 0)
    {
        m_is_connected = false;
        return true;
    }

    return false;
}

bool Sht3xDriver::single_read(bool clock_stretching)
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    uint16_t temperature_raw, humidity_raw;
    float temperature, humidity;

    sht31_bool_t clock_stretch = clock_stretching ? SHT31_BOOL_TRUE : SHT31_BOOL_FALSE;

    if (sht31_single_read(g_sht31_handle, clock_stretch, &temperature_raw, &temperature,
                          &humidity_raw, &humidity) == 0)
    {
        last_temperature = temperature;
        last_humidity = humidity;
        m_error_count = 0;
        return true;
    }
    else
    {
        m_error_count++;
        if (m_error_count > 5)
        {
            m_is_connected = false;
        }
        return false;
    }
}

bool Sht3xDriver::start_continuous_read(float rate)
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    /* Map rate to driver constants */
    sht31_rate_t driver_rate;
    if (rate <= 0.5f)
    {
        driver_rate = SHT31_RATE_0P5HZ;
    }
    else if (rate <= 1.0f)
    {
        driver_rate = SHT31_RATE_1HZ;
    }
    else if (rate <= 2.0f)
    {
        driver_rate = SHT31_RATE_2HZ;
    }
    else if (rate <= 4.0f)
    {
        driver_rate = SHT31_RATE_4HZ;
    }
    else
    {
        driver_rate = SHT31_RATE_10HZ;
    }

    if (sht31_start_continuous_read(g_sht31_handle, driver_rate) == 0)
    {
        m_error_count = 0;
        return true;
    }

    m_error_count++;
    return false;
}

bool Sht3xDriver::stop_continuous_read()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    return sht31_stop_continuous_read(g_sht31_handle) == 0;
}

bool Sht3xDriver::continuous_read()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    uint16_t temperature_raw, humidity_raw;
    float temperature, humidity;

    if (sht31_continuous_read(g_sht31_handle, &temperature_raw, &temperature,
                              &humidity_raw, &humidity) == 0)
    {
        last_temperature = temperature;
        last_humidity = humidity;
        m_error_count = 0;
        return true;
    }
    else
    {
        m_error_count++;
        if (m_error_count > 5)
        {
            m_is_connected = false;
        }
        return false;
    }
}

float Sht3xDriver::get_temperature() const
{
    return last_temperature;
}

float Sht3xDriver::get_humidity() const
{
    return last_humidity;
}

bool Sht3xDriver::check_connection() const
{
    return m_is_connected;
}

bool Sht3xDriver::soft_reset()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    if (sht31_soft_reset(g_sht31_handle) == 0)
    {
        delay_ms(2);
        return true;
    }

    return false;
}

bool Sht3xDriver::set_repeatability(uint8_t repeatability)
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    sht31_repeatability_t repeat;
    switch (repeatability)
    {
    case 1:
        repeat = SHT31_REPEATABILITY_MEDIUM;
        break;
    case 2:
        repeat = SHT31_REPEATABILITY_LOW;
        break;
    case 0:
    default:
        repeat = SHT31_REPEATABILITY_HIGH;
        break;
    }

    return sht31_set_repeatability(g_sht31_handle, repeat) == 0;
}

bool Sht3xDriver::get_repeatability(uint8_t *repeatability)
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected || repeatability == nullptr)
    {
        return false;
    }

    sht31_repeatability_t repeat;
    if (sht31_get_repeatability(g_sht31_handle, &repeat) != 0)
    {
        return false;
    }

    switch (repeat)
    {
    case SHT31_REPEATABILITY_MEDIUM:
        *repeatability = 1;
        break;
    case SHT31_REPEATABILITY_LOW:
        *repeatability = 2;
        break;
    case SHT31_REPEATABILITY_HIGH:
    default:
        *repeatability = 0;
        break;
    }

    return true;
}

bool Sht3xDriver::set_heater(bool enable)
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    sht31_bool_t heater_enable = enable ? SHT31_BOOL_TRUE : SHT31_BOOL_FALSE;
    return sht31_set_heater(g_sht31_handle, heater_enable) == 0;
}

uint16_t Sht3xDriver::get_status()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return 0;
    }

    uint16_t status = 0;
    sht31_get_status(g_sht31_handle, &status);
    return status;
}

bool Sht3xDriver::clear_status()
{
    std::lock_guard<std::mutex> lock(g_driver_mutex);
    g_active_i2c = m_i2c.get(); 
    sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

    if (!m_is_connected)
    {
        return false;
    }

    return sht31_clear_status(g_sht31_handle) == 0;
}

// bool Sht3xDriver::get_serial_number(uint8_t sn[4])
// {
//     std::lock_guard<std::mutex> lock(g_driver_mutex);
//     g_active_i2c = m_i2c.get(); 
//     sht31_handle_t* g_sht31_handle = static_cast<sht31_handle_t*>(m_driver_handle);

//     if (!m_is_connected)
//     {
//         return false;
//     }

//     return sht31_get_serial_number(g_sht31_handle, sn) == 0;
// }

void Sht3xDriver::handle_i2c_timeout()
{
    m_error_count++;
    if (m_error_count > 10)
    {
        m_is_connected = false;
    }
}

int Sht3xDriver::get_error_count() const
{
    return m_error_count;
}
