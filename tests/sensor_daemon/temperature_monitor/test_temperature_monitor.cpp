#include "TemperatureMonitor.hpp"
#include <cassert>
#include <iostream>
#include <cmath>
#include <thread>
#include <chrono>

static int test_count = 0;
static int pass_count = 0;

#define TEST(name) do { test_count++; std::cout << "  TEST: " << name << "... "; } while(0)
#define PASS() do { pass_count++; std::cout << "PASS" << std::endl; } while(0)
#define FAIL(msg) do { std::cout << "FAIL: " << msg << std::endl; return; } while(0)
#define ASSERT(cond, msg) do { if (!(cond)) { FAIL(msg); } } while(0)

// Track anomaly events emitted by the monitor
static std::vector<AnomalyEvent> captured_events;
static void capture_event(const AnomalyEvent& e) {
    captured_events.push_back(e);
}

static void reset_events() {
    captured_events.clear();
}

void test_initial_state_no_alert() {
    TEST("initial state has no alert");
    TemperatureMonitor monitor;
    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "monitor should report NORMAL initially");
    PASS();
}

void test_steady_normal_temp_no_alert() {
    TEST("steady normal temp (~4°C) produces no alert");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    for (int i = 0; i < 12; i++) {
        monitor.feed_temperature(4.5f);
    }

    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "no anomaly expected at steady 4.5°C");
    ASSERT(captured_events.empty(), "no callback events expected");
    PASS();
}

void test_rapid_rise_triggers_warm_food() {
    TEST("rapid temp rise > 0.4°C/s triggers LOAD_WARM_FOOD");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // Simulate rapid rise: jump from 4°C to 15°C in 3 samples
    monitor.feed_temperature(4.0f);   // t=0
    monitor.feed_temperature(10.0f);  // t=5s, delta=6°C over 5s = 1.2°C/s
    monitor.feed_temperature(15.0f);  // t=10s, delta=5°C over 5s = 1.0°C/s

    ASSERT(monitor.get_current_state() != AnomalyState::NORMAL,
           "anomaly should be active after rapid rise");
    ASSERT(captured_events.size() >= 1, "at least one callback expected");

    if (!captured_events.empty()) {
        ASSERT(captured_events[0].type == "LOAD_WARM_FOOD",
               "expected LOAD_WARM_FOOD type, got: " + captured_events[0].type);
    }
    PASS();
}

void test_sustained_high_triggers_overheating() {
    TEST("sustained high temp (> 8°C for 3 samples) triggers FRIDGE_OVERHEATING");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // All samples > 8°C
    for (int i = 0; i < 5; i++) {
        monitor.feed_temperature(9.5f);
    }

    ASSERT(monitor.get_current_state() != AnomalyState::NORMAL,
           "anomaly should be active");
    ASSERT(!captured_events.empty(), "callback expected");

    if (!captured_events.empty()) {
        ASSERT(captured_events[0].type == "LOAD_WARM_FOOD" ||
               captured_events[0].type == "FRIDGE_OVERHEATING",
               "expected LOAD_WARM_FOOD or FRIDGE_OVERHEATING, got: " + captured_events[0].type);
    }
    PASS();
}

void test_freezer_warning() {
    TEST("freezer temp > -15°C for 3 samples triggers FREEZER_WARNING");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    for (int i = 0; i < 5; i++) {
        monitor.feed_temperature_secondary(-12.0f);
    }

    ASSERT(monitor.get_current_state() != AnomalyState::NORMAL,
           "anomaly should be active");
    ASSERT(!captured_events.empty(), "callback expected");

    if (!captured_events.empty()) {
        ASSERT(captured_events[0].type == "FREEZER_WARNING",
               "expected FREEZER_WARNING, got: " + captured_events[0].type);
    }
    PASS();
}

