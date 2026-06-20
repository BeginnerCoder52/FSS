#include "TemperatureMonitor.hpp"
#include <algorithm>
#include <cmath>
#include <chrono>
#include <sstream>

TemperatureMonitor::TemperatureMonitor()
    : m_current_state(AnomalyState::NORMAL), m_last_delta_c(0.0f) {
}

TemperatureMonitor::~TemperatureMonitor() {
}

void TemperatureMonitor::set_callback(AnomalyCallback callback) {
    m_callback = std::move(callback);
}

void TemperatureMonitor::feed_temperature(float temp_c) {
    m_temp_history.push_back(temp_c);
    if (m_temp_history.size() > TEMP_HISTORY_MAX_READINGS) {
        m_temp_history.pop_front();
    }
    analyze();
}

void TemperatureMonitor::feed_temperature_secondary(float temp_c) {
    m_temp2_history.push_back(temp_c);
    if (m_temp2_history.size() > TEMP_HISTORY_MAX_READINGS) {
        m_temp2_history.pop_front();
    }
    analyze();
}

void TemperatureMonitor::reset() {
    m_temp_history.clear();
    m_temp2_history.clear();
    m_current_state = AnomalyState::NORMAL;
    m_last_delta_c = 0.0f;
}

AnomalyState TemperatureMonitor::get_current_state() const {
    return m_current_state;
}

void TemperatureMonitor::analyze() {
    AnomalyState new_state = AnomalyState::NORMAL;
    AnomalyEvent event;
    event.timestamp = get_timestamp_s();
    event.temp_c = 0.0f;
    event.delta_c = 0.0f;
    event.duration_s = 0;
    event.sensor = "primary";

    bool primary_ready = m_temp_history.size() >= MIN_SAMPLES_FOR_ANALYSIS;

    if (primary_ready) {
        size_t n = m_temp_history.size();
        float temp_first = m_temp_history.front();
        float temp_last = m_temp_history.back();

        float slope = (temp_last - temp_first) / static_cast<float>(n * TEMP_POLL_INTERVAL_S);

        m_last_delta_c = temp_last - temp_first;

        bool last_three_over_8 = true;
        size_t start = (n >= 3) ? n - 3 : 0;
        for (size_t i = start; i < n; ++i) {
            if (m_temp_history[i] <= FRIDGE_OVERHEAT_THRESHOLD_C) {
                last_three_over_8 = false;
                break;
            }
        }

        if (slope > SLOPE_THRESHOLD_C_PER_S) {
            new_state = AnomalyState::WARM_FOOD;
            event.type = "LOAD_WARM_FOOD";
            event.temp_c = temp_last;
            event.delta_c = m_last_delta_c;
            event.duration_s = static_cast<int>(n * TEMP_POLL_INTERVAL_S);
            event.sensor = "primary";
        } else if (last_three_over_8) {
            new_state = AnomalyState::FRIDGE_OVERHEATING;
            event.type = "FRIDGE_OVERHEATING";
            event.temp_c = temp_last;
            event.delta_c = m_last_delta_c;
            event.duration_s = static_cast<int>(n * TEMP_POLL_INTERVAL_S);
            event.sensor = "primary";
        }
    }

    bool freezer_ready = m_temp2_history.size() >= MIN_SAMPLES_FOR_ANALYSIS;
    if (freezer_ready && new_state == AnomalyState::NORMAL) {
        size_t n2 = m_temp2_history.size();
        size_t start2 = (n2 >= 3) ? n2 - 3 : 0;
        bool freezer_warning = true;
        for (size_t i = start2; i < n2; ++i) {
            if (m_temp2_history[i] <= FREEZER_WARNING_THRESHOLD_C) {
                freezer_warning = false;
                break;
            }
        }
        if (freezer_warning) {
            new_state = AnomalyState::FREEZER_WARNING;
            event.type = "FREEZER_WARNING";
            event.temp_c = m_temp2_history.back();
            event.delta_c = 0.0f;
            event.duration_s = static_cast<int>(m_temp2_history.size() * TEMP_POLL_INTERVAL_S);
            event.sensor = "secondary";
        }
    }

    if (is_state_transition(new_state)) {
        m_current_state = new_state;
        if (m_callback) {
            m_callback(event);
        }
    }
}

int64_t TemperatureMonitor::get_timestamp_s() const {
    return std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
}

bool TemperatureMonitor::is_state_transition(AnomalyState new_state) const {
    if (m_current_state == AnomalyState::NORMAL && new_state != AnomalyState::NORMAL) {
        return true;
    }
    if (m_current_state != AnomalyState::NORMAL && new_state == AnomalyState::NORMAL) {
        return true;
    }
    if (m_current_state != new_state) {
        return true;
    }
    return false;
}
