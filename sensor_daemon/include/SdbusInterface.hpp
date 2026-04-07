/**
 * @file SdbusInterface.hpp
 * @brief Header file for the SdbusInterface class.
 * 
 * Provides an interface for D-Bus communication within the system.
 */

#ifndef SDBUS_INTERFACE_HPP
#define SDBUS_INTERFACE_HPP

#include <string>
#include <map>

/**
 * @class SdbusInterface
 * @brief Manages D-Bus signals and method calls for inter-process communication.
 */
class SdbusInterface {
public:
    /**
     * @brief Constructor for SdbusInterface.
     */
    SdbusInterface();

    /**
     * @brief Destructor for SdbusInterface.
     */
    ~SdbusInterface();

    /**
     * @brief Establishes a connection to the system D-Bus.
     * @return true if connected successfully, false otherwise.
     */
    bool init_interface();

    /**
     * @brief Emits a signal containing environmental data.
     * @param data A map of environmental readings.
     */
    void emit_env_signal(const std::map<std::string, float>& data);

    /**
     * @brief Emits a signal when the door state changes.
     * @param state The current state of the door ("OPEN" or "CLOSED").
     */
    void emit_door_signal(const std::string& state);

    /**
     * @brief Emits a signal indicating user presence detection.
     * @param user True if user detected, false otherwise.
     */
    void emit_presence_signal(bool user);

    /**
     * @brief Restores IPC connection if D-Bus daemon is restarted.
     * @return true if successful, false otherwise.
     */
    bool reconnect_bus();

    /**
     * @brief Logs errors related to D-Bus communication.
     * @param error_msg Error description.
     */
    void log_bus_error(const std::string& error_msg);

private:
    void* system_bus;           ///< Linux System D-Bus connection.
    std::string interface_name; ///< D-Bus interface name (vn.edu.uit.FSS.Sensor).
    bool is_connected;          ///< Bus connection status.
    int dropped_messages_count; ///< Count of failed signal deliveries.
};

#endif // SDBUS_INTERFACE_HPP