void test_recovery_to_normal() {
    TEST("anomaly clears when temp returns to normal range");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // Trigger anomaly
    for (int i = 0; i < 5; i++) {
        monitor.feed_temperature(10.0f);
    }
    ASSERT(monitor.get_current_state() != AnomalyState::NORMAL,
           "anomaly should be active after high temp");
    reset_events();

    // Recover to normal
    for (int i = 0; i < 12; i++) {
        monitor.feed_temperature(4.0f);
    }
    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "anomaly should clear after recovery");
    PASS();
}

void test_state_transition_guard() {
    TEST("callback fires only on state transitions (NORMAL→ALERT, ALERT→NORMAL)");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // Push initial normal readings to fill deque
    monitor.feed_temperature(4.0f);
    monitor.feed_temperature(4.0f);
    monitor.feed_temperature(4.0f);
    // Still NORMAL because all temps are normal
    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "should still be NORMAL");
    ASSERT(captured_events.empty(), "no callback expected with normal temps");
    reset_events();

    // Now sustained high → NORMAL→FRIDGE_OVERHEATING transition
    monitor.feed_temperature(10.0f);
    monitor.feed_temperature(10.0f);
    monitor.feed_temperature(10.0f);

    ASSERT(monitor.get_current_state() == AnomalyState::FRIDGE_OVERHEATING,
           "should be FRIDGE_OVERHEATING");
    ASSERT(captured_events.size() == 1, "exactly 1 event expected on NORMAL→ALERT");

    // Record the event type for checking later
    std::string first_event_type = captured_events[0].type;
    reset_events();

    // Stay in FRIDGE_OVERHEATING — keep feeding high temps, no new callback
    for (int i = 0; i < 5; i++) {
        monitor.feed_temperature(10.0f);
    }
    ASSERT(monitor.get_current_state() == AnomalyState::FRIDGE_OVERHEATING,
           "should still be FRIDGE_OVERHEATING");
    ASSERT(captured_events.empty(),
           "no callback expected while staying in same alert state");
    reset_events();

    // Recover to normal: ALERT→NORMAL transition fires callback
    for (int i = 0; i < 12; i++) {
        monitor.feed_temperature(4.0f);
    }
    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "should recover to NORMAL");
    ASSERT(captured_events.size() == 1, "exactly 1 event expected on ALERT→NORMAL");
    PASS();
}

void test_load_warm_food_takes_priority() {
    TEST("LOAD_WARM_FOOD takes priority over FRIDGE_OVERHEATING when both conditions met");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // Rapid rise from cold to very high
    monitor.feed_temperature(3.0f);
    monitor.feed_temperature(18.0f);
    monitor.feed_temperature(22.0f);

    ASSERT(!captured_events.empty(), "callback expected");
    if (!captured_events.empty()) {
        ASSERT(captured_events[0].type == "LOAD_WARM_FOOD",
               "expected LOAD_WARM_FOOD (higher priority), got: " + captured_events[0].type);
    }
    PASS();
}

void test_missing_secondary_sensor_no_anomaly() {
    TEST("FREEZER_WARNING not triggered if secondary sensor not fed");
    TemperatureMonitor monitor;
    monitor.set_callback(capture_event);
    reset_events();

    // Only feed primary
    for (int i = 0; i < 10; i++) {
        monitor.feed_temperature(4.0f);
    }

    ASSERT(monitor.get_current_state() == AnomalyState::NORMAL,
           "no anomaly expected");
    PASS();
}

int main() {
    std::cout << "TemperatureMonitor Unit Tests" << std::endl;
    std::cout << "============================" << std::endl;

    test_initial_state_no_alert();
    test_steady_normal_temp_no_alert();
    test_rapid_rise_triggers_warm_food();
    test_sustained_high_triggers_overheating();
    test_freezer_warning();
    test_recovery_to_normal();
    test_state_transition_guard();
    test_load_warm_food_takes_priority();
    test_missing_secondary_sensor_no_anomaly();

    std::cout << "============================" << std::endl;
    std::cout << pass_count << "/" << test_count << " tests passed" << std::endl;

    return (test_count == pass_count) ? 0 : 1;
}
