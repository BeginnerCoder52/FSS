"""
FRTApp (Food Recognition Tracking) - Python AI Core Package
Version: 1.0
Description: YOLOv11-based food recognition and tracking system with D-Bus integration

This package provides the AI pipeline for detecting and tracking food items in a refrigerator
using deep learning models and real-time video processing.

Main Components:
    - FrtMain: Application main controller
    - YoloTfliteEngine: TFLite model inference
    - ImagePreprocessor: Image normalization and preprocessing
    - MotionDetector: Background subtraction (MOG2)
    - CameraUvcDriver: USB camera V4L2 wrapper
    - FrtDbusInterface: D-Bus IPC communication

Author: FSS Project Team
License: Proprietary
"""

__version__ = "1.0"
__all__ = [
    "FrtMain",
    "YoloTfliteEngine",
    "ImagePreprocessor",
    "MotionDetector",
    "CameraUvcDriver",
    "FrtDbusInterface",
    "YoloPipeline"
]

import logging

# Configure module-level logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
