/**
 * @file GpioHandler.cpp
 * @brief Implementation of the GpioHandler class using mock/stub for now.
 * 
 * Note: Real implementation should use libgpiod.
 */

#include "GpioHandler.hpp"
#include <iostream>

GpioHandler::GpioHandler(const std::string& chip_name)
    : chip_name(chip_name), is_ready(false), 
      m_chip_handle(nullptr), m_lines_map(nullptr) {
    // In a real RPi environment, we would open the gpiochip here
    is_ready = true;
}

GpioHandler::~GpioHandler() {
}

bool GpioHandler::request_pin(int pin) {
    // Success stub
    return true;
}

int GpioHandler::read_pin(int pin) {
    // Return 0 (CLOSED) as default stub
    return 0;
}

bool GpioHandler::write_line(int line_offset, int value) {
    // Success stub
    return true;
}
