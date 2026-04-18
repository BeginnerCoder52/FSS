/**
 * @file DoorSensorTest.hpp
 * @brief Unit tests for DoorSensorDriver class (MC-38 sensor).
 * 
 * Tests sensor initialization, state reading, GPIO diagnostics, and convenience methods.
 */

#ifndef DOOR_SENSOR_TEST_HPP
#define DOOR_SENSOR_TEST_HPP

#include <memory>
#include <cstdint>

class GpioHandler;
class DoorSensorDriver;

/**
 * @class DoorSensorTest
 * @brief Test suite for MC-38 door sensor driver functionality.
 */
class DoorSensorTest {
public:
    /**
     * @brief Constructor.
     * @param gpio_offset GPIO line offset for the MC-38 sensor.
     */
    DoorSensorTest(int gpio_offset = 26);

    /**
     * @brief Destructor.
     */
    ~DoorSensorTest();

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
     * @brief Test read_state() API method.
     * @return true if test passed, false otherwise.
     */
    bool test_read_state();

    /**
     * @brief Test is_open() convenience method.
     * @return true if test passed, false otherwise.
     */
    bool test_is_open();

    /**
     * @brief Test is_closed() convenience method.
     * @return true if test passed, false otherwise.
     */
    bool test_is_closed();

    /**
     * @brief Test diagnose_gpio_line() API method.
     * @return true if test passed, false otherwise.
     */
    bool test_diagnose_gpio_line();

    /**
     * @brief Test clear_interrupt_flags() API method.
     * @return true if test passed, false otherwise.
     */
    bool test_clear_interrupt_flags();

    /**
     * @brief Test continuous state monitoring.
     * @return true if test passed, false otherwise.
     */
    bool test_continuous_monitoring();

private:
    /**
     * @brief Helper method to print test results with color codes.
     */
    void print_result(const std::string& test_name, bool passed);

    std::shared_ptr<GpioHandler> m_gpio_handler;      ///< Shared GPIO handler instance.
    std::shared_ptr<DoorSensorDriver> m_driver;       ///< Door sensor driver instance.
    int m_gpio_offset;                                ///< GPIO line offset (GPIO26).
    int m_tests_passed;                               ///< Counter for passed tests.
    int m_tests_failed;                               ///< Counter for failed tests.
};

#endif // DOOR_SENSOR_TEST_HPP
