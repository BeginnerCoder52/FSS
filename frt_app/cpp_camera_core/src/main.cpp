/**
 * main.cpp - C++ Camera Core Main Entry Point
 * Version: 1.0
 * SDD v1.1.0 Compliance
 *
 * Purpose:
 *     Main entry point for FRTApp C++ camera core process.
 *     Captures frames from USB camera and publishes to POSIX shared memory.
 *
 * Usage:
 *     ./camera_core_exec [--device /dev/video0] [--width 640] [--height 480]
 *
 * Process:
 *     1. Initialize VideoCapture (USB camera)
 *     2. Initialize ShmWriter (shared memory)
 *     3. Main loop: capture frame → write to SHM
 *     4. Handle signals for graceful shutdown
 */

#include <signal.h>
#include <unistd.h>
#include <iostream>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <sstream>
#include "VideoCapture.hpp"
#include "ShmWriter.hpp"
#include "CameraConfig.hpp"

// Global state for signal handling
volatile bool g_running = true;

/**
 * Signal handler for graceful shutdown
 */
void signal_handler(int sig) {
    std::cout << "\nReceived signal " << sig << ", shutting down..." << std::endl;
    g_running = false;
}

/**
 * Print usage information
 */
void print_usage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [options]\n"
              << "Options:\n"
              << "  --device PATH    Video device path (default: " << CameraConfig::DEVICE_PATH << ")\n"
              << "  --width N        Capture width (default: " << CameraConfig::DEFAULT_WIDTH << ")\n"
              << "  --height N       Capture height (default: " << CameraConfig::DEFAULT_HEIGHT << ")\n"
              << "  --fps N          Capture FPS (default: " << CameraConfig::DEFAULT_FPS << ")\n"
              << "  --help           Show this help message\n";
}

/**
 * Main entry point
 */
int main(int argc, char* argv[]) {
    // Default configuration
    std::string device_path = CameraConfig::DEVICE_PATH;
    int width = CameraConfig::DEFAULT_WIDTH;
    int height = CameraConfig::DEFAULT_HEIGHT;
    int fps = CameraConfig::DEFAULT_FPS;
    
    // Parse command line arguments
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--device") == 0 && i + 1 < argc) {
            device_path = argv[++i];
        } else if (strcmp(argv[i], "--width") == 0 && i + 1 < argc) {
            width = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--height") == 0 && i + 1 < argc) {
            height = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--fps") == 0 && i + 1 < argc) {
            fps = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }
    
    std::cout << "========================================\n";
    std::cout << "FRTApp C++ Camera Core\n";
    std::cout << "Version: 1.0 (SDD v1.1.0)\n";
    std::cout << "========================================\n";
    std::cout << "Device: " << device_path << "\n";
    std::cout << "Resolution: " << width << "x" << height << " @ " << fps << " FPS\n";
    std::cout << "========================================\n";
    
    // Setup signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Initialize camera
    VideoCapture camera(device_path, width, height, fps);
    if (!camera.open()) {
        std::cerr << "Failed to open camera device\n";
        return 1;
    }
    
    // Initialize shared memory writer
    ShmWriter shm_writer;
    if (!shm_writer.create()) {
        std::cerr << "Failed to create shared memory\n";
        camera.close();
        return 1;
    }
    
    std::cout << "Camera core started successfully\n";
    
    // Main capture loop
    uint32_t frame_count = 0;
    uint64_t last_log_time = 0;
    
    while (g_running) {
        // Capture frame
        cv::Mat frame = camera.read_frame();
        
        if (frame.empty()) {
            // Frame capture failed, pause briefly
            usleep(10000);  // 10ms
            continue;
        }
        
        // Write to shared memory
        if (!shm_writer.write_frame(frame)) {
            std::cerr << "Failed to write frame to shared memory\n";
        }
        
        frame_count++;
        
        // Log progress every `fps` frames (~1 second)
        uint64_t current_time = shm_writer.get_timestamp_us() / 1000000;
        if (current_time - last_log_time >= 1) {
            std::cout << "Frames captured: " << frame_count 
                      << " (frame_id: " << shm_writer.get_frame_id() << ")\n";
            last_log_time = current_time;
        }
        
        // Small delay to prevent CPU overuse
        usleep(1000);  // 1ms
    }
    
    // Cleanup
    std::cout << "\nShutting down camera core...\n";
    shm_writer.close();
    camera.close();
    
    std::cout << "Camera core stopped\n";
    return 0;
}