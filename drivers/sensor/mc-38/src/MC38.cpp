/**
 * @file MC38.cpp
 * @brief Implementation file for MC-38 Magnetic Door Sensor driver.
 * 
 * This driver provides an interface to monitor the state of a magnetic door sensor (MC-38).
 * It uses libgpiod 2.1.1 for GPIO control on Raspberry Pi.
 * 
 * Hardware: Normally Closed (N.C.) Reed Switch Principle
 * - Without magnet: Reed contacts are CLOSED (circuit complete) → GPIO reads 0 (LOW)
 * - With magnet:    Reed contacts are OPEN (circuit open)      → GPIO reads 1 (HIGH)
 * 
 * Semantic Door Status (User Perspective):
 * - GPIO 0 (no magnet): User can push door open → Status: "OPEN"
 * - GPIO 1 (magnet):    Magnet keeps door closed → Status: "CLOSED"
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
    : m_line_offset(gpio_line_offset), m_chip_name(chip_name), m_is_initialized(false), 
      m_chip_handle(nullptr), m_line_handle(nullptr) {
}

/**
 * @brief Destructor.
 * Releases the GPIO line request and closes the chip.
 */
MC38::~MC38() {
    if (m_line_handle != nullptr) {
        gpiod_line_request* request = static_cast<gpiod_line_request*>(m_line_handle);
        gpiod_line_request_release(request);
        m_line_handle = nullptr;
    }
    
    if (m_chip_handle != nullptr) {
        gpiod_chip* chip = static_cast<gpiod_chip*>(m_chip_handle);
        gpiod_chip_close(chip);
        m_chip_handle = nullptr;
    }
}

/**
 * @brief Initializes the GPIO line for input.
 * Opens the GPIO chip, configures the line for input, and requests it.
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

        // Create line settings for input
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

        // Create line config
        gpiod_line_config* line_cfg = gpiod_line_config_new();
        if (!line_cfg) {
            std::cerr << "[MC38] Failed to create line config" << std::endl;
            gpiod_line_settings_free(settings);
            gpiod_chip_close(chip);
            return false;
        }

        // Add line settings to config
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

        // Clean up configs and settings
        gpiod_request_config_free(req_cfg);
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);

        // Store handles
        m_line_handle = static_cast<void*>(request);
        m_chip_handle = static_cast<void*>(chip);
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
 * 
 * N.C. Reed Switch Mapping:
 * - GPIO 0 (reed contacts closed, no magnet): Door is OPEN
 * - GPIO 1 (reed contacts open, magnet):     Door is CLOSED
 * 
 * @return The current DoorStatus (OPEN, CLOSED, or UNKNOWN).
 */
MC38::DoorStatus MC38::getStatus() {
    if (!m_is_initialized || m_line_handle == nullptr) {
        return DoorStatus::UNKNOWN;
    }

    try {
        gpiod_line_request* request = static_cast<gpiod_line_request*>(m_line_handle);
        
        // In libgpiod 2.x, read value using gpiod_line_request_get_value()
        enum gpiod_line_value value = gpiod_line_request_get_value(request, m_line_offset);

        if (value < 0) {
            std::cerr << "[MC38] Read failed: gpiod_line_request_get_value returned " << value << std::endl;
            return DoorStatus::UNKNOWN;
        }

        // N.C. switch: GPIO 0 = OPEN, GPIO 1 = CLOSED
        // GPIOD_LINE_VALUE_INACTIVE (0) = OPEN
        // GPIOD_LINE_VALUE_ACTIVE (1) = CLOSED
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
