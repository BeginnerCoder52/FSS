/**
 * ShmWriter.cpp - POSIX Shared Memory Frame Publisher Implementation
 * Version: 1.0
 * SDD v1.1.0 Compliance
 */

#include "ShmWriter.hpp"
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <iostream>
#include <ctime>
#include <sstream>

/**
 * Constructor
 */
ShmWriter::ShmWriter(
    const std::string& shm_name,
    size_t shm_size)
    : shm_name_(shm_name),
      shm_size_(shm_size),
      is_attached_(false),
      shm_fd_(-1),
      shm_buffer_(nullptr),
      frame_id_(0),
      current_write_offset_(0) {
    
    log_info("ShmWriter initialized (name=" + shm_name_ + ", size=" + std::to_string(shm_size_) + " bytes)");
}

/**
 * Destructor
 */
ShmWriter::~ShmWriter() {
    close();
}

/**
 * Create and attach to shared memory region
 */
bool ShmWriter::create() {
    log_info("Creating shared memory region: " + shm_name_);
    
    try {
        // Create shared memory object
        shm_fd_ = shm_open(shm_name_.c_str(), O_CREAT | O_RDWR, 0666);
        if (shm_fd_ == -1) {
            last_error_ = "Failed to create shared memory: " + shm_name_;
            log_error(last_error_);
            return false;
        }
        
        // Set size
        if (ftruncate(shm_fd_, shm_size_) == -1) {
            last_error_ = "Failed to set shared memory size";
            log_error(last_error_);
            close();
            return false;
        }
        
        // Map memory
        shm_buffer_ = static_cast<uint8_t*>(
            mmap(nullptr, shm_size_, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0)
        );
        if (shm_buffer_ == MAP_FAILED) {
            last_error_ = "Failed to map shared memory";
            log_error(last_error_);
            close();
            return false;
        }
        
        // Initialize memory with zeros
        memset(shm_buffer_, 0, shm_size_);
        
        is_attached_ = true;
        log_info("Shared memory created successfully (" + std::to_string(shm_size_) + " bytes)");
        return true;
        
    } catch (const std::exception& e) {
        last_error_ = std::string("Exception creating SHM: ") + e.what();
        log_error(last_error_);
        close();
        return false;
    }
}

/**
 * Write frame to shared memory
 */
bool ShmWriter::write_frame(const cv::Mat& frame) {
    if (!is_attached_) {
        last_error_ = "Shared memory not initialized";
        log_error(last_error_);
        return false;
    }
    
    try {
        // Validate frame
        if (frame.empty()) {
            last_error_ = "Empty frame provided";
            log_warning(last_error_);
            return false;
        }
        
        // Encode to JPEG
        std::vector<uint8_t> jpeg_data = encode_to_jpeg(frame, JPEG_QUALITY);
        if (jpeg_data.empty()) {
            last_error_ = "JPEG encoding failed";
            log_warning(last_error_);
            return false;
        }
        
        // Calculate total size needed
        size_t jpeg_size = jpeg_data.size();
        size_t total_size = HEADER_SIZE + jpeg_size;
        
        // Check if we have enough space
        if (total_size > shm_size_) {
            log_warning("JPEG size (" + std::to_string(jpeg_size) + 
                       " bytes) exceeds SHM capacity, dropping frame");
            return false;
        }
        
        // Write header
        FrameHeader header;
        memset(&header, 0, sizeof(FrameHeader));
        header.magic = SHM_MAGIC;
        header.width = static_cast<uint32_t>(frame.cols);
        header.height = static_cast<uint32_t>(frame.rows);
        header.format = 3;  // 3 = JPEG
        header.frame_id = frame_id_;
        header.timestamp_us = get_timestamp_us();
        header.jpeg_size = static_cast<uint32_t>(jpeg_size);
        
        memcpy(shm_buffer_, &header, HEADER_SIZE);
        
        // Write JPEG data
        memcpy(shm_buffer_ + HEADER_SIZE, jpeg_data.data(), jpeg_size);
        
        // Increment frame counter
        frame_id_++;
        
        log_debug("Frame written: id=" + std::to_string(frame_id_ - 1) + 
                  ", jpeg_size=" + std::to_string(jpeg_size));
        
        return true;
        
    } catch (const std::exception& e) {
        last_error_ = std::string("Exception writing frame: ") + e.what();
        log_error(last_error_);
        return false;
    }
}

/**
 * Close shared memory
 */
void ShmWriter::close() {
    log_info("Closing shared memory");
    
    try {
        if (shm_buffer_ != nullptr && shm_buffer_ != MAP_FAILED) {
            munmap(shm_buffer_, shm_size_);
            shm_buffer_ = nullptr;
        }
        
        if (shm_fd_ != -1) {
            ::close(shm_fd_);
            shm_fd_ = -1;
        }
        
        // Unlink shared memory object
        if (!shm_name_.empty()) {
            shm_unlink(shm_name_.c_str());
        }
        
        is_attached_ = false;
        log_info("Shared memory closed");
        
    } catch (const std::exception& e) {
        log_error(std::string("Exception closing SHM: ") + e.what());
    }
}

/**
 * Encode frame to JPEG
 */
std::vector<uint8_t> ShmWriter::encode_to_jpeg(const cv::Mat& frame, int quality) {
    std::vector<int> params;
    params.push_back(cv::IMWRITE_JPEG_QUALITY);
    params.push_back(quality);
    
    std::vector<uint8_t> jpeg_data;
    bool ret = cv::imencode(".jpg", frame, jpeg_data, params);
    
    if (!ret) {
        log_error("JPEG encoding failed");
        return std::vector<uint8_t>();
    }
    
    return jpeg_data;
}

/**
 * Get current timestamp in microseconds
 */
uint64_t ShmWriter::get_timestamp_us() const {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000 + ts.tv_nsec / 1000;
}

/**
 * Private helper: Log error
 */
void ShmWriter::log_error(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cerr << "[" << oss.str() << "] ERROR [ShmWriter]: " << message << std::endl;
}

/**
 * Private helper: Log info
 */
void ShmWriter::log_info(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cout << "[" << oss.str() << "] INFO [ShmWriter]: " << message << std::endl;
}

/**
 * Private helper: Log warning
 */
void ShmWriter::log_warning(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cerr << "[" << oss.str() << "] WARN [ShmWriter]: " << message << std::endl;
}

/**
 * Private helper: Log debug
 */
void ShmWriter::log_debug(const std::string& message) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    
    std::cout << "[" << oss.str() << "] DEBUG [ShmWriter]: " << message << std::endl;
}