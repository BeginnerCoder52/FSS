/**
 * @file I2cHandler.hpp
 * @brief Header file for the I2cHandler class.
 * 
 * Provides a low-level interface for I2C communication.
 */

#ifndef I2C_HANDLER_HPP
#define I2C_HANDLER_HPP

#include <string>
#include <cstdint>
#include <vector>

/**
 * @class I2cHandler
 * @brief Manages I2C bus operations including opening, closing, and data transfer.
 */
class I2cHandler {
public:
    /**
     * @brief Constructor for I2cHandler.
     * @param bus_device Path to the I2C bus device (e.g., "/dev/i2c-1").
     */
    I2cHandler(const std::string& bus_device);

    /**
     * @brief Destructor for I2cHandler.
     */
    ~I2cHandler();

    /**
     * @brief Opens the I2C bus.
     * @return true if successful, false otherwise.
     */
    bool open_bus();

    /**
     * @brief Closes the I2C bus.
     */
    void close_bus();

    /**
     * @brief Low-level reading of bytes from physical address.
     * @param addr I2C physical address.
     * @param cmd Command or register address.
     * @return Raw bytes read.
     */
    std::vector<uint8_t> read_bytes(int addr, int cmd);

    /**
     * @brief Sets the I2C slave address for subsequent operations.
     * @param address The 7-bit I2C address.
     * @return true if successful, false otherwise.
     */
    bool set_slave_address(uint8_t address);

    /**
     * @brief Writes data to the I2C bus.
     * @param data Pointer to the data buffer.
     * @param length Number of bytes to write.
     * @return true if successful, false otherwise.
     */
    bool write_data(const uint8_t* data, size_t length);

    /**
     * @brief Reads data from the I2C bus.
     * @param buffer Pointer to the buffer where data will be stored.
     * @param length Number of bytes to read.
     * @return true if successful, false otherwise.
     */
    bool read_data(uint8_t* buffer, size_t length);

private:
    std::string m_bus_device; ///< Path to the I2C device.
    int m_fd;                 ///< File descriptor.
    uint8_t m_current_addr;   ///< Current slave address.
    
    int bus_id;               ///< I2C bus ID (API matching Bảng 1).
    bool is_bus_open;         ///< Bus connection status (API matching Bảng 1).
};

#endif // I2C_HANDLER_HPP
