cmake_minimum_required(VERSION 3.10)
project(FSS_CameraCore VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

find_package(PkgConfig REQUIRED)
# Chỉ yêu cầu core và videoio của OpenCV để nhẹ nhất có thể, không kéo theo GUI
find_package(OpenCV REQUIRED COMPONENTS core videoio)

include_directories(
    include
    ../drivers/usb_web_camera
    ${OpenCV_INCLUDE_DIRS}
)

file(GLOB SOURCES "src/*.cpp")
file(GLOB DRIVER_SOURCES "../drivers/usb_web_camera/*.cpp")

add_executable(camera_core_exec ${SOURCES} ${DRIVER_SOURCES})

# librt (rt) bắt buộc phải có để sử dụng shm_open() cho POSIX Shared Memory
# v4l2 cho truy cập luồng raw camera nếu driver cần
target_link_libraries(camera_core_exec
    PRIVATE
    rt
    v4l2
    ${OpenCV_LIBS}
)
