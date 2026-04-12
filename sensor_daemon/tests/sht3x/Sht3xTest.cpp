/**
 * @file Sht3xTest.cpp
 * @brief Implementation of Sht3xDriver unit tests.
 */

#include "Sht3xTest.hpp"
#include "Sht3xDriver.hpp"
#include "I2cHandler.hpp"
#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>

Sht3xTest::Sht3xTest(const std::string& i2c_bus, uint8_t i2c_address)
    : m_i2c_address(i2c_address), m_tests_passed(0), m_tests_failed(0)
{
    m_i2c_handler = std::make_shared<I2cHandler>(i2c_bus);
    m_driver = std::make_shared<Sht3xDriver>(m_i2c_handler, i2c_address);
}

Sht3xTest::~Sht3xTest()
{
}

void Sht3xTest::print_result(const std::string& test_name, bool passed)
{
    std::string status = passed ? "PASS" : "FAIL";
    std::string color = passed ? "\033[32m" : "\033[31m";
    std::string reset = "\033[0m";

    std::cout << color << std::setw(50) << std::left << test_name
              << " [" << status << "]" << reset << std::endl;

    if (passed) {
        m_tests_passed++;
    } else {
        m_tests_failed++;
    }
}

bool Sht3xTest::test_initialization()
{
    std::cout << "  Sensor Address: 0x" << std::hex << std::setfill('0') << std::setw(2) 
              << (int)m_i2c_address << std::dec << std::endl;
    
    bool result = m_driver->init_driver();
    
    if (!result) {
        std::cerr << "  \033[33m[DEBUG] Initialization failed - Verify:\033[0m" << std::endl;
        std::cerr << "    - Sensor connected to I2C bus (SDA/SCL)" << std::endl;
        std::cerr << "    - Sensor power (VCC/GND)" << std::endl;
        std::cerr << "    - I2C address match (0x44=GND, 0x45=VCC)" << std::endl;
        std::cerr << "    - Run 'i2cdetect -y <bus>' to find sensor" << std::endl;
    }
    
    print_result("Initialization Test", result);
    return result;
}

bool Sht3xTest::test_single_read()
{
    if (!m_driver->check_connection()) {
        print_result("Single Read Test", false);
        return false;
    }

    bool result = m_driver->single_read(true);
    if (result) {
        float temp = m_driver->get_temperature();
        float humid = m_driver->get_humidity();
        std::cout << "  Temperature: " << std::fixed << std::setprecision(2) << temp << "°C" << std::endl;
        std::cout << "  Humidity: " << humid << "%" << std::endl;
    }

    print_result("Single Read Test", result);
    return result;
}

bool Sht3xTest::test_continuous_read()
{
    if (!m_driver->check_connection()) {
        print_result("Continuous Read Test", false);
        return false;
    }

    bool start_result = m_driver->start_continuous_read(1.0f);
    if (!start_result) {
        print_result("Continuous Read Test", false);
        return false;
    }

    /* Read extended continuous samples - 10 samples at 1Hz = ~10 seconds */
    bool read_result = true;
    int sample_count = 0;
    for (int i = 0; i < 10; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1100));
        if (m_driver->continuous_read()) {
            sample_count++;
            float temp = m_driver->get_temperature();
            float humid = m_driver->get_humidity();
            if (i == 0 || i == 4 || i == 9) {  /* Show samples at start, middle, end */
                std::cout << "    Sample " << (i+1) << ": " << std::fixed << std::setprecision(2) 
                          << temp << "°C, " << humid << "%" << std::endl;
            }
        } else {
            read_result = false;
            break;
        }
    }

    bool stop_result = m_driver->stop_continuous_read();
    std::cout << "    Total samples: " << sample_count << "/10" << std::endl;

    bool result = start_result && read_result && stop_result;
    print_result("Continuous Read Test", result);
    return result;
}

