/**
 * @file Sht3xDriver.hpp
 * @brief Header file for the Sht3xDriver class wrapper.
 * 
 * Provides an object-oriented interface for the SHT3x Temperature and Humidity sensor.
 */

#ifndef SHT3X_DRIVER_HPP
#define SHT3X_DRIVER_HPP

#include <memory>
#include <vector>
#include <map>
#include <string>

class I2cHandler;

/**
 * @class Sht3xDriver
 * @brief Wrapper class for the SHT31 sensor, providing temperature and humidity readings.
 */
class Sht3xDriver {
public:
    /**
     * @brief Constructor for Sht3xDriver.
     * @param i2c_handler Pointer to the shared I2C handler.
     * @param i2c_address I2C address of the sensor (default 0x44).
     */
    Sht3xDriver(std::shared_ptr<I2cHandler> i2c_handler, uint8_t i2c_address = 0x44);

    /**
     * @brief Destructor.
     */
    ~Sht3xDriver();

    /**
     * @brief Initializes the sensor hardware (API matching Bảng 1).
     * @return true if successful, false otherwise.
     */
    bool init_driver();

    /**
     * @brief Reads raw data from the sensor.
     * @return Raw bytes read from the sensor.
     */
    std::vector<uint8_t> read_raw_data();

    /**
     * @brief Calculates readings from raw data.
     * @return A map containing "temp" and "humid".
     */
    std::map<std::string, float> calculate_readings();

    /**
     * @brief Checks the hardware connection.
     * @return true if connected, false otherwise.
     */
    bool check_connection();

    /**
     * @brief Resets the sensor.
     */
    void reset_sensor();

    /**
     * @brief Handles I2C timeout errors.
     */
    void handle_i2c_timeout();

    /**
     * @brief Gets the last recorded temperature.
     * @return Temperature in Celsius.
     */
    float get_temperature() const;

    /**
     * @brief Gets the last recorded relative humidity.
     * @return Relative humidity in percentage (0-100%).
     */
    float get_humidity() const;

    /**
     * @brief Performs a software reset of the sensor.
     * @return true if successful, false otherwise.
     */
    bool soft_reset();

private:
    std::shared_ptr<I2cHandler> m_i2c; ///< Reference to the I2C communication handler.
    uint8_t device_address;            ///< I2C address of the device (API matching Bảng 1).
    float last_temperature;            ///< Last measured temperature (API matching Bảng 1).
    float last_humidity;               ///< Last measured humidity (API matching Bảng 1).
    bool m_is_connected;               ///< Connection status flag.
    int m_error_count;                 ///< Counter for measurement or communication errors.
};

#endif // SHT3X_DRIVER_HPP
