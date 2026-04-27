################################################################################
# @file CMakeLists.txt
# @brief CMake configuration for FSS Unit Tests (all modules)
# @author FSS Development Team
# @version 1.0.0
# @date 2024
#
# This CMake file orchestrates the build configuration for all unit tests
# across the FSS project. It handles compiler settings, dependencies, and
# test discovery/execution.
################################################################################

cmake_minimum_required(VERSION 3.10)
project(FSS_UnitTests VERSION 1.0 LANGUAGES C CXX)

# ============================================================================
# Global Build Configuration
# ============================================================================
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler flags for optimal testing environment
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O0 -Wall -Wextra -g --coverage")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O0 -Wall -Wextra -g --coverage")

# Enable CMake testing framework
enable_testing()

# ============================================================================
# Find Required Packages
# ============================================================================
find_package(PkgConfig REQUIRED)

# Google Test (GTest) - Main testing framework
find_package(GTest REQUIRED)

# Required libraries for sensor daemon tests
pkg_check_modules(SDBUS REQUIRED sdbus-c++)
pkg_check_modules(GPIOD REQUIRED libgpiod)

# ============================================================================
# Include Directories
# ============================================================================
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/../sensor_daemon/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/sht3x/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/sht3x/interface
    ${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/vl53l0x/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/mc-38/include
    ${GTEST_INCLUDE_DIRS}
    ${SDBUS_INCLUDE_DIRS}
    ${GPIOD_INCLUDE_DIRS}
)

# ============================================================================
# Add Test Subdirectories
# ============================================================================
# Only sensor_daemon unit tests for now
add_subdirectory(unit/sensor_daemon)

# ============================================================================
# Test Summary Report
# ============================================================================
# This configuration enables:
# - Automatic test discovery via ctest
# - Code coverage reporting (gcov compatible)
# - Multiple test filtering and execution strategies
#
# Build Tests:
#   cmake -B build -DCMAKE_BUILD_TYPE=Debug
#   cmake --build build
#
# Run All Tests:
#   ctest --test-dir build
#
# Run with Verbose Output:
#   ctest --test-dir build -V
#
# Run Specific Test Module:
#   ctest --test-dir build -R SensorDaemonMain -V
#
# Generate Coverage Report:
#   cd build && gcovr --print-summary
################################################################################
