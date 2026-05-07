/**
 * @file Sht3xNativeTest.cpp
 * @brief Native SHT31 test using LibDriver directly with I2C_RDWR interface
 * 
 * This test uses the same I2C communication method as the original
 * working implementation in /drivers/sensor/sht3x/project/raspberrypi4b/
 * 
 * Extended for dual-sensor testing:
 * - Sensor 1: 0x44 on I2C-1 (GPIO 2 SDA, GPIO 3 SCL)
 * - Sensor 2: 0x44 on I2C-5 (GPIO 12 SDA, GPIO 13 SCL)
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

/* I2C Bus Configuration */
#define I2C_BUS_1 0
#define I2C_BUS_5 1
#define NUM_SENSORS 2

static const char *i2c_devices[NUM_SENSORS] = {
    "/dev/i2c-1",  /* Sensor 1: I2C-1 */
    "/dev/i2c-5"   /* Sensor 2: I2C-5 */
};

/* Global state */
static int g_fd[NUM_SENSORS] = {-1, -1};
static sht31_handle_t g_handle[NUM_SENSORS];
static int g_active_bus = -1;  /* Track current active bus for I2C operations */

/* I2C communication functions using I2C_RDWR (matches original working code) */

/**
 * @brief Set the active I2C bus for subsequent operations
 * @param[in] bus_id Bus identifier (I2C_BUS_1 or I2C_BUS_5)
 */
void set_active_bus(int bus_id)
{
    if (bus_id >= 0 && bus_id < NUM_SENSORS) {
        g_active_bus = bus_id;
    }
}

/**
 * @brief Initialize I2C devices
 * Initializes both I2C-1 and I2C-5 buses for dual sensor support
 * Note: Idempotent - safe to call multiple times
 */
uint8_t iic_init(void)
{
    int result = 0;
    bool opened_new = false;
    
    for (int i = 0; i < NUM_SENSORS; i++) {
        /* Skip if already open */
        if (g_fd[i] >= 0) {
            continue;
        }
        
        printf("[I2C] Initializing bus %d: %s\n", i, i2c_devices[i]);
        g_fd[i] = open(i2c_devices[i], O_RDWR);
        if (g_fd[i] < 0) {
            fprintf(stderr, "[I2C] ERROR: Failed to open device %s\n", i2c_devices[i]);
            perror("[I2C] open()");
            result = 1;
        } else {
            printf("[I2C] Opened device %s (fd=%d)\n", i2c_devices[i], g_fd[i]);
            opened_new = true;
        }
    }
    
    /* CRITICAL FIX: Give the Pi kernel 20ms to settle the I2C lines */
    if (opened_new) {
        usleep(20000); 
    }
    
    return result;
}

/**
 * @brief Deinitialize I2C devices
 * Closes all I2C buses
 */
uint8_t iic_deinit(void)
{
    /* Only close the currently active bus, not all of them! */
    if (g_active_bus >= 0 && g_active_bus < NUM_SENSORS) {
        if (g_fd[g_active_bus] >= 0) {
            close(g_fd[g_active_bus]);
            g_fd[g_active_bus] = -1;
            printf("[I2C] Closed bus %d\n", g_active_bus);
        }
    }
    return 0;
}

/**
 * @brief Read data from SHT31 with 16-bit command
 * @param[in] addr I2C address (8-bit, left-shifted by 1)
 * @param[in] reg 16-bit command to send
 * @param[out] buf Data buffer to receive
 * @param[in] len Number of bytes to read
 * @return 0 on success, 1 on error
 * @note Operates on currently active bus (set via set_active_bus)
 */
