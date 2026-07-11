#include "GpioHandler.hpp"
#include <iostream>
#include <gpiod.h>
#include <cstring>
#include <unordered_map>

struct GpioRequestInfo {
    gpiod_line_request* request;
    bool is_input;
};

GpioHandler::GpioHandler(const std::string& chip_name)
    : chip_name(chip_name), is_ready(false),
      m_chip_handle(nullptr), m_lines_map(nullptr) {
    gpiod_chip* chip = gpiod_chip_open(chip_name.c_str());
    if (!chip) {
        std::cerr << "[GpioHandler] Failed to open GPIO chip: " << chip_name
                  << " (" << strerror(errno) << ")" << std::endl;
        is_ready = false;
        return;
    }
    m_chip_handle = static_cast<void*>(chip);
    m_lines_map = static_cast<void*>(new std::unordered_map<int, GpioRequestInfo>());
    is_ready = true;
}

GpioHandler::~GpioHandler() {
    if (m_lines_map) {
        auto* map = static_cast<std::unordered_map<int, GpioRequestInfo>*>(m_lines_map);
        for (auto& [pin, info] : *map) {
            if (info.request) {
                gpiod_line_request_release(info.request);
            }
        }
        delete map;
        m_lines_map = nullptr;
    }
    if (m_chip_handle) {
        gpiod_chip* chip = static_cast<gpiod_chip*>(m_chip_handle);
        gpiod_chip_close(chip);
        m_chip_handle = nullptr;
    }
}

bool GpioHandler::request_pin(int pin) {
    if (!is_ready || !m_chip_handle || !m_lines_map) {
        std::cerr << "[GpioHandler] Not ready, cannot request pin " << pin << std::endl;
        return false;
    }

    auto* map = static_cast<std::unordered_map<int, GpioRequestInfo>*>(m_lines_map);
    if (map->count(pin)) {
        return true;
    }

    gpiod_chip* chip = static_cast<gpiod_chip*>(m_chip_handle);

    gpiod_line_settings* settings = gpiod_line_settings_new();
    if (!settings) {
        std::cerr << "[GpioHandler] Failed to create line settings" << std::endl;
        return false;
    }

    if (gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_INPUT) < 0) {
        std::cerr << "[GpioHandler] Failed to set direction to input" << std::endl;
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_line_config* line_cfg = gpiod_line_config_new();
    if (!line_cfg) {
        std::cerr << "[GpioHandler] Failed to create line config" << std::endl;
        gpiod_line_settings_free(settings);
        return false;
    }

    unsigned int offset = static_cast<unsigned int>(pin);
    if (gpiod_line_config_add_line_settings(line_cfg, &offset, 1, settings) < 0) {
        std::cerr << "[GpioHandler] Failed to add line settings" << std::endl;
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config* req_cfg = gpiod_request_config_new();
    if (!req_cfg) {
        std::cerr << "[GpioHandler] Failed to create request config" << std::endl;
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config_set_consumer(req_cfg, "FSS_GpioHandler");

    gpiod_line_request* request = gpiod_chip_request_lines(chip, req_cfg, line_cfg);
    if (!request) {
        std::cerr << "[GpioHandler] Failed to request GPIO line " << pin
                  << " (" << strerror(errno) << ")" << std::endl;
        gpiod_request_config_free(req_cfg);
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config_free(req_cfg);
    gpiod_line_config_free(line_cfg);
    gpiod_line_settings_free(settings);

    (*map)[pin] = {request, true};
    std::cout << "[GpioHandler] Requested GPIO pin " << pin
              << " on chip " << chip_name << std::endl;
    return true;
}

int GpioHandler::read_pin(int pin) {
    if (!is_ready || !m_lines_map) {
        std::cerr << "[GpioHandler] Not ready, cannot read pin " << pin << std::endl;
        return -1;
    }

    auto* map = static_cast<std::unordered_map<int, GpioRequestInfo>*>(m_lines_map);
    auto it = map->find(pin);
    if (it == map->end()) {
        if (!request_pin(pin)) {
            return -1;
        }
        it = map->find(pin);
        if (it == map->end()) return -1;
    }

    enum gpiod_line_value value = gpiod_line_request_get_value(it->second.request, static_cast<unsigned int>(pin));
    if (value < 0) {
        std::cerr << "[GpioHandler] Failed to read GPIO pin " << pin
                  << " (" << strerror(errno) << ")" << std::endl;
        return -1;
    }
    return static_cast<int>(value);
}

bool GpioHandler::write_line(int line_offset, int value) {
    if (!is_ready || !m_chip_handle) {
        std::cerr << "[GpioHandler] Not ready, cannot write to pin " << line_offset << std::endl;
        return false;
    }

    gpiod_chip* chip = static_cast<gpiod_chip*>(m_chip_handle);

    gpiod_line_settings* settings = gpiod_line_settings_new();
    if (!settings) return false;

    if (gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_OUTPUT) < 0) {
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_line_config* line_cfg = gpiod_line_config_new();
    if (!line_cfg) {
        gpiod_line_settings_free(settings);
        return false;
    }

    unsigned int offset = static_cast<unsigned int>(line_offset);
    if (gpiod_line_config_add_line_settings(line_cfg, &offset, 1, settings) < 0) {
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config* req_cfg = gpiod_request_config_new();
    if (!req_cfg) {
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config_set_consumer(req_cfg, "FSS_GpioHandler");

    gpiod_line_request* request = gpiod_chip_request_lines(chip, req_cfg, line_cfg);
    if (!request) {
        gpiod_request_config_free(req_cfg);
        gpiod_line_config_free(line_cfg);
        gpiod_line_settings_free(settings);
        return false;
    }

    gpiod_request_config_free(req_cfg);
    gpiod_line_config_free(line_cfg);
    gpiod_line_settings_free(settings);

    int ret = gpiod_line_request_set_value(request, offset, value == 0 ? GPIOD_LINE_VALUE_INACTIVE : GPIOD_LINE_VALUE_ACTIVE);
    gpiod_line_request_release(request);

    if (ret < 0) {
        std::cerr << "[GpioHandler] Failed to write GPIO pin " << line_offset << std::endl;
        return false;
    }
    return true;
}
