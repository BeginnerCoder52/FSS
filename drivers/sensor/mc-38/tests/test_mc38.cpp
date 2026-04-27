#include <gpiod.hpp>
#include <iostream>
#include <chrono>
#include <thread>

#define GPIO_CHIP   "/dev/gpiochip0"
#define DOOR_PIN    26

int main() {
    try {
        gpiod::chip chip(GPIO_CHIP);

        auto request = chip.prepare_request();
        request.set_consumer("mc38-door");
        request.add_line_settings(
            DOOR_PIN,
            gpiod::line_settings()
                .set_direction(gpiod::line::direction::INPUT)
                .set_bias(gpiod::line::bias::PULL_UP)
        );

        auto lines = request.do_request();

        std::cout << "[DEBUG] Raw GPIO26 readings (0=LOW, 1=HIGH):" << std::endl;
        std::cout << "        Bring magnets together and apart..." << std::endl;
        std::cout << "----------------------------------------" << std::endl;

        while (true) {
            gpiod::line::value raw = lines.get_value(DOOR_PIN);

            // Print raw value every 200ms so you can see it change
            std::cout << "[RAW] GPIO26 = "
                      << (raw == gpiod::line::value::ACTIVE ? "1 (HIGH)" : "0 (LOW)")
                      << std::endl;

            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }

    } catch (const std::exception& e) {
        std::cerr << "[ERROR] " << e.what() << std::endl;
        return 1;
    }

    return 0;
}