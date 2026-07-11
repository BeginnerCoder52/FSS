cmake_minimum_required(VERSION 3.10)
project(FSS_CameraCore VERSION 1.0 LANGUAGES CXX)

##############################################################################
# PROJECT METADATA (SDD v1.1.0 Compliance)
##############################################################################
# FRTApp C++ Camera Core
# Purpose: USB video capture via V4L2 and POSIX shared memory publishing
# Component Classes:
#   - VideoCapture: V4L2 USB camera stream handling (/dev/video0)
#   - ShmWriter: POSIX shared memory writer for frame data
#
# D-Bus Service: vn.edu.uit.FSS.FRTApp
# Shared Memory: /fss_video_frame (POSIX named shared memory)
# Output Format: JPEG-encoded frames to shared buffer
# Target Platform: Raspberry Pi 4B (ARM aarch64)
##############################################################################

##############################################################################
# COMPILER CONFIGURATION
##############################################################################
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall -Wextra -pedantic")

find_package(PkgConfig REQUIRED)

##############################################################################
# DEPENDENCY DISCOVERY
##############################################################################
# OpenCV - Computer vision library with V4L2 backend
# Components:
#   - core: Basic image data structures and operations
#   - videoio: Video capture from /dev/video0 (V4L2)
#   - imgcodecs: JPEG encoding for frame compression
find_package(OpenCV REQUIRED COMPONENTS core videoio imgcodecs)

##############################################################################
# INCLUDE DIRECTORIES
##############################################################################
include_directories(
    include
    ${OpenCV_INCLUDE_DIRS}
)

##############################################################################
# SOURCE FILES
##############################################################################
# Main source files in src/ directory
file(GLOB SOURCES "src/*.cpp")
list(REMOVE_ITEM SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/camera_test.cpp")

##############################################################################
# BUILD EXECUTABLE
##############################################################################
# Produces: camera_core_exec
# Purpose: Standalone C++ process for USB camera stream handling
add_executable(camera_core_exec ${SOURCES})

##############################################################################
# LINK LIBRARIES
##############################################################################
# Essential libraries for camera and shared memory:
# - rt: Real-time POSIX library
#   Required APIs: shm_open(), shm_unlink(), mmap()
#   Purpose: Create and manage POSIX named shared memory regions
# - v4l2: V4L2 camera API
#   Required APIs: v4l2_ioctl, v4l2_mmap, device I/O controls
#   Purpose: Direct kernel video device access
# - OpenCV libraries: Video capture and JPEG encoding
target_link_libraries(camera_core_exec
    PRIVATE
    rt
    v4l2
    ${OpenCV_LIBS}
)

##############################################################################
# INSTALLATION
##############################################################################
# Install to system binary directory
install(TARGETS camera_core_exec DESTINATION /usr/local/bin)
