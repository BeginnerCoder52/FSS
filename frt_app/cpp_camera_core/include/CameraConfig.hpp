/**
 * CameraConfig.hpp - Camera and Shared Memory Configuration Constants
 * Version: 1.0
 * SDD v1.1.0 Compliance
 */

#ifndef CAMERACONFIG_HPP
#define CAMERACONFIG_HPP

/**
 * Camera Configuration Constants
 * 
 * Defines default parameters for USB camera capture
 * and shared memory configuration.
 */
namespace CameraConfig {

// V4L2 Device Configuration
constexpr const char* DEVICE_PATH = "/dev/video0";
constexpr int DEFAULT_WIDTH = 640;
constexpr int DEFAULT_HEIGHT = 480;
constexpr int DEFAULT_FPS = 30;

// Pixel Format
constexpr int PIXEL_FORMAT = 0;  // 0 = BGR, 1 = RGB, 2 = YUYV/MJPEG

// Shared Memory Configuration
constexpr const char* SHM_NAME = "/fss_video_frame";
constexpr size_t SHM_SIZE = 2 * 1024 * 1024;  // 2 MB for JPEG frames
constexpr int JPEG_QUALITY = 85;  // 0-100 quality setting

// Frame Processing
constexpr int MAX_CONSECUTIVE_FAILURES = 5;
constexpr int CAMERA_RESET_DELAY_MS = 100;

}  // namespace CameraConfig

#endif  // CAMERACONFIG_HPP