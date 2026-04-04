/**
 * @file vl53l0x.c
 * @brief VL53L0X Time-of-Flight Sensor Driver Implementation
 *
 * This driver is based on the Pololu Arduino library and Larry Bank's
 * Linux port (bitbank2/VL53L0X). It provides I2C communication with the
 * VL53L0X sensor for distance measurements on Linux platforms.
 */

#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L

#include "vl53l0x_internal.h"

/**
 * @brief Delay for a specified number of milliseconds
 */
static void delay_ms(uint32_t ms) {
  struct timespec ts;
  ts.tv_sec = ms / 1000;
  ts.tv_nsec = (ms % 1000) * 1000000;
  nanosleep(&ts, NULL);
}

/**
 * @brief Read a single byte from a register
 */
static uint8_t read_reg(vl53l0x_t *dev, uint8_t reg) {
  uint8_t value = 0;

  if (write(dev->i2c_fd, &reg, 1) == 1) {
    read(dev->i2c_fd, &value, 1);
  }

  return value;
}

/**
 * @brief Read a 16-bit value from a register pair
 */
static uint16_t read_reg16(vl53l0x_t *dev, uint8_t reg) {
  uint8_t buf[2] = {0};

  if (write(dev->i2c_fd, &reg, 1) == 1) {
    read(dev->i2c_fd, buf, 2);
  }

  return ((uint16_t)buf[0] << 8) | buf[1];
}

/**
 * @brief Read multiple bytes from a register
 */
static void read_multi(vl53l0x_t *dev, uint8_t reg, uint8_t *buf, int count) {
  if (write(dev->i2c_fd, &reg, 1) == 1) {
    read(dev->i2c_fd, buf, count);
  }
}

/**
 * @brief Write a single byte to a register
 */
static void write_reg(vl53l0x_t *dev, uint8_t reg, uint8_t value) {
  uint8_t buf[2];

  buf[0] = reg;
  buf[1] = value;
  write(dev->i2c_fd, buf, 2);
}

/**
 * @brief Write a 16-bit value to a register pair
 */
static void write_reg16(vl53l0x_t *dev, uint8_t reg, uint16_t value) {
  uint8_t buf[3];

  buf[0] = reg;
  buf[1] = (uint8_t)(value >> 8);
  buf[2] = (uint8_t)value;
  write(dev->i2c_fd, buf, 3);
}

/**
 * @brief Write multiple bytes to a register
 */
static void write_multi(vl53l0x_t *dev, uint8_t reg, uint8_t *buf, int count) {
  uint8_t temp[16];

  temp[0] = reg;
  memcpy(&temp[1], buf, count);
  write(dev->i2c_fd, temp, count + 1);
}

/**
 * @brief Write a list of register/value pairs
 */
static void write_reg_list(vl53l0x_t *dev, const uint8_t *list) {
  uint8_t count = *list++;

  while (count--) {
    write(dev->i2c_fd, list, 2);
    list += 2;
  }
}

/**
 * @brief Get SPAD count and type information
 *
 * Reads SPAD (Single Photon Avalanche Diode) calibration data from the sensor.
 * SPADs are the light-detecting elements - the sensor can enable/disable individual
 * SPADs to optimize performance.
 *
 * Register details (from ST API reverse engineering):
 * - 0x83: SPAD readiness/control register
 * - 0x92: SPAD info register (bits [6:0] = count, bit 7 = aperture type)
 * - 0x81, 0xFF: Page/mode select registers
 */
static int get_spad_info(vl53l0x_t *dev, uint8_t *count,
                         uint8_t *type_is_aperture) {
  int timeout = 0;
  uint8_t temp;

  write_reg_list(dev, spad_init0);
  /* Set bit 2 of register 0x83 to request SPAD info */
  write_reg(dev, 0x83, read_reg(dev, 0x83) | 0x04);
  write_reg_list(dev, spad_init1);

  /* Poll register 0x83 until non-zero (SPAD info ready) */
  while (timeout < MAX_TIMEOUT) {
    if (read_reg(dev, 0x83) != 0x00) {
      break;
    }
    timeout++;
    delay_ms(5);
  }

  if (timeout == MAX_TIMEOUT) {
    fprintf(stderr, "Timeout waiting for SPAD info\n");
    return 0;
  }

  /* Acknowledge SPAD info ready */
  write_reg(dev, 0x83, 0x01);

  /*
   * Register 0x92 contains SPAD reference info:
   * - Bits [6:0]: Reference SPAD count (0-127)
   * - Bit 7: SPAD type (0 = non-aperture, 1 = aperture)
   * Aperture SPADs have a metal mask for reduced sensitivity.
   */
  temp = read_reg(dev, 0x92);
  *count = (temp & 0x7F);           /* Extract bits [6:0] */
  *type_is_aperture = (temp & 0x80) ? 1 : 0;  /* Extract bit 7 */

  /* Cleanup: restore register state */
  write_reg(dev, 0x81, 0x00);
  write_reg(dev, 0xFF, 0x06);       /* Select register page 6 */
  /* Clear bit 2 of register 0x83 */
  write_reg(dev, 0x83, read_reg(dev, 0x83) & ~0x04);
  write_reg_list(dev, spad_init2);

  return 1;
}

