/**
 * @file test_main.cpp
 * @brief Main entry point for SHT31 sensor tests.
 * 
 * Runs comprehensive tests on the SHT3xDriver implementation.
 */

#include "Sht3xTest.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cstring>

void print_usage(const char *program_name)
{
    std::cout << "Usage: " << program_name << " [options]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -b, --bus <device>      I2C bus device (default: /dev/i2c-1)" << std::endl;
    std::cout << "  -a, --address <addr>    Sensor I2C address (0x44 or 0x45, default: 0x44)" << std::endl;
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
    std::string i2c_bus = "/dev/i2c-1";
    std::string i2c_bus_2 = "/dev/i2c-5";
    uint8_t i2c_address = 0x44;

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
    std::cout << "I2C Bus 2: " << i2c_bus_2 << std::endl;
    std::cout << "Sensor Address: 0x" << std::hex << std::setfill('0') << std::setw(2) 
              << (int)i2c_address << std::dec << std::endl << std::endl;
    
    /* Check if I2C device exists */
    check_i2c_device(i2c_bus);
    check_i2c_device(i2c_bus_2);
    
    std::cout << "\033[33m[SETUP HELP]\033[0m Before running tests:" << std::endl;
    std::cout << "  1. Verify I2C bus number (typically 1 for default, check README_PINOUT.md)" << std::endl;
    std::cout << "  2. Run: i2cdetect -y <bus_number>" << std::endl;
    std::cout << "  3. Sensor should appear at 0x" << std::hex << std::setfill('0') 
              << std::setw(2) << (int)i2c_address << std::dec << std::endl;
    std::cout << "  4. Check hardware: SDA=GPIO2, SCL=GPIO3 for default I2C-1" << std::endl << std::endl;

    /* Create test suite and run */
    Sht3xTest test_suite_1(i2c_bus, i2c_address);
    int failed_tests_1 = test_suite_1.run_all_tests();

    Sht3xTest test_suite_2(i2c_bus_2, i2c_address);
    int failed_tests_2 = test_suite_2.run_all_tests();
    return (failed_tests_1 + failed_tests_2) > 0 ? 1 : 0;
}
