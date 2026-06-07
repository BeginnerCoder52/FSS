cmake_minimum_required(VERSION 3.10)
project(tflite_reader C)

set(CMAKE_C_STANDARD 11)

find_package(PkgConfig REQUIRED)
pkg_check_modules(TFLITE REQUIRED tensorflow-lite)

include(CheckIncludeFile)
check_include_file("tensorflow/lite/delegates/xnnpack/xnnpack_delegate.h" HAVE_XNNPACK)

add_library(tflite_reader SHARED
    src/TfliteReader.c
)

target_include_directories(tflite_reader
    PUBLIC include
    PRIVATE ${TFLITE_INCLUDE_DIRS}
)

target_link_libraries(tflite_reader
    PRIVATE ${TFLITE_LIBRARIES}
)

if(HAVE_XNNPACK)
    target_compile_definitions(tflite_reader PRIVATE HAVE_XNNPACK)
    message(STATUS "XNNPACK delegate found — enabling INT8 acceleration")
else()
    message(STATUS "XNNPACK delegate not found — using fallback CPU kernels")
endif()

add_executable(tflite_reader_test src/tflite_reader_test.c)
target_link_libraries(tflite_reader_test tflite_reader)
