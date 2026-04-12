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
#include <gpiod.h>
#include <cstring>

/**
 * @brief Constructor for the MC38 sensor driver.
 * @param gpio_line_offset The GPIO line offset (e.g., 26 for GPIO 26).
 * @param chip_name The GPIO chip name (defaults to "/dev/gpiochip0" for RPi 4B GPIO).
 */
MC38::MC38(int gpio_line_offset, const std::string& chip_name)
    : m_line_offset(gpio_line_offset), m_chip_name(chip_name), m_is_initialized(false), m_line_handle(nullptr) {
}

/**
 * @brief Destructor.
 * Releases the GPIO line if it was requested.
 */
MC38::~MC38() {
    if (m_line_handle != nullptr) {
        gpiod_line_request* request = static_cast<gpiod_line_request*>(m_line_handle);
        gpiod_line_request_release(request);
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
        // Open the GPIO chip
        gpiod_chip* chip = gpiod_chip_open(m_chip_name.c_str());
        if (!chip) {
            std::cerr << "[MC38] Failed to open GPIO chip at " << m_chip_name << std::endl;
            return false;
        }

        // Create line settings for input with pull-up
        gpiod_line_settings* settings = gpiod_line_settings_new();
        if (!settings) {
            std::cerr << "[MC38] Failed to create line settings" << std::endl;
            gpiod_chip_close(chip);
            return false;
        }

        // Set direction to input
        if (gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_INPUT) < 0) {
            std::cerr << "[MC38] Failed to set line direction to input" << std::endl;
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Set bias to pull-up
        if (gpiod_line_settings_set_bias(settings, GPIOD_LINE_BIAS_PULL_UP) < 0) {
            std::cerr << "[MC38] Failed to set pull-up bias" << std::endl;
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Create line config and add the settings for our GPIO line
        gpiod_line_config* line_cfg = gpiod_line_config_new();
        if (!line_cfg) {
            std::cerr << "[MC38] Failed to create line config" << std::endl;
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        unsigned int offset = static_cast<unsigned int>(m_line_offset);
        if (gpiod_line_config_add_line_settings(line_cfg, &offset, 1, settings) < 0) {
            std::cerr << "[MC38] Failed to add line settings to config" << std::endl;
            gpiod_line_config_free(line_cfg);
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Create request config
        gpiod_request_config* req_cfg = gpiod_request_config_new();
        if (!req_cfg) {
            std::cerr << "[MC38] Failed to create request config" << std::endl;
            gpiod_line_config_free(line_cfg);
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Set consumer name
        gpiod_request_config_set_consumer(req_cfg, "FSS_MC38_Driver");

        // Request the line from the chip
        gpiod_line_request* request = gpiod_chip_request_lines(chip, req_cfg, line_cfg);
        if (!request) {
            std::cerr << "[MC38] Failed to request GPIO line " << m_line_offset << std::endl;
            gpiod_request_config_free(req_cfg);
            gpiod_line_config_free(line_cfg);
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Clean up settings, config, and request config
        gpiod_request_config_free(req_cfg);
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        gpiod_chip_close(chip);

        // Store the request handle
        m_line_handle = static_cast<void*>(request);
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
        gpiod_line_request* request = static_cast<gpiod_line_request*>(m_line_handle);
        enum gpiod_line_value value = gpiod_line_request_get_value(request, m_line_offset);

        if (value < 0) {
            std::cerr << "[MC38] Read failed" << std::endl;
            return DoorStatus::UNKNOWN;
        }

        // GPIOD_LINE_VALUE_INACTIVE (0) = Circuit Closed (Door Closed)
        // GPIOD_LINE_VALUE_ACTIVE (1) = Circuit Open (Door Open)
        return (value == GPIOD_LINE_VALUE_INACTIVE) ? DoorStatus::CLOSED : DoorStatus::OPEN;
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
