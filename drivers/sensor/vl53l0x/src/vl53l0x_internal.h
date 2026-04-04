/**
 * @file vl53l0x_internal.h
 * @brief VL53L0X Time-of-Flight Sensor Driver Internal Definitions
 *
 * This header contains private definitions, register addresses, and internal
 * types used by the VL53L0X driver implementation. This file should only be
 * included by vl53l0x.c and not by user code.
 *
 * @note This is an internal header - do not include in application code.
 *       Use vl53l0x.h for the public API.
 *
 * Sources for register addresses and magic numbers:
 * - ST VL53L0X API: https://www.st.com/en/imaging-and-photonics-solutions/vl53l0x.html
 * - Pololu VL53L0X Arduino Library: https://github.com/pololu/vl53l0x-arduino
 * - bitbank2 VL53L0X Linux Port: https://github.com/bitbank2/VL53L0X
 *
 * The VL53L0X has an undocumented register map. Most register addresses and
 * initialization sequences are derived from ST's official API source code
 * and community reverse-engineering efforts.
 */

#ifndef VL53L0X_INTERNAL_H_
#define VL53L0X_INTERNAL_H_

#include "vl53l0x.h"

#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

/* ============================================================================
 * VL53L0X Register Addresses
 *
 * These registers are documented in ST's VL53L0X API source code.
 * Reference: vl53l0x_device.h in ST's STSW-IMG005 package
 * https://www.st.com/en/embedded-software/stsw-img005.html
 * ============================================================================ */

/** Model identification register - returns 0xEE for VL53L0X */
#define REG_IDENTIFICATION_MODEL_ID 0xC0
/** Revision identification register */
#define REG_IDENTIFICATION_REVISION_ID 0xC2
/** System range start - controls measurement start/mode */
#define REG_SYSRANGE_START 0x00
/** Interrupt status - bits [2:0] indicate measurement ready */
#define REG_RESULT_INTERRUPT_STATUS 0x13
/** Range status register - measurement results start at offset +10 */
#define REG_RESULT_RANGE_STATUS 0x14
/** Interrupt clear register - write 0x01 to clear */
#define REG_SYSTEM_INTERRUPT_CLEAR 0x0B
/** GPIO interrupt configuration */
#define REG_SYSTEM_INTERRUPT_CONFIG_GPIO 0x0A
/** GPIO active high/low configuration */
#define REG_GPIO_HV_MUX_ACTIVE_HIGH 0x84
/** Sequence configuration - enables measurement steps */
#define REG_SYSTEM_SEQUENCE_CONFIG 0x01
/** MSRC (Minimum Signal Rate Check) configuration */
#define REG_MSRC_CONFIG_CONTROL 0x60
/** VHV (Voltage High Voltage) pad configuration - bit 0 enables 2.8V mode */
#define REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV 0x89
/** Minimum count rate for final range (Q9.7 fixed point format) */
#define REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE 0x44
/** SPAD enables reference starting register */
#define REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0 0xB0
/** Pre-range VCSEL (Vertical Cavity Surface Emitting Laser) period */
#define REG_PRE_RANGE_CONFIG_VCSEL_PERIOD 0x50
/** Pre-range timeout (high byte) */
#define REG_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI 0x51
/** Pre-range valid phase high threshold */
#define REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH 0x57
/** Pre-range valid phase low threshold */
#define REG_PRE_RANGE_CONFIG_VALID_PHASE_LOW 0x56
/** Final range VCSEL period */
#define REG_FINAL_RANGE_CONFIG_VCSEL_PERIOD 0x70
/** Final range timeout (high byte) */
#define REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI 0x71
/** Final range valid phase high threshold */
#define REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH 0x48
/** Final range valid phase low threshold */
#define REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW 0x47
/** MSRC timeout configuration */
#define REG_MSRC_CONFIG_TIMEOUT_MACROP 0x46
/** Global VCSEL pulse width */
#define REG_GLOBAL_CONFIG_VCSEL_WIDTH 0x32
/** Phase calibration timeout */
#define REG_ALGO_PHASECAL_CONFIG_TIMEOUT 0x30
/** Phase calibration limit */
#define REG_ALGO_PHASECAL_LIM 0x40

/* ============================================================================
 * Sequence Step Enable Masks
 *
 * These bit masks correspond to measurement sequence steps in REG_SYSTEM_SEQUENCE_CONFIG.
 * Reference: VL53L0X_SequenceStepId enum in ST's API (vl53l0x_def.h)
 * ============================================================================ */

