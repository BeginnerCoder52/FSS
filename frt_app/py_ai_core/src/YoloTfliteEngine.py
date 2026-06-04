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

import cv2
import numpy as np
import os
import time
import ctypes
from typing import List, Dict, Optional, Tuple
from loguru import logger

class YoloTfliteEngine:
    """
    YOLOv11 TFLite Inference Engine
    """
    
<<<<<<< HEAD
    # Model path (placeholder until YOLO model available)
    DEFAULT_MODEL_PATH = os.environ.get(
        "FSS_MODEL_PATH",
        "/opt/fss/models/yolov11n.tflite"
    )
=======
    DEFAULT_MODEL_PATH = "/opt/fss/models/yolov11n_fp32.tflite"
>>>>>>> f3aa189ce70fa84f2aa6a83396ea4f388804e2fb
    
    # Inference parameters
    CONFIDENCE_THRESHOLD = 0.60      # Minimum confidence for detection
    IOU_THRESHOLD = 0.45             # NMS IoU threshold
    
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, use_c_backend: bool = True,
                 c_precision: int = 2):
        """
        Initialize YOLO TFLite engine.
        """
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.is_initialized = False
        self.use_c_backend = use_c_backend
        self._c_lib = None
        self._c_reader = None
        self._c_input_size = 0
        self._input_tensor = None
        
        # Class names (example for food items)
        self.classes = ["food_item"] # To be updated with actual model classes
        
        if self.use_c_backend:
            self._init_c_backend()
        
        logger.info("YoloTfliteEngine initialized (model={})".format(model_path))
    
    def _init_c_backend(self) -> None:
        """
        Initialize C backend via ctypes (optional, fallback to Python on failure).
        """
        try:
            self._c_lib = ctypes.CDLL("libtflite_reader.so")

            self._c_lib.tflite_reader_create.argtypes = [ctypes.c_char_p, ctypes.c_int]
            self._c_lib.tflite_reader_create.restype = ctypes.c_void_p

            self._c_lib.tflite_reader_get_input_dims.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int
            ]
            self._c_lib.tflite_reader_get_input_dims.restype = ctypes.c_int

            self._c_lib.tflite_reader_get_input_size.argtypes = [ctypes.c_void_p]
            self._c_lib.tflite_reader_get_input_size.restype = ctypes.c_int

            self._c_lib.tflite_reader_run_inference.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t
            ]
            self._c_lib.tflite_reader_run_inference.restype = ctypes.c_int

            self._c_lib.tflite_reader_get_output.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
            ]
            self._c_lib.tflite_reader_get_output.restype = ctypes.POINTER(ctypes.c_float)

            self._c_lib.tflite_reader_get_precision.argtypes = [ctypes.c_void_p]
            self._c_lib.tflite_reader_get_precision.restype = ctypes.c_int

            self._c_lib.tflite_reader_destroy.argtypes = [ctypes.c_void_p]
            self._c_lib.tflite_reader_destroy.restype = None

            logger.info("C TFLite backend library loaded successfully")
        except Exception as e:
            logger.warning("C backend unavailable ({}), falling back to Python".format(e))
            self.use_c_backend = False
            self._c_lib = None

    def load_model_mmap(self) -> bool:
        """
        Load TFLite model using memory mapping.
        """
        logger.info("Loading YOLOv11 model: {}".format(self.model_path))
        
        if self.use_c_backend and self._c_lib:
            return self._load_model_c()
        
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
    
    def _load_model_c(self) -> bool:
        """
        Load model using C TFLite reader backend.
        """
        try:
            precision_enum = 2
            model_path_bytes = self.model_path.encode('utf-8')
            self._c_reader = self._c_lib.tflite_reader_create(model_path_bytes, precision_enum)
            if not self._c_reader:
                logger.error("C reader returned NULL, falling back to Python")
                self.use_c_backend = False
                return False

            dims_arr = (ctypes.c_int * 4)()
            num_dims = self._c_lib.tflite_reader_get_input_dims(
                self._c_reader, dims_arr, 4
            )
            if num_dims < 0:
                logger.error("C reader failed to get input dims")
                self.use_c_backend = False
                return False

            self._c_input_size = self._c_lib.tflite_reader_get_input_size(self._c_reader)
            if self._c_input_size < 0:
                logger.error("C reader failed to get input size")
                self.use_c_backend = False
                return False

            self.is_initialized = True
            logger.info("Model loaded via C backend ({} bytes input)".format(self._c_input_size))
            return True
        except Exception as e:
            logger.warning("C backend load failed ({}), falling back to Python".format(e))
            self.use_c_backend = False
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

            self._input_tensor = tensor_data

            if self.use_c_backend and self._c_lib and self._c_reader:
                return

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

            if self.use_c_backend and self._c_lib and self._c_reader:
                start_time = time.time()
                input_data = self._input_tensor.ctypes.data_as(ctypes.c_void_p)
                ret = self._c_lib.tflite_reader_run_inference(
                    self._c_reader, input_data, self._c_input_size
                )
                inference_time = (time.time() - start_time) * 1000
                if ret != 0:
                    logger.error("C backend inference failed with code {}".format(ret))
                    return
                logger.debug("C inference completed in {:.1f}ms".format(inference_time))
                return
            
            start_time = time.time()
            self.interpreter.invoke()
            inference_time = (time.time() - start_time) * 1000
            logger.debug("Inference completed in {:.1f}ms".format(inference_time))
            
        except Exception as e:
            logger.exception("Error during inference: {}".format(e))
            self.handle_tensor_allocation_error()
    
    def _get_output_boxes_c(self) -> List[Dict]:
        """
        Extract detection boxes from C backend output.
        """
        try:
            num_out = ctypes.c_int(0)
            out_ptr = self._c_lib.tflite_reader_get_output(self._c_reader, ctypes.byref(num_out))
            if not out_ptr or num_out.value <= 0:
                logger.warning("C backend returned no output")
                return []

            num_elements = num_out.value
            out_array = np.ctypeslib.as_array(out_ptr, shape=(num_elements,)).copy()

            YOLO_GRID_CELLS = 8400
            actual_per_det = num_elements // YOLO_GRID_CELLS
            num_classes = actual_per_det - 4

            if num_elements % YOLO_GRID_CELLS != 0 or num_classes <= 0:
                logger.warning("C output size {}: expected multiple of {}, got {} values per det ({} classes)".format(
                    num_elements, YOLO_GRID_CELLS, actual_per_det, num_classes))
                return []

            num_detections = YOLO_GRID_CELLS
            output_data = out_array.reshape(num_detections, actual_per_det)

            boxes = output_data[:, :4]
            scores = output_data[:, 4:]

            if scores.max() > 1.0:
                scores = 1.0 / (1.0 + np.exp(-np.clip(scores, -15, 15)))

            class_ids = np.argmax(scores, axis=1)
            max_scores = np.max(scores, axis=1)

            mask = max_scores > self.CONFIDENCE_THRESHOLD
            boxes = boxes[mask]
            max_scores = max_scores[mask]
            class_ids = class_ids[mask]

            if len(boxes) == 0:
                return []

            # Boxes are in [x_center, y_center, width, height] normalized to [0,1]
            # (YOLOv11 TFLite outputs normalized coords; if range > 2.0, it's pixel-space)
            if boxes.max() > 2.0:
                inv_size = 1.0 / 640.0
            else:
                inv_size = 1.0

            results = []
            for i in range(len(boxes)):
                xc, yc, w, h = boxes[i]
                x1 = (xc - w/2) * inv_size
                y1 = (yc - h/2) * inv_size
                x2 = (xc + w/2) * inv_size
                y2 = (yc + h/2) * inv_size

                results.append({
                    "class_id": int(class_ids[i]),
                    "confidence": float(max_scores[i]),
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "category": self.classes[class_ids[i]] if class_ids[i] < len(self.classes) else "unknown"
                })

            nms_boxes = []
            for r in results:
                bx1, by1, bx2, by2 = r["bbox"]
                nms_boxes.append([bx1, by1, bx2 - bx1, by2 - by1])

            indices = cv2.dnn.NMSBoxes(
                nms_boxes,
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
            logger.exception("Error extracting C backend output boxes: {}".format(e))
            return []

    def get_output_boxes(self) -> List[Dict]:
        """
        Extract detection boxes from YOLO output.
        """
        try:
            if not self.is_initialized:
                return []

            if self.use_c_backend and self._c_lib and self._c_reader:
                return self._get_output_boxes_c()

            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            if output_data.shape[1] < output_data.shape[2]:
                output_data = output_data.transpose(0, 2, 1)
            
            predictions = output_data[0]
            
            num_classes = predictions.shape[1] - 4
            self.classes = [f"class_{i}" for i in range(num_classes)] if num_classes != len(self.classes) else self.classes
            
            boxes = predictions[:, :4]
            scores = predictions[:, 4:]
            
            if scores.max() > 1.0:
                scores = 1.0 / (1.0 + np.exp(-np.clip(scores, -15, 15)))
            
            class_ids = np.argmax(scores, axis=1)
            max_scores = np.max(scores, axis=1)
            
            mask = max_scores > self.CONFIDENCE_THRESHOLD
            boxes = boxes[mask]
            max_scores = max_scores[mask]
            class_ids = class_ids[mask]
            
            if len(boxes) == 0:
                return []
            
            if boxes.max() > 2.0:
                inv_size = 1.0 / 640.0
            else:
                inv_size = 1.0
            
            results = []
            for i in range(len(boxes)):
                xc, yc, w, h = boxes[i]
                x1 = (xc - w/2) * inv_size
                y1 = (yc - h/2) * inv_size
                x2 = (xc + w/2) * inv_size
                y2 = (yc + h/2) * inv_size
                
                results.append({
                    "class_id": int(class_ids[i]),
                    "confidence": float(max_scores[i]),
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "category": self.classes[class_ids[i]] if class_ids[i] < len(self.classes) else "unknown"
                })
            
            nms_boxes = []
            for r in results:
                bx1, by1, bx2, by2 = r["bbox"]
                nms_boxes.append([bx1, by1, bx2 - bx1, by2 - by1])
            
            indices = cv2.dnn.NMSBoxes(
                nms_boxes,
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

if __name__ == "__main__":
    logger.info("YoloTfliteEngine - Test Entry Point")
    engine = YoloTfliteEngine()
    engine.load_model_mmap()
