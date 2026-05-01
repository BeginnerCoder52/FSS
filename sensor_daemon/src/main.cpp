/**
 * @file main.cpp
 * @brief Entry point for the Sensor Daemon application.
 */

#include "SensorDaemonMain.hpp"
#include <iostream>
#include <thread>
#include <chrono>

/**
 * @brief Main function.
 * @param argc Argument count.
 * @param argv Argument vector.
 * @return Execution status code.
 */
int main(int argc, char *argv[])
{
    SensorDaemonMain app;

    // Retry initialization until successful
    while (!app.init_app())
    {
        std::cerr << "Initialization failed. Retrying in 2 seconds..." << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }

    if (!app.start_app())
    {
        std::cerr << "Failed to start Sensor Daemon application." << std::endl;
        return 1;
    }

    app.run_main_loop();

    return 0;
}