/** TCC (Target Centre Check) - verifies target is centered */
#define SEQUENCE_ENABLE_TCC 0x10
/** DSS (Dynamic SPAD Selection) - optimizes SPAD usage */
#define SEQUENCE_ENABLE_DSS 0x08
/** MSRC (Minimum Signal Rate Check) - validates signal strength */
#define SEQUENCE_ENABLE_MSRC 0x04
/** Pre-range measurement step */
#define SEQUENCE_ENABLE_PRE_RANGE 0x40
/** Final range measurement step - actual distance measurement */
#define SEQUENCE_ENABLE_FINAL_RANGE 0x80

/* ============================================================================
 * Timing and Timeout Constants
 * ============================================================================ */

/**
 * Maximum timeout for I2C polling operations (iterations).
 * With 5ms delay per iteration, this gives ~500ms total timeout.
 */
#define MAX_TIMEOUT 100

/* ============================================================================
 * Macros for VCSEL Period Calculations
 *
 * These formulas are derived from ST's API source code.
 * Reference: vl53l0x_api_core.c in STSW-IMG005
 *
 * The macro period is the fundamental timing unit for the sensor,
 * calculated from the VCSEL (laser) pulse period.
 * ============================================================================ */

/**
 * Calculate macro period from VCSEL period in PCLKs.
 *
 * Formula: macro_period_ns = 2304 * vcsel_period_pclks * 1655 / 1000
 * The constants 2304 and 1655 are hardware timing parameters from ST's datasheet.
 * - 2304: PLL period multiplier
 * - 1655: Internal timing constant (related to 60.4 MHz XTAL)
 * The +500 provides rounding.
 */
#define CALC_MACRO_PERIOD(vcsel_period_pclks)                                  \
  ((((uint32_t)2304 * (vcsel_period_pclks) * 1655) + 500) / 1000)

/**
 * Encode VCSEL period for register storage.
 * Register value = (period_pclks / 2) - 1
 * Valid periods: 8, 10, 12, 14, 16, 18 PCLKs
 */
#define ENCODE_VCSEL_PERIOD(period_pclks) (((period_pclks) >> 1) - 1)

/* ============================================================================
 * Internal Types
 * ============================================================================ */

/**
 * @brief VCSEL period types for configuration
 */
typedef enum {
  VCSEL_PERIOD_PRE_RANGE,   /**< Pre-range measurement VCSEL period */
  VCSEL_PERIOD_FINAL_RANGE  /**< Final range measurement VCSEL period */
} vcsel_period_type_t;

/**
 * @brief Sequence step timeout structure
 *
 * Stores timing information for each measurement sequence step.
 * Times are stored in both MCLKs (macro clocks) and microseconds.
 */
typedef struct {
  uint16_t pre_range_vcsel_period_pclks;    /**< Pre-range VCSEL period */
  uint16_t final_range_vcsel_period_pclks;  /**< Final range VCSEL period */
  uint16_t msrc_dss_tcc_mclks;              /**< MSRC/DSS/TCC timeout in MCLKs */
  uint16_t pre_range_mclks;                 /**< Pre-range timeout in MCLKs */
  uint16_t final_range_mclks;               /**< Final range timeout in MCLKs */
  uint32_t msrc_dss_tcc_us;                 /**< MSRC/DSS/TCC timeout in us */
  uint32_t pre_range_us;                    /**< Pre-range timeout in us */
  uint32_t final_range_us;                  /**< Final range timeout in us */
} sequence_step_timeouts_t;

/* ============================================================================
 * Register Initialization Lists
 *
 * These initialization sequences are derived from ST's official VL53L0X API.
 * The exact purpose of many undocumented registers is not publicly known.
 *
 * Format: First byte is count, followed by (register, value) pairs.
 *
 * Sources:
 * - ST STSW-IMG005 API: vl53l0x_api.c, VL53L0X_DataInit() and VL53L0X_StaticInit()
 * - Pololu Arduino library: https://github.com/pololu/vl53l0x-arduino/blob/master/VL53L0X.cpp
 * - bitbank2 Linux port: https://github.com/bitbank2/VL53L0X/blob/master/vl53l0x.c
 * ============================================================================ */

/**
 * I2C mode initialization sequence 1
 * Sets up I2C communication parameters
 * Registers 0x88, 0x80, 0xFF, 0x00 are undocumented I2C config registers
 */
static const uint8_t i2c_mode1[] = {4,    0x88, 0x00, 0x80, 0x01,
                                    0xFF, 0x01, 0x00, 0x00};

/**
 * I2C mode initialization sequence 2
 * Completes I2C setup and returns to normal mode
 */
static const uint8_t i2c_mode2[] = {3, 0x00, 0x01, 0xFF, 0x00, 0x80, 0x00};

/**
 * SPAD initialization sequence 0
 * Prepares for SPAD (Single Photon Avalanche Diode) info readout
 * Register 0xFF is a page/bank select register
 */
