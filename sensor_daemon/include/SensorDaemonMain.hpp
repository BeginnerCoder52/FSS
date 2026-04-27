/**
 * @file SensorDaemonMain.hpp
 * @brief Header file for the main application class of the Sensor Daemon.
 *
 * This class coordinates the initialization, execution, and lifecycle management
 * of the sensor monitoring system.
 */

#ifndef SENSOR_DAEMON_MAIN_HPP
#define SENSOR_DAEMON_MAIN_HPP

#include <string>
#include <memory>

// Forward declarations
class InputProcessor;
class OutputProcessor;
class SystemWatchdog;

/**
 * @class SensorDaemonMain
 * @brief Main application class for controlling the sensor daemon's lifecycle and core logic.
 */
class SensorDaemonMain
{
public:
    /**
     * @brief Constructor for SensorDaemonMain.
     */
    SensorDaemonMain();

    /**
     * @brief Destructor for SensorDaemonMain.
     */
    ~SensorDaemonMain();

    /**
     * @brief Initializes all internal components and system resources.
     * @return true if initialization is successful, false otherwise.
     */
    bool init_app();

    /**
     * @brief Starts the application's execution flow.
     * @return true if started successfully, false otherwise.
     */
    bool start_app();

    /**
     * @brief Gracefully stops the application and releases resources.
     */
    void stop_app();

    /**
     * @brief The main execution loop of the daemon.
     *
     * Handles periodic polling and event processing.
     */
    void run_main_loop();

    /**
     * @brief Triggers environmental data polling and broadcasts events.
     */
    void process_environment_data();

    /**
     * @brief Attempts to recover the application from a fault state.
     * @return true if recovery is successful, false otherwise.
     */
    bool recover_from_fault();

    /**
     * @brief Logs the current status of the entire system.
     */
    void log_system_status();

    private:
    std::string current_state; ///< Current operational state (INIT, IDLE, ERROR).
    bool is_running;           ///< Loop control flag.
    int loop_interval_ms;      ///< Delay between main loop cycles.
    int polling_rate_env_ms;   ///< Polling frequency for environmental sensors (e.g., 5000 ms).
    int polling_rate_dist_ms;  ///< Polling frequency for distance sensors (e.g., 500 ms).

    std::unique_ptr<InputProcessor> input_processor;   ///< Sensor data collection logic.
    std::unique_ptr<OutputProcessor> output_processor; ///< Signal broadcasting logic.
    std::unique_ptr<SystemWatchdog> watchdog;          ///< OS survival reporting.
    };

    #endif // SENSOR_DAEMON_MAIN_HPP
