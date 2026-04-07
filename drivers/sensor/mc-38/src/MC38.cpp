/**
 * @file MC38.cpp
 * @brief Implementation file for MC-38 Magnetic Door Sensor driver.
 * 
 * This driver provides an interface to monitor the state of a magnetic door sensor (MC-38).
 * It typically uses a GPIO line with an internal pull-up resistor.
 * 
 * @author SMART_MIRROR FSS Team
 */

#include "MC38.hpp"
#include <iostream>
#include <gpiod.hpp>

/**
 * @brief Constructor for the MC38 sensor driver.
 * @param gpio_line_offset The GPIO line offset (e.g., 4 for GPIO 4).
 * @param chip_name The GPIO chip name (defaults to "/dev/gpiochip4" for RPi 4B GPIO).
 */
MC38::MC38(int gpio_line_offset, const std::string& chip_name)
    : m_line_offset(gpio_line_offset), m_chip_name(chip_name), m_is_initialized(false), m_line_handle(nullptr) {
}

/**
 * @brief Destructor.
 * Releases the GPIO line if it was requested.
 */
MC38::~MC38() {
    if (m_is_initialized && m_line_handle != nullptr) {
        gpiod::line* line = static_cast<gpiod::line*>(m_line_handle);
        line->release();
        delete line;
        m_line_handle = nullptr;
    }
}

/**
 * @brief Initializes the GPIO line for input with a pull-up resistor.
 * This method requests the GPIO line from the specified chip and configures it
 * as an input with an internal pull-up resistor.
 * 
 * @return true if initialization was successful, false otherwise.
 */
bool MC38::initialize() {
    try {
        gpiod::chip chip(m_chip_name);
        gpiod::line* line = new gpiod::line(chip.get_line(m_line_offset));

        gpiod::line_request config;
        config.consumer = "FSS_MC38_Driver";
        config.request_type = gpiod::line_request::DIRECTION_INPUT;
        
        // Use internal pull-up resistor.
        // Note: For some platforms/kernels, pull-up might not be supported via libgpiod 1.x directly.
        // It requires the kernel to support bias flags.
        config.flags = gpiod::line_request::FLAG_BIAS_PULL_UP;

        line->request(config);
        
        m_line_handle = static_cast<void*>(line);
        m_is_initialized = true;
        
        std::cout << "[MC38] Initialized GPIO line " << m_line_offset << " on chip " << m_chip_name << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[MC38] Initialization failed: " << e.what() << std::endl;
        m_is_initialized = false;
        return false;
    }
}

/**
 * @brief Reads the current status of the door sensor.
 * The door status is based on the logic:
 * - 0 (Low)  = Magnet is close, circuit is closed -> CLOSED
 * - 1 (High) = Magnet is far, circuit is open    -> OPEN
 * 
 * @return The current DoorStatus (CLOSED, OPEN, or UNKNOWN).
 */
MC38::DoorStatus MC38::getStatus() {
    if (!m_is_initialized || m_line_handle == nullptr) {
        return DoorStatus::UNKNOWN;
    }

    try {
        gpiod::line* line = static_cast<gpiod::line*>(m_line_handle);
        int value = line->get_value();

        // 0 = Circuit Closed (Door Closed), 1 = Circuit Open (Door Open)
        return (value == 0) ? DoorStatus::CLOSED : DoorStatus::OPEN;
    } catch (const std::exception& e) {
        std::cerr << "[MC38] Read failed: " << e.what() << std::endl;
        return DoorStatus::UNKNOWN;
    }
}

/**
 * @brief Convenient method to check if the door is currently open.
 * @return true if the door is open, false otherwise.
 */
bool MC38::isDoorOpen() {
    return getStatus() == DoorStatus::OPEN;
}

/**
 * @brief Convenient method to check if the door is currently closed.
 * @return true if the door is closed, false otherwise.
 */
bool MC38::isDoorClosed() {
    return getStatus() == DoorStatus::CLOSED;
}
