/**
 * @file Sht3xTest.hpp
 * @brief Unit tests for Sht3xDriver class.
 * 
 * Tests sensor initialization, reading modes, configuration, and error handling.
 */

#ifndef SHT3X_TEST_HPP
#define SHT3X_TEST_HPP

#include <memory>
#include <vector>
#include <cstdint>
#include <string>

class I2cHandler;
class Sht3xDriver;

/**
 * @class Sht3xTest
 * @brief Test suite for SHT31 sensor driver functionality.
 */
class Sht3xTest {
public:
    /**
     * @brief Constructor.
     * @param i2c_bus I2C bus device path (e.g., "/dev/i2c-1").
     * @param i2c_address Sensor I2C address (0x44 or 0x45).
     */
    Sht3xTest(const std::string& i2c_bus, uint8_t i2c_address = 0x44);

    /**
     * @brief Destructor.
     */
    ~Sht3xTest();

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
     * @brief Test single read measurement mode.
     * @return true if test passed, false otherwise.
     */
    bool test_single_read();

    /**
     * @brief Test continuous read measurement mode.
     * @return true if test passed, false otherwise.
     */
    bool test_continuous_read();

    /**
     * @brief Test sensor repeatability configuration.
     * @return true if test passed, false otherwise.
     */
    bool test_set_repeatability();

    /**
     * @brief Test heater command.
     * @return true if test passed, false otherwise.
     */
    bool test_set_heater();

    /**
     * @brief Test soft reset function.
     * @return true if test passed, false otherwise.
     */
    bool test_soft_reset();

    /**
     * @brief Test status register operations.
     * @return true if test passed, false otherwise.
     */
    bool test_status_register();

    // /**
    //  * @brief Test serial number retrieval.
    //  * @return true if test passed, false otherwise.
    //  */
    // bool test_serial_number();

    /**
     * @brief Test connection checking mechanism.
     * @return true if test passed, false otherwise.
     */
    bool test_connection_check();

    /**
     * @brief Test error count tracking.
     * @return true if test passed, false otherwise.
     */
    bool test_error_handling();

private:
    std::shared_ptr<I2cHandler> m_i2c_handler;  ///< I2C communication handler.
    std::shared_ptr<Sht3xDriver> m_driver;      ///< Driver instance under test.
    uint8_t m_i2c_address;                      ///< Sensor I2C address.
    int m_tests_passed;                         ///< Count of passed tests.
    int m_tests_failed;                         ///< Count of failed tests.
    std::string m_bus_name;                     ///< Store bus name for logging

    /**
     * @brief Print test result.
     * @param test_name Name of the test.
     * @param passed true if passed, false if failed.
     */
    void print_result(const std::string& test_name, bool passed);
};

#endif // SHT3X_TEST_HPP
