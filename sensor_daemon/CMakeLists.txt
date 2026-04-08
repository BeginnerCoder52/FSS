cmake_minimum_required(VERSION 3.10)
project(FSS_SensorDaemon VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Tối ưu hóa cho Raspberry Pi
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

# Tìm các package cần thiết thông qua pkg-config
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDBUS REQUIRED sdbus-c++)
pkg_check_modules(ZMQ REQUIRED libzmq)

# Bao gồm thư mục header của daemon và thư mục drivers
include_directories(
    include
    ../drivers/sensor/sht3x
    ../drivers/sensor/vl53l0x
    ../drivers/sensor/mc-38
    ${SDBUS_INCLUDE_DIRS}
    ${ZMQ_INCLUDE_DIRS}
)

# Gom tất cả source code lại
file(GLOB SOURCES "src/*.cpp")
# (Tùy chọn) Thêm source của phần driver nếu bạn không build static lib riêng
file(GLOB DRIVER_SOURCES "../drivers/sensor/**/*.cpp")

# Tạo executable
add_executable(sensor_daemon_exec ${SOURCES} ${DRIVER_SOURCES})

# Link libraries (i2c cho sensor, sdbus-c++ cho D-Bus, zmq cho IPC)
target_link_libraries(sensor_daemon_exec
    PRIVATE
    i2c
    ${SDBUS_LIBRARIES}
    ${ZMQ_LIBRARIES}
)
