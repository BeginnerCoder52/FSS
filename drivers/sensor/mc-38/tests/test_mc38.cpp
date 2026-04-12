/**
 * @file test_mc38.cpp
 * @brief Test program for MC-38 Magnetic Door Sensor driver on GPIO26.
 * 
 * This test program demonstrates and verifies the functionality of the MC-38
 * magnetic door sensor driver using GPIO26 and Ground.
 * 
 * Hardware Setup:
 * - MC-38 Terminal 1: Connected to GPIO26 (Pin 37)
 * - MC-38 Terminal 2: Connected to Ground (Pin 39)
 * 
 * Build Instructions:
 *   g++ -std=c++17 -o test_mc38 test_mc38.cpp ../src/MC38.cpp \
 *       -I../include -lgpiod
 * 
 * Run as root:
 *   sudo ./test_mc38
 * 
 * @author SMART_MIRROR FSS Team
 */

#include "../include/MC38.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <iomanip>
#include <cstring>
#include <ctime>
#include <unistd.h>

/**
 * @brief Prints a formatted header for test output
 */
void printHeader(const std::string& title) {
    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "  " << title << std::endl;
    std::cout << std::string(60, '=') << std::endl;
}

/**
 * @brief Prints a formatted section separator
 */
void printSeparator() {
    std::cout << std::string(60, '-') << std::endl;
}

/**
 * @brief Prints sensor status in a formatted way
 */
void printStatus(const MC38::DoorStatus& status) {
    std::string status_str;
    std::string indicator;
    
    switch (status) {
        case MC38::DoorStatus::CLOSED:
            status_str = "CLOSED";
            indicator = "[●] MAGNET DETECTED - Door is CLOSED";
            break;
        case MC38::DoorStatus::OPEN:
            status_str = "OPEN";
            indicator = "[○] NO MAGNET - Door is OPEN";
            break;
        case MC38::DoorStatus::UNKNOWN:
            status_str = "UNKNOWN";
            indicator = "[?] ERROR - Could not read door status";
            break;
    }
    
    std::cout << "Status: " << std::setw(10) << std::left << status_str 
              << " | " << indicator << std::endl;
}

/**
 * @brief Test 1: Initialization test
 * Verifies that the MC38 sensor can be properly initialized on GPIO26
 */
bool test_initialization() {
    printHeader("TEST 1: MC38 Initialization");
    
    std::cout << "Initializing MC38 on GPIO26 (/dev/gpiochip0)..." << std::endl;
    
    MC38 sensor(26);  // GPIO26
    
    if (sensor.initialize()) {
        std::cout << "✓ MC38 successfully initialized on GPIO26" << std::endl;
        return true;
    } else {
        std::cout << "✗ Failed to initialize MC38 on GPIO26" << std::endl;
        return false;
    }
}

/**
 * @brief Test 2: Single status read test
 * Reads the door status once and verifies the operation
 */
bool test_single_read() {
    printHeader("TEST 2: Single Status Read");
    
    MC38 sensor(26);  // GPIO26
    
    if (!sensor.initialize()) {
        std::cout << "✗ Failed to initialize sensor" << std::endl;
        return false;
    }
    
    std::cout << "Reading door status..." << std::endl;
    MC38::DoorStatus status = sensor.getStatus();
    
    if (status == MC38::DoorStatus::UNKNOWN) {
        std::cout << "✗ Failed to read sensor status" << std::endl;
        return false;
    }
    
    std::cout << "✓ Successfully read sensor status" << std::endl;
    printStatus(status);
    return true;
}

/**
 * @brief Test 3: Helper methods test
 * Tests the isDoorOpen() and isDoorClosed() convenience methods
 */
