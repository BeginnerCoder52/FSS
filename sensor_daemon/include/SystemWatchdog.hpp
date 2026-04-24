/**
 * @file SystemWatchdog.hpp
 * @brief Header file for the SystemWatchdog class.
 * 
 * Monitors the daemon's health and provides status reports.
 */

#ifndef SYSTEM_WATCHDOG_HPP
#define SYSTEM_WATCHDOG_HPP

#include <string>

/**
 * @class SystemWatchdog
 * @brief Implements health monitoring and reporting for the Sensor Daemon.
 */
class SystemWatchdog {
public:
    /**
     * @brief Constructor for SystemWatchdog.
     */
    SystemWatchdog();

    /**
     * @brief Destructor for SystemWatchdog.
     */
    ~SystemWatchdog();

    /**
     * @brief Initializes the watchdog driver and parameters.
     * @return true if initialized successfully, false otherwise.
     */
    bool init_driver();

    /**
     * @brief Pings the watchdog to indicate the application is still alive.
     */
    void ping();

    /**
     * @brief Notifies the system that the daemon is ready for operation.
     */
    void notify_ready();

    /**
     * @brief Notifies the system that the daemon is stopping.
     */
    void notify_stopping();

    /**
     * @brief Reports an error status to the system.
     * @param err_str Description of the error encountered.
     */
    void report_error_status(const std::string& err_str);

private:
    int interval_ms;     ///< The expected interval between pings in milliseconds.
    float last_ping_ts; ///< Timestamp of the last successful ping.
};

#endif // SYSTEM_WATCHDOG_HPP
