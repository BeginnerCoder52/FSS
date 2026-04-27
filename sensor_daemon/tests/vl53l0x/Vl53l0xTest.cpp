/**
 * @file Vl53l0xTest.cpp
 * @brief Implementation of Vl53l0xDriver unit tests.
 */

#include "Vl53l0xTest.hpp"
#include "Vl53l0xDriver.hpp"
#include "I2cHandler.hpp"
#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>

Vl53l0xTest::Vl53l0xTest(const std::string& i2c_bus, uint8_t i2c_address)
    : m_i2c_address(i2c_address), m_tests_passed(0), m_tests_failed(0)
{
    m_i2c_handler = std::make_shared<I2cHandler>(i2c_bus);
    m_driver = std::make_shared<Vl53l0xDriver>(m_i2c_handler, i2c_address);
}

Vl53l0xTest::~Vl53l0xTest()
{
}

void Vl53l0xTest::print_result(const std::string& test_name, bool passed)
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

bool Vl53l0xTest::test_initialization()
{
    std::cout << "  I2C Bus: /dev/i2c-6" << std::endl;
    std::cout << "  Sensor Address: 0x" << std::hex << std::setfill('0') << std::setw(2) 
              << (int)m_i2c_address << std::dec << std::endl;
    
    bool result = m_driver->init_driver();
    
    if (!result) {
        std::cerr << "  \033[33m[DEBUG] Initialization failed - Verify:\033[0m" << std::endl;
        std::cerr << "    - Sensor connected to I2C bus 6 (GPIO 22/23)" << std::endl;
        std::cerr << "    - Sensor power (VCC=3.3V, GND)" << std::endl;
        std::cerr << "    - Check pinout: VL53L0X on I2C-6" << std::endl;
        std::cerr << "    - Run 'i2cdetect -y 6' to find sensor" << std::endl;
    }
    
    print_result("Initialization Test", result);
    return result;
}

bool Vl53l0xTest::test_single_measurement()
{
    if (!m_driver->check_connection()) {
        print_result("Single Measurement Test", false);
        return false;
    }

    float distance_m = m_driver->read_distance_meters();
    bool result = (distance_m >= 0.03f && distance_m <= 2.0f);
    
    if (result) {
        std::cout << "  Distance: " << std::fixed << std::setprecision(3) << distance_m << " m" << std::endl;
        std::cout << "  User Detected: " << (m_driver->is_user_detected() ? "Yes" : "No") << std::endl;
    } else {
        std::cerr << "  Unexpected distance reading: " << distance_m << " m" << std::endl;
    }

    print_result("Single Measurement Test", result);
    return result;
}

bool Vl53l0xTest::test_continuous_measurement()
{
    if (!m_driver->check_connection()) {
        print_result("Continuous Measurement Test", false);
        return false;
    }

    bool start_result = m_driver->start_continuous();
    if (!start_result) {
        print_result("Continuous Measurement Test", false);
        return false;
    }

    /* Read continuous samples - 5 samples at ~1s intervals */
    bool read_result = true;
    int sample_count = 0;
    for (int i = 0; i < 5; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        
        float distance_m = m_driver->read_distance_meters();
        if (distance_m >= 0.03f && distance_m <= 2.0f) {
            sample_count++;
            std::cout << "  Sample " << (i+1) << ": " << std::fixed << std::setprecision(3) 
                      << distance_m << " m" << std::endl;
        } else {
            read_result = false;
            break;
        }
    }

    bool stop_result = m_driver->stop_continuous();
    if (!stop_result) {
        std::cerr << "  Failed to stop continuous mode" << std::endl;
        read_result = false;
    }

    bool overall_result = read_result && (sample_count >= 3);
    print_result("Continuous Measurement Test", overall_result);
    return overall_result;
}

bool Vl53l0xTest::test_get_distance()
{
    if (!m_driver->check_connection()) {
        print_result("Get Distance (mm) Test", false);
        return false;
    }

    uint16_t distance_mm = m_driver->get_distance();
    bool result = (distance_mm >= 30 && distance_mm <= 2000);
    
    if (result) {
        std::cout << "  Distance: " << distance_mm << " mm" << std::endl;
    } else {
        std::cerr << "  Unexpected distance reading: " << distance_mm << " mm" << std::endl;
    }

    print_result("Get Distance (mm) Test", result);
    return result;
}

bool Vl53l0xTest::test_read_distance_meters()
{
    if (!m_driver->check_connection()) {
        print_result("Read Distance (meters) Test", false);
        return false;
    }

    float distance_m = m_driver->read_distance_meters();
    bool result = (distance_m >= 0.03f && distance_m <= 2.0f);
    
    if (result) {
        std::cout << "  Distance: " << std::fixed << std::setprecision(3) << distance_m << " m" << std::endl;
    } else {
        std::cerr << "  Unexpected distance reading: " << distance_m << " m" << std::endl;
    }

    print_result("Read Distance (meters) Test", result);
    return result;
}

bool Vl53l0xTest::test_user_detection()
{
    if (!m_driver->check_connection()) {
        print_result("User Detection Test", false);
        return false;
    }

    /* Read multiple distances to get a reliable signal */
    float avg_distance = 0.0f;
    int sample_count = 3;
    
    for (int i = 0; i < sample_count; ++i) {
        avg_distance += m_driver->read_distance_meters();
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    avg_distance /= sample_count;

    bool is_detected = m_driver->is_user_detected();
    bool expected = (avg_distance > 0.05f && avg_distance <= 0.8f);
    bool result = (is_detected == expected);
    
    std::cout << "  Average Distance: " << std::fixed << std::setprecision(3) << avg_distance << " m" << std::endl;
    std::cout << "  Threshold: 0.05m - 0.8m" << std::endl;
    std::cout << "  User Detected: " << (is_detected ? "Yes" : "No") << std::endl;

    print_result("User Detection Test", result);
    return result;
}

bool Vl53l0xTest::test_connection_status()
{
    bool connected = m_driver->check_connection();
    print_result("Connection Status Test", connected);
    return connected;
}

bool Vl53l0xTest::test_sensor_reset()
{
    if (!m_driver->check_connection()) {
        print_result("Sensor Reset Test", false);
        return false;
    }

    m_driver->reset_sensor();
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    bool result = m_driver->check_connection();
    if (result) {
        float distance_m = m_driver->read_distance_meters();
        result = (distance_m >= 0.03f && distance_m <= 2.0f);
        if (result) {
            std::cout << "  Post-reset distance: " << std::fixed << std::setprecision(3) << distance_m << " m" << std::endl;
        }
    }

    print_result("Sensor Reset Test", result);
    return result;
}

int Vl53l0xTest::run_all_tests()
{
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "         VL53L0X Time-of-Flight Sensor Driver Test Suite" << std::endl;
    std::cout << std::string(70, '=') << std::endl << std::endl;

    std::cout << "Running tests on VL53L0X sensor..." << std::endl << std::endl;

    test_initialization();
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    if (m_driver->check_connection()) {
        test_single_measurement();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_get_distance();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_read_distance_meters();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_continuous_measurement();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_user_detection();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_connection_status();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        test_sensor_reset();
    } else {
        std::cerr << "\n\033[31mSensor not connected. Skipping remaining tests.\033[0m\n" << std::endl;
    }

    /* Print summary */
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "Test Summary:" << std::endl;
    std::cout << "  Passed: \033[32m" << m_tests_passed << "\033[0m" << std::endl;
    std::cout << "  Failed: \033[31m" << m_tests_failed << "\033[0m" << std::endl;
    std::cout << std::string(70, '=') << std::endl << std::endl;

    return m_tests_failed;
}