bool test_helper_methods() {
    printHeader("TEST 3: Helper Methods (isDoorOpen/isDoorClosed)");
    
    MC38 sensor(26);  // GPIO26
    
    if (!sensor.initialize()) {
        std::cout << "✗ Failed to initialize sensor" << std::endl;
        return false;
    }
    
    std::cout << "Testing convenience methods..." << std::endl;
    
    bool is_open = sensor.isDoorOpen();
    bool is_closed = sensor.isDoorClosed();
    
    // Exactly one should be true at any given time
    if ((is_open && !is_closed) || (!is_open && is_closed)) {
        std::cout << "✓ Helper methods working correctly" << std::endl;
        std::cout << "  - isDoorOpen(): " << (is_open ? "true" : "false") << std::endl;
        std::cout << "  - isDoorClosed(): " << (is_closed ? "true" : "false") << std::endl;
        return true;
    } else {
        std::cout << "✗ Helper methods returned inconsistent results" << std::endl;
        return false;
    }
}

/**
 * @brief Test 4: Continuous monitoring test
 * Continuously monitors the door sensor for 10 seconds
 */
bool test_continuous_monitoring() {
    printHeader("TEST 4: Continuous Monitoring (10 seconds)");
    
    MC38 sensor(26);  // GPIO26
    
    if (!sensor.initialize()) {
        std::cout << "✗ Failed to initialize sensor" << std::endl;
        return false;
    }
    
    std::cout << "Monitoring door sensor for 10 seconds..." << std::endl;
    std::cout << "Try opening/closing the door while this runs." << std::endl;
    printSeparator();
    
    MC38::DoorStatus last_status = MC38::DoorStatus::UNKNOWN;
    auto start_time = std::chrono::steady_clock::now();
    int update_count = 0;
    
    while (true) {
        auto current_time = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            current_time - start_time
        ).count();
        
        if (elapsed >= 10) {
            break;
        }
        
        MC38::DoorStatus current_status = sensor.getStatus();
        
        // Print status update only when it changes
        if (current_status != last_status || update_count % 20 == 0) {
            std::time_t now = std::time(nullptr);
            std::cout << "[" << std::put_time(std::localtime(&now), "%H:%M:%S") << "] ";
            printStatus(current_status);
            last_status = current_status;
            update_count = 0;
        }
        
        update_count++;
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    printSeparator();
    std::cout << "✓ Continuous monitoring completed" << std::endl;
    return true;
}

/**
 * @brief Main test runner
 * Executes all tests and reports results
 */
int main() {
    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════╗" << std::endl;
    std::cout << "║       MC-38 MAGNETIC DOOR SENSOR TEST SUITE (GPIO26)      ║" << std::endl;
    std::cout << "║                                                          ║" << std::endl;
    std::cout << "║  Hardware Configuration:                                 ║" << std::endl;
    std::cout << "║  - MC38 Terminal 1 → GPIO26 (Pin 37)                     ║" << std::endl;
    std::cout << "║  - MC38 Terminal 2 → Ground (Pin 39)                     ║" << std::endl;
    std::cout << "║                                                          ║" << std::endl;
    std::cout << "║  Note: This test requires root privileges and a          ║" << std::endl;
    std::cout << "║  properly connected MC-38 sensor.                        ║" << std::endl;
    std::cout << "╚══════════════════════════════════════════════════════════╝" << std::endl;
    
    // Check if running as root
    if (geteuid() != 0) {
        std::cerr << "\n⚠ WARNING: This test should be run as root for GPIO access." << std::endl;
        std::cerr << "Try: sudo ./test_mc38\n" << std::endl;
    }
    
    // Run tests
    int passed = 0;
    int total = 4;
    
    // Test 1: Initialization
    if (test_initialization()) {
        passed++;
    }
    
    // Test 2: Single Read
    if (test_single_read()) {
        passed++;
    }
    
    // Test 3: Helper Methods
    if (test_helper_methods()) {
        passed++;
    }
    
    // Test 4: Continuous Monitoring
    if (test_continuous_monitoring()) {
        passed++;
    }
    
    // Print summary
    printHeader("TEST SUMMARY");
    std::cout << "Tests passed: " << passed << "/" << total << std::endl;
    
    if (passed == total) {
        std::cout << "✓ All tests completed successfully!" << std::endl;
        std::cout << "\nThe MC-38 sensor on GPIO26 is working correctly." << std::endl;
    } else {
        std::cout << "✗ Some tests failed. Please check the GPIO configuration." << std::endl;
    }
    
    std::cout << std::string(60, '=') << "\n" << std::endl;
    
    return (passed == total) ? 0 : 1;
}
