/**
 * @file DoorSensorDriver.hpp
 * @brief Header file for the DoorSensorDriver class wrapper.
 * 
 * Provides an object-oriented interface for the MC-38 Magnetic Door Sensor.
 */

#ifndef DOOR_SENSOR_DRIVER_HPP
#define DOOR_SENSOR_DRIVER_HPP

#include <memory>
#include <string>

class GpioHandler;

/**
 * @class DoorSensorDriver
 * @brief Wrapper class for the MC-38 sensor, managing its state and configuration.
 */
class DoorSensorDriver {
public:
    /**
     * @brief Constructor for DoorSensorDriver.
     * @param gpio_handler Pointer to the shared GPIO handler.
     * @param gpio_offset GPIO line offset for the sensor.
     */
    DoorSensorDriver(std::shared_ptr<GpioHandler> gpio_handler, int gpio_offset);

    /**
     * @brief Destructor.
     */
    ~DoorSensorDriver();

    /**
     * @brief Initializes the sensor hardware (API matching Bảng 1).
     * @return true if successful, false otherwise.
     */
    bool init_driver();

    /**
     * @brief Reads the current status (High/Low) and returns state string.
     * @return "OPEN" or "CLOSED".
     */
    std::string read_state();

    /**
     * @brief Clears hardware interrupt flags if OS buffer overflows.
     */
    void clear_interrupt_flags();

    /**
     * @brief Checks if the pin is occupied by another application.
     * @return true if available, false otherwise.
     */
    bool diagnose_gpio_line();

    /**
     * @brief Reads the current status of the door.
     * @return true if the door is OPEN, false if CLOSED.
     */
    bool is_open();

    /**
     * @brief Reads the current status of the door.
     * @return true if the door is CLOSED, false if OPEN.
     */
    bool is_closed();

private:
    std::shared_ptr<GpioHandler> m_gpio; ///< Reference to the GPIO management handler.
    int pin_offset;                      ///< GPIO pin offset (API matching Bảng 1).
    int debounce_ms;                     ///< Software debounce time in ms.
    std::string current_state;           ///< Current state (OPEN / CLOSED).
    bool is_connected;                   ///< Connection status flag.
};

#endif // DOOR_SENSOR_DRIVER_HPP