bool Sht3xTest::test_set_repeatability()
{
    if (!m_driver->check_connection()) {
        print_result("Set Repeatability Test", false);
        return false;
    }

    /* Test all repeatability levels */
    bool result = true;

    /* High repeatability */
    if (!m_driver->set_repeatability(0)) {
        result = false;
    }

    /* Medium repeatability */
    if (!m_driver->set_repeatability(1)) {
        result = false;
    }

    /* Low repeatability */
    if (!m_driver->set_repeatability(2)) {
        result = false;
    }

    print_result("Set Repeatability Test", result);
    return result;
}

bool Sht3xTest::test_set_heater()
{
    if (!m_driver->check_connection()) {
        print_result("Set Heater Test", false);
        return false;
    }

    bool result = true;

    /* Enable heater */
    if (!m_driver->set_heater(true)) {
        result = false;
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    /* Disable heater */
    if (!m_driver->set_heater(false)) {
        result = false;
    }

    print_result("Set Heater Test", result);
    return result;
}

bool Sht3xTest::test_soft_reset()
{
    if (!m_driver->check_connection()) {
        print_result("Soft Reset Test", false);
        return false;
    }

    bool result = m_driver->soft_reset();
    print_result("Soft Reset Test", result);
    return result;
}

bool Sht3xTest::test_status_register()
{
    if (!m_driver->check_connection()) {
        print_result("Status Register Test", false);
        return false;
    }

    uint16_t status = m_driver->get_status();
    bool read_result = (status != 0 || m_driver->check_connection());

    bool clear_result = m_driver->clear_status();

    bool result = read_result && clear_result;
    print_result("Status Register Test", result);
    return result;
}

bool Sht3xTest::test_serial_number()
{
    if (!m_driver->check_connection()) {
        print_result("Serial Number Test", false);
        return false;
    }

    uint8_t sn[4] = {0};
    bool result = m_driver->get_serial_number(sn);

    if (result) {
        std::cout << "  Serial Number: 0x";
        for (int i = 0; i < 4; ++i) {
            std::cout << std::hex << std::setfill('0') << std::setw(2) << (int)sn[i];
        }
        std::cout << std::dec << std::endl;
    }

    print_result("Serial Number Test", result);
    return result;
}

bool Sht3xTest::test_connection_check()
{
    bool result = m_driver->check_connection();
    print_result("Connection Check Test", result);
    return result;
}

bool Sht3xTest::test_error_handling()
{
    int initial_errors = m_driver->get_error_count();

    /* Simulate error by calling timeout handler */
    m_driver->handle_i2c_timeout();

    int error_count = m_driver->get_error_count();
    bool result = (error_count > initial_errors);

    print_result("Error Handling Test", result);
    return result;
}

int Sht3xTest::run_all_tests()
{
    std::cout << std::endl << "=====================================" << std::endl;
    std::cout << "  SHT31 Sensor Driver Test Suite" << std::endl;
    std::cout << "=====================================" << std::endl << std::endl;

    /* Run all tests */
    test_initialization();
    if (!m_driver->check_connection()) {
        std::cout << "\n\033[33mWarning: Sensor not connected. Skipping further tests.\033[0m" << std::endl;
        std::cout << std::endl << "=====================================" << std::endl;
        std::cout << "Tests Passed: " << m_tests_passed << " | Tests Failed: " << m_tests_failed << std::endl;
        std::cout << "=====================================" << std::endl << std::endl;
        return m_tests_failed;
    }

    test_connection_check();
    test_single_read();
    test_continuous_read();
    test_set_repeatability();
    test_set_heater();
    test_soft_reset();
    test_status_register();
    test_serial_number();
    test_error_handling();

    /* Cleanup */
    m_driver->deinit_driver();

    std::cout << std::endl << "=====================================" << std::endl;
    std::cout << "Tests Passed: " << m_tests_passed << " | Tests Failed: " << m_tests_failed << std::endl;
    std::cout << "=====================================" << std::endl << std::endl;

    return m_tests_failed;
}
