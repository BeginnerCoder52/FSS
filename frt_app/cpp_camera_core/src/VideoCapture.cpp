/**
 * VideoCapture.cpp - USB Camera V4L2 Capture Implementation
 * Version: 1.0
 * SDD v1.1.0 Compliance
 */

#include "VideoCapture.hpp"
#include <iostream>
#include <ctime>
#include <sstream>

/**
 * Constructor
 */
VideoCapture::VideoCapture(
    const std::string& device_path,
    int width,
    int height,
    int fps)
    : device_path_(device_path),
      frame_width_(width),
      frame_height_(height),
      target_fps_(fps),
      is_open_(false),
      consecutive_read_failures_(0),
      capture_(nullptr) {
    
    log_info("VideoCapture initialized (device=" + device_path +
             ", " + std::to_string(width) + "x" + std::to_string(height) +
             " @ " + std::to_string(fps) + " FPS)");
}

/**
 * Destructor
 */
VideoCapture::~VideoCapture() {
    close();
}

/**
 * Open camera stream via V4L2
 */
bool VideoCapture::open() {
    log_info("Opening camera stream from " + device_path_);
    
    try {
        // Create VideoCapture with V4L2 backend
        capture_ = std::make_unique<cv::VideoCapture>(device_path_, cv::CAP_V4L2);
        
        if (!capture_ || !capture_->isOpened()) {
            last_error_ = "Failed to open camera device: " + device_path_;
            log_error(last_error_);
            is_open_ = false;
            return false;
        }
        
        // Configure capture parameters
        capture_->set(cv::CAP_PROP_FRAME_WIDTH, frame_width_);
        capture_->set(cv::CAP_PROP_FRAME_HEIGHT, frame_height_);
        capture_->set(cv::CAP_PROP_FPS, target_fps_);
        
        // Verify configuration
        int actual_width = static_cast<int>(capture_->get(cv::CAP_PROP_FRAME_WIDTH));
        int actual_height = static_cast<int>(capture_->get(cv::CAP_PROP_FRAME_HEIGHT));
        
        if (actual_width != frame_width_ || actual_height != frame_height_) {
            std::stringstream ss;
            ss << "Camera resolution mismatch: requested " << frame_width_ << "x"
               << frame_height_ << ", got " << actual_width << "x" << actual_height;
            log_error(ss.str());
            // Continue anyway, camera may have different available modes
        }
        
        is_open_ = true;
        consecutive_read_failures_ = 0;
        
        log_info("Camera stream opened successfully (" +
                std::to_string(actual_width) + "x" + std::to_string(actual_height) + ")");
        
        return true;
        
    } catch (const std::exception& e) {
        last_error_ = std::string("Exception opening camera: ") + e.what();
        log_error(last_error_);
        is_open_ = false;
        capture_ = nullptr;
        return false;
    }
}

/**
 * Close camera stream
 */
void VideoCapture::close() {
    log_info("Closing camera stream");
    
    try {
        if (capture_) {
            capture_->release();
            capture_ = nullptr;
        }
        
        is_open_ = false;
        consecutive_read_failures_ = 0;
        log_info("Camera released");
        
    } catch (const std::exception& e) {
        log_error(std::string("Exception closing camera: ") + e.what());
    }
}

/**
 * Capture frame from camera
 */
cv::Mat VideoCapture::read_frame() {
    if (!is_open_ || !capture_) {
        last_error_ = "Camera not open";
        consecutive_read_failures_++;
        
        if (consecutive_read_failures_ >= MAX_CONSECUTIVE_FAILURES) {
            log_error("Max consecutive read failures reached");
            return cv::Mat();  // Return empty Mat
        }
        
        return cv::Mat();
    }
    
    try {
        cv::Mat frame;
        bool ret = capture_->read(frame);
        
        if (!ret || frame.empty()) {
            consecutive_read_failures_++;
            
            if (consecutive_read_failures_ % 10 == 0) {  // Log every 10th failure
                log_error("Frame read failed (attempts: " +
                         std::to_string(consecutive_read_failures_) + ")");
            }
            
            if (consecutive_read_failures_ >= MAX_CONSECUTIVE_FAILURES) {
                last_error_ = "Too many consecutive read failures";
                log_error(last_error_);
            }
            
            return cv::Mat();
        }
        
        // Success: reset failure counter
        consecutive_read_failures_ = 0;
        return frame;
        
    } catch (const std::exception& e) {
        last_error_ = std::string("Exception reading frame: ") + e.what();
        log_error(last_error_);
        consecutive_read_failures_++;
        return cv::Mat();
    }
}

/**
 * Reset camera connection
 */
bool VideoCapture::reset() {
    log_error("USB bus reset requested");
    
    try {
        // Close current connection
        close();
        
        // Wait for device to settle
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        
        // Attempt to reopen
        if (open()) {
            log_info("Camera reset successful");
            return true;
        } else {
            log_error("Camera reset failed - could not reopen device");
            return false;
        }
        
    } catch (const std::exception& e) {
        last_error_ = std::string("Exception during reset: ") + e.what();
        log_error(last_error_);
        return false;
    }
}

/**
 * Private helper: Log error
 */
void VideoCapture::log_error(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cerr << "[" << oss.str() << "] ERROR [VideoCapture]: " << message << std::endl;
}

/**
 * Private helper: Log info
 */
void VideoCapture::log_info(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cout << "[" << oss.str() << "] INFO [VideoCapture]: " << message << std::endl;
}