/**
 * @brief Decode a sequence step timeout from register value
 *
 * The VL53L0X stores timeouts in a compressed format to fit larger values
 * in 16 bits. Format: (LSB << MSB) + 1
 * - Bits [7:0]: LSB (mantissa)
 * - Bits [15:8]: MSB (exponent/shift amount)
 *
 * Reference: ST API vl53l0x_api_core.c, VL53L0X_decode_timeout()
 */
static uint16_t decode_timeout(uint16_t reg_val) {
  /* Extract mantissa (low byte) and exponent (high byte), compute: mantissa << exponent + 1 */
  return (uint16_t)((reg_val & 0x00FF) << (uint16_t)((reg_val & 0xFF00) >> 8)) +
         1;
}

/**
 * @brief Encode a sequence step timeout for register storage
 *
 * Converts a timeout value in MCLKs to the compressed register format.
 * Finds the smallest exponent (ms_byte) such that the mantissa fits in 8 bits.
 *
 * Reference: ST API vl53l0x_api_core.c, VL53L0X_encode_timeout()
 */
static uint16_t encode_timeout(uint16_t timeout_mclks) {
  uint32_t ls_byte = 0;
  uint16_t ms_byte = 0;

  if (timeout_mclks > 0) {
    ls_byte = timeout_mclks - 1;

    /* Shift right until mantissa fits in 8 bits (< 256) */
    while ((ls_byte & 0xFFFFFF00) > 0) {
      ls_byte >>= 1;
      ms_byte++;
    }

    /* Combine: exponent in high byte, mantissa in low byte */
    return (ms_byte << 8) | (ls_byte & 0xFF);
  }

  return 0;
}

/**
 * @brief Convert timeout from MCLKs to microseconds
 */
static uint32_t timeout_mclks_to_us(uint16_t mclks, uint8_t vcsel_pclks) {
  uint32_t macro_period_ns = CALC_MACRO_PERIOD(vcsel_pclks);

  return ((mclks * macro_period_ns) + (macro_period_ns / 2)) / 1000;
}

/**
 * @brief Convert timeout from microseconds to MCLKs
 */
static uint32_t timeout_us_to_mclks(uint32_t us, uint8_t vcsel_pclks) {
  uint32_t macro_period_ns = CALC_MACRO_PERIOD(vcsel_pclks);

  return (((us * 1000) + (macro_period_ns / 2)) / macro_period_ns);
}

/**
 * @brief Get sequence step timeouts
 */
static void get_sequence_step_timeouts(vl53l0x_t *dev, uint8_t enables,
                                       sequence_step_timeouts_t *t) {
  t->pre_range_vcsel_period_pclks =
      ((read_reg(dev, REG_PRE_RANGE_CONFIG_VCSEL_PERIOD) + 1) << 1);

  t->msrc_dss_tcc_mclks = read_reg(dev, REG_MSRC_CONFIG_TIMEOUT_MACROP) + 1;
  t->msrc_dss_tcc_us = timeout_mclks_to_us(t->msrc_dss_tcc_mclks,
                                           t->pre_range_vcsel_period_pclks);

  t->pre_range_mclks =
      decode_timeout(read_reg16(dev, REG_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI));
  t->pre_range_us =
      timeout_mclks_to_us(t->pre_range_mclks, t->pre_range_vcsel_period_pclks);

  t->final_range_vcsel_period_pclks =
      ((read_reg(dev, REG_FINAL_RANGE_CONFIG_VCSEL_PERIOD) + 1) << 1);

  t->final_range_mclks =
      decode_timeout(read_reg16(dev, REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI));

  if (enables & SEQUENCE_ENABLE_PRE_RANGE) {
    t->final_range_mclks -= t->pre_range_mclks;
  }

  t->final_range_us = timeout_mclks_to_us(t->final_range_mclks,
                                          t->final_range_vcsel_period_pclks);
}

/**
 * @brief Set VCSEL pulse period
 *
 * Configures the VCSEL (Vertical Cavity Surface Emitting Laser) pulse period
 * for either pre-range or final range measurements. Longer periods give better
 * performance at longer ranges but slower measurement speed.
 *
 * Valid periods:
 * - Pre-range: 12, 14, 16, 18 PCLKs
 * - Final range: 8, 10, 12, 14 PCLKs
 *
 * The phase valid high/low values are calibration parameters from ST's API
 * that ensure proper signal detection at each pulse period setting.
 *
 * Reference: ST API vl53l0x_api.c, VL53L0X_SetVcselPulsePeriod()
 */
