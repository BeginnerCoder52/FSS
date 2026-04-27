/**
 * @file DoorSensorDriver.cpp
 * @brief Implementation of the DoorSensorDriver class using MC38 driver.
 */

#include "DoorSensorDriver.hpp"
#include "GpioHandler.hpp"
#include <iostream>

// Include original driver header
#include "../../drivers/sensor/mc-38/include/MC38.hpp"

// Private pointer to MC38 instance
static MC38* g_mc38_ptr = nullptr;

DoorSensorDriver::DoorSensorDriver(std::shared_ptr<GpioHandler> gpio_handler, int gpio_offset)
    : m_gpio(gpio_handler), pin_offset(gpio_offset), 
      debounce_ms(50), current_state("CLOSED"), is_connected(false) {
}

DoorSensorDriver::~DoorSensorDriver() {
    if (g_mc38_ptr) {
        delete g_mc38_ptr;
        g_mc38_ptr = nullptr;
    }
}

bool DoorSensorDriver::init_driver() {
    // Instantiate MC38 with GPIO26 offset and correct chip device (/dev/gpiochip0)
    g_mc38_ptr = new MC38(pin_offset, "/dev/gpiochip0");
    if (!g_mc38_ptr->initialize()) {
        is_connected = false;
        return false;
    }
    is_connected = true;
    return true;
}

std::string DoorSensorDriver::read_state() {
    if (!g_mc38_ptr) return "UNKNOWN";
    
    if (g_mc38_ptr->isDoorOpen()) {
        current_state = "OPEN";
    } else {
        current_state = "CLOSED";
    }
    return current_state;
}

void DoorSensorDriver::clear_interrupt_flags() {
}

bool DoorSensorDriver::diagnose_gpio_line() {
    return is_connected;
}

bool DoorSensorDriver::is_open() {
    return read_state() == "OPEN";
}

bool DoorSensorDriver::is_closed() {
    return read_state() == "CLOSED";
}
