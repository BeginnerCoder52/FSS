/**
 * @file test_last_measurement.c
 * @brief Test for VL53L0X Last Shot Retrieval Feature
 *
 * This test verifies that the VL53L0X sensor correctly stores and retrieves
 * the last measurement with timestamp.
 *
 * Test Criteria:
 *   - Sensor initializes successfully
 *   - vl53l0x_get_last_measurement performs blocking read when no prior
 * measurement
 *   - Last measurement is correctly stored after single and continuous reads
 *   - Timestamp is valid and monotonically increasing
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "vl53l0x.h"

/**
 * @brief I2C bus number for Raspberry Pi 4
 */
#define I2C_BUS 1

/**
 * @brief Minimum valid distance in mm
 */
#define MIN_DISTANCE_MM 30

/**
 * @brief Maximum valid distance in mm (long range mode)
 */
#define MAX_DISTANCE_MM 2000

/**
 * @brief Test result codes
 */
#define TEST_PASS 0
#define TEST_FAIL 1

/**
 * @brief Test sensor initialization
 *
 * @param sensor Pointer to sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_init(vl53l0x_t *sensor) {
  vl53l0x_error_t err;

  printf("[TEST] Sensor initialization... ");

  err = vl53l0x_init(sensor, I2C_BUS, VL53L0X_DEFAULT_ADDRESS,
                     VL53L0X_MODE_LONG_RANGE);

  if (err != VL53L0X_OK) {
    printf("FAILED (error code: %d)\n", err);
    return TEST_FAIL;
  }

  printf("PASSED\n");
  return TEST_PASS;
}

/**
 * @brief Test that get_last_measurement performs blocking read when no prior
 * measurement
 *
 * @param sensor Pointer to initialized sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_last_measurement_blocking(vl53l0x_t *sensor) {
  vl53l0x_error_t err;
  uint16_t distance_mm;
  struct timespec timestamp;

  printf("[TEST] Last measurement blocking read (no prior measurement)... ");

  err = vl53l0x_get_last_measurement(sensor, &distance_mm, &timestamp);

  if (err != VL53L0X_OK) {
    printf("FAILED (error code: %d)\n", err);
    return TEST_FAIL;
  }

  /* Verify distance is in valid range */
  if (distance_mm < MIN_DISTANCE_MM || distance_mm > MAX_DISTANCE_MM) {
    printf("FAILED (distance %u mm out of range)\n", distance_mm);
    return TEST_FAIL;
  }

  /* Verify timestamp is valid (non-zero) */
  if (timestamp.tv_sec == 0 && timestamp.tv_nsec == 0) {
    printf("FAILED (invalid timestamp)\n");
    return TEST_FAIL;
  }

  printf("PASSED (distance: %u mm)\n", distance_mm);
  return TEST_PASS;
}