static int set_vcsel_pulse_period(vl53l0x_t *dev, vcsel_period_type_t type,
                                  uint8_t period_pclks) {
  uint8_t vcsel_period_reg = ENCODE_VCSEL_PERIOD(period_pclks);
  uint8_t enables;
  sequence_step_timeouts_t timeouts;
  uint16_t new_timeout_mclks;

  enables = read_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG);
  get_sequence_step_timeouts(dev, enables, &timeouts);

  if (type == VCSEL_PERIOD_PRE_RANGE) {
    /*
     * Pre-range phase valid thresholds.
     * These values are from ST's API and define the acceptable
     * phase window for each VCSEL period setting.
     */
    switch (period_pclks) {
    case 12:
      write_reg(dev, REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH, 0x18);  /* Phase high = 24 */
      break;
    case 14:
      write_reg(dev, REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH, 0x30);  /* Phase high = 48 */
      break;
    case 16:
      write_reg(dev, REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH, 0x40);  /* Phase high = 64 */
      break;
    case 18:
      write_reg(dev, REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH, 0x50);  /* Phase high = 80 */
      break;
    default:
      return 0;
    }

    /* Phase low threshold is always 0x08 for pre-range */
    write_reg(dev, REG_PRE_RANGE_CONFIG_VALID_PHASE_LOW, 0x08);
    write_reg(dev, REG_PRE_RANGE_CONFIG_VCSEL_PERIOD, vcsel_period_reg);

    /* Recalculate and update timeouts for new period */
    new_timeout_mclks =
        timeout_us_to_mclks(timeouts.pre_range_us, period_pclks);
    write_reg16(dev, REG_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI,
                encode_timeout(new_timeout_mclks));

    new_timeout_mclks =
        timeout_us_to_mclks(timeouts.msrc_dss_tcc_us, period_pclks);
    /* MSRC timeout is 8-bit, max value 255 */
    write_reg(dev, REG_MSRC_CONFIG_TIMEOUT_MACROP,
              (new_timeout_mclks > 256) ? 255 : (new_timeout_mclks - 1));

  } else if (type == VCSEL_PERIOD_FINAL_RANGE) {
    /*
     * Final range configuration for each VCSEL period.
     * Each setting requires specific phase thresholds, VCSEL width,
     * and phase calibration parameters from ST's characterization data.
     *
     * Register 0xFF is used for page/bank selection to access
     * additional configuration registers.
     */
    switch (period_pclks) {
    case 8:
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH, 0x10);
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW, 0x08);
      write_reg(dev, REG_GLOBAL_CONFIG_VCSEL_WIDTH, 0x02);
      write_reg(dev, REG_ALGO_PHASECAL_CONFIG_TIMEOUT, 0x0C);
      write_reg(dev, 0xFF, 0x01);  /* Select page 1 */
      write_reg(dev, REG_ALGO_PHASECAL_LIM, 0x30);
      write_reg(dev, 0xFF, 0x00);  /* Select page 0 */
      break;
    case 10:
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH, 0x28);
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW, 0x08);
      write_reg(dev, REG_GLOBAL_CONFIG_VCSEL_WIDTH, 0x03);
      write_reg(dev, REG_ALGO_PHASECAL_CONFIG_TIMEOUT, 0x09);
      write_reg(dev, 0xFF, 0x01);
      write_reg(dev, REG_ALGO_PHASECAL_LIM, 0x20);
      write_reg(dev, 0xFF, 0x00);
      break;
    case 12:
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH, 0x38);
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW, 0x08);
      write_reg(dev, REG_GLOBAL_CONFIG_VCSEL_WIDTH, 0x03);
      write_reg(dev, REG_ALGO_PHASECAL_CONFIG_TIMEOUT, 0x08);
      write_reg(dev, 0xFF, 0x01);
      write_reg(dev, REG_ALGO_PHASECAL_LIM, 0x20);
      write_reg(dev, 0xFF, 0x00);
      break;
    case 14:
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH, 0x48);
      write_reg(dev, REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW, 0x08);
      write_reg(dev, REG_GLOBAL_CONFIG_VCSEL_WIDTH, 0x03);
      write_reg(dev, REG_ALGO_PHASECAL_CONFIG_TIMEOUT, 0x07);
      write_reg(dev, 0xFF, 0x01);
      write_reg(dev, REG_ALGO_PHASECAL_LIM, 0x20);
      write_reg(dev, 0xFF, 0x00);
      break;
    default:
      return 0;
    }

    write_reg(dev, REG_FINAL_RANGE_CONFIG_VCSEL_PERIOD, vcsel_period_reg);

    /* Recalculate final range timeout */
    new_timeout_mclks =
        timeout_us_to_mclks(timeouts.final_range_us, period_pclks);

    if (enables & SEQUENCE_ENABLE_PRE_RANGE) {
      new_timeout_mclks += timeouts.pre_range_mclks;
    }

    write_reg16(dev, REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI,
                encode_timeout(new_timeout_mclks));
  } else {
    return 0;
  }

  /* Update timing budget to account for new period */
  set_measurement_timing_budget(dev, dev->timing_budget);

  /*
   * Perform phase calibration after changing VCSEL period.
   * Sequence config 0x02 enables only MSRC for calibration.
   */
  {
    uint8_t sequence_config = read_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG);
    write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0x02);
    perform_single_ref_calibration(dev, 0x00);
    write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, sequence_config);
  }

  return 1;
}

