/**
 * @file Vl53l0xDriver.hpp
 * @brief Header file for the Vl53l0xDriver class wrapper.
 * 
 * Provides an object-oriented interface for the VL53L0X Time-of-Flight (ToF) distance sensor.
 */

#ifndef VL53L0X_DRIVER_HPP
#define VL53L0X_DRIVER_HPP

#include <memory>

class I2cHandler;

/**
 * @class Vl53l0xDriver
 * @brief Wrapper class for the VL53L0X sensor, providing precise distance measurements.
 */
class Vl53l0xDriver {
public:
    /**
     * @brief Constructor for Vl53l0xDriver.
     * @param i2c_handler Pointer to the shared I2C handler.
     * @param i2c_address I2C address of the sensor (default 0x29).
     */
    Vl53l0xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address = 0x29);

    /**
     * @brief Destructor.
     */
    ~Vl53l0xDriver();

    /**
     * @brief Initializes the sensor hardware (API matching Bảng 1).
     * @return true if successful, false otherwise.
     */
    bool init_driver();

    /**
     * @brief Reads the distance directly from I2C and converts to METERS.
     * @return Distance in meters.
     */
    float read_distance_meters();

    /**
     * @brief Evaluates if a user is detected based on threshold.
     * @return true if detected, false otherwise.
     */
    bool is_user_detected();

    /**
     * @brief Checks the hardware connection.
     * @return true if connected, false otherwise.
     */
    bool check_connection();

    /**
     * @brief Resets the ToF sensor chip.
     */
    void reset_sensor();

    /**
     * @brief Handles I2C timeout errors.
     */
    void handle_i2c_timeout();

    /**
     * @brief Sets the sensor into continuous measurement mode.
     * @return true if successful, false otherwise.
     */
    bool start_continuous();

    /**
     * @brief Stops the continuous measurement mode.
     * @return true if successful, false otherwise.
     */
    bool stop_continuous();

    /**
     * @brief Reads the distance measurement.
     * @return Distance in millimeters (mm).
     */
    uint16_t get_distance();

    /**
     * @brief Checks if the data is ready to be read.
     * @return true if data ready, false otherwise.
     */
    bool is_data_ready();

private:
    std::shared_ptr<I2cHandler> m_i2c; ///< Reference to the I2C communication handler.
    uint8_t device_address;            ///< I2C address of the device (API matching Bảng 1).
    float threshold_meters;            ///< Threshold distance for user detection in METERS.
    float last_distance_meters;        ///< Last recorded distance value in METERS.
    bool m_is_connected;               ///< Connection status flag.
    int m_error_count;                 ///< Counter for measurement or communication errors.
};

#endif // VL53L0X_DRIVER_HPP
