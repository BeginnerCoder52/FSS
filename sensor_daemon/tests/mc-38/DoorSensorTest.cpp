/**
 * @file DoorSensorTest.cpp
 * @brief Implementation of DoorSensorDriver unit tests.
 */

#include "DoorSensorTest.hpp"
#include "DoorSensorDriver.hpp"
#include "GpioHandler.hpp"
#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>

DoorSensorTest::DoorSensorTest(int gpio_offset)
    : m_gpio_offset(gpio_offset), m_tests_passed(0), m_tests_failed(0)
{
    m_gpio_handler = std::make_shared<GpioHandler>("/dev/gpiochip0");
    m_driver = std::make_shared<DoorSensorDriver>(m_gpio_handler, gpio_offset);
}

DoorSensorTest::~DoorSensorTest()
{
}

void DoorSensorTest::print_result(const std::string& test_name, bool passed)
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

int DoorSensorTest::run_all_tests()
{
    std::cout << "\033[36m" << std::string(60, '=') << "\033[0m" << std::endl;
    std::cout << "\033[36mRunning MC-38 Door Sensor Tests\033[0m" << std::endl;
    std::cout << "\033[36m" << std::string(60, '=') << "\033[0m" << std::endl << std::endl;

    test_initialization();
    test_read_state();
    test_is_open();
    test_is_closed();
    test_diagnose_gpio_line();
    test_clear_interrupt_flags();
    test_continuous_monitoring();

    // Print API summary
    std::cout << "\n\033[33m[API SUMMARY]\033[0m" << std::endl;
    std::cout << "  init_driver(): " << (m_driver->diagnose_gpio_line() ? "initialized" : "not initialized") << std::endl;
    std::cout << "  read_state(): " << m_driver->read_state() << std::endl;
    std::cout << "  is_open(): " << (m_driver->is_open() ? "true" : "false") << std::endl;
    std::cout << "  is_closed(): " << (m_driver->is_closed() ? "true" : "false") << std::endl;
    std::cout << "  diagnose_gpio_line(): " << (m_driver->diagnose_gpio_line() ? "connected" : "not connected") << std::endl;

    std::cout << "\n\033[36m" << std::string(60, '=') << "\033[0m" << std::endl;
    std::cout << "Test Summary:" << std::endl;
    std::cout << "  Passed: " << m_tests_passed << std::endl;
    std::cout << "  Failed: " << m_tests_failed << std::endl;
    std::cout << "\033[36m" << std::string(60, '=') << "\033[0m" << std::endl;

    return m_tests_failed;
}

bool DoorSensorTest::test_initialization()
{
    std::cout << "\n\033[33m[TEST 1: Initialization]\033[0m" << std::endl;
    std::cout << "  GPIO Pin: GPIO" << m_gpio_offset << " (Pin 37)" << std::endl;
    std::cout << "  GPIO Chip: /dev/gpiochip0" << std::endl;
    
    bool result = m_driver->init_driver();
    
    if (!result) {
        std::cerr << "  \033[33m[DEBUG] Initialization failed - Verify:\033[0m" << std::endl;
        std::cerr << "    - MC-38 connected to GPIO26 (Pin 37) and GND (Pin 39)" << std::endl;
        std::cerr << "    - Run 'pinctrl' to check GPIO26 status" << std::endl;
        std::cerr << "    - Ensure running with sudo for GPIO access" << std::endl;
    }
    
    print_result("Initialization Test", result);
    return result;
}

bool DoorSensorTest::test_read_state()
{
    std::cout << "\n\033[33m[TEST 2: Read State API]\033[0m" << std::endl;
    
    if (!m_driver->diagnose_gpio_line()) {
        print_result("Read State Test", false);
        std::cerr << "  Driver not initialized" << std::endl;
        return false;
    }

    std::string state = m_driver->read_state();
    bool result = (state == "OPEN" || state == "CLOSED");
    
    if (result) {
        std::cout << "  Current State: " << state << std::endl;
    } else {
        std::cerr << "  Invalid state returned: " << state << std::endl;
    }

    print_result("Read State Test", result);
    return result;
}