/**
 * @brief Set the measurement timing budget
 *
 * The timing budget is the total time allowed for one measurement.
 * This function distributes the budget across the enabled sequence steps.
 *
 * Overhead values (in microseconds) are empirically determined by ST
 * and account for internal processing time between steps.
 * Reference: ST API vl53l0x_api.c, VL53L0X_SetMeasurementTimingBudgetMicroSeconds()
 *
 * @param dev Pointer to device handle
 * @param budget_us Total measurement time budget in microseconds
 * @return 1 on success, 0 on failure
 */
static int set_measurement_timing_budget(vl53l0x_t *dev, uint32_t budget_us) {
  uint32_t used_budget_us;
  uint32_t final_range_timeout_us;
  uint16_t final_range_timeout_mclks;
  uint8_t enables;
  sequence_step_timeouts_t timeouts;

  /*
   * Overhead constants from ST's API (vl53l0x_api.c)
   * These represent fixed processing time for each measurement phase.
   * Values determined empirically by ST through characterization.
   */
  const uint16_t start_overhead = 1320;       /* Measurement start overhead (us) */
  const uint16_t end_overhead = 960;          /* Measurement end overhead (us) */
  const uint16_t msrc_overhead = 660;         /* MSRC step overhead (us) */
  const uint16_t tcc_overhead = 590;          /* TCC step overhead (us) */
  const uint16_t dss_overhead = 690;          /* DSS step overhead (us) */
  const uint16_t pre_range_overhead = 660;    /* Pre-range step overhead (us) */
  const uint16_t final_range_overhead = 550;  /* Final range step overhead (us) */

  /* Minimum timing budget - cannot measure faster than 20ms */
  const uint32_t min_timing_budget = 20000;

  if (budget_us < min_timing_budget) {
    return 0;
  }

  used_budget_us = start_overhead + end_overhead;

  enables = read_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG);
  get_sequence_step_timeouts(dev, enables, &timeouts);

  if (enables & SEQUENCE_ENABLE_TCC) {
    used_budget_us += (timeouts.msrc_dss_tcc_us + tcc_overhead);
  }

  if (enables & SEQUENCE_ENABLE_DSS) {
    used_budget_us += 2 * (timeouts.msrc_dss_tcc_us + dss_overhead);
  } else if (enables & SEQUENCE_ENABLE_MSRC) {
    used_budget_us += (timeouts.msrc_dss_tcc_us + msrc_overhead);
  }

  if (enables & SEQUENCE_ENABLE_PRE_RANGE) {
    used_budget_us += (timeouts.pre_range_us + pre_range_overhead);
  }

  if (enables & SEQUENCE_ENABLE_FINAL_RANGE) {
    used_budget_us += final_range_overhead;

    if (used_budget_us > budget_us) {
      return 0;
    }

    final_range_timeout_us = budget_us - used_budget_us;

    final_range_timeout_mclks = timeout_us_to_mclks(
        final_range_timeout_us, timeouts.final_range_vcsel_period_pclks);

    if (enables & SEQUENCE_ENABLE_PRE_RANGE) {
      final_range_timeout_mclks += timeouts.pre_range_mclks;
    }

    write_reg16(dev, REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI,
                encode_timeout(final_range_timeout_mclks));

    dev->timing_budget = budget_us;
  }

  return 1;
}

/**
 * @brief Get the measurement timing budget
 *
 * Calculates the current timing budget by summing the time for all
 * enabled sequence steps plus their associated overhead.
 *
 * Note: start_overhead differs between get (1910us) and set (1320us).
 * This asymmetry is from ST's original API - likely accounts for
 * additional setup time when reading vs writing the budget.
 *
 * Reference: ST API vl53l0x_api.c, VL53L0X_GetMeasurementTimingBudgetMicroSeconds()
 */