static const uint8_t spad_init0[] = {4,    0x80, 0x01, 0xFF, 0x01,
                                     0x00, 0x00, 0xFF, 0x06};

/**
 * SPAD initialization sequence 1
 * Continues SPAD configuration
 * Register 0x94 contains SPAD calibration data
 * Register 0x83 is used for SPAD readiness polling
 */
static const uint8_t spad_init1[] = {5,    0xFF, 0x07, 0x81, 0x01, 0x80,
                                     0x01, 0x94, 0x6B, 0x83, 0x00};

/**
 * SPAD initialization sequence 2
 * Finalizes SPAD setup and returns to normal register page
 */
static const uint8_t spad_init2[] = {4,    0xFF, 0x01, 0x00, 0x01,
                                     0xFF, 0x00, 0x80, 0x00};

/**
 * SPAD configuration
 * Configures SPAD reference settings
 * Register 0x4F/0x4E: SPAD timing parameters
 * Register 0xB6: Part of SPAD enables reference map
 */
static const uint8_t spad_config[] = {5,    0xFF, 0x01, 0x4F, 0x00, 0x4E,
                                      0x2C, 0xFF, 0x00, 0xB6, 0xB4};

/**
 * Default tuning settings
 *
 * This 80-register sequence configures the sensor's internal algorithms.
 * These values are extracted from ST's API VL53L0X_load_tuning_settings().
 * They configure:
 * - Signal rate limits and thresholds
 * - Ranging algorithm parameters
 * - Crosstalk compensation
 * - Return signal optimization
 *
 * The exact function of each undocumented register is proprietary to ST.
 * Modifying these values is not recommended without extensive testing.
 *
 * Notable registers in sequence:
 * - 0x24/0x25: Signal rate limits
 * - 0x44/0x45: Range ignore threshold
 * - 0x46-0x48: Timing parameters
 * - 0x50-0x57: Pre-range configuration
 * - 0x70-0x78: Final range configuration
 */
static const uint8_t default_tuning[] = {
    80,   0xFF, 0x01, 0x00, 0x00, 0xFF, 0x00, 0x09, 0x00, 0x10, 0x00, 0x11,
    0x00, 0x24, 0x01, 0x25, 0xFF, 0x75, 0x00, 0xFF, 0x01, 0x4E, 0x2C, 0x48,
    0x00, 0x30, 0x20, 0xFF, 0x00, 0x30, 0x09, 0x54, 0x00, 0x31, 0x04, 0x32,
    0x03, 0x40, 0x83, 0x46, 0x25, 0x60, 0x00, 0x27, 0x00, 0x50, 0x06, 0x51,
    0x00, 0x52, 0x96, 0x56, 0x08, 0x57, 0x30, 0x61, 0x00, 0x62, 0x00, 0x64,
    0x00, 0x65, 0x00, 0x66, 0xA0, 0xFF, 0x01, 0x22, 0x32, 0x47, 0x14, 0x49,
    0xFF, 0x4A, 0x00, 0xFF, 0x00, 0x7A, 0x0A, 0x7B, 0x00, 0x78, 0x21, 0xFF,
    0x01, 0x23, 0x34, 0x42, 0x00, 0x44, 0xFF, 0x45, 0x26, 0x46, 0x05, 0x40,
    0x40, 0x0E, 0x06, 0x20, 0x1A, 0x43, 0x40, 0xFF, 0x00, 0x34, 0x03, 0x35,
    0x44, 0xFF, 0x01, 0x31, 0x04, 0x4B, 0x09, 0x4C, 0x05, 0x4D, 0x04, 0xFF,
    0x00, 0x44, 0x00, 0x45, 0x20, 0x47, 0x08, 0x48, 0x28, 0x67, 0x00, 0x70,
    0x04, 0x71, 0x01, 0x72, 0xFE, 0x76, 0x00, 0x77, 0x00, 0xFF, 0x01, 0x0D,
    0x01, 0xFF, 0x00, 0x80, 0x01, 0x01, 0xF8, 0xFF, 0x01, 0x8E, 0x01, 0x00,
    0x01, 0xFF, 0x00, 0x80, 0x00};

/* ============================================================================
 * Internal Function Declarations
 * ============================================================================ */

/**
 * @brief Delay for a specified number of milliseconds
 * @param ms Milliseconds to delay
 */
static void delay_ms(uint32_t ms);

/**
 * @brief Read a single byte from a register
 * @param dev Pointer to device handle
 * @param reg Register address
 * @return Register value
 */
static uint8_t read_reg(vl53l0x_t *dev, uint8_t reg);

/**
 * @brief Read a 16-bit value from a register pair
 * @param dev Pointer to device handle
 * @param reg Register address
 * @return 16-bit register value
 */
