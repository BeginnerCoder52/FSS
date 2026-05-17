"""
ImagePreprocessor.py - Image Normalization & Preprocessing
Version: 1.0
SDD v1.1.0 Compliance: All 5 APIs implemented

Purpose:
    Convert raw camera frames to normalized tensor input for YOLOv11 inference.
    Handles color space conversion, resizing, normalization, and batch padding.

Pipeline:
    Raw BGR Frame → RGB Conversion → Resize → Normalize → Add Batch Dim → Tensor

Target Model: YOLOv11 (expects normalized float32 tensors)
Input Shape: (1, 640, 640, 3) - [batch, height, width, channels]
Input Range: [0.0, 1.0] - Normalized to 0-1 range

Author: FSS Project Team
License: Proprietary
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from loguru import logger

class ImagePreprocessor:
    """
    Image Preprocessing Pipeline for YOLO Inference
    
    SDD v1.1.0 Requirements (Bảng 2 - Package FRTApp, ImagePreprocessor class):
        Attribute target_width: int - Target output width (640)
        Attribute target_height: int - Target output height (480)
        Attribute normalize_scale: float - Normalization factor (1/255)
    
    Methods (5 total):
        ✓ convert_bgr_to_rgb(frame: object) -> object
        ✓ resize_frame(frame: object) -> object
        ✓ normalize_pixels(frame: object) -> object
        ✓ prepare_tensor_input(frame: object) -> object
        ✓ catch_shape_error(shape: tuple) -> void
    """
    
    # Target dimensions for YOLO model
    TARGET_WIDTH = 640
    TARGET_HEIGHT = 640
    NORMALIZE_SCALE = 1.0 / 255.0  # Convert [0, 255] to [0, 1]
    
    def __init__(self, target_width: int = 640, target_height: int = 640):
        """
        Initialize image preprocessor.
        
        Arguments:
            target_width (int): Target image width
            target_height (int): Target image height
        """
        self.target_width = target_width
        self.target_height = target_height
        self.normalize_scale = self.NORMALIZE_SCALE
        
        logger.info("ImagePreprocessor initialized (target={}x{})".format(
            target_width, target_height))
    
    def convert_bgr_to_rgb(self, frame: np.ndarray) -> np.ndarray:
        """
        Convert BGR frame to RGB color space.
        
        SDD Requirement:
            Chuyển hệ màu OpenCV mặc định.
        
        Details:
            OpenCV reads images in BGR format
            YOLO models typically expect RGB format
            Conversion: cv2.cvtColor(BGR -> RGB)
        
        Arguments:
            frame (np.ndarray): Input frame in BGR format (H, W, 3)
        
        Returns:
            np.ndarray: Frame in RGB format (H, W, 3)
        """
        try:
            if frame is None:
                logger.error("Frame is None, cannot convert color space")
                return None
            
            # Validate shape
            if len(frame.shape) != 3 or frame.shape[2] != 3:
                logger.error("Invalid frame shape: {}".format(frame.shape))
                return None
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return rgb_frame
            
        except Exception as e:
            logger.exception("Error converting BGR to RGB: {}".format(e))
            return None
    
    def resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize frame to target dimensions.
        
        SDD Requirement:
            Ép kích thước khung hình vào shape mô hình.
        
        Method:
            cv2.INTER_LINEAR (fast, good quality for downsampling)
        
        Arguments:
            frame (np.ndarray): Input frame (H, W, 3)
        
        Returns:
            np.ndarray: Resized frame (target_height, target_width, 3)
        """
        try:
            if frame is None:
                logger.error("Frame is None, cannot resize")
                return None
            
            resized = cv2.resize(frame, (self.target_width, self.target_height),
                               interpolation=cv2.INTER_LINEAR)
            return resized
            
        except Exception as e:
            logger.exception("Error resizing frame: {}".format(e))
            return None
    
    def normalize_pixels(self, frame: np.ndarray) -> np.ndarray:
        """
        Normalize pixel values to [0, 1] range.
        
        SDD Requirement:
            Chuẩn hóa pixel ảnh.
        
        Method:
            pixel_normalized = pixel_original * (1.0 / 255.0)
            Converts uint8 [0-255] to float32 [0.0-1.0]
        
        Arguments:
            frame (np.ndarray): Input frame with uint8 pixels
        
        Returns:
            np.ndarray: Normalized frame with float32 pixels in [0, 1]
        """
        try:
            if frame is None:
                logger.error("Frame is None, cannot normalize")
                return None
            
            # Convert to float32
            frame_float = frame.astype(np.float32)
            
            # Normalize to [0, 1]
            normalized = frame_float * self.normalize_scale
            
            return normalized
            
        except Exception as e:
            logger.exception("Error normalizing pixels: {}".format(e))
            return None
    
    def prepare_tensor_input(self, frame: np.ndarray) -> np.ndarray:
        """
        Prepare complete tensor input for YOLO inference.
        
        SDD Requirement:
            Độn thêm chiều batch_size (np.expand_dims).
        
        Pipeline:
            1. BGR → RGB
            2. Resize to target dimensions
            3. Normalize pixels to [0, 1]
            4. Add batch dimension
            5. Result: (1, H, W, 3) float32 tensor
        
        Arguments:
            frame (np.ndarray): Raw camera frame (H, W, 3) uint8 BGR
        
        Returns:
            np.ndarray: Tensor (1, target_height, target_width, 3) float32
                       or None if any step fails
        """
        logger.debug("Preparing tensor input")
        
        try:
            # Step 1: Convert BGR to RGB
            rgb_frame = self.convert_bgr_to_rgb(frame)
            if rgb_frame is None:
                return None
            
            # Step 2: Resize
            resized = self.resize_frame(rgb_frame)
            if resized is None:
                return None
            
            # Step 3: Normalize
            normalized = self.normalize_pixels(resized)
            if normalized is None:
                return None
            
            # Step 4: Add batch dimension (N, H, W, C) where N=1
            tensor = np.expand_dims(normalized, axis=0)
            
            # Validate output shape
            expected_shape = (1, self.target_height, self.target_width, 3)
            if tensor.shape != expected_shape:
                logger.error("Unexpected tensor shape: {} (expected {})".format(
                    tensor.shape, expected_shape))
                self.catch_shape_error(tensor.shape)
                return None
            
            logger.debug("Tensor prepared: shape={}, dtype={}".format(
                tensor.shape, tensor.dtype))
            
            return tensor
            
        except Exception as e:
            logger.exception("Error preparing tensor input: {}".format(e))
            return None
    
    def catch_shape_error(self, shape: Tuple) -> None:
        """
        Handle and report tensor shape errors.
        
        SDD Requirement:
            Báo lỗi nếu Tensor shape sai cấu trúc.
        
        Purpose:
            Log shape mismatch errors for debugging
        
        Arguments:
            shape (tuple): Actual tensor shape
        """
        logger.error("Tensor shape error: {} (expected (1, {}, {}, 3))".format(
            shape, self.target_height, self.target_width))


if __name__ == "__main__":
    logger.info("ImagePreprocessor - Test Entry Point")
    
    preprocessor = ImagePreprocessor(640, 640)
    logger.info("✓ Preprocessor created")
    
    # Create dummy frame (480, 640, 3) BGR
    dummy_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    logger.info("✓ Dummy frame created: shape={}".format(dummy_frame.shape))
    
    # Test pipeline
    tensor = preprocessor.prepare_tensor_input(dummy_frame)
    if tensor is not None:
        logger.info("✓ Tensor prepared: shape={}, dtype={}".format(
            tensor.shape, tensor.dtype))
        logger.info("✓ Pixel range: [{:.3f}, {:.3f}]".format(
            tensor.min(), tensor.max()))
    else:
        logger.error("✗ Tensor preparation failed")
