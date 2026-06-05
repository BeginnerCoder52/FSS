cmake_minimum_required(VERSION 3.10)
project(ui_mock_cli VERSION 1.0)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Add source files
set(SOURCES
    src/main.cpp
)

# Find sdbus-c++
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDBUSCPP REQUIRED sdbus-c++)

# Create executable
add_executable(ui_mock_cli ${SOURCES})

# Include directories
target_include_directories(ui_mock_cli PRIVATE ${SDBUSCPP_INCLUDE_DIRS})

# Link libraries
target_link_libraries(ui_mock_cli PRIVATE ${SDBUSCPP_LIBRARIES})
