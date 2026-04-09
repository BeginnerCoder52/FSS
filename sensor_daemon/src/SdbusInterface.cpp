/**
 * @file SdbusInterface.cpp
 * @brief Implementation of the SdbusInterface class using sdbus-c++.
 */

#include "SdbusInterface.hpp"
#include <sdbus-c++/sdbus-c++.h>
#include <iostream>

// Internal structure to hold sdbus-c++ objects
struct SdbusData {
    std::unique_ptr<sdbus::IConnection> connection;
    std::unique_ptr<sdbus::IObject> object;
};

SdbusInterface::SdbusInterface()
    : system_bus(nullptr), interface_name("vn.edu.uit.FSS.Sensor"),
      is_connected(false), dropped_messages_count(0) {
}

SdbusInterface::~SdbusInterface() {
    if (system_bus) {
        delete static_cast<SdbusData*>(system_bus);
        system_bus = nullptr;
    }
}

bool SdbusInterface::init_interface() {
    try {
        if (system_bus) {
            delete static_cast<SdbusData*>(system_bus);
            system_bus = nullptr;
        }

        auto data = new SdbusData();
        data->connection = sdbus::createSystemBusConnection();
        
        data->object = sdbus::createObject(*data->connection, sdbus::ObjectPath{"/vn/edu/uit/FSS/Sensor"});
        
        system_bus = data;
        is_connected = true;
        return true;
    } catch (const sdbus::Error& e) {
        std::cerr << "Sdbus-c++ init failed: " << e.what() << std::endl;
        is_connected = false;
        return false;
    }
}

void SdbusInterface::emit_env_signal(const std::map<std::string, float>& data_map) {
    if (!is_connected || !system_bus) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        // Find keys safely
        float temp = 0.0f;
        float humid = 0.0f;
        if (data_map.count("temp")) temp = data_map.at("temp");
        if (data_map.count("humid")) humid = data_map.at("humid");

        data->object->emitSignal("EnvironmentDataChanged")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(static_cast<double>(temp), static_cast<double>(humid));
    } catch (const sdbus::Error& e) { 
        std::cerr << "Sdbus emit_env_signal failed: " << e.what() << std::endl;
        dropped_messages_count++; 
    }
}

void SdbusInterface::emit_door_signal(const std::string& state) {
    if (!is_connected || !system_bus) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        data->object->emitSignal("DoorStateChanged")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(state);
    } catch (const sdbus::Error& e) { 
        std::cerr << "Sdbus emit_door_signal failed: " << e.what() << std::endl;
        dropped_messages_count++; 
    }
}

void SdbusInterface::emit_presence_signal(bool user) {
    if (!is_connected || !system_bus) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        data->object->emitSignal("UserPresenceDetected")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(user);
    } catch (const sdbus::Error& e) { 
        std::cerr << "Sdbus emit_presence_signal failed: " << e.what() << std::endl;
        dropped_messages_count++; 
    }
}

bool SdbusInterface::reconnect_bus() {
    return init_interface();
}

void SdbusInterface::log_bus_error(const std::string& error_msg) {
    std::cerr << "[D-Bus Error] " << error_msg << std::endl;
}
