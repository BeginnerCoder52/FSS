cmake_minimum_required(VERSION 3.10)
project(FSS_SensorDaemon VERSION 1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Tối ưu hóa cho Raspberry Pi
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

# Tìm các package cần thiết thông qua pkg-config
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDBUS REQUIRED sdbus-c++)
pkg_check_modules(ZMQ REQUIRED libzmq)
pkg_check_modules(GPIOD REQUIRED libgpiod)

# Bao gồm thư mục header của daemon và thư mục drivers
include_directories(
    include
    ../drivers/sensor/sht3x/src
    ../drivers/sensor/sht3x/interface
    ../drivers/sensor/sht3x/example
    ../drivers/sensor/vl53l0x/src
    ../drivers/sensor/mc-38/include
    ${SDBUS_INCLUDE_DIRS}
    ${ZMQ_INCLUDE_DIRS}
    ${GPIOD_INCLUDE_DIRS}
)

# Gom tất cả source code lại (C++ và C)
file(GLOB SOURCES "src/*.cpp")
set(DRIVER_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/sht3x/src/driver_sht31.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/sht31_driver_interface.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/vl53l0x/src/vl53l0x.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/../drivers/sensor/mc-38/src/MC38.cpp"
)

# Tạo executable
add_executable(sensor_daemon_exec ${SOURCES} ${DRIVER_SOURCES})

# Add compile flags for libgpiod
target_compile_options(sensor_daemon_exec PRIVATE ${GPIOD_CFLAGS})

# Link libraries (i2c für sensor, gpiod für GPIO, sdbus-c++ for D-Bus, zmq for IPC)
target_link_libraries(sensor_daemon_exec
    PRIVATE
    i2c
    systemd
    ${SDBUS_LIBRARIES}
    ${ZMQ_LIBRARIES}
    ${GPIOD_LIBRARIES}
)
