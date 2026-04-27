/**
 * @file SystemWatchdog.cpp
 * @brief Implementation of the SystemWatchdog class using systemd notifications.
 */

#include "SystemWatchdog.hpp"
#include <systemd/sd-daemon.h>
#include <iostream>
#include <sstream>
#include <chrono>
#include <ctime>

SystemWatchdog::SystemWatchdog() : interval_ms(5000), last_ping_ts(0.0f) {
    // Initialize with default watchdog interval
}

SystemWatchdog::~SystemWatchdog() {
    // Destructor implementation
}

bool SystemWatchdog::init_driver() {
    try {
        // Get watchdog interval from systemd
        uint64_t usec = 0;
        int ret = sd_watchdog_enabled(0, &usec);
        
        if (ret > 0) {
            // Watchdog is enabled, convert microseconds to milliseconds
            interval_ms = static_cast<int>(usec / 1000);
            // Set interval to half of systemd timeout for safety margin
            interval_ms = interval_ms / 2;
            if (interval_ms < 1000) interval_ms = 1000; // Minimum 1 second
        } else if (ret == 0) {
            // Watchdog not enabled, use default
            interval_ms = 5000;
        } else {
            // Error occurred
            std::cerr << "Failed to query systemd watchdog status" << std::endl;
            return false;
        }
        
        // Initialize last ping timestamp
        last_ping_ts = static_cast<float>(std::chrono::system_clock::now().time_since_epoch().count()) / 1e9f;
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "SystemWatchdog init_driver exception: " << e.what() << std::endl;
        return false;
    }
}

void SystemWatchdog::ping() {
    try {
        // Send WATCHDOG=1 to systemd
        int ret = sd_notify(0, "WATCHDOG=1");
        if (ret < 0) {
            std::cerr << "Failed to send watchdog ping: " << ret << std::endl;
        }
        
        // Update last ping timestamp
        last_ping_ts = static_cast<float>(std::chrono::system_clock::now().time_since_epoch().count()) / 1e9f;
    } catch (const std::exception& e) {
        std::cerr << "SystemWatchdog ping exception: " << e.what() << std::endl;
    }
}

void SystemWatchdog::notify_ready() {
    try {
        // Send READY=1 to systemd when daemon is ready
        int ret = sd_notify(0, "READY=1\nSTATUS=Sensor Daemon initialized and ready");
        if (ret < 0) {
            std::cerr << "Failed to send ready notification: " << ret << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "SystemWatchdog notify_ready exception: " << e.what() << std::endl;
    }
}

void SystemWatchdog::notify_stopping() {
    try {
        // Send STOPPING=1 to systemd before shutdown
        int ret = sd_notify(0, "STOPPING=1\nSTATUS=Sensor Daemon stopping gracefully");
        if (ret < 0) {
            std::cerr << "Failed to send stopping notification: " << ret << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "SystemWatchdog notify_stopping exception: " << e.what() << std::endl;
    }
}

void SystemWatchdog::report_error_status(const std::string& err_str) {
    try {
        // Report error status to systemd
        std::ostringstream status_msg;
        status_msg << "STATUS=Error: " << err_str;
        
        int ret = sd_notify(0, status_msg.str().c_str());
        if (ret < 0) {
            std::cerr << "Failed to send error status: " << ret << std::endl;
        }
        
        // Also print to stderr for logging
        std::cerr << "[Sensor Daemon Error] " << err_str << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "SystemWatchdog report_error_status exception: " << e.what() << std::endl;
    }
}
