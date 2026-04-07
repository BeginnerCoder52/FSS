/**
 * @file I2cHandler.cpp
 * @brief Implementation of the I2cHandler class using Linux I2C-dev.
 */

#include "I2cHandler.hpp"
#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <cstring>

I2cHandler::I2cHandler(const std::string& bus_device)
    : m_bus_device(bus_device), m_fd(-1), m_current_addr(0x00),
      is_bus_open(false) {
    // Extract numeric ID from "/dev/i2c-X"
    if (bus_device.length() > 9) {
        try {
            bus_id = std::stoi(bus_device.substr(9));
        } catch (...) {
            bus_id = 1;
        }
    } else {
        bus_id = 1;
    }
}

I2cHandler::~I2cHandler() {
    close_bus();
}

bool I2cHandler::open_bus() {
    if (is_bus_open) return true;

    m_fd = open(m_bus_device.c_str(), O_RDWR);
    if (m_fd < 0) {
        std::cerr << "Failed to open I2C bus: " << m_bus_device << std::endl;
        return false;
    }

    is_bus_open = true;
    return true;
}

void I2cHandler::close_bus() {
    if (is_bus_open && m_fd >= 0) {
        close(m_fd);
        m_fd = -1;
    }
    is_bus_open = false;
}

std::vector<uint8_t> I2cHandler::read_bytes(int addr, int cmd) {
    std::vector<uint8_t> data;
    if (!set_slave_address(static_cast<uint8_t>(addr))) return data;

    uint8_t reg = static_cast<uint8_t>(cmd);
    if (write(m_fd, &reg, 1) != 1) return data;

    uint8_t buffer[32]; // Default buffer size
    int bytes_read = read(m_fd, buffer, sizeof(buffer));
    if (bytes_read > 0) {
        data.assign(buffer, buffer + bytes_read);
    }

    return data;
}

bool I2cHandler::set_slave_address(uint8_t address) {
    if (!is_bus_open && !open_bus()) return false;

    if (m_current_addr != address) {
        if (ioctl(m_fd, I2C_SLAVE, address) < 0) {
            std::cerr << "Failed to set I2C slave address: 0x" << std::hex << (int)address << std::endl;
            return false;
        }
        m_current_addr = address;
    }
    return true;
}

bool I2cHandler::write_data(const uint8_t* data, size_t length) {
    if (!is_bus_open || m_fd < 0) return false;
    return write(m_fd, data, length) == static_cast<ssize_t>(length);
}

bool I2cHandler::read_data(uint8_t* buffer, size_t length) {
    if (!is_bus_open || m_fd < 0) return false;
    return read(m_fd, buffer, length) == static_cast<ssize_t>(length);
}
