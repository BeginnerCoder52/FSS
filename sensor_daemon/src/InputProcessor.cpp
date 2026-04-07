/**
 * @file InputProcessor.cpp
 * @brief Implementation of the InputProcessor class.
 */

#include "InputProcessor.hpp"
#include "Sht3xDriver.hpp"
#include "Vl53l0xDriver.hpp"
#include "DoorSensorDriver.hpp"
#include "I2cHandler.hpp"
#include "GpioHandler.hpp"
#include <ctime>

InputProcessor::InputProcessor() 
    : last_poll_timestamp(0.0f) {
    m_i2c_main = std::make_shared<I2cHandler>("/dev/i2c-1");
    m_i2c_ext = std::make_shared<I2cHandler>("/dev/i2c-6");
    m_gpio_handler = std::make_shared<GpioHandler>("gpiochip4");

    sht3x = std::make_unique<Sht3xDriver>(m_i2c_main, 0x44);
    vl53l0x = std::make_unique<Vl53l0xDriver>(m_i2c_ext, 0x29);
    door_sensor = std::make_unique<DoorSensorDriver>(m_gpio_handler, 17); // MC-38 (GPIO 17)
}

InputProcessor::~InputProcessor() {
}

bool InputProcessor::init_sensors() {
    bool success = true;
    if (!sht3x->init_driver()) success = false;
    if (!vl53l0x->init_driver()) success = false;
    if (!door_sensor->init_driver()) success = false;
    return success;
}

std::map<std::string, float> InputProcessor::poll_all_data() {
    // API matching Bảng 1
    std::map<std::string, float> data;
    
    // Update timestamp
    last_poll_timestamp = static_cast<float>(std::time(nullptr));
    
    // TODO: Poll real data from drivers
    data["temp"] = 25.0f; // Placeholder
    data["humid"] = 60.0f; // Placeholder
    data["distance"] = 0.5f; // Placeholder (meters)
    data["door"] = 0.0f; // 0 for CLOSED, 1 for OPEN
    data["timestamp"] = last_poll_timestamp;

    return data;
}

void InputProcessor::get_env_data(float& temp, float& hum) {
    temp = 25.0f;
    hum = 60.0f;
}

uint16_t InputProcessor::get_distance_data() {
    return 500;
}

bool InputProcessor::get_door_status() {
    return false;
}
