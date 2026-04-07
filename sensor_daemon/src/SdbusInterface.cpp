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
}

bool SdbusInterface::init_interface() {
    try {
        auto data = new SdbusData();
        data->connection = sdbus::createSystemBusConnection();
        
        const std::string objectPath = "/vn/edu/uit/FSS/Sensor";
        data->object = sdbus::createObject(*data->connection, objectPath);
        
        // Register Signals
        data->object->registerSignal("vn.edu.uit.FSS.Sensor", "EnvironmentDataChanged")
                     .withParameters<float, float>();
        data->object->registerSignal("vn.edu.uit.FSS.Sensor", "DoorStateChanged")
                     .withParameters<std::string>();
        data->object->registerSignal("vn.edu.uit.FSS.Sensor", "UserPresenceDetected")
                     .withParameters<bool>();
        
        data->object->finishRegistration();
        system_bus = data;
        is_connected = true;
        return true;
    } catch (const sdbus::Error& e) {
        std::cerr << "Sdbus-c++ init failed: " << e.what() << std::endl;
        return false;
    }
}

void SdbusInterface::emit_env_signal(const std::map<std::string, float>& data_map) {
    if (!is_connected) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        data->object->emitSignal("EnvironmentDataChanged")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(data_map.at("temp"), data_map.at("humid"));
    } catch (...) { dropped_messages_count++; }
}

void SdbusInterface::emit_door_signal(const std::string& state) {
    if (!is_connected) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        data->object->emitSignal("DoorStateChanged")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(state);
    } catch (...) { dropped_messages_count++; }
}

void SdbusInterface::emit_presence_signal(bool user) {
    if (!is_connected) return;
    auto data = static_cast<SdbusData*>(system_bus);
    try {
        data->object->emitSignal("UserPresenceDetected")
                     .onInterface("vn.edu.uit.FSS.Sensor")
                     .withArguments(user);
    } catch (...) { dropped_messages_count++; }
}

bool SdbusInterface::reconnect_bus() {
    return init_interface();
}

void SdbusInterface::log_bus_error(const std::string& error_msg) {
    std::cerr << "[D-Bus Error] " << error_msg << std::endl;
}
