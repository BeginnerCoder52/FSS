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
    if (!input_processor->init_sensors()) return false;
    if (!output_processor->init_ipc()) return false;
    if (!watchdog->init()) return false;
    current_state = "IDLE";
    return true;
}

bool SensorDaemonMain::start_app() {
    is_running = true;
    current_state = "IDLE";
    run_main_loop();
    return true;
}

void SensorDaemonMain::stop_app() {
    is_running = false;
    watchdog->notify_stopping();
}

void SensorDaemonMain::run_main_loop() {
    while (is_running) {
        // Main loop coordination
        process_environment_data();
        
        watchdog->ping();
        std::this_thread::sleep_for(std::chrono::milliseconds(loop_interval_ms));
    }
}

void SensorDaemonMain::process_environment_data() {
    // API matching Bảng 1
    // Read I2C and emit D-Bus/ZMQ signals periodically
    auto data = input_processor->poll_all_data();
    output_processor->broadcast_system_events(data);
}

bool SensorDaemonMain::recover_from_fault() {
    // API matching Bảng 1
    return true;
}

void SensorDaemonMain::log_system_status() {
    // API matching Bảng 1
}
