cmake_minimum_required(VERSION 3.10)
project(FSS_SensorDaemon_Tests VERSION 1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GPIOD REQUIRED libgpiod)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/sensor/sht3x/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/sensor/sht3x/interface
    ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/sensor/vl53l0x/src
    ${GPIOD_INCLUDE_DIRS}
)

# SHT31 Driver source files
set(SHT3X_DRIVER_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/sensor/sht3x/src/driver_sht31.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/sht31_driver_interface.c"
)

# Wrapper implementation
set(WRAPPER_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/I2cHandler.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/Sht3xDriver.cpp"
)

# Test sources
set(TEST_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/sht3x/Sht3xTest.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/sht3x/test_main.cpp"
)

# Create test executable
add_executable(sht3x_test
    ${SHT3X_DRIVER_SOURCES}
    ${WRAPPER_SOURCES}
    ${TEST_SOURCES}
)

# Link libraries
target_link_libraries(sht3x_test
    PRIVATE
    i2c
    pthread
    ${GPIOD_LIBRARIES}
)

# Compilation flags for libgpiod
target_compile_options(sht3x_test PRIVATE ${GPIOD_CFLAGS})

# Native test executable (uses I2C_RDWR directly, no wrapper)
add_executable(sht3x_native_test
    ${SHT3X_DRIVER_SOURCES}
    "${CMAKE_CURRENT_SOURCE_DIR}/sht3x/Sht3xNativeTest.cpp"
)

# Link libraries for native test
target_link_libraries(sht3x_native_test
    PRIVATE
    i2c
    pthread
)

# VL53L0X Driver source files
set(VL53L0X_DRIVER_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/sensor/vl53l0x/src/vl53l0x.c"
)

# VL53L0X Wrapper implementation
set(VL53L0X_WRAPPER_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/I2cHandler.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/Vl53l0xDriver.cpp"
)

# VL53L0X Test sources
set(VL53L0X_TEST_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/vl53l0x/Vl53l0xTest.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/vl53l0x/test_main.cpp"
)

# Create VL53L0X test executable
add_executable(vl53l0x_test
    ${VL53L0X_DRIVER_SOURCES}
    ${VL53L0X_WRAPPER_SOURCES}
    ${VL53L0X_TEST_SOURCES}
)

# Link libraries for VL53L0X test
target_link_libraries(vl53l0x_test
    PRIVATE
    i2c
    pthread
    ${GPIOD_LIBRARIES}
)

# Compilation flags for libgpiod
target_compile_options(vl53l0x_test PRIVATE ${GPIOD_CFLAGS})

