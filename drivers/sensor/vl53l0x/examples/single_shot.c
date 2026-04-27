/**
 * @file main.c
 * @brief VL53L0X Single Shot Measurement Demo
 *
 * Demonstrates single distance measurement using the VL53L0X
 * Time-of-Flight sensor on Raspberry Pi.
 *
 * Usage: ./vl53l0x_single
 */

#include <stdio.h>
#include <stdlib.h>

#include "vl53l0x.h"

/**
 * @brief I2C bus number for Raspberry Pi 4
 */
#define I2C_BUS 1

/**
 * @brief Main entry point
 *
 * Initializes the VL53L0X sensor, displays model info,
 * performs a single distance measurement, and exits.
 *
 * @return 0 on success, non-zero on failure
 */
int main(void) {
  vl53l0x_t sensor;
  vl53l0x_error_t err;
  uint16_t distance_mm;
  uint8_t model, revision;

  printf("VL53L0X Single Distance Measurement\n");
  printf("====================================\n\n");

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
      fprintf(stderr, "(unknown error)\n");
    }
    return EXIT_FAILURE;
  }

  printf("Sensor initialized successfully!\n\n");

  /* Get and display sensor model information */
  err = vl53l0x_get_model(&sensor, &model, &revision);
  if (err == VL53L0X_OK) {
    printf("Sensor Information:\n");
    printf("  Model ID:    0x%02X\n", model);
    printf("  Revision:    0x%02X\n", revision);
    printf("\n");
  }

  /* Perform a single distance measurement */
  printf("Performing single distance measurement...\n");
  err = vl53l0x_read_single(&sensor, &distance_mm);

  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Measurement failed ");
    switch (err) {
    case VL53L0X_ERROR_TIMEOUT:
      fprintf(stderr, "(timeout)\n");
      break;
    default:
      fprintf(stderr, "(unknown error)\n");
    }
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }

  /* Display the measurement result */
  printf("\n");
  printf("=== MEASUREMENT RESULT ===\n");
  printf("  Distance: %u mm\n", distance_mm);
  printf("==========================\n");

  /* Clean up */
  vl53l0x_close(&sensor);

  return EXIT_SUCCESS;
}
