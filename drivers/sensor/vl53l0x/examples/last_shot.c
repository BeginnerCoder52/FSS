/**
 * @file last_shot.c
 * @brief VL53L0X Last Shot Retrieval Demo
 *
 * Demonstrates the last shot retrieval feature using the VL53L0X
 * Time-of-Flight sensor. Shows that measurements are stored and can
 * be retrieved later without triggering a new measurement.
 *
 * Usage: ./vl53l0x_last
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
 * @brief Format and print a timestamp
 */
static void print_timestamp(const struct timespec *ts) {
  struct tm *tm_info = localtime(&ts->tv_sec);
  char time_buffer[64];
  strftime(time_buffer, sizeof(time_buffer), "%Y-%m-%d %H:%M:%S", tm_info);
  printf("%s.%03ld", time_buffer, ts->tv_nsec / 1000000);
}

/**
 * @brief Main entry point
 *
 * Demonstrates last shot retrieval functionality - proving that
 * the stored measurement is returned without taking a new one.
 *
 * @return 0 on success, non-zero on failure
 */
int main(void) {
  vl53l0x_t sensor;
  vl53l0x_error_t err;
  uint16_t distance_mm;
  struct timespec timestamp;

  printf("VL53L0X Last Shot Retrieval Demo\n");
  printf("================================\n\n");

  /* Initialize the sensor in long range mode */
  printf("Initializing VL53L0X sensor...\n");
  err = vl53l0x_init(&sensor, I2C_BUS, VL53L0X_DEFAULT_ADDRESS,
                     VL53L0X_MODE_LONG_RANGE);

  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Failed to initialize sensor ");
    switch (err) {
      case VL53L0X_ERROR_I2C_OPEN:
        fprintf(stderr, "(could not open I2C bus)\n");
        break;
      case VL53L0X_ERROR_I2C_ACCESS:
        fprintf(stderr, "(could not access I2C device)\n");
        break;
      case VL53L0X_ERROR_INIT:
        fprintf(stderr, "(sensor init failed)\n");
        break;
      default:
        fprintf(stderr, "(unknown error: %d)\n", err);
        break;
    }
    return EXIT_FAILURE;
  }
  printf("Sensor initialized successfully!\n\n");

  /* --- Main Test: Prove last shot retrieval works --- */
  printf("=== Last Shot Retrieval Test ===\n\n");

  /* Step 1: Take a single measurement */
  printf("Step 1: Taking a single measurement...\n");
  err = vl53l0x_read_single(&sensor, &distance_mm);
  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Single read failed (error: %d)\n", err);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }
  uint16_t original_measurement = distance_mm;
  printf("  Measured distance: %u mm\n\n", original_measurement);

  /* Step 2: Wait 2 seconds (sensor would measure different value if polled) */
  printf("Step 2: Waiting 2 seconds...\n");
  printf("  (If get_last_measurement took a new reading, it would likely differ\n");
  printf("   due to sensor noise or slight position changes)\n");
  struct timespec sleep_ts = {2, 0}; /* 2 seconds */
  nanosleep(&sleep_ts, NULL);
  printf("  Done waiting.\n\n");

  /* Step 3: Retrieve the last measurement - should match original */
  printf("Step 3: Retrieving last measurement (should NOT trigger new read)...\n");
  err = vl53l0x_get_last_measurement(&sensor, &distance_mm, &timestamp);
  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Failed to get last measurement (error: %d)\n", err);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }

  printf("  Retrieved distance: %u mm\n", distance_mm);
  printf("  Timestamp: ");
  print_timestamp(&timestamp);
  printf("\n\n");

  /* Step 4: Verify they match */
  printf("=== RESULT ===\n");
  printf("  Original measurement:  %u mm\n", original_measurement);
  printf("  Retrieved measurement: %u mm\n", distance_mm);

  if (distance_mm == original_measurement) {
    printf("\n  SUCCESS: Last shot retrieval works correctly!\n");
    printf("  The stored value was returned without taking a new measurement.\n");
  } else {
    printf("\n  FAILURE: Values do not match!\n");
    printf("  Expected %u mm but got %u mm.\n", original_measurement, distance_mm);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }

  printf("\n");

  /* Step 5: Take another measurement and verify it updates */
  printf("=== Bonus: Verify storage updates ===\n\n");
  printf("Taking a new measurement...\n");
  err = vl53l0x_read_single(&sensor, &distance_mm);
  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Single read failed (error: %d)\n", err);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }
  uint16_t new_measurement = distance_mm;
  printf("  New measured distance: %u mm\n\n", new_measurement);

  printf("Retrieving last measurement again...\n");
  err = vl53l0x_get_last_measurement(&sensor, &distance_mm, &timestamp);
  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Failed to get last measurement (error: %d)\n", err);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }

  printf("  Retrieved distance: %u mm\n", distance_mm);
  if (distance_mm == new_measurement) {
    printf("  SUCCESS: Storage correctly updated to new value!\n");
  } else {
    printf("  FAILURE: Storage not updated correctly!\n");
  }

  /* Cleanup */
  printf("\n================================\n");
  printf("Demo completed successfully!\n");
  vl53l0x_close(&sensor);

  return EXIT_SUCCESS;
}