static uint32_t get_measurement_timing_budget(vl53l0x_t *dev) {
  uint8_t enables;
  sequence_step_timeouts_t timeouts;
  uint32_t budget_us;

  /*
   * Overhead constants from ST's API
   * Note: start_overhead is 1910us here vs 1320us in set function
   */
  const uint16_t start_overhead = 1910;       /* Measurement start overhead (us) */
  const uint16_t end_overhead = 960;          /* Measurement end overhead (us) */
  const uint16_t msrc_overhead = 660;         /* MSRC step overhead (us) */
  const uint16_t tcc_overhead = 590;          /* TCC step overhead (us) */
  const uint16_t dss_overhead = 690;          /* DSS step overhead (us) */
  const uint16_t pre_range_overhead = 660;    /* Pre-range step overhead (us) */
  const uint16_t final_range_overhead = 550;  /* Final range step overhead (us) */

  budget_us = start_overhead + end_overhead;

  enables = read_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG);
  get_sequence_step_timeouts(dev, enables, &timeouts);

  if (enables & SEQUENCE_ENABLE_TCC) {
    budget_us += (timeouts.msrc_dss_tcc_us + tcc_overhead);
  }

  if (enables & SEQUENCE_ENABLE_DSS) {
    budget_us += 2 * (timeouts.msrc_dss_tcc_us + dss_overhead);
  } else if (enables & SEQUENCE_ENABLE_MSRC) {
    budget_us += (timeouts.msrc_dss_tcc_us + msrc_overhead);
  }

  if (enables & SEQUENCE_ENABLE_PRE_RANGE) {
    budget_us += (timeouts.pre_range_us + pre_range_overhead);
  }

  if (enables & SEQUENCE_ENABLE_FINAL_RANGE) {
    budget_us += (timeouts.final_range_us + final_range_overhead);
  }

  dev->timing_budget = budget_us;

  return budget_us;
}

/**
 * @brief Perform single reference calibration
 *
 * Performs VHV (Voltage High Voltage) or phase calibration.
 * This is required during initialization to calibrate internal references.
 *
 * @param dev Pointer to device handle
 * @param vhv_init Calibration type:
 *        - 0x40: VHV calibration (voltage reference)
 *        - 0x00: Phase calibration
 *
 * Reference: ST API vl53l0x_api.c, VL53L0X_perform_single_ref_calibration()
 */
