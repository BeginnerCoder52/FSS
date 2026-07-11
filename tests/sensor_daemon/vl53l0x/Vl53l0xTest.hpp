/**
 * @file Vl53l0xTest.hpp
 * @brief Unit tests for Vl53l0xDriver class.
 * 
 * Tests sensor initialization, distance reading modes, connection status, and error handling.
 */

#ifndef VL53L0X_TEST_HPP
#define VL53L0X_TEST_HPP

#include <memory>
#include <vector>
#include <cstdint>

class I2cHandler;
class Vl53l0xDriver;

/**
 * @class Vl53l0xTest
 * @brief Test suite for VL53L0X Time-of-Flight sensor driver functionality.
 */
class Vl53l0xTest {
public:
    /**
     * @brief Constructor.
     * @param i2c_bus I2C bus device path (e.g., "/dev/i2c-6").
     * @param i2c_address Sensor I2C address (default 0x29).
     */
    Vl53l0xTest(const std::string& i2c_bus, uint8_t i2c_address = 0x29);

    /**
     * @brief Destructor.
     */
    ~Vl53l0xTest();

    /**
     * @brief Run all test cases.
     * @return Number of failed tests (0 if all pass).
     */
    int run_all_tests();

    /**
     * @brief Test sensor initialization.
     * @return true if test passed, false otherwise.
     */
    bool test_initialization();

    /**
     * @brief Test single distance measurement.
     * @return true if test passed, false otherwise.
     */
    bool test_single_measurement();

    /**
     * @brief Test continuous distance measurement mode.
     * @return true if test passed, false otherwise.
     */
    bool test_continuous_measurement();

    /**
     * @brief Test distance reading in millimeters.
     * @return true if test passed, false otherwise.
     */
    bool test_get_distance();

    /**
     * @brief Test distance reading in meters.
     * @return true if test passed, false otherwise.
     */
    bool test_read_distance_meters();

    /**
     * @brief Test user detection based on threshold.
     * @return true if test passed, false otherwise.
     */
    bool test_user_detection();

    /**
     * @brief Test connection checking mechanism.
     * @return true if test passed, false otherwise.
     */
    bool test_connection_status();

    /**
     * @brief Test sensor reset functionality.
     * @return true if test passed, false otherwise.
     */
    bool test_sensor_reset();

private:
    /**
     * @brief Print test result with color formatting.
     * @param test_name Name of the test.
     * @param passed Whether the test passed.
     */
    void print_result(const std::string& test_name, bool passed);

    std::shared_ptr<I2cHandler> m_i2c_handler;  ///< I2C handler instance.
    std::shared_ptr<Vl53l0xDriver> m_driver;    ///< VL53L0X driver instance.
    uint8_t m_i2c_address;                      ///< I2C address of the sensor.
    int m_tests_passed;                         ///< Count of passed tests.
    int m_tests_failed;                         ///< Count of failed tests.
};

#endif // VL53L0X_TEST_HPP
