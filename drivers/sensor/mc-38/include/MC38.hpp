/**
 * @file MC38.hpp
 * @brief Header file for MC-38 Magnetic Door Sensor driver.
 * 
 * This driver provides an interface to monitor the state of a magnetic door sensor (MC-38).
 * It typically uses a GPIO line with an internal pull-up resistor.
 * 
 * @author SMART_MIRROR FSS Team
 */

#ifndef MC38_HPP
#define MC38_HPP

#include <string>

/**
 * @class MC38
 * @brief Represents an MC-38 Magnetic Door Sensor.
 * 
 * Hardware: Normally Closed (N.C.) Reed Switch
 * - One wire to GPIO (e.g., GPIO 26 / Pin 37)
 * - One wire to Ground (e.g., Pin 39)
 * - GPIO has internal pull-up resistor
 * 
 * N.C. Reed Switch Principle:
 * - Without magnet: Reed switch contacts are CLOSED (circuit complete) → GPIO reads 0 (LOW)
 * - With magnet:    Reed switch contacts are OPEN (circuit broken)   → GPIO reads 1 (HIGH)
 * 
 * Semantic Mapping (User Perspective):
 * - GPIO 0 (No magnet): Door is OPEN (user can open it)
 * - GPIO 1 (Magnet):    Door is CLOSED (magnet keeps it closed)
 */
class MC38 {
public:
    /**
     * @enum DoorStatus
     * @brief Represents the possible states of the door.
     */
    enum class DoorStatus {
        CLOSED,   /**< Magnet is close, sensor circuit is closed */
        OPEN,     /**< Magnet is far, sensor circuit is open */
        UNKNOWN   /**< State is undetermined or initialization failed */
    };

    /**
     * @brief Constructor for the MC38 sensor driver.
     * @param gpio_line_offset The GPIO line offset (e.g., 26 for GPIO 26).
     * @param chip_name The GPIO chip name (defaults to "/dev/gpiochip0" for RPi 4B GPIO).
     */
    MC38(int gpio_line_offset, const std::string& chip_name = "/dev/gpiochip0");

    /**
     * @brief Destructor.
     */
    ~MC38();

    /**
     * @brief Initializes the GPIO line for input with a pull-up resistor.
     * @return true if initialization was successful, false otherwise.
     */
    bool initialize();

    /**
     * @brief Reads the current status of the door sensor.
     * @return The current DoorStatus (CLOSED, OPEN, or UNKNOWN).
     */
    DoorStatus getStatus();

    /**
     * @brief Convenient method to check if the door is currently open.
     * @return true if the door is open, false otherwise.
     */
    bool isDoorOpen();

    /**
     * @brief Convenient method to check if the door is currently closed.
     * @return true if the door is closed, false otherwise.
     */
    bool isDoorClosed();

private:
    int m_line_offset;          /**< GPIO line offset */
    std::string m_chip_name;    /**< Name of the GPIO chip device */
    bool m_is_initialized;      /**< Flag indicating if the sensor is initialized */
    
    void* m_chip_handle;        /**< Handle to the GPIO chip (must remain open) */
    void* m_line_handle;        /**< Opaque pointer to the GPIO line resource */
};

#endif // MC38_HPP