static int perform_single_ref_calibration(vl53l0x_t *dev, uint8_t vhv_init) {
  int timeout = 0;

  /*
   * Start measurement with calibration mode:
   * - Bit 0 (0x01): Start measurement
   * - Bit 6 (0x40): VHV calibration mode (if set)
   */
  write_reg(dev, REG_SYSRANGE_START, 0x01 | vhv_init);

  /* Wait for measurement complete - bits [2:0] indicate interrupt status */
  while ((read_reg(dev, REG_RESULT_INTERRUPT_STATUS) & 0x07) == 0) {
    timeout++;
    delay_ms(5);
    if (timeout > MAX_TIMEOUT) {
      return 0;
    }
  }

  /* Clear interrupt and stop measurement */
  write_reg(dev, REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
  write_reg(dev, REG_SYSRANGE_START, 0x00);

  return 1;
}

/**
 * @brief Initialize the sensor
 *
 * Performs full sensor initialization including:
 * - I2C communication setup
 * - SPAD reference calibration
 * - Default tuning parameter loading
 * - Optional long-range mode configuration
 * - VHV and phase reference calibration
 *
 * Reference: ST API vl53l0x_api.c, VL53L0X_DataInit() + VL53L0X_StaticInit()
 */
static int init_sensor(vl53l0x_t *dev, int long_range) {
  uint8_t spad_count = 0;
  uint8_t spad_type_is_aperture = 0;
  uint8_t ref_spad_map[6];
  uint8_t first_spad;
  uint8_t spads_enabled;
  int i;

  /*
   * Enable 2.8V I/O mode by setting bit 0 of VHV config register.
   * Required for proper operation when VDD is 2.8V (vs 1.8V).
   */
  write_reg(dev, REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV,
            read_reg(dev, REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV) | 0x01);

  /* Set I2C standard mode */
  write_reg_list(dev, i2c_mode1);
  /*
   * Register 0x91 contains the "stop variable" - a calibration value
   * needed for single-shot measurements. Must be saved during init.
   */
  dev->stop_variable = read_reg(dev, 0x91);

  write_reg_list(dev, i2c_mode2);

  /* Ensure sensor is in a known state (stop any active measurement) */
  write_reg(dev, REG_SYSRANGE_START, 0x00);

  /*
   * Disable SIGNAL_RATE_MSRC and SIGNAL_RATE_PRE_RANGE limit checks.
   * Bits [4:1] = 0x12 disables these checks for more permissive ranging.
   */
  write_reg(dev, REG_MSRC_CONFIG_CONTROL,
            read_reg(dev, REG_MSRC_CONFIG_CONTROL) | 0x12);

  /*
   * Set minimum signal rate return limit to 0.25 MCPS (mega counts per second).
   * Register uses Q9.7 fixed-point format: 0.25 * 128 = 32
   * This is the minimum signal strength required for a valid reading.
   */
  write_reg16(dev, REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE, 32);

  /* Enable all sequence steps: TCC, DSS, MSRC, Pre-range, Final range */
  write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0xFF);

  if (!get_spad_info(dev, &spad_count, &spad_type_is_aperture)) {
    return 0;
  }

  /* Read current SPAD enables (6 bytes = 48 SPADs) */
  read_multi(dev, REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, ref_spad_map, 6);
  write_reg_list(dev, spad_config);

  /*
   * Configure SPAD enables based on calibration data.
   * Aperture SPADs start at index 12, non-aperture at index 0.
   */
  first_spad = spad_type_is_aperture ? 12 : 0;
  spads_enabled = 0;

  /* Enable only the required number of SPADs of the correct type */
  for (i = 0; i < 48; i++) {
    if (i < first_spad || spads_enabled == spad_count) {
      /* Disable SPAD: clear bit i in the 6-byte map */
      ref_spad_map[i >> 3] &= ~(1 << (i & 7));
    } else if (ref_spad_map[i >> 3] & (1 << (i & 7))) {
      spads_enabled++;
    }
  }

  write_multi(dev, REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, ref_spad_map, 6);

  /* Load default tuning settings (80 register writes) */
  write_reg_list(dev, default_tuning);

  /*
   * Configure for long range mode if requested.
   * Long range: 30-2000mm at reduced accuracy
   * Default: 30-800mm at higher accuracy
   */
  if (long_range) {
    /*
     * Lower the minimum count rate to 0.1 MCPS for long range.
     * Q9.7 format: 0.1 * 128 ≈ 13
     */
    write_reg16(dev, REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE, 13);
    /*
     * Increase VCSEL pulse periods for longer range.
     * Longer pulses = more photons = better detection at distance.
     * Pre-range: 18 PCLKs (vs default 14)
     * Final range: 14 PCLKs (vs default 10)
     */
    set_vcsel_pulse_period(dev, VCSEL_PERIOD_PRE_RANGE, 18);
    set_vcsel_pulse_period(dev, VCSEL_PERIOD_FINAL_RANGE, 14);
  }

  /*
   * Configure GPIO interrupt for "new sample ready"
   * 0x04 = interrupt on new sample ready
   */
  write_reg(dev, REG_SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04);
  /*
   * Set interrupt polarity to active low (clear bit 4)
   * This is typical for open-drain interrupt outputs
   */
  write_reg(dev, REG_GPIO_HV_MUX_ACTIVE_HIGH,
            read_reg(dev, REG_GPIO_HV_MUX_ACTIVE_HIGH) & ~0x10);
  /* Clear any pending interrupts */
  write_reg(dev, REG_SYSTEM_INTERRUPT_CLEAR, 0x01);

  dev->timing_budget = get_measurement_timing_budget(dev);

  /*
   * Set sequence config to 0xE8:
   * - Final range enabled (0x80)
   * - Pre-range enabled (0x40)
   * - DSS enabled (0x20)
   * - MSRC disabled (0x08 = 0)
   * This is the default ranging sequence.
   */
  write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0xE8);
  set_measurement_timing_budget(dev, dev->timing_budget);

  /*
   * Perform reference calibration:
   * 1. VHV calibration (0x40) - calibrates voltage references
   * 2. Phase calibration (0x00) - calibrates timing/phase
   */
  write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0x01);  /* Enable TCC only */
  if (!perform_single_ref_calibration(dev, 0x40)) {
    return 0;
  }

  write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0x02);  /* Enable MSRC only */
  if (!perform_single_ref_calibration(dev, 0x00)) {
    return 0;
  }

  /* Restore default sequence config */
  write_reg(dev, REG_SYSTEM_SEQUENCE_CONFIG, 0xE8);

  return 1;
}

/**
 * @brief Read range in continuous mode
 *
 * Waits for a measurement to complete and reads the distance.
 * The range value is stored at REG_RESULT_RANGE_STATUS + 10 (offset 0x14 + 10 = 0x1E).
 *
 * @param dev Pointer to device handle
 * @return Range in millimeters, or 0xFFFF on timeout
 */
