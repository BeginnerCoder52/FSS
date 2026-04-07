/**
 * @file Vl53l0xDriver.cpp
 * @brief Implementation of the Vl53l0xDriver class using VL53L0X C Driver.
 */

#include "Vl53l0xDriver.hpp"
#include "I2cHandler.hpp"
#include <iostream>

// Include original driver header
#include "../../drivers/sensor/vl53l0x/src/vl53l0x.h"

// Private data structure for VL53L0X driver
static vl53l0x_t g_vl53l0x_dev;

Vl53l0xDriver::Vl53l0xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address)
    : m_i2c(i2c_handler), device_address(i2c_address), threshold_meters(0.8f), last_distance_meters(0.0f),
      m_is_connected(false), m_error_count(0) {
}

Vl53l0xDriver::~Vl53l0xDriver() {
    vl53l0x_close(&g_vl53l0x_dev);
}

bool Vl53l0xDriver::init_driver() {
    int bus_num = 1; // Default
    if (m_i2c) {
        // Extract bus number from device string or variable
        // For simplicity, we use 6 as per PINOUT map for VL53L0X
        bus_num = 6; 
    }

    if (vl53l0x_init(&g_vl53l0x_dev, bus_num, device_address, VL53L0X_MODE_DEFAULT) != VL53L0X_OK) {
        m_is_connected = false;
        return false;
    }

    m_is_connected = true;
    return true;
}

float Vl53l0xDriver::read_distance_meters() {
    uint16_t dist_mm;
    if (vl53l0x_read_single(&g_vl53l0x_dev, &dist_mm) == VL53L0X_OK) {
        last_distance_meters = static_cast<float>(dist_mm) / 1000.0f;
        m_is_connected = true;
        m_error_count = 0;
    } else {
        m_error_count++;
        if (m_error_count > 5) m_is_connected = false;
    }
    return last_distance_meters;
}

bool Vl53l0xDriver::is_user_detected() {
    return (last_distance_meters > 0.05f && last_distance_meters <= threshold_meters);
}

bool Vl53l0xDriver::check_connection() {
    return m_is_connected;
}

void Vl53l0xDriver::reset_sensor() {
    // Re-init as reset
    init_driver();
}

void Vl53l0xDriver::handle_i2c_timeout() {
    m_error_count++;
}

bool Vl53l0xDriver::start_continuous() {
    return vl53l0x_start_continuous(&g_vl53l0x_dev) == VL53L0X_OK;
}

bool Vl53l0xDriver::stop_continuous() {
    return vl53l0x_stop_continuous(&g_vl53l0x_dev) == VL53L0X_OK;
}

uint16_t Vl53l0xDriver::get_distance() {
    return static_cast<uint16_t>(last_distance_meters * 1000.0f);
}

bool Vl53l0xDriver::is_data_ready() {
    return true; 
}
