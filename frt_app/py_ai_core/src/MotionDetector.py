"""
MotionDetector.py - Background Subtraction with MOG2
Version: 1.0
SDD v1.1.0 Compliance: All 4 APIs implemented

Purpose:
    Detect motion in video frames using MOG2 (Mixture of Gaussians v2)
    background subtraction algorithm. Filters out static scenes to reduce
    unnecessary AI inference overhead.

Algorithm: MOG2 (Gaussian Mixture Model)
    - Adaptive background model
    - Robust to lighting changes
    - Fast processing (~5-10ms per frame)
    - Memory-efficient

Use Case:
    - Skip inference on static frames (door closed, no motion)
    - Improve performance: Only run YOLO when motion detected
    - Reduce false positives from light flicker

Author: FSS Project Team
License: Proprietary
"""

import cv2
import numpy as np
from loguru import logger

class MotionDetector:
    """
    Motion Detection using OpenCV MOG2 Background Subtraction
    
    SDD v1.1.0 Requirements (Bảng 2 - Package FRTApp, MotionDetector class):
        Attribute mog2_subtractor: object - BackgroundSubtractorMOG2 instance
        Attribute pixel_change_threshold: int - Threshold for motion (%)
    
    Methods (4 total):
        ✓ init_mog2() -> void
        ✓ apply_background_subtraction(frame: object) -> object
        ✓ is_motion_detected(mask: object) -> bool
        ✓ reset_background_model() -> void
    """
    
    # MOG2 configuration parameters
    MOG2_HISTORY = 500              # Number of frames for background model
    MOG2_THRESHOLD = 16.0           # Variance threshold
    MOG2_DETECT_SHADOWS = True      # Detect shadows as objects
    
    # Motion detection threshold (% of changed pixels)
    PIXEL_CHANGE_THRESHOLD = 1.0    # Trigger if > 1% of pixels changed
    
    def __init__(self, threshold_percent: float = 1.0):
        """
        Initialize motion detector.
        
        Arguments:
            threshold_percent (float): % of pixels that must change to trigger motion
        """
        self.mog2_subtractor = None
        self.pixel_change_threshold = threshold_percent
        
        logger.info("MotionDetector initialized (threshold={}%)".format(
            threshold_percent))
    
    def init_mog2(self) -> None:
        """
        Initialize MOG2 background subtractor.
        
        SDD Requirement:
            Cấu hình MOG2.
        
        Parameters:
            - History: 500 frames (captures ~17s at 30 FPS)
            - Threshold: 16.0 (variance sensitivity)
            - Shadows: Detect shadows as moving objects
        
        Returns:
            void
        """
        logger.info("Initializing MOG2 background subtractor")
        
        try:
            self.mog2_subtractor = cv2.createBackgroundSubtractorMOG2(
                detectShadows=self.MOG2_DETECT_SHADOWS,
                history=self.MOG2_HISTORY,
                varThreshold=self.MOG2_THRESHOLD
            )
            logger.info("MOG2 initialized (history={}, threshold={})".format(
                self.MOG2_HISTORY, self.MOG2_THRESHOLD))
            
        except Exception as e:
            logger.exception("Error initializing MOG2: {}".format(e))
    
    def apply_background_subtraction(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply MOG2 background subtraction to frame.
        
        SDD Requirement:
            Truyền frame vào, trả về binary mask.
        
        Process:
            1. Convert BGR to grayscale (optional, MOG2 works in grayscale)
            2. Apply MOG2 to get foreground mask
            3. Apply morphological operations to clean mask
            4. Return binary mask (0=background, 255=foreground)
        
        Arguments:
            frame (np.ndarray): Input frame (H, W, 3) BGR
        
        Returns:
            np.ndarray: Binary foreground mask (H, W) uint8 {0, 255}
                       or None if error
        """
        if self.mog2_subtractor is None:
            logger.error("MOG2 not initialized")
            return None
        
        if frame is None:
            logger.error("Frame is None")
            return None
        
        try:
            # Apply MOG2 subtraction
            mask = self.mog2_subtractor.apply(frame)
            
            # Apply morphological operations to clean mask
            # Remove noise with closing (dilation + erosion)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            return mask
            
        except Exception as e:
            logger.exception("Error applying background subtraction: {}".format(e))
            return None
    
    def is_motion_detected(self, mask: np.ndarray) -> bool:
        """
        Detect if motion is present in foreground mask.
        
        SDD Requirement:
            Kiểm tra mask vượt qua ngưỡng threshold không.
        
        Logic:
            1. Count non-zero pixels in mask (foreground)
            2. Calculate percentage: (foreground / total) * 100
            3. Compare with threshold: is_motion = (percentage > threshold)
        
        Arguments:
            mask (np.ndarray): Binary foreground mask from MOG2
        
        Returns:
            bool: True if motion detected, False otherwise
        """
        if mask is None:
            logger.warning("Mask is None, no motion")
            return False
        
        try:
            # Count foreground pixels
            non_zero = cv2.countNonZero(mask)
            total = mask.shape[0] * mask.shape[1]
            
            # Calculate percentage
            percent_changed = (non_zero / total) * 100.0
            
            # Threshold check
            is_motion = percent_changed > self.pixel_change_threshold
            
            logger.debug("Motion check: {:.2f}% changed (threshold: {}%)".format(
                percent_changed, self.pixel_change_threshold))
            
            return is_motion
            
        except Exception as e:
            logger.exception("Error detecting motion: {}".format(e))
            return False
    
    def reset_background_model(self) -> None:
        """
        Reset MOG2 background model.
        
        SDD Requirement:
            Xóa nền hiện tại để chống nhiễu sáng.
        
        Use Cases:
            - Sudden lighting change
            - Recovery from crash
            - Transitioning from IDLE to TRACKING
        
        Returns:
            void
        """
        logger.info("Resetting MOG2 background model")
        
        try:
            if self.mog2_subtractor is not None:
                # Reinitialize MOG2
                self.init_mog2()
                logger.info("Background model reset successfully")
            
        except Exception as e:
            logger.exception("Error resetting background model: {}".format(e))


if __name__ == "__main__":
    logger.info("MotionDetector - Test Entry Point")
    
    detector = MotionDetector(threshold_percent=1.0)
    detector.init_mog2()
    logger.info("✓ Detector initialized")
    
    # Create dummy frames
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)  # Black frame
    frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 50  # Slightly brighter
    
    # Test background subtraction
    mask1 = detector.apply_background_subtraction(frame1)
    mask2 = detector.apply_background_subtraction(frame2)
    
    if mask2 is not None:
        motion = detector.is_motion_detected(mask2)
        logger.info("✓ Motion detected: {}".format(motion))
    
    detector.reset_background_model()
    logger.info("✓ Background model reset")
