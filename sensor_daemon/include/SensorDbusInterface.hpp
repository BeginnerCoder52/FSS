/**
 * @file SensorDbusInterface.hpp
 * @brief Header file for the SensorDbusInterface class.
 * 
 * Provides an interface for D-Bus communication within the system.
 */

#ifndef SENSOR_DBUS_INTERFACE_HPP
#define SENSOR_DBUS_INTERFACE_HPP

#include <string>
#include <map>

/**
 * @class SensorDbusInterface
 * @brief Manages D-Bus signals and method calls for inter-process communication.
 */
class SensorDbusInterface {
public:
    /**
     * @brief Constructor for SensorDbusInterface.
     */
    SensorDbusInterface();

    /**
     * @brief Destructor for SensorDbusInterface.
     */
    ~SensorDbusInterface();

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
    void* system_bus;           ///< Internal sdbus-c++ data (SdbusData*).
    std::string interface_name; ///< D-Bus interface name (vn.edu.uit.FSS.Sensor).
    bool is_connected;          ///< Bus connection status.
    int dropped_messages_count; ///< Count of failed signal deliveries.
};

#endif // SENSOR_DBUS_INTERFACE_HPP
