/**
 * @file test_main.cpp
 * @brief Main entry point for MC-38 door sensor tests.
 * 
 * Runs comprehensive tests on the DoorSensorDriver implementation.
 */

#include "DoorSensorTest.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cstring>

void print_usage(const char *program_name)
{
    std::cout << "Usage: " << program_name << " [options]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -g, --gpio <offset>     GPIO offset for MC-38 sensor (default: 26)" << std::endl;
    std::cout << "  -h, --help              Show this help message" << std::endl;
}

/**
 * @brief Check if GPIO device exists and print diagnostics.
 */
void check_gpio_device()
{
    std::ifstream device_check("/dev/gpiochip0");
    if (!device_check.good()) {
        std::cerr << "\033[31m[ERROR]\033[0m GPIO device not found: /dev/gpiochip0" << std::endl;
        std::cerr << "Available GPIO devices:" << std::endl;
        system("ls /dev/gpiochip* 2>/dev/null || echo '  (none found)'");
        std::cerr << std::endl;
    }
}

int main(int argc, char *argv[])
{
    int gpio_offset = 26;

    /* Parse command line arguments */
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "-g") == 0 || strcmp(argv[i], "--gpio") == 0) {
            if (i + 1 < argc) {
                gpio_offset = std::stoi(argv[++i]);
            }
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            std::cerr << "Unknown option: " << argv[i] << std::endl;
            print_usage(argv[0]);
            return 1;
        }
    }

    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════╗" << std::endl;
    std::cout << "║          MC-38 DOOR SENSOR DRIVER TEST SUITE             ║" << std::endl;
    std::cout << "║                                                          ║" << std::endl;
    std::cout << "║  Hardware Configuration:                                 ║" << std::endl;
    std::cout << "║  - MC38 Terminal 1 → GPIO" << std::setw(2) << gpio_offset << " (Pin 37)              ║" << std::endl;
    std::cout << "║  - MC38 Terminal 2 → Ground (Pin 39)                     ║" << std::endl;
    std::cout << "║  - GPIO Chip: /dev/gpiochip0                            ║" << std::endl;
    std::cout << "║                                                          ║" << std::endl;
    std::cout << "║  Note: This test requires root privileges (sudo)         ║" << std::endl;
    std::cout << "╚══════════════════════════════════════════════════════════╝" << std::endl << std::endl;
    
    /* Check if GPIO device exists */
    check_gpio_device();
    
    std::cout << "\033[33m[SETUP HELP]\033[0m Before running tests:" << std::endl;
    std::cout << "  1. Verify MC-38 is connected to GPIO26 (Pin 37) and GND (Pin 39)" << std::endl;
    std::cout << "  2. Run: pinctrl to check GPIO26 status" << std::endl;
    std::cout << "  3. Ensure running with sudo: sudo ./test_mc38" << std::endl;
    std::cout << "  4. For reference, check: grep 'MC-38' /path/to/README_PINOUT.md" << std::endl << std::endl;

    /* Create test suite and run */
    DoorSensorTest test_suite(gpio_offset);
    int failed_tests = test_suite.run_all_tests();

    return failed_tests > 0 ? 1 : 0;
}
