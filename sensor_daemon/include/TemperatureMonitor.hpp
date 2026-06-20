#ifndef TEMPERATURE_MONITOR_HPP
#define TEMPERATURE_MONITOR_HPP

#include <deque>
#include <string>
#include <functional>
#include <cstdint>

#define TEMP_HISTORY_MAX_READINGS 10
#define TEMP_POLL_INTERVAL_S 5
#define SLOPE_THRESHOLD_C_PER_S 0.4f
#define FRIDGE_OVERHEAT_THRESHOLD_C 8.0f
#define FREEZER_WARNING_THRESHOLD_C -15.0f
#define MIN_SAMPLES_FOR_ANALYSIS 3

struct AnomalyEvent {
    std::string type;
    float temp_c;
    float delta_c;
    int duration_s;
    std::string sensor;
    int64_t timestamp;
};

enum class AnomalyState {
    NORMAL,
    WARM_FOOD,
    FRIDGE_OVERHEATING,
    FREEZER_WARNING
};

class TemperatureMonitor {
public:
    using AnomalyCallback = std::function<void(const AnomalyEvent&)>;

    TemperatureMonitor();
    ~TemperatureMonitor();

    void set_callback(AnomalyCallback callback);

    void feed_temperature(float temp_c);
    void feed_temperature_secondary(float temp_c);

    void reset();

    AnomalyState get_current_state() const;

private:
    void analyze();
    int64_t get_timestamp_s() const;
    bool is_state_transition(AnomalyState new_state) const;

    std::deque<float> m_temp_history;
    std::deque<float> m_temp2_history;
    AnomalyState m_current_state;
    AnomalyCallback m_callback;
    float m_last_delta_c;
};

#endif // TEMPERATURE_MONITOR_HPP
