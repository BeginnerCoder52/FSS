/**
 * @file test_main.cpp
 * @brief Main entry point for VL53L0X sensor tests.
 * 
 * Runs comprehensive tests on the Vl53l0xDriver implementation.
 */

#include "Vl53l0xTest.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cstring>

void print_usage(const char *program_name)
{
    std::cout << "Usage: " << program_name << " [options]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -b, --bus <device>      I2C bus device (default: /dev/i2c-6)" << std::endl;
    std::cout << "  -a, --address <addr>    Sensor I2C address (default: 0x29)" << std::endl;
    std::cout << "  -h, --help              Show this help message" << std::endl;
}

/**
 * @brief Check if I2C device exists and print diagnostics.
 */
void check_i2c_device(const std::string& i2c_bus)
{
    std::ifstream device_check(i2c_bus);
    if (!device_check.good()) {
        std::cerr << "\033[31m[ERROR]\033[0m I2C device not found: " << i2c_bus << std::endl;
        std::cerr << "Available I2C devices:" << std::endl;
        system("ls /dev/i2c-* 2>/dev/null || echo '  (none found)'");
        std::cerr << std::endl;
    }
}

int main(int argc, char *argv[])
{
    std::string i2c_bus = "/dev/i2c-6";
    uint8_t i2c_address = 0x29;

    /* Parse command line arguments */
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "-b") == 0 || strcmp(argv[i], "--bus") == 0) {
            if (i + 1 < argc) {
                i2c_bus = argv[++i];
            }
        } else if (strcmp(argv[i], "-a") == 0 || strcmp(argv[i], "--address") == 0) {
            if (i + 1 < argc) {
                i2c_address = strtol(argv[++i], nullptr, 0);
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

    std::cout << "I2C Bus: " << i2c_bus << std::endl;
    std::cout << "Sensor Address: 0x" << std::hex << std::setfill('0') << std::setw(2) 
              << (int)i2c_address << std::dec << std::endl << std::endl;
    
    /* Check if I2C device exists */
    check_i2c_device(i2c_bus);
    
    std::cout << "\033[33m[SETUP HELP]\033[0m Before running tests:" << std::endl;
    std::cout << "  1. Verify I2C-6 is enabled: check /boot/config.txt or /boot/firmware/config.txt" << std::endl;
    std::cout << "  2. Must have: dtoverlay=i2c6,pins_22_23 in config" << std::endl;
    std::cout << "  3. Run: i2cdetect -y 6" << std::endl;
    std::cout << "  4. Sensor should appear at 0x" << std::hex << std::setfill('0') 
              << std::setw(2) << (int)i2c_address << std::dec << std::endl;
    std::cout << "  5. Check hardware: SDA=GPIO22, SCL=GPIO23, VCC=3.3V, GND" << std::endl;
    std::cout << "  6. Refer to README_PINOUT.md for pinout details" << std::endl << std::endl;

    /* Create test suite and run */
    Vl53l0xTest test_suite(i2c_bus, i2c_address);
    int failed_tests = test_suite.run_all_tests();

    return failed_tests > 0 ? 1 : 0;
}
