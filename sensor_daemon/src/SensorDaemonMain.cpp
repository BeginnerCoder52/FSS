/**
 * @file SensorDaemonMain.cpp
 * @brief Implementation of the SensorDaemonMain class.
 */

#include "SensorDaemonMain.hpp"
#include "InputProcessor.hpp"
#include "OutputProcessor.hpp"
#include "SystemWatchdog.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <fstream>
#include <sstream>
#include <ctime>
#include <iomanip>
#include <sys/sysinfo.h>
#include <unistd.h>

SensorDaemonMain::SensorDaemonMain()
    : current_state("INIT"), is_running(false), loop_interval_ms(100),
      polling_rate_env_ms(5000), polling_rate_dist_ms(500) {
    input_processor = std::make_unique<InputProcessor>();
    output_processor = std::make_unique<OutputProcessor>();
    watchdog = std::make_unique<SystemWatchdog>();
}

SensorDaemonMain::~SensorDaemonMain() {
}

bool SensorDaemonMain::init_app() {
    try {
        if (!watchdog->init_driver()) {
            std::cerr << "Failed to initialize watchdog driver" << std::endl;
            current_state = "ERROR";
            return false;
        }

        if (!input_processor->init_sensors()) {
            std::cerr << "Failed to initialize sensors" << std::endl;
            current_state = "ERROR";
            return false;
        }

        if (!output_processor->init_ipc()) {
            std::cerr << "Failed to initialize IPC interface" << std::endl;
            current_state = "ERROR";
            return false;
        }

        current_state = "IDLE";
        return true;
    } catch (const std::exception& e) {
        std::cerr << "init_app exception: " << e.what() << std::endl;
        current_state = "ERROR";
        return false;
    }
}

bool SensorDaemonMain::start_app() {
    try {
        if (current_state != "IDLE") {
            std::cerr << "Cannot start app, current state: " << current_state << std::endl;
            return false;
        }

        if (!input_processor || !output_processor || !watchdog) {
            std::cerr << "Required components are not initialized" << std::endl;
            return false;
        }

        is_running = true;
        current_state = "RUNNING";
        watchdog->notify_ready();
        run_main_loop();
        return true;
    } catch (const std::exception& e) {
        std::cerr << "start_app exception: " << e.what() << std::endl;
        current_state = "ERROR";
        return false;
    }
}

void SensorDaemonMain::stop_app() {
    try {
        is_running = false;
        current_state = "STOPPING";
        watchdog->notify_stopping();
    } catch (const std::exception& e) {
        std::cerr << "stop_app exception: " << e.what() << std::endl;
    }
}

void SensorDaemonMain::run_main_loop() {
    auto last_env_poll = std::chrono::system_clock::now();
    auto last_dist_poll = std::chrono::system_clock::now();
    auto last_watchdog_ping = std::chrono::system_clock::now();
    auto last_status_log = std::chrono::system_clock::now();
    int status_log_interval_ms = 60000; // Log status every 60 seconds

    while (is_running) {
        try {
            auto current_time = std::chrono::system_clock::now();
            auto duration_since_env = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - last_env_poll);
            auto duration_since_dist = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - last_dist_poll);
            auto duration_since_watchdog = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - last_watchdog_ping);
            auto duration_since_status_log = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - last_status_log);

            // Environmental sensor polling
            if (duration_since_env.count() >= polling_rate_env_ms) {
                process_environment_data();
                last_env_poll = current_time;
            }

            // Distance sensor polling
            if (duration_since_dist.count() >= polling_rate_dist_ms) {
                uint16_t distance = input_processor->get_distance_data();
                output_processor->broadcast_distance_data(distance);
                last_dist_poll = current_time;
            }

            // Watchdog heartbeat
            if (duration_since_watchdog.count() >= 4000) { // Ping every 4 seconds
                watchdog->ping();
                last_watchdog_ping = current_time;
            }

            // Status logging
            if (duration_since_status_log.count() >= status_log_interval_ms) {
                log_system_status();
                last_status_log = current_time;
            }

            // Sleep to prevent CPU spinning
            std::this_thread::sleep_for(std::chrono::milliseconds(loop_interval_ms));
        } catch (const std::exception& e) {
            std::cerr << "Exception in main loop: " << e.what() << std::endl;
            current_state = "ERROR";
            if (!recover_from_fault()) {
                std::cerr << "Recovery failed, stopping daemon" << std::endl;
                is_running = false;
            }
        }
    }

    current_state = "STOPPED";
}

