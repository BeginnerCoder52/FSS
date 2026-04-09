/**
 * @file Sht3xDriver.cpp
 * @brief Implementation of the Sht3xDriver class using LibDriver SHT31.
 */

#include "Sht3xDriver.hpp"
#include "I2cHandler.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <cstring>

// Include original driver header
#include "driver_sht31.h"

// Static handle for the C driver callbacks
static sht31_handle_t g_sht31_handle;
static std::shared_ptr<I2cHandler> g_i2c_ptr = nullptr;

// Bridge functions for LibDriver C API
extern "C" {
    uint8_t iic_init(void) { return 0; }
    uint8_t iic_deinit(void) { return 0; }
    uint8_t iic_read_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len) {
        if (!g_i2c_ptr) return 1;
        if (!g_i2c_ptr->set_slave_address(addr >> 1)) return 1;
        
        uint8_t reg_buf[2];
        reg_buf[0] = (reg >> 8) & 0xFF;
        reg_buf[1] = reg & 0xFF;
        
        if (!g_i2c_ptr->write_data(reg_buf, 2)) return 1;
        // SHT31 needs delay after measurement command
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        return g_i2c_ptr->read_data(buf, len) ? 0 : 1;
    }
    uint8_t iic_write_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len) {
        if (!g_i2c_ptr) return 1;
        if (!g_i2c_ptr->set_slave_address(addr >> 1)) return 1;
        
        uint8_t total_buf[2 + 32]; // command + data
        total_buf[0] = (reg >> 8) & 0xFF;
        total_buf[1] = reg & 0xFF;
        if (len > 0) memcpy(&total_buf[2], buf, len);
        
        return g_i2c_ptr->write_data(total_buf, 2 + len) ? 0 : 1;
    }
    void delay_ms(uint32_t ms) {
        std::this_thread::sleep_for(std::chrono::milliseconds(ms));
    }
    void debug_print(const char *const fmt, ...) {
        // Optional logging
    }
}

Sht3xDriver::Sht3xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address)
    : m_i2c(i2c_handler), device_address(i2c_address), last_temperature(0.0f), last_humidity(0.0f),
      m_is_connected(false), m_error_count(0) {
    g_i2c_ptr = m_i2c;
}

Sht3xDriver::~Sht3xDriver() {
    sht31_deinit(&g_sht31_handle);
}

bool Sht3xDriver::init_driver() {
    DRIVER_SHT31_LINK_INIT(&g_sht31_handle, sht31_handle_t);
    DRIVER_SHT31_LINK_IIC_INIT(&g_sht31_handle, iic_init);
    DRIVER_SHT31_LINK_IIC_DEINIT(&g_sht31_handle, iic_deinit);
    DRIVER_SHT31_LINK_IIC_READ_ADDRESS16(&g_sht31_handle, iic_read_address16);
    DRIVER_SHT31_LINK_IIC_WRITE_ADDRESS16(&g_sht31_handle, iic_write_address16);
    DRIVER_SHT31_LINK_DELAY_MS(&g_sht31_handle, delay_ms);
    DRIVER_SHT31_LINK_DEBUG_PRINT(&g_sht31_handle, debug_print);

    if (device_address == 0x44) {
        sht31_set_addr_pin(&g_sht31_handle, SHT31_ADDRESS_0);
    } else {
        sht31_set_addr_pin(&g_sht31_handle, SHT31_ADDRESS_1);
    }

    if (sht31_init(&g_sht31_handle) != 0) {
        m_is_connected = false;
        return false;
    }

    m_is_connected = true;
    return true;
}

std::vector<uint8_t> Sht3xDriver::read_raw_data() {
    return std::vector<uint8_t>();
}

std::map<std::string, float> Sht3xDriver::calculate_readings() {
    uint16_t t_raw, h_raw;
    float t_s, h_s;
    
    if (sht31_single_read(&g_sht31_handle, SHT31_BOOL_TRUE, &t_raw, &t_s, &h_raw, &h_s) == 0) {
        last_temperature = t_s;
        last_humidity = h_s;
        m_is_connected = true;
        m_error_count = 0;
    } else {
        m_error_count++;
        if (m_error_count > 5) m_is_connected = false;
    }

    std::map<std::string, float> readings;
    readings["temp"] = last_temperature;
    readings["humid"] = last_humidity;
    return readings;
}

bool Sht3xDriver::check_connection() {
    return m_is_connected;
}

void Sht3xDriver::reset_sensor() {
    sht31_soft_reset(&g_sht31_handle);
}

void Sht3xDriver::handle_i2c_timeout() {
    m_error_count++;
}

float Sht3xDriver::get_temperature() const {
    return last_temperature;
}

float Sht3xDriver::get_humidity() const {
    return last_humidity;
}

bool Sht3xDriver::soft_reset() {
    return sht31_soft_reset(&g_sht31_handle) == 0;
}
