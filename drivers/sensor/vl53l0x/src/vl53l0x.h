/**
 * @file vl53l0x.h
 * @brief VL53L0X Time-of-Flight Sensor Driver Interface
 *
 * This header provides the public API for the VL53L0X ToF distance sensor
 * driver. The driver communicates with the sensor via I2C and supports
 * single shot distance measurements.
 */

#ifndef VL53L0X_H_
#define VL53L0X_H_

#include <stdint.h>
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Default I2C address of the VL53L0X sensor
 */
#define VL53L0X_DEFAULT_ADDRESS 0x29

/**
 * @brief Error codes returned by VL53L0X functions
 */
typedef enum {
  VL53L0X_OK = 0,           /**< Operation completed successfully */
  VL53L0X_ERROR_I2C_OPEN,   /**< Failed to open I2C device */
  VL53L0X_ERROR_I2C_ACCESS, /**< Failed to access I2C slave */
  VL53L0X_ERROR_INIT,       /**< Sensor initialization failed */
  VL53L0X_ERROR_TIMEOUT,    /**< Operation timed out */
  VL53L0X_ERROR_RANGE,      /**< Measurement out of valid range */
  VL53L0X_ERROR_NOT_READY   /**< Measurement not ready (for non-blocking) */
} vl53l0x_error_t;

/**
 * @brief Sensor measurement mode
 */
typedef enum {
  VL53L0X_MODE_DEFAULT,   /**< Default mode: 30-800mm range */
  VL53L0X_MODE_LONG_RANGE /**< Long range mode: 30-2000mm range */
} vl53l0x_mode_t;

/**
 * @brief VL53L0X device handle structure
 */
typedef struct {
  int i2c_fd;                      /**< I2C file descriptor */
  uint8_t i2c_address;             /**< I2C device address */
  uint8_t stop_variable;           /**< Calibration stop variable */
  uint32_t timing_budget;          /**< Measurement timing budget in us */
  uint16_t last_measurement_mm;    /**< Last measurement value in mm */
  struct timespec last_measurement_time; /**< Timestamp of last measurement */
  uint8_t has_valid_measurement;   /**< Flag indicating valid measurement */
} vl53l0x_t;

/**
 * @brief Initialize the VL53L0X sensor
 *
 * Opens the I2C bus, configures the sensor with the specified mode,
 * and performs calibration. Must be called before reading distance.
 *
 * @param dev Pointer to device handle structure
 * @param i2c_bus I2C bus number (e.g., 1 for /dev/i2c-1 on Raspberry Pi)
 * @param address I2C address of the sensor (usually VL53L0X_DEFAULT_ADDRESS)
 * @param mode Operating mode (VL53L0X_MODE_DEFAULT or VL53L0X_MODE_LONG_RANGE)
 *
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_init(vl53l0x_t *dev, int i2c_bus, uint8_t address,
                             vl53l0x_mode_t mode);

/**
 * @brief Perform a single distance measurement
 *
 * Triggers a single shot measurement and waits for the result.
 * This is a blocking operation that waits for measurement completion.
 *
 * @param dev Pointer to initialized device handle
 * @param distance_mm Pointer to store the measured distance in millimeters
 *
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_read_single(vl53l0x_t *dev, uint16_t *distance_mm);

/**
 * @brief Get sensor model and revision information
 *
 * @param dev Pointer to initialized device handle
 * @param model Pointer to store model ID (can be NULL)
 * @param revision Pointer to store revision ID (can be NULL)
 *
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_get_model(vl53l0x_t *dev, uint8_t *model,
                                  uint8_t *revision);

/**
 * @brief Close the VL53L0X device and release resources
 *
 * @param dev Pointer to device handle
 */
void vl53l0x_close(vl53l0x_t *dev);

/**
 * @brief Start continuous measurement mode
 *
 * Configures the sensor to take measurements continuously (back-to-back).
 * Must be called before vl53l0x_read_continuous().
 *
 * @param dev Pointer to initialized device handle
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_start_continuous(vl53l0x_t *dev);

/**
 * @brief Stop continuous measurement mode
 *
 * Stops the continuous measurement mode and returns the sensor to idle.
 *
 * @param dev Pointer to initialized device handle
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_stop_continuous(vl53l0x_t *dev);

/**
 * @brief Read a measurement in continuous mode (non-blocking)
 *
 * Checks if a new measurement is ready. If so, reads it and returns VL53L0X_OK.
 * If not ready, returns VL53L0X_ERROR_NOT_READY immediately.
 *
 * @param dev Pointer to initialized device handle
 * @param distance_mm Pointer to store the measured distance
 * @return VL53L0X_OK if data read, VL53L0X_ERROR_NOT_READY if no data, or other
 * error
 */
vl53l0x_error_t vl53l0x_read_continuous(vl53l0x_t *dev, uint16_t *distance_mm);

/**
 * @brief Get the last measurement result with timestamp
 *
 * Retrieves the most recent measurement value and timestamp.
 * If no valid measurement has been taken since initialization,
 * performs a blocking single measurement first.
 *
 * @param dev Pointer to initialized device handle
 * @param distance_mm Pointer to store the last measured distance in mm
 * @param timestamp Pointer to store the timestamp of the measurement (can be NULL)
 * @return VL53L0X_OK on success, or an error code on failure
 */
vl53l0x_error_t vl53l0x_get_last_measurement(vl53l0x_t *dev,
                                             uint16_t *distance_mm,
                                             struct timespec *timestamp);

#ifdef __cplusplus
}
#endif

#endif /* VL53L0X_H_ */
