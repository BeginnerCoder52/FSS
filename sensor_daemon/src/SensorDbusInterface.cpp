/**
 * @file SensorDbusInterface.cpp
 * @brief Implementation of the SensorDbusInterface class using sdbus-c++.
 */

#include "SensorDbusInterface.hpp"
#include <sdbus-c++/sdbus-c++.h>
#include <iostream>
#include <sstream>

// Internal structure to hold sdbus-c++ objects
struct SdbusData {
    std::unique_ptr<sdbus::IConnection> connection;
    std::unique_ptr<sdbus::IObject> object;
};

SensorDbusInterface::SensorDbusInterface()
    : system_bus(nullptr), interface_name("vn.edu.uit.FSS.Sensor"),
      is_connected(false), dropped_messages_count(0) {
}

SensorDbusInterface::~SensorDbusInterface() {
    if (system_bus) {
        try {
            delete static_cast<SdbusData*>(system_bus);
            system_bus = nullptr;
        } catch (const std::exception& e) {
            std::cerr << "Exception during SensorDbusInterface destructor: " << e.what() << std::endl;
        }
    }
}

bool SensorDbusInterface::init_interface() {
    try {
        // Clean up existing connection if any
        if (system_bus) {
            delete static_cast<SdbusData*>(system_bus);
            system_bus = nullptr;
        }

        auto data = new SdbusData();
        
        // Create system bus connection
        data->connection = sdbus::createSystemBusConnection();
        if (!data->connection) {
            std::cerr << "Failed to create system bus connection" << std::endl;
            delete data;
            is_connected = false;
            return false;
        }
        
        // Create D-Bus object
        data->object = sdbus::createObject(*data->connection, sdbus::ObjectPath{"/vn/edu/uit/FSS/Sensor"});
        if (!data->object) {
            std::cerr << "Failed to create D-Bus object" << std::endl;
            delete data;
            is_connected = false;
            return false;
        }
        
        system_bus = data;
        is_connected = true;
        std::cerr << "[D-Bus] Connection established successfully" << std::endl;
        return true;
    } catch (const sdbus::Error& e) {
        std::cerr << "[D-Bus] Connection failed: " << e.what() << std::endl;
        is_connected = false;
        return false;
    } catch (const std::exception& e) {
        std::cerr << "[D-Bus] Unexpected error during connection: " << e.what() << std::endl;
        is_connected = false;
        return false;
    }
}

void SensorDbusInterface::emit_env_signal(const std::map<std::string, float>& data_map) {
    if (!is_connected || !system_bus) {
        std::cerr << "[D-Bus] Cannot emit signal, interface not connected" << std::endl;
        dropped_messages_count++;
        return;
    }
    
    try {
        auto data = static_cast<SdbusData*>(system_bus);
        if (!data || !data->object) {
            std::cerr << "[D-Bus] Invalid data object" << std::endl;
            dropped_messages_count++;
            return;
        }
        
        // Extract temperature and humidity with safe defaults
        float temp = 0.0f;
        float humid = 0.0f;
        if (data_map.count("temp")) temp = data_map.at("temp");
        if (data_map.count("humid")) humid = data_map.at("humid");

        data->object->emitSignal("EnvironmentDataChanged")
                     .onInterface(interface_name)
                     .withArguments(static_cast<double>(temp), static_cast<double>(humid));
    } catch (const sdbus::Error& e) { 
        std::cerr << "[D-Bus] emit_env_signal failed: " << e.what() << std::endl;
        dropped_messages_count++;
    } catch (const std::exception& e) {
        std::cerr << "[D-Bus] emit_env_signal unexpected error: " << e.what() << std::endl;
        dropped_messages_count++;
    }
}

void SensorDbusInterface::emit_door_signal(const std::string& state) {
    if (!is_connected || !system_bus) {
        std::cerr << "[D-Bus] Cannot emit signal, interface not connected" << std::endl;
        dropped_messages_count++;
        return;
    }
    
    try {
        auto data = static_cast<SdbusData*>(system_bus);
        if (!data || !data->object) {
            std::cerr << "[D-Bus] Invalid data object" << std::endl;
            dropped_messages_count++;
            return;
        }
        
        data->object->emitSignal("DoorStateChanged")
                     .onInterface(interface_name)
                     .withArguments(state);
    } catch (const sdbus::Error& e) { 
        std::cerr << "[D-Bus] emit_door_signal failed: " << e.what() << std::endl;
        dropped_messages_count++;
    } catch (const std::exception& e) {
        std::cerr << "[D-Bus] emit_door_signal unexpected error: " << e.what() << std::endl;
        dropped_messages_count++;
    }
}

void SensorDbusInterface::emit_presence_signal(bool user) {
    if (!is_connected || !system_bus) {
        std::cerr << "[D-Bus] Cannot emit signal, interface not connected" << std::endl;
        dropped_messages_count++;
        return;
    }
    
    try {
        auto data = static_cast<SdbusData*>(system_bus);
        if (!data || !data->object) {
            std::cerr << "[D-Bus] Invalid data object" << std::endl;
            dropped_messages_count++;
            return;
        }
        
        data->object->emitSignal("UserPresenceDetected")
                     .onInterface(interface_name)
                     .withArguments(user);
    } catch (const sdbus::Error& e) { 
        std::cerr << "[D-Bus] emit_presence_signal failed: " << e.what() << std::endl;
        dropped_messages_count++;
    } catch (const std::exception& e) {
        std::cerr << "[D-Bus] emit_presence_signal unexpected error: " << e.what() << std::endl;
        dropped_messages_count++;
    }
}

bool SensorDbusInterface::reconnect_bus() {
    try {
        std::cerr << "[D-Bus] Attempting to reconnect..." << std::endl;
        return init_interface();
    } catch (const std::exception& e) {
        std::cerr << "[D-Bus] Reconnection exception: " << e.what() << std::endl;
        return false;
    }
}

void SensorDbusInterface::log_bus_error(const std::string& error_msg) {
    std::ostringstream oss;
    oss << "[D-Bus Error] " << error_msg 
        << " (dropped messages: " << dropped_messages_count << ")";
    std::cerr << oss.str() << std::endl;
}
