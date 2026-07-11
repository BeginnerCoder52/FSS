/**
 * ShmWriter.hpp - POSIX Shared Memory Writer for Video Frames
 * Version: 1.0
 * SDD v1.1.0 Compliance
 *
 * Purpose:
 *     Write JPEG-encoded video frames to POSIX shared memory region.
 *     Enables efficient inter-process communication with Python AI pipeline.
 *
 * Shared Memory Details:
 *     - Name: /fss_video_frame (POSIX named shared memory)
 *     - Size: Configurable (default: 2MB for 1080p JPEG)
 *     - Access: Multi-reader, single-writer pattern
 *     - Format: JPEG-encoded frame + metadata header
 *
 * Metadata Layout (Header):
 *     struct {
 *         uint32_t frame_id;              // Sequential frame counter
 *         uint64_t timestamp_us;          // Microsecond timestamp
 *         uint32_t jpeg_size;             // JPEG data size in bytes
 *         uint32_t reserved;              // Reserved for future use
 *     } (16 bytes)
 *
 * Data Layout:
 *     [16-byte header] + [JPEG data] + [padding to frame_size]
 *
 * Integration:
 *     - Source: VideoCapture (BGR frames)
 *     - Consumer: DBDaemon (reads frames on FoodDetected event)
 *
 * Author: FSS Project Team
 * License: Proprietary
 */

#ifndef SHMWRITER_HPP
#define SHMWRITER_HPP

#include <string>
#include <cstdint>
#include <memory>
#include <opencv2/opencv.hpp>

/**
 * Frame Metadata Header Structure
 *
 * Stored at the beginning of shared memory block.
 * Allows consumers to parse frame data correctly.
 * 64-byte aligned structure for efficient memory access.
 */
struct FrameHeader {
    uint32_t magic;           ///< 0xDEADBEEF for validation
    uint32_t width;           ///< Frame width in pixels
    uint32_t height;          ///< Frame height in pixels
    uint32_t format;          ///< Color format (0=BGR, 1=RGB, 2=YUYV, 3=JPEG)
    uint64_t timestamp_us;    ///< Timestamp in microseconds (Unix epoch)
    uint32_t frame_id;        ///< Sequential frame number (0-indexed)
    uint32_t jpeg_size;       ///< Size of JPEG data in bytes
    uint32_t reserved[8];     ///< Reserved for future use (padding to 64 bytes)
};

/**
 * ShmWriter - POSIX Shared Memory Frame Publisher
 *
 * Responsibilities:
 *     - Create/open shared memory region
 *     - Encode frames to JPEG
 *     - Write frame + metadata to SHM
 *     - Manage frame ID counter
 *     - Handle SHM full conditions
 *
 * Thread Safety:
 *     - Single writer (no internal locking)
 *     - Multiple readers (via SHM)
 *     - Reader synchronization: Use frame_id to detect updates
 *
 * Error Handling:
 *     - SHM creation failed: Log error, stop daemon
 *     - JPEG encoding failed: Log warning, skip frame
 *     - SHM full: Drop oldest frame, log warning
 *     - Detachment failed: Log error, continue
 */
class ShmWriter {
public:
    // Configuration Constants
    static constexpr const char* SHM_NAME = "/fss_video_frame";
    static constexpr size_t DEFAULT_SHM_SIZE = 2 * 1024 * 1024;  // 2 MB
    static constexpr int JPEG_QUALITY = 85;                       // 0-100
    static constexpr size_t HEADER_SIZE = 64;                     // 64-byte aligned
    static constexpr uint32_t SHM_MAGIC = 0xDEADBEEF;
    
    /**
     * Constructor
     *
     * Arguments:
     *     shm_name: Name of shared memory region (default: /fss_video_frame)
     *     shm_size: Size in bytes (default: 2MB)
     */
    ShmWriter(
        const std::string& shm_name = SHM_NAME,
        size_t shm_size = DEFAULT_SHM_SIZE
    );
    
