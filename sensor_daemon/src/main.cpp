/**
 * @file main.cpp
 * @brief Entry point for the Sensor Daemon application.
 */

#include "SensorDaemonMain.hpp"
#include <iostream>

/**
 * @brief Main function.
 * @param argc Argument count.
 * @param argv Argument vector.
 * @return Execution status code.
 */
int main(int argc, char *argv[])
{
    SensorDaemonMain app;

    if (!app.init_app())
    {
        std::cerr << "Failed to initialize Sensor Daemon application." << std::endl;
        return 1;
    }

    if (!app.start_app())
    {
        std::cerr << "Failed to start Sensor Daemon application." << std::endl;
        return 1;
    }

    app.run_main_loop();

    return 0;
}