/**
 * @brief Test that last measurement is correctly stored after single read
 *
 * @param sensor Pointer to initialized sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_last_measurement_after_single(vl53l0x_t *sensor) {
  vl53l0x_error_t err;
  uint16_t single_distance_mm;
  uint16_t last_distance_mm;
  struct timespec timestamp;

  printf("[TEST] Last measurement after single read... ");

  /* Perform a single read */
  err = vl53l0x_read_single(sensor, &single_distance_mm);
  if (err != VL53L0X_OK) {
    printf("FAILED (single read error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Get last measurement */
  err = vl53l0x_get_last_measurement(sensor, &last_distance_mm, &timestamp);
  if (err != VL53L0X_OK) {
    printf("FAILED (get_last error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Verify last measurement matches single measurement */
  if (last_distance_mm != single_distance_mm) {
    printf("FAILED (mismatch: single=%u, last=%u)\n", single_distance_mm,
           last_distance_mm);
    return TEST_FAIL;
  }

  printf("PASSED (distance: %u mm)\n", last_distance_mm);
  return TEST_PASS;
}

/**
 * @brief Test timestamp monotonicity between measurements
 *
 * @param sensor Pointer to initialized sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_timestamp_monotonicity(vl53l0x_t *sensor) {
  vl53l0x_error_t err;
  uint16_t distance_mm;
  struct timespec timestamp1, timestamp2;

  printf("[TEST] Timestamp monotonicity... ");

  /* Get first measurement timestamp */
  err = vl53l0x_get_last_measurement(sensor, &distance_mm, &timestamp1);
  if (err != VL53L0X_OK) {
    printf("FAILED (first get_last error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Perform another single read to update timestamp */
  err = vl53l0x_read_single(sensor, &distance_mm);
  if (err != VL53L0X_OK) {
    printf("FAILED (single read error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Get second measurement timestamp */
  err = vl53l0x_get_last_measurement(sensor, &distance_mm, &timestamp2);
  if (err != VL53L0X_OK) {
    printf("FAILED (second get_last error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Verify timestamp2 >= timestamp1 */
  if (timestamp2.tv_sec < timestamp1.tv_sec ||
      (timestamp2.tv_sec == timestamp1.tv_sec &&
       timestamp2.tv_nsec < timestamp1.tv_nsec)) {
    printf("FAILED (timestamp not monotonic)\n");
    return TEST_FAIL;
  }

  printf("PASSED\n");
  return TEST_PASS;
}

/**
 * @brief Test last measurement after continuous mode
 *
 * @param sensor Pointer to initialized sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_last_measurement_continuous(vl53l0x_t *sensor) {
  vl53l0x_error_t err;
  uint16_t continuous_distance_mm = 0;
  uint16_t last_distance_mm;
  struct timespec timestamp;
  struct timespec sleep_ts = {0, 50000000}; /* 50ms */
  int attempts = 0;
  int max_attempts = 40; /* 2 seconds max */

  printf("[TEST] Last measurement after continuous mode... ");

  /* Start continuous mode */
  err = vl53l0x_start_continuous(sensor);
  if (err != VL53L0X_OK) {
    printf("FAILED (start continuous error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Wait for a measurement */
  while (attempts < max_attempts) {
    err = vl53l0x_read_continuous(sensor, &continuous_distance_mm);
    if (err == VL53L0X_OK) {
      break;
    }
    nanosleep(&sleep_ts, NULL);
    attempts++;
  }

  /* Stop continuous mode */
  vl53l0x_stop_continuous(sensor);

  if (err != VL53L0X_OK) {
    printf("FAILED (no continuous measurement within timeout)\n");
    return TEST_FAIL;
  }

  /* Get last measurement */
  err = vl53l0x_get_last_measurement(sensor, &last_distance_mm, &timestamp);
  if (err != VL53L0X_OK) {
    printf("FAILED (get_last error: %d)\n", err);
    return TEST_FAIL;
  }

  /* Verify last measurement matches continuous measurement */
  if (last_distance_mm != continuous_distance_mm) {
    printf("FAILED (mismatch: continuous=%u, last=%u)\n", continuous_distance_mm,
           last_distance_mm);
    return TEST_FAIL;
  }

  printf("PASSED (distance: %u mm)\n", last_distance_mm);
  return TEST_PASS;
}

/**
 * @brief Test NULL timestamp parameter handling
 *
 * @param sensor Pointer to initialized sensor device
 * @return TEST_PASS on success, TEST_FAIL on failure
 */
static int test_null_timestamp(vl53l0x_t *sensor) {
  vl53l0x_error_t err;
  uint16_t distance_mm;

  printf("[TEST] Get last measurement with NULL timestamp... ");

  err = vl53l0x_get_last_measurement(sensor, &distance_mm, NULL);
  if (err != VL53L0X_OK) {
    printf("FAILED (error code: %d)\n", err);
    return TEST_FAIL;
  }

  printf("PASSED (distance: %u mm)\n", distance_mm);
  return TEST_PASS;
}

int main(void) {
  vl53l0x_t sensor;
  int failed_tests = 0;

  printf("\n");
  printf("==================================================\n");
  printf("VL53L0X Last Shot Retrieval Test\n");
  printf("==================================================\n\n");

  /* Run tests */
  if (test_init(&sensor) != TEST_PASS) {
    printf("\nTest suite aborted: initialization failed.\n");
    return EXIT_FAILURE;
  }

  failed_tests += test_last_measurement_blocking(&sensor);
  failed_tests += test_last_measurement_after_single(&sensor);
  failed_tests += test_timestamp_monotonicity(&sensor);
  failed_tests += test_last_measurement_continuous(&sensor);
  failed_tests += test_null_timestamp(&sensor);

  /* Cleanup */
  vl53l0x_close(&sensor);

  /* Summary */
  printf("\n==================================================\n");
  if (failed_tests == 0) {
    printf("All tests PASSED\n");
  } else {
    printf("%d test(s) FAILED\n", failed_tests);
  }
  printf("==================================================\n");

  return (failed_tests == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
