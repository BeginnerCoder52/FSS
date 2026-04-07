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
    // Distance usually triggers presence
}

void OutputProcessor::broadcast_door_status(bool is_open) {
    sdbus_interface->emit_door_signal(is_open ? "OPEN" : "CLOSED");
}

void OutputProcessor::broadcast_system_events(const std::map<std::string, float>& data) {
    // Logic to decide when to broadcast based on thresholds or change detection
    if (data.count("temp") && data.count("humid")) {
        broadcast_env_data(data.at("temp"), data.at("humid"));
    }
    
    if (data.count("door")) {
        broadcast_door_status(data.at("door") > 0.5f);
    }
    
    if (data.count("presence")) {
        sdbus_interface->emit_presence_signal(data.at("presence") > 0.5f);
    }
}
