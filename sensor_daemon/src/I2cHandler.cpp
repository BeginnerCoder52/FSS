/**
 * @file I2cHandler.cpp
 * @brief Implementation of the I2cHandler class using Linux I2C-dev with I2C_RDWR interface.
 * 
 * Uses raw I2C message interface (I2C_RDWR) compatible with LibDriver SHT31,
 * matching the original working implementation from raspberry pi driver.
 */

#include "I2cHandler.hpp"
#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
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
    if (!is_bus_open && !open_bus()) return data;

    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[2];
    uint8_t reg = static_cast<uint8_t>(cmd);
    uint8_t buffer[32];

    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg) * 2);

    /* Message 1: Write register address */
    msgs[0].addr = (static_cast<uint8_t>(addr)) >> 1;
    msgs[0].flags = 0;
    msgs[0].buf = &reg;
    msgs[0].len = 1;

    /* Message 2: Read data */
    msgs[1].addr = (static_cast<uint8_t>(addr)) >> 1;
    msgs[1].flags = I2C_M_RD;
    msgs[1].buf = buffer;
    msgs[1].len = sizeof(buffer);

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 2;

    if (ioctl(m_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        std::cerr << "I2C read failed" << std::endl;
        return data;
    }

    data.assign(buffer, buffer + msgs[1].len);
    return data;
}

bool I2cHandler::set_slave_address(uint8_t address) {
    if (!is_bus_open && !open_bus()) return false;
    m_current_addr = address;
    return true;
}

bool I2cHandler::write_data(const uint8_t* data, size_t length) {
    if (!is_bus_open || m_fd < 0) return false;

    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[1];
    uint8_t addr_7bit = (m_current_addr >> 1) & 0x7F;  /* Convert 8-bit to 7-bit address */

    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg));

    msgs[0].addr = addr_7bit;
    msgs[0].flags = 0;
    msgs[0].buf = const_cast<uint8_t*>(data);
    msgs[0].len = length;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 1;

    if (ioctl(m_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        std::cerr << "I2C write failed" << std::endl;
        return false;
    }

    return true;
}

bool I2cHandler::read_data(uint8_t* buffer, size_t length) {
    if (!is_bus_open || m_fd < 0) return false;

    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[1];
    uint8_t addr_7bit = (m_current_addr >> 1) & 0x7F;  /* Convert 8-bit to 7-bit address */

    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg));

    msgs[0].addr = addr_7bit;
    msgs[0].flags = I2C_M_RD;
    msgs[0].buf = buffer;
    msgs[0].len = length;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 1;

    if (ioctl(m_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        std::cerr << "I2C read failed" << std::endl;
        return false;
    }

    return true;
}

bool I2cHandler::read_address16(uint8_t addr, uint16_t reg, uint8_t* buf, uint16_t len)
{
    if (!is_bus_open || m_fd < 0) return false;

    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[2];
    uint8_t addr_buf[2];
    uint8_t addr_7bit = addr >> 1;

    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg) * 2);

    /* Prepare 16-bit register address */
    addr_buf[0] = (reg >> 8) & 0xFF;
    addr_buf[1] = reg & 0xFF;

    /* Message 1: Write 16-bit register address */
    msgs[0].addr = addr_7bit;
    msgs[0].flags = 0;
    msgs[0].buf = addr_buf;
    msgs[0].len = 2;

    /* Message 2: Read data */
    msgs[1].addr = addr_7bit;
    msgs[1].flags = I2C_M_RD;
    msgs[1].buf = buf;
    msgs[1].len = len;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 2;

    if (ioctl(m_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        std::cerr << "I2C read_address16 failed" << std::endl;
        return false;
    }

    return true;
}

bool I2cHandler::write_address16(uint8_t addr, uint16_t reg, uint8_t* buf, uint16_t len)
{
    if (!is_bus_open || m_fd < 0) return false;

    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[1];
    uint8_t write_buf[34];
    uint8_t addr_7bit = addr >> 1;

    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg));

    /* Build write buffer: [cmd_high, cmd_low, data...] */
    write_buf[0] = (reg >> 8) & 0xFF;
    write_buf[1] = reg & 0xFF;

    if (len > 0 && len <= 32) {
        memcpy(&write_buf[2], buf, len);
    }

    /* Single message: Write command + data */
    msgs[0].addr = addr_7bit;
    msgs[0].flags = 0;
    msgs[0].buf = write_buf;
    msgs[0].len = 2 + len;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 1;

    if (ioctl(m_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        std::cerr << "I2C write_address16 failed" << std::endl;
        return false;
    }

    return true;
}