void SensorDaemonMain::process_environment_data() {
    try {
        auto data = input_processor->poll_all_data();
        output_processor->broadcast_system_events(data);
    } catch (const std::exception& e) {
        std::cerr << "process_environment_data exception: " << e.what() << std::endl;
        watchdog->report_error_status("Failed to process environment data");
    }
}

bool SensorDaemonMain::recover_from_fault() {
    try {
        static int recovery_attempts = 0;
        const int max_recovery_attempts = 3;

        if (recovery_attempts >= max_recovery_attempts) {
            std::cerr << "Maximum recovery attempts reached" << std::endl;
            watchdog->report_error_status("Recovery failed: max attempts exceeded");
            return false;
        }

        recovery_attempts++;
        
        // Report recovery in progress
        std::ostringstream msg;
        msg << "Recovery in progress (attempt " << recovery_attempts << "/" << max_recovery_attempts << ")";
        watchdog->report_error_status(msg.str());

        // Backoff strategy: 1s, 2s, 4s
        int backoff_ms = (1000 << (recovery_attempts - 1));
        std::this_thread::sleep_for(std::chrono::milliseconds(backoff_ms));

        // Attempt to reinitialize sensors
        std::cerr << "Attempting to reinitialize sensors..." << std::endl;
        if (!input_processor->init_sensors()) {
            std::cerr << "Sensor reinitialization failed" << std::endl;
            return false;
        }

        // Attempt to reconnect D-Bus
        std::cerr << "Attempting to reconnect D-Bus..." << std::endl;
        if (!output_processor->init_ipc()) {
            std::cerr << "D-Bus reconnection failed" << std::endl;
            return false;
        }

        // Reset state machine
        current_state = "IDLE";
        recovery_attempts = 0;
        watchdog->report_error_status("Recovery successful, resuming operation");
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "recover_from_fault exception: " << e.what() << std::endl;
        return false;
    }
}

void SensorDaemonMain::log_system_status() {
    try {
        struct sysinfo info;
        if (sysinfo(&info) != 0) {
            std::cerr << "Failed to get system info" << std::endl;
            return;
        }

        auto now = std::chrono::system_clock::now();
        auto time_t_now = std::chrono::system_clock::to_time_t(now);
        
        std::ostringstream timestamp;
        timestamp << std::put_time(std::gmtime(&time_t_now), "%Y-%m-%dT%H:%M:%SZ");

        // Calculate memory usage
        long total_ram = info.totalram * info.mem_unit;
        long free_ram = info.freeram * info.mem_unit;
        long used_ram = total_ram - free_ram;
        long ram_mb = used_ram / (1024 * 1024);

        // Get CPU load (1-minute average)
        double cpu_load = info.loads[0] / (double)(1 << SI_LOAD_SHIFT);
        int cpu_percent = static_cast<int>(cpu_load * 100 / sysconf(_SC_NPROCESSORS_ONLN));
        if (cpu_percent > 100) cpu_percent = 100;

        // Get process uptime
        long uptime_seconds = info.uptime;

        // Format log entry
        std::ostringstream log_entry;
        log_entry << timestamp.str() << " | state=" << current_state 
                  << " | ram=" << ram_mb << "MB"
                  << " | cpu=" << cpu_percent << "%"
                  << " | uptime=" << uptime_seconds << "s";

        // Write to log file
        const char* log_path = "/var/log/sensor_daemon.log";
        std::ofstream log_file(log_path, std::ios::app);
        if (log_file.is_open()) {
            log_file << log_entry.str() << std::endl;
            log_file.close();
        } else {
            // Fallback to stderr if log file cannot be opened
            std::cerr << "[Status] " << log_entry.str() << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "log_system_status exception: " << e.what() << std::endl;
    }
}
