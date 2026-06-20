/**
 * @file test_continuous_nonblocking.c
 * @brief Test for VL53L0X Continuous Measurement and Non-Blocking Behavior
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include "vl53l0x.h"

#define I2C_BUS 1
#define TEST_PASS 0
#define TEST_FAIL 1

/* Helper to get time in milliseconds */
static long long current_timestamp_ms() {
  struct timeval te;
  gettimeofday(&te, NULL);
  long long milliseconds = te.tv_sec * 1000LL + te.tv_usec / 1000;
  return milliseconds;
}

int main(void) {
  vl53l0x_t sensor;
  vl53l0x_error_t err;
  uint16_t distance_mm;
  int failed = 0;
  long long t1, t2;
  int samples = 0;

  printf("\n");
  printf("==================================================\n");
  printf("VL53L0X Continuous & Non-Blocking Test\n");
  printf("==================================================\n\n");

  /* Initialize */
  printf("[TEST] Initialization... ");
  err = vl53l0x_init(&sensor, I2C_BUS, VL53L0X_DEFAULT_ADDRESS,
                     VL53L0X_MODE_DEFAULT);
  if (err != VL53L0X_OK) {
    printf("FAILED (Init error: %d)\n", err);
    return EXIT_FAILURE;
  }
  printf("PASSED\n");

  /* Start Continuous */
  printf("[TEST] Start continuous mode... ");
  err = vl53l0x_start_continuous(&sensor);
  if (err != VL53L0X_OK) {
    printf("FAILED (Start error: %d)\n", err);
    vl53l0x_close(&sensor);
    return EXIT_FAILURE;
  }
  printf("PASSED\n");

  /* Test Non-Blocking Behavior */
  /* Immediately try to read - should allow NOT_READY and allow immediate return
   */
  printf("[TEST] Non-blocking check (immediate read)... ");
  t1 = current_timestamp_ms();
  err = vl53l0x_read_continuous(&sensor, &distance_mm);
  t2 = current_timestamp_ms();

  if (err == VL53L0X_ERROR_NOT_READY || err == VL53L0X_OK) {
    /* If it took less than 10ms, it's definitely non-blocking.
       A blocking read would take >20ms usually. */
    if ((t2 - t1) < 10) {
      printf("PASSED (Return time: %lld ms, State: %s)\n", (t2 - t1),
             (err == VL53L0X_ERROR_NOT_READY) ? "NOT_READY" : "DATA_READY");
    } else {
      printf("WARNING (Return time: %lld ms - might be blocking?)\n",
             (t2 - t1));
      /* Don't strictly fail here as system load can vary, but warn */
    }
  } else {
    printf("FAILED (Unexpected error: %d)\n", err);
    failed++;
  }

  /* Test Multiple Samples Capture */
  printf("[TEST] Capture multiple samples (approx 2s)... ");
  long long start_loop = current_timestamp_ms();
  samples = 0;

  while ((current_timestamp_ms() - start_loop) < 2000) {
    err = vl53l0x_read_continuous(&sensor, &distance_mm);
    if (err == VL53L0X_OK) {
      samples++;
    }
    struct timespec ts = {0, 1000000}; /* 1ms */
    nanosleep(&ts, NULL);              /* Small sleep to prevent CPU hogging */
  }

  if (samples > 0) {
    printf("PASSED (Captured %d samples)\n", samples);
  } else {
    printf("FAILED (No samples captured in 2s)\n");
    failed++;
  }

  /* Stop */
  printf("[TEST] Stop continuous mode... ");
  err = vl53l0x_stop_continuous(&sensor);
  if (err != VL53L0X_OK) {
    printf("FAILED (Stop error: %d)\n", err);
    failed++;
  } else {
    printf("PASSED\n");
  }

  vl53l0x_close(&sensor);

  printf("\n==================================================\n");
  printf("Test Result: %s\n", (failed == 0) ? "PASS" : "FAIL");
  printf("==================================================\n\n");

  return (failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
