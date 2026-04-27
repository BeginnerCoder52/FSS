/**
 * @file GpioHandler.hpp
 * @brief Header file for the GpioHandler class.
 * 
 * Provides an interface for GPIO management using libgpiod.
 */

#ifndef GPIO_HANDLER_HPP
#define GPIO_HANDLER_HPP

#include <string>
#include <cstdint>

/**
 * @class GpioHandler
 * @brief Handles GPIO line configuration, input/output operations, and interrupts.
 */
class GpioHandler {
public:
    /**
     * @brief Constructor for GpioHandler.
     * @param chip_name Path to the GPIO chip (e.g., "gpiochip4").
     */
    GpioHandler(const std::string& chip_name);

    /**
     * @brief Destructor for GpioHandler.
     */
    ~GpioHandler();

    /**
     * @brief Requests a GPIO pin for use (API matching Bảng 1).
     * @param pin Offset of the GPIO line.
     * @return true if successful, false otherwise.
     */
    bool request_pin(int pin);

    /**
     * @brief Reads the physical level of a GPIO pin (API matching Bảng 1).
     * @param pin Offset of the GPIO line.
     * @return 0 for LOW, 1 for HIGH.
     */
    int read_pin(int pin);

    /**
     * @brief Writes a value to a GPIO line.
     * @param line_offset Offset of the GPIO line.
     * @param value 0 for LOW, 1 for HIGH.
     * @return true if successful, false otherwise.
     */
    bool write_line(int line_offset, int value);

private:
    std::string chip_name; ///< Chip name (API matching Bảng 1).
    bool is_ready;         ///< Readiness status (API matching Bảng 1).
    
    void* m_chip_handle;   ///< Handle to the GPIO chip resource.
    void* m_lines_map;     ///< Map of requested lines.
};

#endif // GPIO_HANDLER_HPP