static uint16_t read_reg16(vl53l0x_t *dev, uint8_t reg);

/**
 * @brief Read multiple bytes from a register
 * @param dev Pointer to device handle
 * @param reg Register address
 * @param buf Buffer to store data
 * @param count Number of bytes to read
 */
static void read_multi(vl53l0x_t *dev, uint8_t reg, uint8_t *buf, int count);

/**
 * @brief Write a single byte to a register
 * @param dev Pointer to device handle
 * @param reg Register address
 * @param value Value to write
 */
static void write_reg(vl53l0x_t *dev, uint8_t reg, uint8_t value);

/**
 * @brief Write a 16-bit value to a register pair
 * @param dev Pointer to device handle
 * @param reg Register address
 * @param value 16-bit value to write
 */
static void write_reg16(vl53l0x_t *dev, uint8_t reg, uint16_t value);

/**
 * @brief Write multiple bytes to a register
 * @param dev Pointer to device handle
 * @param reg Register address
 * @param buf Buffer containing data
 * @param count Number of bytes to write
 */
static void write_multi(vl53l0x_t *dev, uint8_t reg, uint8_t *buf, int count);

/**
 * @brief Write a list of register/value pairs
 * @param dev Pointer to device handle
 * @param list List of register/value pairs
 */
static void write_reg_list(vl53l0x_t *dev, const uint8_t *list);

/**
 * @brief Get SPAD count and type information
 * @param dev Pointer to device handle
 * @param count Pointer to store SPAD count
 * @param type_is_aperture Pointer to store aperture flag
 * @return 0 on success, -1 on failure
 */
static int get_spad_info(vl53l0x_t *dev, uint8_t *count,
                         uint8_t *type_is_aperture);

/**
 * @brief Initialize the sensor hardware
 * @param dev Pointer to device handle
 * @param long_range Enable long range mode
 * @return 0 on success, -1 on failure
 */
static int init_sensor(vl53l0x_t *dev, int long_range);

/**
 * @brief Perform single reference calibration
 * @param dev Pointer to device handle
 * @param vhv_init VHV initialization flag
 * @return 0 on success, -1 on failure
 */
static int perform_single_ref_calibration(vl53l0x_t *dev, uint8_t vhv_init);

/**
 * @brief Set measurement timing budget
 * @param dev Pointer to device handle
 * @param budget_us Timing budget in microseconds
 * @return 0 on success, -1 on failure
 */
static int set_measurement_timing_budget(vl53l0x_t *dev, uint32_t budget_us);

/**
 * @brief Get current measurement timing budget
 * @param dev Pointer to device handle
 * @return Timing budget in microseconds
 */
static uint32_t get_measurement_timing_budget(vl53l0x_t *dev);

/**
 * @brief Get sequence step timeouts
 * @param dev Pointer to device handle
 * @param enables Enabled sequence steps
 * @param timeouts Pointer to timeout structure
 */
static void get_sequence_step_timeouts(vl53l0x_t *dev, uint8_t enables,
                                       sequence_step_timeouts_t *timeouts);

/**
 * @brief Decode timeout register value
 * @param reg_val Raw register value
 * @return Decoded timeout value
 */
static uint16_t decode_timeout(uint16_t reg_val);

/**
 * @brief Encode timeout value for register
 * @param timeout_mclks Timeout in MCLKs
 * @return Encoded register value
 */
static uint16_t encode_timeout(uint16_t timeout_mclks);

/**
 * @brief Convert timeout from MCLKs to microseconds
 * @param mclks Timeout in MCLKs
 * @param vcsel_pclks VCSEL period in PCLKs
 * @return Timeout in microseconds
 */
static uint32_t timeout_mclks_to_us(uint16_t mclks, uint8_t vcsel_pclks);

/**
 * @brief Convert timeout from microseconds to MCLKs
 * @param us Timeout in microseconds
 * @param vcsel_pclks VCSEL period in PCLKs
 * @return Timeout in MCLKs
 */
static uint32_t timeout_us_to_mclks(uint32_t us, uint8_t vcsel_pclks);

/**
 * @brief Set VCSEL pulse period
 * @param dev Pointer to device handle
 * @param type Period type (pre-range or final range)
 * @param period_pclks Period in PCLKs
 * @return 0 on success, -1 on failure
 */
static int set_vcsel_pulse_period(vl53l0x_t *dev, vcsel_period_type_t type,
                                  uint8_t period_pclks);

/**
 * @brief Read range measurement in continuous mode
 * @param dev Pointer to device handle
 * @return Range measurement in millimeters
 */
static uint16_t read_range_continuous_mm(vl53l0x_t *dev);

#endif /* VL53L0X_INTERNAL_H_ */
