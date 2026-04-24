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
    try {
        bool success = true;
        
        // Initialize SHT3x environmental sensor
        if (!sht3x || !sht3x->init_driver()) {
            std::cerr << "Failed to initialize SHT3x environmental sensor" << std::endl;
            success = false;
        }
        
        // Initialize VL53L0x distance sensor
        if (!vl53l0x || !vl53l0x->init_driver()) {
            std::cerr << "Failed to initialize VL53L0x distance sensor" << std::endl;
            success = false;
        }
        
        // Initialize Door sensor
        if (!door_sensor || !door_sensor->init_driver()) {
            std::cerr << "Failed to initialize Door sensor" << std::endl;
            success = false;
        }
        
        return success;
    } catch (const std::exception& e) {
        std::cerr << "InputProcessor init_sensors exception: " << e.what() << std::endl;
        return false;
    }
}

std::map<std::string, float> InputProcessor::poll_all_data() {
    std::map<std::string, float> data;
    
    try {
        // Update timestamp with current Unix time
        last_poll_timestamp = static_cast<float>(std::time(nullptr));
        data["timestamp"] = last_poll_timestamp;
        
        // Poll SHT3x environmental sensor
        if (sht3x) {
            if (sht3x->single_read(true)) {
                data["temp"] = sht3x->get_temperature();
                data["humid"] = sht3x->get_humidity();
            } else {
                data["temp"] = 0.0f;
                data["humid"] = 0.0f;
            }
        }

        // Poll VL53L0x distance sensor
        if (vl53l0x) {
            data["distance"] = vl53l0x->read_distance_meters();
            data["presence"] = vl53l0x->is_user_detected() ? 1.0f : 0.0f;
        }

        // Poll Door sensor
        if (door_sensor) {
            data["door"] = door_sensor->is_open() ? 1.0f : 0.0f;
        }
    } catch (const std::exception& e) {
        std::cerr << "InputProcessor poll_all_data exception: " << e.what() << std::endl;
    }

    return data;
}

void InputProcessor::get_env_data(float& temp, float& hum) {
    try {
        if (sht3x) {
            temp = sht3x->get_temperature();
            hum = sht3x->get_humidity();
        } else {
            temp = 0.0f;
            hum = 0.0f;
        }
    } catch (const std::exception& e) {
        std::cerr << "InputProcessor get_env_data exception: " << e.what() << std::endl;
        temp = 0.0f;
        hum = 0.0f;
    }
}

uint16_t InputProcessor::get_distance_data() {
    try {
        if (vl53l0x) {
            return vl53l0x->get_distance();
        }
    } catch (const std::exception& e) {
        std::cerr << "InputProcessor get_distance_data exception: " << e.what() << std::endl;
    }
    return 0;
}

bool InputProcessor::get_door_status() {
    try {
        if (door_sensor) {
            return door_sensor->is_open();
        }
    } catch (const std::exception& e) {
        std::cerr << "InputProcessor get_door_status exception: " << e.what() << std::endl;
    }
    return false;
}