    /**
     * Destructor
     *     Automatically detach from shared memory
     */
    ~ShmWriter();
    
    /**
     * Create and attach to shared memory region
     *
     * Purpose:
     *     Initialize POSIX shared memory for frame publishing.
     *
     * Process:
     *     1. Create shared memory object (shm_open)
     *     2. Configure size (ftruncate)
     *     3. Map to process address space (mmap)
     *     4. Initialize metadata
     *
     * Returns:
     *     true: Successfully created/attached to SHM
     *     false: Failed to create SHM
     *
     * Error Handling:
     *     - Permission denied: Log critical, return false
     *     - No space left: Log error, return false
     *     - SHM already exists: Reuse existing (if size matches)
     */
    bool create();
    
    /**
     * Write frame to shared memory
     *
     * Purpose:
     *     Encode frame to JPEG and write with metadata to SHM.
     *
     * Process:
     *     1. Validate frame (not empty)
     *     2. Encode BGR → JPEG
     *     3. Write header (frame_id, timestamp, jpeg_size)
     *     4. Write JPEG data
     *     5. Increment frame_id
     *
     * Arguments:
     *     frame: BGR image (cv::Mat)
     *
     * Returns:
     *     true: Frame written successfully
     *     false: Write failed (SHM full, encoding error, etc.)
     *
     * Error Handling:
     *     - JPEG encoding failed: Log warning, return false
     *     - SHM full: Drop oldest frame, retry, log warning
     *     - Buffer overflow: Log error, return false
     */
    bool write_frame(const cv::Mat& frame);
    
    /**
     * Close and detach from shared memory
     *
     * Purpose:
     *     Clean up SHM resources.
     *
     * Returns:
     *     void
     */
    void close();
    
    /**
     * Check if SHM is attached and ready
     *
     * Returns:
     *     true: SHM initialized and ready
     *     false: SHM not initialized
     */
    bool is_ready() const { return is_attached_; }
    
    /**
     * Get current frame ID
     *
     * Returns:
     *     uint32_t: Sequential frame counter
     */
    uint32_t get_frame_id() const { return frame_id_; }
    
    /**
     * Get shared memory size
     *
     * Returns:
     *     size_t: Size in bytes
     */
    size_t get_shm_size() const { return shm_size_; }
    
    /**
     * Get error status string
     *
     * Returns:
     *     String describing last error (empty if no error)
     */
    const std::string& get_last_error() const { return last_error_; }
    
    /**
     * Get current timestamp in microseconds (public for main.cpp)
     *
     * Returns:
     *     uint64_t: Unix timestamp in microseconds
     */
    uint64_t get_timestamp_us() const;

private:
    // Member Variables
    std::string shm_name_;
    size_t shm_size_;
    bool is_attached_;
    std::string last_error_;
    
    // Shared memory pointers
    int shm_fd_;                    // File descriptor for shm_open
    uint8_t* shm_buffer_;           // Mapped memory region
    
    // Frame management
    uint32_t frame_id_;             // Sequential frame counter
    size_t current_write_offset_;   // Current write position in SHM
    
    // Private helper methods
    /**
     * Encode frame to JPEG
     *
     * Arguments:
     *     frame: BGR image
     *     quality: JPEG quality (0-100)
     *
     * Returns:
     *     std::vector<uint8_t>: JPEG-encoded data
     *     Empty vector: If encoding failed
     */
    std::vector<uint8_t> encode_to_jpeg(const cv::Mat& frame, int quality);
    
    /**
     * Log error message with timestamp
     */
    void log_error(const std::string& message);
    
    /**
     * Log info message with timestamp
     */
    void log_info(const std::string& message);
    
    /**
     * Log warning message with timestamp
     */
    void log_warning(const std::string& message);
    
    /**
     * Log debug message with timestamp
     */
    void log_debug(const std::string& message);
};

#endif // SHMWRITER_HPP
