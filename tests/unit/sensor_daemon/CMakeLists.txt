################################################################################
# @file CMakeLists.txt
# @brief CMake configuration for Sensor Daemon Unit Tests
# @author FSS Development Team
# @version 1.0.0
# @date 2024
#
# This CMake file configures all unit tests for the sensor_daemon module.
# It includes tests for:
#   - SensorDaemonMain (main orchestrator)
#   - InputProcessor (sensor data acquisition)
#   - OutputProcessor (IPC broadcasting)
#   - SystemWatchdog (health monitoring)
#   - Individual sensor drivers (SHT3x, VL53L0x, MC-38)
#   - D-Bus interface communication
#
# Following ASPICE principles, tests cover:
#   - Unit functionality
#   - Component integration
#   - Error handling and recovery
#   - State machine transitions
################################################################################

cmake_minimum_required(VERSION 3.10)
project(SensorDaemon_Tests LANGUAGES C CXX)

# ============================================================================
# Configure Compiler and Build Environment
# ============================================================================
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Enable code coverage and debugging symbols
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O0 -g --coverage -fPIC")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O0 -g --coverage -fPIC")

# ============================================================================
# Define Source Files
# ============================================================================
# Core sensor daemon implementation
set(DAEMON_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/SensorDaemonMain.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/InputProcessor.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/OutputProcessor.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/SystemWatchdog.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/SensorDbusInterface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/Sht3xDriver.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/Vl53l0xDriver.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/DoorSensorDriver.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/I2cHandler.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/GpioHandler.cpp
)

# Driver implementation files (C sources)
set(DRIVER_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../drivers/sensor/sht3x/src/driver_sht31.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../sensor_daemon/src/sht31_driver_interface.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../drivers/sensor/vl53l0x/src/vl53l0x.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../drivers/sensor/mc-38/src/MC38.cpp
)

# Test files
set(TEST_SOURCES
    SensorDaemonMainTest.cpp
    InputProcessorTest.cpp
    OutputProcessorTest.cpp
    SystemWatchdogTest.cpp
    Sht3xDriverTest.cpp
    Vl53l0xDriverTest.cpp
    DoorSensorDriverTest.cpp
    SensorDbusInterfaceTest.cpp
)

# ============================================================================
# Add Executable for Each Test Module
# ============================================================================
# Test: SensorDaemonMain
add_executable(test_sensor_daemon_main
    test_sensor_daemon_main.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: InputProcessor
add_executable(test_input_processor
    test_input_processor.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: OutputProcessor
add_executable(test_output_processor
    test_output_processor.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: SystemWatchdog
add_executable(test_system_watchdog
    test_system_watchdog.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: Sht3xDriver
add_executable(test_sht3x_driver
    test_sht3x_driver.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: Vl53l0xDriver
add_executable(test_vl53l0x_driver
    test_vl53l0x_driver.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: DoorSensorDriver
add_executable(test_door_sensor_driver
    test_door_sensor_driver.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# Test: SensorDbusInterface
add_executable(test_sensor_dbus_interface
    test_sensor_dbus_interface.cpp
    ${DAEMON_SOURCES}
    ${DRIVER_SOURCES}
)

# ============================================================================
# Link Libraries and Dependencies
# ============================================================================
# List of test executables
set(TEST_TARGETS
    test_sensor_daemon_main
    test_input_processor
    test_output_processor
    test_system_watchdog
    test_sht3x_driver
    test_vl53l0x_driver
    test_door_sensor_driver
    test_sensor_dbus_interface
)

foreach(test_target ${TEST_TARGETS})
    # Google Test library
    target_link_libraries(${test_target} PRIVATE ${GTEST_LIBRARIES} gtest 
    gtest_main 
    gmock 
    gmock_main
    pthread)
    
    # System libraries
    target_link_libraries(${test_target} PRIVATE
        i2c
        systemd
        ${SDBUS_LIBRARIES}
        ${GPIOD_LIBRARIES}
    )
    
    # Add compile options
    target_compile_options(${test_target} PRIVATE ${GPIOD_CFLAGS})
endforeach()

# ============================================================================
# Register Tests with CTest
# ============================================================================
foreach(test_target ${TEST_TARGETS})
    add_test(NAME ${test_target} COMMAND ${test_target})
endforeach()

# ============================================================================
# Custom Commands for Test Execution
# ============================================================================
# Run all sensor daemon tests
add_custom_target(test_sensor_daemon
    COMMAND ctest --test-dir ${CMAKE_CURRENT_BINARY_DIR} -V
    DEPENDS ${TEST_TARGETS}
    COMMENT "Running all Sensor Daemon Unit Tests"
)

# Run with coverage report
add_custom_target(test_coverage
    COMMAND ${CMAKE_CTEST_COMMAND} --test-dir ${CMAKE_CURRENT_BINARY_DIR} -V
    COMMAND gcovr --print-summary
    DEPENDS ${TEST_TARGETS}
    COMMENT "Running tests with coverage analysis"
)

################################################################################
