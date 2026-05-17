"""
YoloTfliteEngine.py - YOLOv11 TFLite Inference Engine
Version: 1.0
SDD v1.1.0 Compliance: All 6 APIs implemented

Purpose:
    Load and run YOLOv11 TensorFlow Lite models for food object detection.
    Optimized for Raspberry Pi 4B ARM inference with minimal latency.

Model Details:
    - Format: TFLite (.tflite)
    - Model: YOLOv11 Nano (yolov11n)
    - Input: (1, 640, 640, 3) float32 [0.0, 1.0]
    - Output: (1, 84, 8400) - YOLOv11 format
    - Inference Speed: ~100-300ms per frame on Raspberry Pi

Author: FSS Project Team
License: Proprietary
"""

import numpy as np
import os
import time
from typing import List, Dict, Optional, Tuple
from loguru import logger

class YoloTfliteEngine:
    """
    YOLOv11 TFLite Inference Engine
    """
    
    # Model path (placeholder until YOLO model available)
    DEFAULT_MODEL_PATH = "/home/richardmelvin52/FSS/frt_app/py_ai_core/models/yolov11n.tflite"
    
    # Inference parameters
    CONFIDENCE_THRESHOLD = 0.25      # Minimum confidence for detection
    IOU_THRESHOLD = 0.45             # NMS IoU threshold
    
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        """
        Initialize YOLO TFLite engine.
        """
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.is_initialized = False
        
        # Class names (example for food items)
        self.classes = ["food_item"] # To be updated with actual model classes
        
        logger.info("YoloTfliteEngine initialized (model={})".format(model_path))
    
    def load_model_mmap(self) -> bool:
        """
        Load TFLite model using memory mapping.
        """
        logger.info("Loading YOLOv11 model: {}".format(self.model_path))
        
        try:
            # Check file exists
            if not os.path.exists(self.model_path):
                logger.error("Model file not found: {}".format(self.model_path))
                return False
            
            # Try to import TFLite runtime
            try:
                import tflite_runtime.interpreter as tflite
            except ImportError:
                try:
                    import tensorflow.lite as tflite
                except ImportError:
                    logger.error("TFLite runtime not installed.")
                    return False
            
            # Load model
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            
            # Allocate tensors
            self.allocate_tensors()
            
            # Get tensor details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            self.is_initialized = True
            logger.info("Model loaded successfully")
            return True
            
        except Exception as e:
            logger.exception("Error loading model: {}".format(e))
            return False
    
    def allocate_tensors(self) -> None:
        """
        Allocate tensor buffers.
        """
        try:
            if self.interpreter is not None:
                self.interpreter.allocate_tensors()
                logger.debug("Tensors allocated successfully")
        except Exception as e:
            logger.exception("Error allocating tensors: {}".format(e))
            self.handle_tensor_allocation_error()
    
    def set_input_tensor(self, tensor_data: np.ndarray) -> None:
        """
        Set input tensor for inference.
        """
        try:
            if not self.is_initialized:
                return
            
            # Set input data
            self.interpreter.set_tensor(self.input_details[0]['index'], tensor_data)
        except Exception as e:
            logger.exception("Error setting input tensor: {}".format(e))
    
    def invoke_inference(self) -> None:
        """
        Run YOLO inference.
        """
        try:
            if not self.is_initialized:
                return
            
            start_time = time.time()
            self.interpreter.invoke()
            inference_time = (time.time() - start_time) * 1000
            logger.debug("Inference completed in {:.1f}ms".format(inference_time))
            
        except Exception as e:
            logger.exception("Error during inference: {}".format(e))
            self.handle_tensor_allocation_error()
    
    def get_output_boxes(self) -> List[Dict]:
        """
        Extract detection boxes from YOLO output.
        """
        try:
            if not self.is_initialized:
                return []
            
            # Get output tensor
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # YOLOv11 output is typically (1, 84, 8400) or (1, 8400, 84)
            # If (1, 84, 8400), transpose to (1, 8400, 84)
            if output_data.shape[1] < output_data.shape[2]:
                output_data = output_data.transpose(0, 2, 1)
            
            # Remove batch dimension: (8400, 84)
            predictions = output_data[0]
            
            # Extract boxes and scores
            boxes = predictions[:, :4]  # [x_center, y_center, width, height]
            scores = predictions[:, 4:]  # Class scores
            
            # Get max score and class ID for each box
            class_ids = np.argmax(scores, axis=1)
            max_scores = np.max(scores, axis=1)
            
            # Filter by confidence threshold
            mask = max_scores > self.CONFIDENCE_THRESHOLD
            boxes = boxes[mask]
            max_scores = max_scores[mask]
            class_ids = class_ids[mask]
            
            if len(boxes) == 0:
                return []
            
            # Convert [x_center, y_center, w, h] to [x1, y1, x2, y2]
            # Coordinates are usually normalized [0, 640]
            results = []
            for i in range(len(boxes)):
                x, y, w, h = boxes[i]
                x1 = x - w/2
                y1 = y - h/2
                x2 = x + w/2
                y2 = y + h/2
                
                results.append({
                    "class_id": int(class_ids[i]),
                    "confidence": float(max_scores[i]),
                    "bbox": [float(x1), float(y1), float(w), float(h)],
                    "category": self.classes[class_ids[i]] if class_ids[i] < len(self.classes) else "unknown"
                })
            
            # Apply NMS (Non-Maximum Suppression)
            indices = cv2.dnn.NMSBoxes(
                [r["bbox"] for r in results],
                [r["confidence"] for r in results],
                self.CONFIDENCE_THRESHOLD,
                self.IOU_THRESHOLD
            )
            
            final_results = []
            if len(indices) > 0:
                for i in indices.flatten():
                    final_results.append(results[i])
            
            return final_results
            
        except Exception as e:
            logger.exception("Error extracting output boxes: {}".format(e))
            return []
    
    def handle_tensor_allocation_error(self) -> None:
        """
        Handle tensor allocation/inference errors.
        """
        logger.critical("Tensor error detected, resetting interpreter")
        self.is_initialized = False
        self.interpreter = None
        # Attempt to reload model
        self.load_model_mmap()

import cv2 # Required for NMSBoxes

if __name__ == "__main__":
    logger.info("YoloTfliteEngine - Test Entry Point")
    engine = YoloTfliteEngine()
    engine.load_model_mmap()
