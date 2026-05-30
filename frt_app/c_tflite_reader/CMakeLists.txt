cmake_minimum_required(VERSION 3.10)
project(tflite_reader C)

set(CMAKE_C_STANDARD 11)

find_package(TensorFlowLite REQUIRED)

add_library(tflite_reader SHARED
    src/TfliteReader.c
)

target_include_directories(tflite_reader
    PUBLIC include
    PRIVATE ${TensorFlowLite_INCLUDE_DIRS}
)

target_link_libraries(tflite_reader
    PRIVATE ${TensorFlowLite_LIBRARIES}
)

add_executable(tflite_reader_test src/tflite_reader_test.c)
target_link_libraries(tflite_reader_test tflite_reader)
