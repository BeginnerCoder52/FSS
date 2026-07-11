/**
 * @file OutputProcessor.cpp
 * @brief Implementation of the OutputProcessor class.
 */

#include "OutputProcessor.hpp"
#include "SensorDbusInterface.hpp"
#include <iostream>
#include <sstream>
#include <iomanip>

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
        sdbus_interface->emit_distance_signal(data);
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_distance_data exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_distance_data failed: ") + e.what());
        }
    }
}

void OutputProcessor::broadcast_env_data_updated(const std::map<std::string, float>& data) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast env data updated, interface not initialized" << std::endl;
            return;
        }
        
        // Format environmental data as JSON string
        std::ostringstream json_stream;
        json_stream << "{";
        
        bool first = true;
        
        // Add temperature (primary sensor)
        if (data.count("temp")) {
            if (!first) json_stream << ", ";
            json_stream << "\"temp\": " << std::fixed << std::setprecision(2) << data.at("temp");
            first = false;
        }
        
        // Add humidity (primary sensor)
        if (data.count("humid")) {
            if (!first) json_stream << ", ";
            json_stream << "\"humid\": " << std::fixed << std::setprecision(2) << data.at("humid");
            first = false;
        }
        
        // Add temperature (secondary sensor)
        if (data.count("temp_2")) {
            if (!first) json_stream << ", ";
            json_stream << "\"temp_2\": " << std::fixed << std::setprecision(2) << data.at("temp_2");
            first = false;
        }
        
        // Add humidity (secondary sensor)
        if (data.count("humid_2")) {
            if (!first) json_stream << ", ";
            json_stream << "\"humid_2\": " << std::fixed << std::setprecision(2) << data.at("humid_2");
            first = false;
        }
        
        json_stream << "}";
        
        sdbus_interface->emit_env_data_updated(json_stream.str());
    } catch (const std::exception& e) {
        std::cerr << "OutputProcessor broadcast_env_data_updated exception: " << e.what() << std::endl;
        if (sdbus_interface) {
            sdbus_interface->log_bus_error(std::string("broadcast_env_data_updated failed: ") + e.what());
        }
    }
}

void OutputProcessor::broadcast_door_status(bool is_open) {
    try {
        if (!sdbus_interface) {
            std::cerr << "OutputProcessor: Cannot broadcast door status, interface not initialized" << std::endl;
            return;
        }
        
        sdbus_interface->emit_door_signal(is_open ? "DOOR_OPEN" : "DOOR_CLOSE");
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
        
        // Broadcast updated environment data if available (includes both sensors)
        if (data.count("temp") && data.count("humid")) {
            broadcast_env_data_updated(data);
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