static uint16_t read_range_continuous_mm(vl53l0x_t *dev) {
  int timeout = 0;
  uint16_t range;

  /*
   * Wait for measurement ready.
   * Bits [2:0] of interrupt status indicate:
   * - 0: No interrupt
   * - 1: Level low (not used)
   * - 2: Level high (not used)
   * - 3: Out of window (not used)
   * - 4: New sample ready
   * We check if any of bits [2:0] are set (interrupt triggered).
   */
  while ((read_reg(dev, REG_RESULT_INTERRUPT_STATUS) & 0x07) == 0) {
    timeout++;
    delay_ms(5);
    if (timeout > MAX_TIMEOUT) {
      return 0xFFFF;
    }
  }

  /*
   * Read 16-bit range value from result register.
   * The range is at offset +10 from REG_RESULT_RANGE_STATUS (0x14).
   * This gives register 0x1E (RESULT_RANGE_VALUE).
   */
  range = read_reg16(dev, REG_RESULT_RANGE_STATUS + 10);

  /* Clear interrupt to allow next measurement */
  write_reg(dev, REG_SYSTEM_INTERRUPT_CLEAR, 0x01);

  return range;
}

/*
 * Public API implementation
 */

vl53l0x_error_t vl53l0x_init(vl53l0x_t *dev, int i2c_bus, uint8_t address,
                             vl53l0x_mode_t mode) {
  char filename[32];

  if (dev == NULL) {
    return VL53L0X_ERROR_INIT;
  }

  dev->i2c_address = address;
  dev->i2c_fd = -1;
  dev->stop_variable = 0;
  dev->timing_budget = 0;
  dev->last_measurement_mm = 0;
  dev->last_measurement_time.tv_sec = 0;
  dev->last_measurement_time.tv_nsec = 0;
  dev->has_valid_measurement = 0;

  snprintf(filename, sizeof(filename), "/dev/i2c-%d", i2c_bus);

  dev->i2c_fd = open(filename, O_RDWR);
  if (dev->i2c_fd < 0) {
    fprintf(stderr, "Failed to open I2C bus %s\n", filename);
    return VL53L0X_ERROR_I2C_OPEN;
  }

  if (ioctl(dev->i2c_fd, I2C_SLAVE, address) < 0) {
    fprintf(stderr, "Failed to acquire I2C bus access\n");
    close(dev->i2c_fd);
    dev->i2c_fd = -1;
    return VL53L0X_ERROR_I2C_ACCESS;
  }

  if (!init_sensor(dev, mode == VL53L0X_MODE_LONG_RANGE)) {
    close(dev->i2c_fd);
    dev->i2c_fd = -1;
    return VL53L0X_ERROR_INIT;
  }

  return VL53L0X_OK;
}

vl53l0x_error_t vl53l0x_read_single(vl53l0x_t *dev, uint16_t *distance_mm) {
  int timeout;

  if (dev == NULL || dev->i2c_fd < 0 || distance_mm == NULL) {
    return VL53L0X_ERROR_INIT;
  }

  /*
   * Single shot measurement initialization sequence.
   * This sequence is from ST's API VL53L0X_PerformSingleRangingMeasurement().
   *
   * Registers 0x80, 0xFF, 0x00 are undocumented mode/page select registers.
   * The stop_variable (from register 0x91) is a calibration value that
   * must be written before each measurement for accurate results.
   */
  write_reg(dev, 0x80, 0x01);           /* Enter config mode */
  write_reg(dev, 0xFF, 0x01);           /* Select register page 1 */
  write_reg(dev, 0x00, 0x00);           /* Clear some state */
  write_reg(dev, 0x91, dev->stop_variable);  /* Write calibration value */
  write_reg(dev, 0x00, 0x01);           /* Set measurement flag */
  write_reg(dev, 0xFF, 0x00);           /* Select register page 0 */
  write_reg(dev, 0x80, 0x00);           /* Exit config mode */

  /*
   * Start single-shot ranging measurement.
   * Bit 0 (0x01) = start measurement
   * Bits [3:1] = mode (0 = single shot)
   */
  write_reg(dev, REG_SYSRANGE_START, 0x01);

  /* Wait for start bit to clear (measurement in progress) */
  timeout = 0;
  while (read_reg(dev, REG_SYSRANGE_START) & 0x01) {
    timeout++;
    delay_ms(5);
    if (timeout > MAX_TIMEOUT) {
      return VL53L0X_ERROR_TIMEOUT;
    }
  }

  *distance_mm = read_range_continuous_mm(dev);

  if (*distance_mm == 0xFFFF) {
    return VL53L0X_ERROR_TIMEOUT;
  }

  /* Store last measurement with timestamp */
  dev->last_measurement_mm = *distance_mm;
  clock_gettime(CLOCK_REALTIME, &dev->last_measurement_time);
  dev->has_valid_measurement = 1;

  return VL53L0X_OK;
}

