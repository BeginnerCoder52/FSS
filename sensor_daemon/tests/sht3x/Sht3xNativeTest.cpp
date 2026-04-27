/**
 * @file Sht3xNativeTest.cpp
 * @brief Native SHT31 test using LibDriver directly with I2C_RDWR interface
 * 
 * This test uses the same I2C communication method as the original
 * working implementation in /drivers/sensor/sht3x/project/raspberrypi4b/
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <stdarg.h>
#include <chrono>
#include <thread>
#include <iostream>
#include <iomanip>

extern "C" {
#include "driver_sht31.h"
}

/* Global state */
static int g_fd = -1;
static sht31_handle_t g_handle;

/* I2C communication functions using I2C_RDWR (matches original working code) */
uint8_t iic_init(void)
{
    const char *device = "/dev/i2c-1";
    g_fd = open(device, O_RDWR);
    if (g_fd < 0) {
        perror("Failed to open I2C device");
        return 1;
    }
    printf("[I2C] Opened device %s (fd=%d)\n", device, g_fd);
    return 0;
}

uint8_t iic_deinit(void)
{
    if (g_fd >= 0) {
        close(g_fd);
        g_fd = -1;
    }
    return 0;
}

uint8_t iic_read_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
{
    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[2];
    uint8_t addr_buf[2];
    
    if (g_fd < 0) {
        fprintf(stderr, "[I2C] Device not opened\n");
        return 1;
    }

    /* Clear message structures */
    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg) * 2);

    /* Prepare address (addr is already left-shifted by 1, need to shift back) */
    addr_buf[0] = (reg >> 8) & 0xFF;
    addr_buf[1] = reg & 0xFF;

    /* Message 1: Write 16-bit register address */
    msgs[0].addr = addr >> 1;
    msgs[0].flags = 0;
    msgs[0].buf = addr_buf;
    msgs[0].len = 2;

    /* Message 2: Read data */
    msgs[1].addr = addr >> 1;
    msgs[1].flags = I2C_M_RD;
    msgs[1].buf = buf;
    msgs[1].len = len;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 2;

    /* Execute I2C transaction */
    if (ioctl(g_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        perror("[I2C] Read failed");
        return 1;
    }

    return 0;
}

uint8_t iic_write_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
{
    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[1];
    uint8_t write_buf[34];

    if (g_fd < 0) {
        fprintf(stderr, "[I2C] Device not opened\n");
        return 1;
    }

    /* Clear structures */
    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg));

    /* Build write buffer: [cmd_high, cmd_low, data...] */
    write_buf[0] = (reg >> 8) & 0xFF;
    write_buf[1] = reg & 0xFF;

    if (len > 0 && len <= 32) {
        memcpy(&write_buf[2], buf, len);
    }

    /* Single message: Write command + data */
    msgs[0].addr = addr >> 1;
    msgs[0].flags = 0;
    msgs[0].buf = write_buf;
    msgs[0].len = 2 + len;

    i2c_rdwr_data.msgs = msgs;
    i2c_rdwr_data.nmsgs = 1;

    /* Execute I2C transaction */
    if (ioctl(g_fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        perror("[I2C] Write failed");
        return 1;
    }

    return 0;
}

