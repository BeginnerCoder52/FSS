/**
 * @file InputProcessor.hpp
 * @brief Header file for the InputProcessor class.
 * 
 * Manages sensor data acquisition from various hardware drivers.
 */

#ifndef INPUT_PROCESSOR_HPP
#define INPUT_PROCESSOR_HPP

#include <memory>
#include <map>
#include <string>

class Sht3xDriver;
class Vl53l0xDriver;
class DoorSensorDriver;
class I2cHandler;
class GpioHandler;

/**
 * @class InputProcessor
 * @brief Handles data collection from all sensors (Environmental, Distance, Door).
 */
class InputProcessor {
public:
    /**
     * @brief Constructor for InputProcessor.
     */
    InputProcessor();

    /**
     * @brief Destructor for InputProcessor.
     */
    ~InputProcessor();

    /**
     * @brief Initializes all connected sensor hardware.
     * @return true if all sensors are initialized correctly, false otherwise.
     */
    bool init_sensors();

    /**
     * @brief Polls data from all sensors.
     * @return A map containing sensor readings and last_poll_timestamp.
     */
    std::map<std::string, float> poll_all_data();

    /**
     * @brief Gets the last measured environmental data.
     * @param temp Reference to store temperature.
     * @param hum Reference to store humidity.
     */
    void get_env_data(float& temp, float& hum);

    /**
     * @brief Gets the last measured distance data.
     * @return Distance in mm.
     */
    uint16_t get_distance_data();

    /**
     * @brief Gets the current door status.
     * @return true if open, false if closed.
     */
    bool get_door_status();

private:
    std::shared_ptr<I2cHandler> m_i2c_main; ///< Handler for i2c-1.
    std::shared_ptr<I2cHandler> m_i2c_ext;  ///< Handler for i2c-6.
    std::shared_ptr<GpioHandler> m_gpio_handler;

    std::unique_ptr<Sht3xDriver> sht3x;     ///< SHT3x Environmental sensor.
    std::unique_ptr<Vl53l0xDriver> vl53l0x; ///< VL53L0X Distance sensor.
    std::unique_ptr<DoorSensorDriver> door_sensor; ///< MC-38 Door sensor.

    float last_poll_timestamp; ///< Precise Unix timestamp of the last poll.
};

#endif // INPUT_PROCESSOR_HPP