vl53l0x_error_t vl53l0x_get_model(vl53l0x_t *dev, uint8_t *model,
                                  uint8_t *revision) {
  if (dev == NULL || dev->i2c_fd < 0) {
    return VL53L0X_ERROR_INIT;
  }

  if (model != NULL) {
    *model = read_reg(dev, REG_IDENTIFICATION_MODEL_ID);
  }

  if (revision != NULL) {
    *revision = read_reg(dev, REG_IDENTIFICATION_REVISION_ID);
  }

  return VL53L0X_OK;
}

void vl53l0x_close(vl53l0x_t *dev) {
  if (dev != NULL && dev->i2c_fd >= 0) {
    close(dev->i2c_fd);
    dev->i2c_fd = -1;
  }
}

vl53l0x_error_t vl53l0x_start_continuous(vl53l0x_t *dev) {
  if (dev == NULL || dev->i2c_fd < 0) {
    return VL53L0X_ERROR_INIT;
  }

  /*
   * Continuous measurement initialization sequence.
   * Same setup as single-shot but with different start mode.
   */
  write_reg(dev, 0x80, 0x01);           /* Enter config mode */
  write_reg(dev, 0xFF, 0x01);           /* Select register page 1 */
  write_reg(dev, 0x00, 0x00);           /* Clear some state */
  write_reg(dev, 0x91, dev->stop_variable);  /* Write calibration value */
  write_reg(dev, 0x00, 0x01);           /* Set measurement flag */
  write_reg(dev, 0xFF, 0x00);           /* Select register page 0 */
  write_reg(dev, 0x80, 0x00);           /* Exit config mode */

  /*
   * Start continuous back-to-back measurement.
   * 0x02 = continuous ranging mode (vs 0x01 for single-shot)
   * Sensor will take measurements as fast as timing budget allows.
   */
  write_reg(dev, REG_SYSRANGE_START, 0x02);

  return VL53L0X_OK;
}

vl53l0x_error_t vl53l0x_stop_continuous(vl53l0x_t *dev) {
  if (dev == NULL || dev->i2c_fd < 0) {
    return VL53L0X_ERROR_INIT;
  }

  /*
   * Stop continuous measurement.
   * Writing 0x01 with continuous mode active stops the measurement.
   */
  write_reg(dev, REG_SYSRANGE_START, 0x01);

  /*
   * Restore idle state sequence.
   * This ensures the sensor is properly reset for next measurement.
   */
  write_reg(dev, 0xFF, 0x01);           /* Select register page 1 */
  write_reg(dev, 0x00, 0x00);           /* Clear state */
  write_reg(dev, 0x91, dev->stop_variable);  /* Re-apply calibration */
  write_reg(dev, 0x00, 0x01);           /* Set flag */
  write_reg(dev, 0xFF, 0x00);           /* Select register page 0 */

  return VL53L0X_OK;
}

vl53l0x_error_t vl53l0x_read_continuous(vl53l0x_t *dev, uint16_t *distance_mm) {
  if (dev == NULL || dev->i2c_fd < 0 || distance_mm == NULL) {
    return VL53L0X_ERROR_INIT;
  }

  /*
   * Check if new measurement is ready (non-blocking).
   * Bits [2:0] of interrupt status indicate measurement complete.
   */
  if ((read_reg(dev, REG_RESULT_INTERRUPT_STATUS) & 0x07) == 0) {
    return VL53L0X_ERROR_NOT_READY;
  }

  /* Read measurement from result register (offset +10 from status register) */
  *distance_mm = read_reg16(dev, REG_RESULT_RANGE_STATUS + 10);

  /* Clear interrupt to allow next measurement */
  write_reg(dev, REG_SYSTEM_INTERRUPT_CLEAR, 0x01);

  if (*distance_mm == 0xFFFF) {
    return VL53L0X_ERROR_RANGE;
  }

  /* Store last measurement with timestamp */
  dev->last_measurement_mm = *distance_mm;
  clock_gettime(CLOCK_REALTIME, &dev->last_measurement_time);
  dev->has_valid_measurement = 1;

  return VL53L0X_OK;
}

vl53l0x_error_t vl53l0x_get_last_measurement(vl53l0x_t *dev,
                                             uint16_t *distance_mm,
                                             struct timespec *timestamp) {
  if (dev == NULL || dev->i2c_fd < 0 || distance_mm == NULL) {
    return VL53L0X_ERROR_INIT;
  }

  /* If no valid measurement exists, perform a blocking single measurement */
  if (!dev->has_valid_measurement) {
    vl53l0x_error_t err = vl53l0x_read_single(dev, distance_mm);
    if (err != VL53L0X_OK) {
      return err;
    }
  }

  /* Return the last measurement and timestamp */
  *distance_mm = dev->last_measurement_mm;
  if (timestamp != NULL) {
    *timestamp = dev->last_measurement_time;
  }

  return VL53L0X_OK;
}
