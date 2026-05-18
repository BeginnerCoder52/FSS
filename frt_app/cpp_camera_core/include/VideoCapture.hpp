/**
 * VideoCapture.hpp - USB Camera V4L2 Capture Driver
 * Version: 1.0
 * SDD v1.1.0 Compliance
 *
 * Purpose:
 *     C++ wrapper for USB camera video capture via OpenCV V4L2 backend.
 *     Handles frame capture, buffering, and device management for
 *     Raspberry Pi 4B with Generic HD USB camera.
 *
 * Device Configuration:
 *     - Device Path: /dev/video0 (USB camera)
 *     - Backend: OpenCV cv::CAP_V4L2
 *     - Resolution: 640x480 (configurable)
 *     - FPS: 30 (target frame rate)
 *     - Format: BGR (OpenCV standard)
 *
 * Integration:
 *     - Input: Video stream from USB camera
 *     - Output: JPEG-encoded frames to shared memory
 *     - Used by: FRTApp Python process via SHM
 *
 * Author: FSS Project Team
 * License: Proprietary
 */

#ifndef VIDEOCAPTURE_HPP
#define VIDEOCAPTURE_HPP

#include <string>
#include <memory>
#include <thread>
#include <chrono>
#include <opencv2/opencv.hpp>
#include <opencv2/videoio.hpp>

/**
 * VideoCapture - USB Camera Stream Handler
 *
 * Responsibilities:
 *     - Open/close USB camera device
 *     - Capture frames at target FPS
 *     - Handle device errors and reconnection
 *     - Provide frame data to SHM writer
 *
 * Error Handling:
 *     - Device not found: Return false
 *     - Frame capture timeout: Log warning, retry
 *     - USB disconnection: Trigger reset/reconnection
 */
class VideoCapture {
public:
    // Configuration Constants
    static constexpr const char* DEFAULT_DEVICE = "/dev/video0";
    static constexpr int DEFAULT_WIDTH = 640;
    static constexpr int DEFAULT_HEIGHT = 480;
    static constexpr int DEFAULT_FPS = 30;
    
    /**
     * Constructor
     *
     * Arguments:
     *     device_path: Path to video device (e.g., /dev/video0)
     *     width: Capture width in pixels
     *     height: Capture height in pixels
     *     fps: Target frames per second
     */
    VideoCapture(
        const std::string& device_path = DEFAULT_DEVICE,
        int width = DEFAULT_WIDTH,
        int height = DEFAULT_HEIGHT,
        int fps = DEFAULT_FPS
    );
    
    /**
     * Destructor
     *     Automatically closes camera if open
     */
    ~VideoCapture();
    
    /**
     * Open camera stream via V4L2
     *
     * Purpose:
     *     Initialize USB camera device and configure capture parameters.
     *
     * Process:
     *     1. Create cv::VideoCapture with V4L2 backend
     *     2. Set resolution, FPS, and format
     *     3. Verify stream is readable
     *
     * Returns:
     *     true: Camera opened successfully
     *     false: Failed to open device
     *
     * Error Handling:
     *     - Device file missing: Log error, return false
     *     - Permission denied: Log critical, return false
     *     - Device in use: Log warning, return false
     */
    bool open();
    
    /**
     * Close camera stream
     *
     * Purpose:
     *     Release camera resources and free device.
     *
     * Returns:
     *     void
     */
    void close();
    
    /**
     * Capture frame from camera
     *
     * Purpose:
     *     Read one frame from camera stream and return as OpenCV Mat.
     *
     * Returns:
     *     cv::Mat: BGR frame (height x width x 3), CV_8UC3 type
     *     Empty Mat: If capture failed
     *
     * Error Handling:
     *     - Camera not open: Log warning, return empty Mat
     *     - Frame read timeout: Log error, trigger recovery
     */
    cv::Mat read_frame();
    
    /**
     * Check if camera is open and streaming
     *
     * Returns:
     *     true: Camera is open and ready
     *     false: Camera not open or error state
     */
    bool is_open() const { return is_open_; }
    
    /**
     * Get frame dimensions
     *
     * Returns:
     *     Pair of (width, height)
     */
    std::pair<int, int> get_frame_size() const {
        return {frame_width_, frame_height_};
    }
    
    /**
     * Reset camera connection
     *
     * Purpose:
     *     Attempt to recover from stuck/disconnected camera.
     *
     * Process:
     *     1. Close current connection
     *     2. Wait 100ms
     *     3. Reopen connection
     *
     * Returns:
     *     true: Reset successful
     *     false: Reset failed
     */
    bool reset();
    
    /**
     * Get error status string
     *
     * Returns:
     *     String describing last error (empty if no error)
     */
    const std::string& get_last_error() const { return last_error_; }

private:
    // Member Variables
    std::string device_path_;
    int frame_width_;
    int frame_height_;
    int target_fps_;
    bool is_open_;
    std::string last_error_;
    
    // Error tracking (initialized before OpenCV capture object)
    int consecutive_read_failures_;
    static constexpr int MAX_CONSECUTIVE_FAILURES = 5;
    
    // OpenCV capture object
    std::unique_ptr<cv::VideoCapture> capture_;
    
    // Private helper methods
    /**
     * Log error message with timestamp
     */
    void log_error(const std::string& message);
    
    /**
     * Log info message with timestamp
     */
    void log_info(const std::string& message);
};

#endif // VIDEOCAPTURE_HPP
