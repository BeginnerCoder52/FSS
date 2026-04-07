/**
 * @file SdbusInterface.cpp
 * @brief Implementation of the SdbusInterface class.
 */

#include "SdbusInterface.hpp"
#include <iostream>

SdbusInterface::SdbusInterface()
    : system_bus(nullptr), interface_name("vn.edu.uit.FSS.Sensor"),
      is_connected(false), dropped_messages_count(0) {
}

SdbusInterface::~SdbusInterface() {
}

bool SdbusInterface::init_interface() {
    // API matching Bảng 1
    is_connected = true;
    return true;
}

void SdbusInterface::emit_env_signal(const std::map<std::string, float>& data) {
    // API matching Bảng 1
    if (!is_connected) {
        dropped_messages_count++;
        return;
    }
    std::cout << "[D-Bus] Emitting Environmental Data Signal" << std::endl;
}

void SdbusInterface::emit_door_signal(const std::string& state) {
    // API matching Bảng 1
    if (!is_connected) {
        dropped_messages_count++;
        return;
    }
    std::cout << "[D-Bus] Emitting Door State Changed Signal: " << state << std::endl;
}

void SdbusInterface::emit_presence_signal(bool user) {
    // API matching Bảng 1
    if (!is_connected) {
        dropped_messages_count++;
        return;
    }
    std::cout << "[D-Bus] Emitting User Presence Detected Signal: " << (user ? "TRUE" : "FALSE") << std::endl;
}

bool SdbusInterface::reconnect_bus() {
    // API matching Bảng 1
    return init_interface();
}

void SdbusInterface::log_bus_error(const std::string& error_msg) {
    // API matching Bảng 1
    std::cerr << "[D-Bus Error] " << error_msg << std::endl;
}
