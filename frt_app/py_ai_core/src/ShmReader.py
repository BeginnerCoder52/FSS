"""
ShmReader.py - POSIX Shared Memory Frame Reader
Version: 1.0
SDD v1.1.0 Compliance

Purpose:
    Read JPEG-encoded video frames from POSIX shared memory published by C++ camera core.
    Provides interface for FrtMain to consume frames without direct USB camera access.

SHM Layout:
    Offset 0-63:  FrameHeader (64 bytes)
        - magic (uint32) = 0xDEADBEEF
        - width (uint32)
        - height (uint32)
        - format (uint32)
        - timestamp_us (uint64)
        - frame_id (uint32)
        - jpeg_size (uint32)
        - reserved (32 bytes)
    Offset 64+:   JPEG frame data (variable size)

Integration:
    Used by: FrtMain.run_inference_loop()
    Input: /fss_video_frame shared memory
    Output: cv::Mat BGR frame (or None if error)
"""

import os
import struct
import mmap
import threading
from typing import Optional
import cv2
import numpy as np
from loguru import logger


class ShmReader:
    """
    Reader for POSIX shared memory video frames.
    
    ASPICE Traceability:
        - Requirement: FRT_REQ_005 (Frame acquisition from camera core)
        - Requirement: FRT_REQ_015 (IPC via shared memory)
    """
    
    # Configuration constants
    SHM_NAME = "/fss_video_frame"
    SHM_PATH = "/dev/shm/fss_video_frame"
    SHM_SIZE = 2 * 1024 * 1024  # 2 MB
    HEADER_SIZE = 64  # bytes
    SHM_MAGIC = 0xDEADBEEF
    
    # Frame header struct format: little-endian
    # I = uint32 (4), Q = uint64 (8)
    # Format: magic, width, height, format, timestamp, frame_id, jpeg_size, reserved[8]
    HEADER_FORMAT = '<IIIIQII8I'
    
    def __init__(self):
        """
        Constructor
        """
        self.shm_fd_ = -1
        self.shm_buffer_ = None
        self.is_attached_ = False
        self.last_frame_id_ = -1
        self.missed_frames_ = 0
        self.total_frames_read_ = 0
        self.last_error_ = ""
        self._lock = threading.Lock()
        
        logger.info("ShmReader initialized (shm_path={}, size={}MB)",
                   self.SHM_PATH, self.SHM_SIZE // (1024*1024))
    
    def __del__(self):
        """Destructor - cleanup on deletion"""
        self.close()
    
    def attach(self) -> bool:
        """
        Attach to shared memory region
        """
        try:
            logger.info("Attaching to shared memory: {}", self.SHM_PATH)
            
            # Open shared memory object (read-only)
            if not os.path.exists(self.SHM_PATH):
                self.last_error_ = f"SHM file not found: {self.SHM_PATH}"
                logger.debug(self.last_error_)
                return False

            self.shm_fd_ = os.open(self.SHM_PATH, os.O_RDONLY)
            
            # Map to address space
            self.shm_buffer_ = mmap.mmap(
                self.shm_fd_,
                self.SHM_SIZE,
                access=mmap.ACCESS_READ
            )
            
            self.is_attached_ = True
            self.last_frame_id_ = -1
            self.missed_frames_ = 0
            
            logger.info("Shared memory attached successfully ({}B)", self.SHM_SIZE)
            return True
            
        except FileNotFoundError:
            self.last_error_ = f"SHM not found: {self.SHM_PATH}"
            logger.error(self.last_error_)
            self.is_attached_ = False
            return False
        
        except PermissionError:
            self.last_error_ = f"Permission denied accessing SHM: {self.SHM_PATH}"
            logger.error(self.last_error_)
            self.is_attached_ = False
            return False
        
        except Exception as e:
            self.last_error_ = f"Exception attaching to SHM: {str(e)}"
            logger.error(self.last_error_)
            self.is_attached_ = False
            return False
    
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read next frame from shared memory
        """
        if not self.is_attached_:
            # Try to re-attach if not attached
            if not self.attach():
                return None
        
        try:
            with self._lock:
                # Read header (64 bytes)
                self.shm_buffer_.seek(0)
                header_data = self.shm_buffer_.read(self.HEADER_SIZE)
                
                if len(header_data) < self.HEADER_SIZE:
                    self.last_error_ = "Failed to read frame header"
                    logger.warning(self.last_error_)
                    return None
                
                # Parse header
                unpacked = struct.unpack(self.HEADER_FORMAT, header_data)
                magic = unpacked[0]
                width = unpacked[1]
                height = unpacked[2]
                fmt = unpacked[3]
                timestamp_us = unpacked[4]
                frame_id = unpacked[5]
                jpeg_size = unpacked[6]
                
                # Validate magic
                if magic != self.SHM_MAGIC:
                    self.last_error_ = f"Invalid SHM magic: {hex(magic)}"
                    # logger.debug(self.last_error_)
                    return None
                
                # Check if this is a new frame
                if frame_id == self.last_frame_id_:
                    return None
                
                # Validate JPEG size
                if jpeg_size == 0 or jpeg_size > self.SHM_SIZE - self.HEADER_SIZE:
                    self.last_error_ = f"Invalid JPEG size: {jpeg_size}"
                    logger.warning(self.last_error_)
                    return None
                
                # Check for missed frames
                if self.last_frame_id_ >= 0:
                    missed = frame_id - self.last_frame_id_ - 1
                    if missed > 0:
                        self.missed_frames_ += missed
                        logger.debug("Detected {} missed frames (id {} → {})",
                                    missed, self.last_frame_id_, frame_id)
                
                self.last_frame_id_ = frame_id
                
                # Read JPEG data
                self.shm_buffer_.seek(self.HEADER_SIZE)
                jpeg_data = self.shm_buffer_.read(jpeg_size)
                
                if len(jpeg_data) != jpeg_size:
                    self.last_error_ = f"Incomplete JPEG data: {len(jpeg_data)}/{jpeg_size}"
                    logger.warning(self.last_error_)
                    return None
                
                # Decode JPEG
                jpeg_array = np.frombuffer(jpeg_data, dtype=np.uint8)
                frame = cv2.imdecode(jpeg_array, cv2.IMREAD_COLOR)
                
                if frame is None:
                    self.last_error_ = "JPEG decode failed"
                    logger.warning(self.last_error_)
                    return None
                
                self.total_frames_read_ += 1
                
                return frame
                
        except Exception as e:
            self.last_error_ = f"Exception reading frame: {str(e)}"
            logger.error(self.last_error_)
            return None
    
    def close(self):
        """
        Close shared memory connection
        """
        try:
            if self.shm_buffer_ is not None:
                self.shm_buffer_.close()
                self.shm_buffer_ = None
            
            if self.shm_fd_ != -1:
                os.close(self.shm_fd_)
                self.shm_fd_ = -1
            
            self.is_attached_ = False
            
        except Exception as e:
            logger.debug("Exception closing SHM: {}", str(e))
    
    def is_ready(self) -> bool:
        """
        Check if SHM reader is ready
        """
        return self.is_attached_
    
    def get_stats(self) -> dict:
        """
        Get reader statistics for diagnostics
        """
        return {
            'total_frames_read': self.total_frames_read_,
            'missed_frames': self.missed_frames_,
            'last_frame_id': self.last_frame_id_,
            'last_error': self.last_error_
        }