uint8_t iic_read_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
{
    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[2];
    uint8_t addr_buf[2];
    
    /* Validate active bus */
    if (g_active_bus < 0 || g_active_bus >= NUM_SENSORS) {
        fprintf(stderr, "[I2C] ERROR: Invalid active bus: %d\n", g_active_bus);
        return 1;
    }
    
    int fd = g_fd[g_active_bus];
    if (fd < 0) {
        fprintf(stderr, "[I2C] ERROR: Bus %d device not opened (fd=%d)\n", g_active_bus, fd);
        return 1;
    }

    /* Clear message structures */
    memset(&i2c_rdwr_data, 0, sizeof(struct i2c_rdwr_ioctl_data));
    memset(msgs, 0, sizeof(struct i2c_msg) * 2);

    /* Prepare 16-bit command bytes */
    addr_buf[0] = (reg >> 8) & 0xFF;
    addr_buf[1] = reg & 0xFF;

    /* Message 1: Write 16-bit command */
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

    /* Log operation */
    printf("[I2C] Bus %d Read: addr=0x%02X cmd=0x%04X len=%d\n", 
           g_active_bus, addr >> 1, reg, len);

    /* Execute I2C transaction */
    if (ioctl(fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        fprintf(stderr, "[I2C] ERROR: Bus %d read failed: ", g_active_bus);
        perror("ioctl(I2C_RDWR)");
        return 1;
    }

    return 0;
}

/**
 * @brief Write command to SHT31 with 16-bit address
 * @param[in] addr I2C address (8-bit, left-shifted by 1)
 * @param[in] reg 16-bit command to send
 * @param[in] buf Optional data buffer to write
 * @param[in] len Number of data bytes (0 if no data)
 * @return 0 on success, 1 on error
 * @note Operates on currently active bus (set via set_active_bus)
 */
uint8_t iic_write_address16(uint8_t addr, uint16_t reg, uint8_t *buf, uint16_t len)
{
    struct i2c_rdwr_ioctl_data i2c_rdwr_data;
    struct i2c_msg msgs[1];
    uint8_t write_buf[34];

    /* Validate active bus */
    if (g_active_bus < 0 || g_active_bus >= NUM_SENSORS) {
        fprintf(stderr, "[I2C] ERROR: Invalid active bus: %d\n", g_active_bus);
        return 1;
    }
    
    int fd = g_fd[g_active_bus];
    if (fd < 0) {
        fprintf(stderr, "[I2C] ERROR: Bus %d device not opened (fd=%d)\n", g_active_bus, fd);
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

    /* Log operation */
    printf("[I2C] Bus %d Write: addr=0x%02X cmd=0x%04X len=%d\n", 
           g_active_bus, addr >> 1, reg, len);

    /* Execute I2C transaction */
    if (ioctl(fd, I2C_RDWR, &i2c_rdwr_data) < 0) {
        fprintf(stderr, "[I2C] ERROR: Bus %d write failed: ", g_active_bus);
        perror("ioctl(I2C_RDWR)");
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

/* Test functions for dual-sensor support */

/**
 * @brief Initialize a single SHT31 sensor
 * @param[in] sensor_id Sensor index (0 or 1)
 * @return true on success, false on failure
 */
bool test_sensor_init(int sensor_id)
{
    printf("\n[TEST] Sensor %d Initialization\n", sensor_id + 1);
    
    /* Set active bus for this sensor */
    set_active_bus(sensor_id);
    
    /* Ensure bus is open so we can send the manual Break command */
    if (g_fd[sensor_id] < 0) {
        iic_init();
    }

    printf("  Sending BREAK command (0x3093) to clear stuck loops...\n");
    iic_write_address16(0x88, 0x3093, NULL, 0);
    delay_ms(20);

    printf("  Setting address pin to 0x44 (ADDR=GND)...\n");
    if (sht31_set_addr_pin(&g_handle[sensor_id], SHT31_ADDRESS_0) != 0) {
        printf("  [FAIL] Sensor %d: Failed to set address pin\n", sensor_id + 1);
        return false;
    }

    printf("  Initializing driver...\n");
    if (sht31_init(&g_handle[sensor_id]) != 0) {
        printf("  [FAIL] Sensor %d: Failed to initialize driver\n", sensor_id + 1);
        return false;
    }

    /* CRITICAL FIX: Increase boot delay after soft reset from 10ms to 20ms */
    printf("  Waiting 20ms for sensor to boot...\n");
    delay_ms(20);

    printf("  Setting repeatability to HIGH...\n");
    if (sht31_set_repeatability(&g_handle[sensor_id], SHT31_REPEATABILITY_HIGH) != 0) {
        printf("  [FAIL] Sensor %d: Failed to set repeatability\n", sensor_id + 1);
        sht31_deinit(&g_handle[sensor_id]);
        return false;
    }
    delay_ms(5); // <-- TH�M D�NG N�Y

    printf("  Setting ART...\n");
    if (sht31_set_art(&g_handle[sensor_id]) != 0) {
        printf("  [FAIL] Sensor %d: Failed to set ART\n", sensor_id + 1);
        sht31_deinit(&g_handle[sensor_id]);
        return false;
    }
    delay_ms(5); // <-- TH�M D�NG N�Y

    printf("  Disabling heater...\n");
    if (sht31_set_heater(&g_handle[sensor_id], SHT31_BOOL_FALSE) != 0) {
        printf("  [FAIL] Sensor %d: Failed to set heater\n", sensor_id + 1);
        sht31_deinit(&g_handle[sensor_id]);
        return false;
    }
    delay_ms(5); // <-- TH�M D�NG N�Y

    printf("  [PASS] Sensor %d initialization successful\n", sensor_id + 1);
    return true;
}

/**
 * @brief Read temperature and humidity from a sensor
 * @param[in] sensor_id Sensor index (0 or 1)
 * @return true on success, false on failure
 */
bool test_sensor_read(int sensor_id)
{
    printf("\n[TEST] Sensor %d Single Read (Clock Stretching)\n", sensor_id + 1);
    
    /* Set active bus for this sensor */
    set_active_bus(sensor_id);
    
    uint16_t temperature_raw, humidity_raw;
    float temperature, humidity;

    if (sht31_single_read(&g_handle[sensor_id], SHT31_BOOL_TRUE, &temperature_raw, &temperature,
                          &humidity_raw, &humidity) != 0) {
        printf("  [FAIL] Sensor %d: Single read failed\n", sensor_id + 1);
        return false;
    }

    printf("  Sensor %d - Temperature: %.2f°C (raw: 0x%04X)\n", sensor_id + 1, temperature, temperature_raw);
    printf("  Sensor %d - Humidity: %.2f%% (raw: 0x%04X)\n", sensor_id + 1, humidity, humidity_raw);
    printf("  [PASS] Sensor %d single read successful\n", sensor_id + 1);
    return true;
}

/**
 * @brief Get serial number from a sensor
 * @param[in] sensor_id Sensor index (0 or 1)
 * @return true on success, false on failure
 */
bool test_sensor_serial(int sensor_id)
{
    printf("\n[TEST] Sensor %d Serial Number\n", sensor_id + 1);
    
    /* Set active bus for this sensor */
    set_active_bus(sensor_id);

    uint8_t serial[4];
    if (sht31_get_serial_number(&g_handle[sensor_id], serial) != 0) {
        printf("  [FAIL] Sensor %d: Failed to get serial number\n", sensor_id + 1);
        return false;
    }

    uint32_t serial_num = (serial[0] << 24) | (serial[1] << 16) | (serial[2] << 8) | serial[3];
    printf("  Sensor %d - Serial: 0x%08X\n", sensor_id + 1, serial_num);
    printf("  [PASS] Sensor %d serial number retrieved\n", sensor_id + 1);
    return true;
}

/**
 * @brief Get status register from a sensor
 * @param[in] sensor_id Sensor index (0 or 1)
 * @return true on success, false on failure
 */
bool test_sensor_status(int sensor_id)
{
    printf("\n[TEST] Sensor %d Status Register\n", sensor_id + 1);
    
    /* Set active bus for this sensor */
    set_active_bus(sensor_id);

    uint16_t status;
    if (sht31_get_status(&g_handle[sensor_id], &status) != 0) {
        printf("  [FAIL] Sensor %d: Failed to get status\n", sensor_id + 1);
        return false;
    }

    printf("  Sensor %d - Status: 0x%04X\n", sensor_id + 1, status);
    printf("  [PASS] Sensor %d status retrieved\n", sensor_id + 1);
    return true;
}

int main(int argc, char *argv[])
{
    printf("\n========================================\n");
    printf("  SHT31 Dual-Sensor Native Driver Test\n");
    printf("========================================\n");
    printf("  Sensor 1: 0x44 on I2C-1 (GPIO 2/3)\n");
    printf("  Sensor 2: 0x44 on I2C-5 (GPIO 12/13)\n");
    printf("========================================\n");

    int tests_passed = 0;
    int tests_failed = 0;

    /* Initialize I2C interfaces */
    printf("\n[SETUP] Initializing I2C interfaces\n");
    if (iic_init() != 0) {
        printf("[ERROR] Failed to initialize I2C devices\n");
        return 1;
    }

    /* Link callbacks for Sensor 1 */
    printf("[SETUP] Linking driver callbacks for Sensor 1 (I2C-1)\n");
    DRIVER_SHT31_LINK_INIT(&g_handle[I2C_BUS_1], sht31_handle_t);
    DRIVER_SHT31_LINK_IIC_INIT(&g_handle[I2C_BUS_1], iic_init);
    DRIVER_SHT31_LINK_IIC_DEINIT(&g_handle[I2C_BUS_1], iic_deinit);
    DRIVER_SHT31_LINK_IIC_READ_ADDRESS16(&g_handle[I2C_BUS_1], iic_read_address16);
    DRIVER_SHT31_LINK_IIC_WRITE_ADDRESS16(&g_handle[I2C_BUS_1], iic_write_address16);
    DRIVER_SHT31_LINK_DELAY_MS(&g_handle[I2C_BUS_1], delay_ms);
    DRIVER_SHT31_LINK_DEBUG_PRINT(&g_handle[I2C_BUS_1], debug_print);
    DRIVER_SHT31_LINK_RECEIVE_CALLBACK(&g_handle[I2C_BUS_1], receive_callback);

    /* Link callbacks for Sensor 2 */
    printf("[SETUP] Linking driver callbacks for Sensor 2 (I2C-5)\n");
    DRIVER_SHT31_LINK_INIT(&g_handle[I2C_BUS_5], sht31_handle_t);
    DRIVER_SHT31_LINK_IIC_INIT(&g_handle[I2C_BUS_5], iic_init);
    DRIVER_SHT31_LINK_IIC_DEINIT(&g_handle[I2C_BUS_5], iic_deinit);
    DRIVER_SHT31_LINK_IIC_READ_ADDRESS16(&g_handle[I2C_BUS_5], iic_read_address16);
    DRIVER_SHT31_LINK_IIC_WRITE_ADDRESS16(&g_handle[I2C_BUS_5], iic_write_address16);
    DRIVER_SHT31_LINK_DELAY_MS(&g_handle[I2C_BUS_5], delay_ms);
    DRIVER_SHT31_LINK_DEBUG_PRINT(&g_handle[I2C_BUS_5], debug_print);
    DRIVER_SHT31_LINK_RECEIVE_CALLBACK(&g_handle[I2C_BUS_5], receive_callback);

    /* Initialize Sensor 1 */
    if (test_sensor_init(I2C_BUS_1)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Initialize Sensor 2 */
    if (test_sensor_init(I2C_BUS_5)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Read from Sensor 1 */
    if (test_sensor_read(I2C_BUS_1)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Read from Sensor 2 */
    if (test_sensor_read(I2C_BUS_5)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    // /* Get Serial Number from Sensor 1 */
    // if (test_sensor_serial(I2C_BUS_1)) {
    //     tests_passed++;
    // } else {
    //     tests_failed++;
    // }

    // /* Get Serial Number from Sensor 2 */
    // if (test_sensor_serial(I2C_BUS_5)) {
    //     tests_passed++;
    // } else {
    //     tests_failed++;
    // }

    /* Get Status from Sensor 1 */
    if (test_sensor_status(I2C_BUS_1)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Get Status from Sensor 2 */
    if (test_sensor_status(I2C_BUS_5)) {
        tests_passed++;
    } else {
        tests_failed++;
    }

    /* Cleanup */
    printf("\n[CLEANUP] Deinitializing drivers\n");
    for (int i = 0; i < NUM_SENSORS; i++) {
        set_active_bus(i);
        sht31_deinit(&g_handle[i]);
        printf("[CLEANUP] Sensor %d deinitialized\n", i + 1);
    }
    iic_deinit();

    /* Summary */
    printf("\n========================================\n");
    printf("Test Results\n");
    printf("========================================\n");
    printf("Tests Passed: %d\n", tests_passed);
    printf("Tests Failed: %d\n", tests_failed);
    printf("========================================\n\n");

    return tests_failed > 0 ? 1 : 0;
}