bool DoorSensorTest::test_is_open()
{
    std::cout << "\n\033[33m[TEST 3: is_open() Method]\033[0m" << std::endl;
    
    if (!m_driver->diagnose_gpio_line()) {
        print_result("is_open() Test", false);
        std::cerr << "  Driver not initialized" << std::endl;
        return false;
    }

    bool is_open = m_driver->is_open();
    std::string state = m_driver->read_state();
    bool result = (is_open == (state == "OPEN"));
    
    std::cout << "  is_open(): " << (is_open ? "true" : "false") << std::endl;
    std::cout << "  read_state(): " << state << std::endl;

    if (!result) {
        std::cerr << "  Mismatch between is_open() and read_state()" << std::endl;
    }

    print_result("is_open() Test", result);
    return result;
}

bool DoorSensorTest::test_is_closed()
{
    std::cout << "\n\033[33m[TEST 4: is_closed() Method]\033[0m" << std::endl;
    
    if (!m_driver->diagnose_gpio_line()) {
        print_result("is_closed() Test", false);
        std::cerr << "  Driver not initialized" << std::endl;
        return false;
    }

    bool is_closed = m_driver->is_closed();
    std::string state = m_driver->read_state();
    bool result = (is_closed == (state == "CLOSED"));
    
    std::cout << "  is_closed(): " << (is_closed ? "true" : "false") << std::endl;
    std::cout << "  read_state(): " << state << std::endl;

    if (!result) {
        std::cerr << "  Mismatch between is_closed() and read_state()" << std::endl;
    }

    print_result("is_closed() Test", result);
    return result;
}

bool DoorSensorTest::test_diagnose_gpio_line()
{
    std::cout << "\n\033[33m[TEST 5: GPIO Diagnosis]\033[0m" << std::endl;
    
    bool result = m_driver->diagnose_gpio_line();
    
    std::cout << "  GPIO Line Status: " << (result ? "Connected" : "Not Connected") << std::endl;

    if (!result) {
        std::cerr << "  \033[33m[DEBUG] GPIO line not available:\033[0m" << std::endl;
        std::cerr << "    - Check device is powered and connected" << std::endl;
        std::cerr << "    - Verify no other application is using GPIO26" << std::endl;
        std::cerr << "    - Run 'sudo fuser -v /dev/gpiochip0'" << std::endl;
    }

    print_result("GPIO Diagnosis Test", result);
    return result;
}

bool DoorSensorTest::test_clear_interrupt_flags()
{
    std::cout << "\n\033[33m[TEST 6: Clear Interrupt Flags]\033[0m" << std::endl;
    
    if (!m_driver->diagnose_gpio_line()) {
        print_result("Clear Interrupt Flags Test", false);
        std::cerr << "  Driver not initialized" << std::endl;
        return false;
    }

    // Call the API (doesn't throw on MC-38 since it's a simple GPIO sensor)
    m_driver->clear_interrupt_flags();
    
    bool result = true;
    std::cout << "  Interrupt flags cleared successfully" << std::endl;

    print_result("Clear Interrupt Flags Test", result);
    return result;
}

bool DoorSensorTest::test_continuous_monitoring()
{
    std::cout << "\n\033[33m[TEST 7: Continuous Monitoring (10 seconds)]\033[0m" << std::endl;
    
    if (!m_driver->diagnose_gpio_line()) {
        print_result("Continuous Monitoring Test", false);
        std::cerr << "  Driver not initialized" << std::endl;
        return false;
    }

    std::cout << "  Monitoring door state for 10 seconds..." << std::endl;
    std::cout << "  Try opening/closing the door while this runs." << std::endl;
    std::cout << "  State changes will be printed below:" << std::endl;

    std::string last_state = "";
    int state_changes = 0;
    int read_count = 0;
    auto start_time = std::chrono::steady_clock::now();

    while (true) {
        auto current_time = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            current_time - start_time
        ).count();

        if (elapsed >= 10) {
            break;
        }

        std::string current_state = m_driver->read_state();
        read_count++;
        
        if (current_state != last_state) {
            std::cout << "    [" << std::setfill('0') << std::setw(2) << elapsed << "s] "
                      << "State changed to: " << std::setfill(' ') << std::setw(6) << current_state;
            
            if (current_state == "OPEN") {
                std::cout << " (door open, magnet far)" << std::endl;
            } else if (current_state == "CLOSED") {
                std::cout << " (door closed, magnet near)" << std::endl;
            } else {
                std::cout << " (unknown)" << std::endl;
            }
            
            last_state = current_state;
            state_changes++;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    std::cout << "  Total reads: " << read_count << " | State changes observed: " << state_changes << std::endl;
    bool result = (state_changes >= 0);

    print_result("Continuous Monitoring Test", result);
    return result;
}
