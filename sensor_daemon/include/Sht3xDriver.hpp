/**
 * @file Sht3xDriver.hpp
 * @brief Header file for the Sht3xDriver class wrapper.
 * 
 * Provides an object-oriented interface for the SHT31 Temperature and Humidity sensor.
 * Wraps the LibDriver C API into a C++ class for use in sensor_daemon.
 */

#ifndef SHT3X_DRIVER_HPP
#define SHT3X_DRIVER_HPP

#include <memory>
#include <vector>
#include <map>
#include <string>
#include <cstdint>

class I2cHandler;

/**
 * @class Sht3xDriver
 * @brief C++ wrapper for SHT31 sensor driver, providing temperature and humidity acquisition.
 */
class Sht3xDriver {
public:
    /**
     * @brief Constructor for Sht3xDriver.
     * @param i2c_handler Pointer to the shared I2C handler instance.
     * @param i2c_address I2C address of the sensor (default 0x44).
     */
    Sht3xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address = 0x44);

    /**
     * @brief Destructor. Cleans up sensor resources.
     */
    ~Sht3xDriver();

    /**
     * @brief Initializes the sensor and underlying driver (API spec - Bảng 1).
     * @return true if initialization succeeded, false otherwise.
     */
    bool init_driver();

    /**
     * @brief Deinitializes the sensor and driver.
     * @return true if deinitialization succeeded, false otherwise.
     */
    bool deinit_driver();

    /**
     * @brief Performs a single temperature and humidity measurement.
     * @param clock_stretching Enable clock stretching during measurement (true/false).
     * @return true if measurement succeeded, false otherwise.
     */
    bool single_read(bool clock_stretching = true);

    /**
     * @brief Starts continuous measurement mode at specified rate.
     * @param rate Measurement rate (0.5, 1, 2, 4, or 10 Hz).
     * @return true if successful, false otherwise.
     */
    bool start_continuous_read(float rate);

    /**
     * @brief Stops continuous measurement mode.
     * @return true if successful, false otherwise.
     */
    bool stop_continuous_read();

    /**
     * @brief Reads temperature and humidity in continuous mode.
     * @return true if read succeeded, false otherwise.
     */
    bool continuous_read();

    /**
     * @brief Retrieves last measured temperature value.
     * @return Temperature in degrees Celsius.
     */
    float get_temperature() const;

    /**
     * @brief Retrieves last measured relative humidity value.
     * @return Relative humidity percentage (0-100%).
     */
    float get_humidity() const;

    /**
     * @brief Checks if sensor is currently connected and operational.
     * @return true if connected, false otherwise.
     */
    bool check_connection() const;

    /**
     * @brief Performs soft reset of the sensor.
     * @return true if reset succeeded, false otherwise.
     */
    bool soft_reset();

    /**
     * @brief Sets sensor repeatability level for measurements.
     * @param repeatability Repeatability level (0=high, 1=medium, 2=low).
     * @return true if successful, false otherwise.
     */
    bool set_repeatability(uint8_t repeatability);

    /**
     * @brief Gets the current sensor repeatability level.
     * @param repeatability Pointer to store current repeatability level.
     * @return true if successful, false otherwise.
     */
    bool get_repeatability(uint8_t *repeatability);

    /**
     * @brief Enables or disables sensor heater.
     * @param enable true to enable heater, false to disable.
     * @return true if successful, false otherwise.
     */
    bool set_heater(bool enable);

    /**
     * @brief Retrieves sensor status register value.
     * @return Status register value (bit flags).
     */
    uint16_t get_status();

    /**
     * @brief Clears sensor status register.
     * @return true if cleared successfully, false otherwise.
     */
    bool clear_status();

    // /**
    //  * @brief Retrieves sensor serial number.
    //  * @param sn Buffer to store 4-byte serial number.
    //  * @return true if successful, false otherwise.
    //  */
    // bool get_serial_number(uint8_t sn[4]);

    /**
     * @brief Handles I2C communication errors.
     * @note Internal error tracking mechanism.
     */
    void handle_i2c_timeout();

    /**
     * @brief Gets current error count.
     * @return Number of consecutive errors.
     */
    int get_error_count() const;

private:
    std::shared_ptr<I2cHandler> m_i2c;      ///< Reference to I2C communication handler.
    uint8_t device_address;                 ///< I2C address of sensor (API spec - Bảng 1).
    float last_temperature;                 ///< Last measured temperature in °C (API spec - Bảng 1).
    float last_humidity;                    ///< Last measured humidity in % (API spec - Bảng 1).
    bool m_is_connected;                    ///< Connection status indicator.
    int m_error_count;                      ///< Consecutive error counter.
    void *m_driver_handle;                  ///< Opaque handle to C driver structure.
};

#endif // SHT3X_DRIVER_HPP
