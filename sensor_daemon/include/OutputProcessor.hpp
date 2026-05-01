/**
 * @file OutputProcessor.hpp
 * @brief Header file for the OutputProcessor class.
 * 
 * Manages outgoing communication and event broadcasting.
 */

#ifndef OUTPUT_PROCESSOR_HPP
#define OUTPUT_PROCESSOR_HPP

#include <memory>
#include <map>
#include <string>

// Forward declaration
class SensorDbusInterface;

/**
 * @class OutputProcessor
 * @brief Responsible for processing and broadcasting system events to other modules.
 */
class OutputProcessor {
public:
    /**
     * @brief Constructor for OutputProcessor.
     */
    OutputProcessor();

    /**
     * @brief Destructor for OutputProcessor.
     */
    ~OutputProcessor();

    /**
     * @brief Initializes the Inter-Process Communication (IPC) interface.
     * @return true if IPC is initialized successfully, false otherwise.
     */
    bool init_ipc();

    /**
     * @brief Broadcasts environmental data (temp, hum) to the D-Bus system.
     * @param temp Current temperature.
     * @param hum Current humidity.
     */
    void broadcast_env_data(float temp, float hum);

    /**
     * @brief Broadcasts distance data to the D-Bus system.
     * @param distance Current distance in mm.
     */
    void broadcast_distance_data(uint16_t distance);

    /**
     * @brief Broadcasts updated environmental data from all sensors in JSON format.
     * @param data Data map containing all sensor readings.
     */
    void broadcast_env_data_updated(const std::map<std::string, float>& data);

    /**
     * @brief Broadcasts door status to the D-Bus system.
     * @param is_open Current door status.
     */
    void broadcast_door_status(bool is_open);

    /**
     * @brief Analyzes data from InputProcessor and triggers appropriate emit functions.
     * @param data Data map from InputProcessor.
     */
    void broadcast_system_events(const std::map<std::string, float>& data);

private:
    std::shared_ptr<SensorDbusInterface> sdbus_interface; ///< Interface for D-Bus communication.
};

#endif // OUTPUT_PROCESSOR_HPP
