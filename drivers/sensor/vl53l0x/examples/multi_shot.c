/**
 * @file multi_shot.c
 * @brief VL53L0X Continuous Measurement Demo
 */

#define _POSIX_C_SOURCE 200809L

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#include "vl53l0x.h"

#define I2C_BUS 1

volatile sig_atomic_t keep_running = 1;

void handle_sigint(int sig) {
  (void)sig;
  keep_running = 0;
}

int main(void) {
  vl53l0x_t sensor;
  vl53l0x_error_t err;
  uint16_t distance_mm;

  int sample_count = 0;

  printf("VL53L0X Continuous Measurement Demo\n");
  printf("===================================\n\n");

  /* Initialize the sensor */
  printf("Initializing VL53L0X sensor...\n");
  err = vl53l0x_init(&sensor, I2C_BUS, VL53L0X_DEFAULT_ADDRESS,
                     VL53L0X_MODE_DEFAULT);

  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Failed to initialize sensor (error code: %d)\n",
            err);
    return EXIT_FAILURE;
  }
  printf("Sensor initialized!\n");

  /* Setup signal handler */
  signal(SIGINT, handle_sigint);

  /* Start continuous mode */
  printf("Starting continuous mode...\n");
  err = vl53l0x_start_continuous(&sensor);
  if (err != VL53L0X_OK) {
    fprintf(stderr, "Error: Failed to start continuous mode\n");
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }

  printf("Measuring... Press Ctrl+C to stop.\n\n");

  while (keep_running) {
    err = vl53l0x_read_continuous(&sensor, &distance_mm);

    if (err == VL53L0X_OK) {
      printf("\nDistance: %u mm", distance_mm);
      fflush(stdout);
      sample_count++;
    } else if (err == VL53L0X_ERROR_NOT_READY) {
      printf(".");
      fflush(stdout);
      struct timespec ts = {0, 10000000}; /* 10ms */
      nanosleep(&ts, NULL);
    } else {
      printf("Error reading: %d\n", err);
    }
  }

  printf("\n\nStopping continuous mode...\n");
  vl53l0x_stop_continuous(&sensor);

  printf("Measured %d samples in ~10 seconds.\n", sample_count);

  vl53l0x_close(&sensor);
  return EXIT_SUCCESS;
}
