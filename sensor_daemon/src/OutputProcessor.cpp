/**
 * @file OutputProcessor.cpp
 * @brief Implementation of the OutputProcessor class.
 */

#include "OutputProcessor.hpp"
#include "SdbusInterface.hpp"
#include <iostream>

OutputProcessor::OutputProcessor() {
    sdbus_interface = std::make_shared<SdbusInterface>();
}

OutputProcessor::~OutputProcessor() {
}

bool OutputProcessor::init_ipc() {
    return sdbus_interface->init_interface();
}

void OutputProcessor::broadcast_env_data(float temp, float hum) {
    std::map<std::string, float> data;
    data["temp"] = temp;
    data["humid"] = hum;
    sdbus_interface->emit_env_signal(data);
}

void OutputProcessor::broadcast_distance_data(uint16_t distance) {
    // Convert mm to meters if needed or send as is
    bool detected = (distance < 800);
    sdbus_interface->emit_presence_signal(detected);
}

void OutputProcessor::broadcast_door_status(bool is_open) {
    sdbus_interface->emit_door_signal(is_open ? "OPEN" : "CLOSED");
}

void OutputProcessor::broadcast_system_events(const std::map<std::string, float>& data) {
    // API matching Bảng 1
    // Analyze data and trigger signals
    if (data.count("temp") && data.count("humid")) {
        broadcast_env_data(data.at("temp"), data.at("humid"));
    }
    
    if (data.count("door")) {
        broadcast_door_status(data.at("door") > 0.5f);
    }
    
    if (data.count("distance")) {
        // Example logic for presence
        sdbus_interface->emit_presence_signal(data.at("distance") < 0.8f);
    }
}