void delay_ms(uint32_t ms)
{
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

void debug_print(const char *const fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vfprintf(stdout, fmt, args);
    va_end(args);
}

void receive_callback(uint16_t type)
{
    (void)type;
}

/* Test functions */
bool test_init()
{
    printf("\n[TEST] Initialization\n");
    printf("  Setting address pin to 0x44 (ADDR=GND)...\n");
    
    if (sht31_set_addr_pin(&g_handle, SHT31_ADDRESS_0) != 0) {
        printf("  [FAIL] Failed to set address pin\n");
        return false;
    }

    printf("  Initializing driver...\n");
    if (sht31_init(&g_handle) != 0) {
        printf("  [FAIL] Failed to initialize\n");
        return false;
    }

    printf("  Waiting 10ms...\n");
    delay_ms(10);

    printf("  Setting repeatability to HIGH...\n");
    if (sht31_set_repeatability(&g_handle, SHT31_REPEATABILITY_HIGH) != 0) {
        printf("  [FAIL] Failed to set repeatability\n");
        sht31_deinit(&g_handle);
        return false;
    }

    printf("  Setting ART...\n");
    if (sht31_set_art(&g_handle) != 0) {
        printf("  [FAIL] Failed to set ART\n");
        sht31_deinit(&g_handle);
        return false;
    }

    printf("  Disabling heater...\n");
    if (sht31_set_heater(&g_handle, SHT31_BOOL_FALSE) != 0) {
        printf("  [FAIL] Failed to set heater\n");
        sht31_deinit(&g_handle);
        return false;
    }

    printf("  [PASS] Initialization successful\n");
    return true;
}

bool test_single_read()
{
    printf("\n[TEST] Single Read (Clock Stretching)\n");
    
    uint16_t temperature_raw, humidity_raw;
    float temperature, humidity;

    if (sht31_single_read(&g_handle, SHT31_BOOL_TRUE, &temperature_raw, &temperature,
                          &humidity_raw, &humidity) != 0) {
        printf("  [FAIL] Single read failed\n");
        return false;
    }

    printf("  Temperature: %.2f°C (raw: 0x%04X)\n", temperature, temperature_raw);
    printf("  Humidity: %.2f%% (raw: 0x%04X)\n", humidity, humidity_raw);
    printf("  [PASS] Single read successful\n");
    return true;
}

bool test_serial_number()
{
    printf("\n[TEST] Serial Number\n");

    uint8_t serial[4];
    if (sht31_get_serial_number(&g_handle, serial) != 0) {
        printf("  [FAIL] Failed to get serial number\n");
        return false;
    }

    uint32_t serial_num = (serial[0] << 24) | (serial[1] << 16) | (serial[2] << 8) | serial[3];
    printf("  Serial: 0x%08X\n", serial_num);
    printf("  [PASS] Serial number retrieved\n");
    return true;
}

bool test_status()
{
    printf("\n[TEST] Status Register\n");

    uint16_t status;
    if (sht31_get_status(&g_handle, &status) != 0) {
        printf("  [FAIL] Failed to get status\n");
        return false;
    }

    printf("  Status: 0x%04X\n", status);
    printf("  [PASS] Status retrieved\n");
    return true;
}

bool test_repeatability()
{
    printf("\n[TEST] Repeatability Configuration\n");

    if (sht31_set_repeatability(&g_handle, SHT31_REPEATABILITY_MEDIUM) != 0) {
        printf("  [FAIL] Failed to set medium repeatability\n");
        return false;
    }

    if (sht31_set_repeatability(&g_handle, SHT31_REPEATABILITY_HIGH) != 0) {
        printf("  [FAIL] Failed to set high repeatability\n");
        return false;
    }

    printf("  [PASS] Repeatability configuration successful\n");
    return true;
}

int main(int argc, char *argv[])
{
    printf("\n========================================\n");
    printf("  SHT31 Native Driver Test Suite\n");
    printf("========================================\n");

    int tests_passed = 0;
    int tests_failed = 0;

    /* Initialize I2C interface */
    printf("\n[SETUP] Initializing I2C interface\n");
    if (iic_init() != 0) {
        printf("[ERROR] Failed to initialize I2C\n");
        return 1;
    }

    /* Link all callbacks */
    printf("[SETUP] Linking driver callbacks\n");
    DRIVER_SHT31_LINK_INIT(&g_handle, sht31_handle_t);
    DRIVER_SHT31_LINK_IIC_INIT(&g_handle, iic_init);
    DRIVER_SHT31_LINK_IIC_DEINIT(&g_handle, iic_deinit);
    DRIVER_SHT31_LINK_IIC_READ_ADDRESS16(&g_handle, iic_read_address16);
    DRIVER_SHT31_LINK_IIC_WRITE_ADDRESS16(&g_handle, iic_write_address16);
    DRIVER_SHT31_LINK_DELAY_MS(&g_handle, delay_ms);
    DRIVER_SHT31_LINK_DEBUG_PRINT(&g_handle, debug_print);
    DRIVER_SHT31_LINK_RECEIVE_CALLBACK(&g_handle, receive_callback);

    /* Run tests */
    if (test_init()) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    if (test_single_read()) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    if (test_serial_number()) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    if (test_status()) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    if (test_repeatability()) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Cleanup */
    printf("\n[CLEANUP] Deinitializing driver\n");
    sht31_deinit(&g_handle);
    iic_deinit();

    /* Summary */
    printf("\n========================================\n");
    printf("Tests Passed: %d\n", tests_passed);
    printf("Tests Failed: %d\n", tests_failed);
    printf("========================================\n\n");

    return tests_failed > 0 ? 1 : 0;
}
