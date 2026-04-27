/**
 * @file OutputProcessor.cpp
 * @brief Implementation of the OutputProcessor class.
 */

#include "OutputProcessor.hpp"
#include "SensorDbusInterface.hpp"
#include <iostream>

OutputProcessor::OutputProcessor() {
    sdbus_interface = std::make_shared<SensorDbusInterface>();
}

OutputProcessor::~OutputProcessor() {
}

bool OutputProcessor::init_ipc() {
    if (!sdbus_interface) {
        std::cerr << "OutputProcessor: SensorDbusInterface not initialized" << std::endl;
        return false;
    }
    return sdbus_interface->init_interface();
}

void OutputProcessor::broadcast_env_data(float temp, float hum) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast env data, interface not initialized" << std::endl;
            return;
        }
        
        std::map<std::string, float> data;
        data["temp"] = temp;
        data["humid"] = hum;
        sdbus_interface->emit_env_signal(data);
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_env_data exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_env_data failed: ") + e.what());
        }
    }
}

void OutputProcessor::broadcast_distance_data(uint16_t distance) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast distance data, interface not initialized" << std::endl;
            return;
        }
        
        std::map<std::string, float> data;
        data["distance"] = static_cast<float>(distance);
        sdbus_interface->emit_env_signal(data);
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_distance_data exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_distance_data failed: ") + e.what());
        }
    }
}

void OutputProcessor::broadcast_door_status(bool is_open) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast door status, interface not initialized" << std::endl;
            return;
        }
        
        sdbus_interface->emit_door_signal(is_open ? "OPEN" : "CLOSED");
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_door_status exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_door_status failed: ") + e.what());
        }
    }
}

void OutputProcessor::broadcast_system_events(const std::map<std::string, float>& data) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast system events, interface not initialized" << std::endl;
            return;
        }
        
        // Broadcast environment data if available
        if (data.count("temp") && data.count("humid")) {
            broadcast_env_data(data.at("temp"), data.at("humid"));
        }
        
        // Broadcast door status if available
        if (data.count("door")) {
            broadcast_door_status(data.at("door") > 0.5f);
        }
        
        // Broadcast presence status if available
        if (data.count("presence")) {
            sdbus_interface->emit_presence_signal(data.at("presence") > 0.5f);
        }
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_system_events exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_system_events failed: ") + e.what());
        }
    }
}
