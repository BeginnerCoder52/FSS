/**
 * @file diagnose.c
 * @brief VL53L0X Hardware Diagnostic Tool
 *
 * Checks if the sensor is accessible on the I2C bus and verifies its identity.
 * Useful for determining if the sensor is "broken" or just misconfigured.
 */

#define _POSIX_C_SOURCE 199309L
#include "vl53l0x.h"
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define I2C_BUS 1
#define ADDR 0x29

// Direct I2C register read helper for diagnosis
// (Bypasses driver to check raw hardware access)
static int diag_read_reg(int fd, uint8_t reg, uint8_t *val) {
  if (write(fd, &reg, 1) != 1) {
    return -1;
  }
  if (read(fd, val, 1) != 1) {
    return -1;
  }
  return 0;
}

int main(void) {
  printf("=======================================\n");
  printf("VL53L0X Hardware Diagnosis\n");
  printf("=======================================\n");

  // 1. Open I2C Bus
  char filename[32];
  snprintf(filename, sizeof(filename), "/dev/i2c-%d", I2C_BUS);
  printf("[1/4] Opening I2C bus %s... ", filename);

  int fd = open(filename, O_RDWR);
  if (fd < 0) {
    printf("FAIL\n");
    printf("      Error: Could not open I2C bus. Check permissions or if I2C "
           "is enabled.\n");
    return 1;
  }
  printf("PASS\n");

  // 2. Acquire Bus Access
  printf("[2/4] Connecting to address 0x%02X... ", ADDR);
  if (ioctl(fd, I2C_SLAVE, ADDR) < 0) {
    printf("FAIL\n");
    printf("      Error: Could not acquire bus access.\n");
    close(fd);
    return 1;
  }
  printf("PASS\n");

  // 3. Check Model ID (Register 0xC0)
  // The VL53L0X should always return 0xEE at register 0xC0
  printf("[3/4] check Model ID (Reg 0xC0)... ");
  uint8_t model_id = 0;
  if (diag_read_reg(fd, 0xC0, &model_id) < 0) {
    printf("FAIL\n");
    printf("      Error: I2C Read failed. Sensor might be disconnected or "
           "unpowered.\n");
    close(fd);
    return 1;
  }

  if (model_id == 0xEE) {
    printf("PASS (Got 0xEE)\n");
  } else {
    printf("FAIL\n");
    printf("      Error: Invalid Model ID. Expected 0xEE, got 0x%02X.\n",
           model_id);
    printf("      This suggests the device at 0x29 is NOT a VL53L0X or is "
           "malfunctioning.\n");
    close(fd);
    return 1;
  }

  // 4. Check Revision ID (Reg 0xC2)
  printf("      Checking Revision ID (Reg 0xC2)... ");
  uint8_t rev_id = 0;
  diag_read_reg(fd, 0xC2, &rev_id);
  printf("0x%02X\n", rev_id);

  close(fd);

  printf("\n---------------------------------------\n");
  printf("HARDWARE STATUS: OK\n");
  printf("The sensor is alive and responding correctly to identification "
         "queries.\n");
  printf("If you are still having driver issues, it is likely a "
         "software/configuration problem.\n");
  printf("---------------------------------------\n");

  return 0;
}
