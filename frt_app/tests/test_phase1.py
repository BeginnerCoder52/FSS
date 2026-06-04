#!/usr/bin/env python3
"""
test_phase1.py - Phase 1 Unit Tests for FRTApp Components
Version: 1.0

Purpose:
    Test all Python AI core components individually before integration testing.
    Verifies API signatures, error handling, and basic functionality.

Test Suite:
    1. FrtMain - Application controller
    2. FrtDbusInterface - D-Bus communication
    3. CameraUvcDriver - Camera operations
    4. ImagePreprocessor - Image processing
    5. MotionDetector - Motion detection
    6. YoloTfliteEngine - Model inference

Usage:
    python3 test_phase1.py [--verbose]

Author: FSS Project Team
License: Proprietary
"""

import sys
import os
import time
from pathlib import Path
import numpy as np
from loguru import logger

FRT_SRC = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if FRT_SRC not in sys.path:
    sys.path.insert(0, FRT_SRC)

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO",
           format="<level>{time:HH:mm:ss}</level> | <level>{level: <8}</level> | {message}")

# ============================================================================
# TEST UTILITIES
# ============================================================================

class TestResult:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.tests = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        self.tests.append(("✓ PASS", test_name))
        logger.info("✓ PASS: {}".format(test_name))
    
    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.tests.append(("✗ FAIL", test_name, error))
        logger.error("✗ FAIL: {} - {}".format(test_name, error))
    
    def add_warn(self, test_name: str, message: str):
        self.warnings += 1
        self.tests.append(("⚠ WARN", test_name, message))
        logger.warning("⚠ WARN: {} - {}".format(test_name, message))
    
    def summary(self):
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info("Passed:  {}".format(self.passed))
        logger.info("Failed:  {}".format(self.failed))
        logger.info("Warnings: {}".format(self.warnings))
        logger.info("Total:   {}".format(self.passed + self.failed + self.warnings))
        logger.info("=" * 80)
        
        return self.failed == 0

# Global result tracker
results = TestResult()

# ============================================================================
# TEST 1: FrtMain - Application Controller
# ============================================================================

def test_frtmain():
    """Test FrtMain class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.1: FrtMain Application Controller")
    logger.info("=" * 80)
    
    try:
        from FrtMain import FrtMain, AppState
        
        # Test 1: Instantiation
        try:
            app = FrtMain()
            results.add_pass("FrtMain.init()")
        except Exception as e:
            results.add_fail("FrtMain.init()", str(e))
            return
        
        # Test 2: Initial state
        try:
            assert app.current_state == AppState.INIT.value
            assert app.is_running == False
            results.add_pass("FrtMain.initial_state")
        except AssertionError as e:
            results.add_fail("FrtMain.initial_state", "Invalid initial state")
        
        # Test 3: init_pipeline() signature
        try:
            result = app.init_pipeline()
            assert isinstance(result, bool)
            results.add_pass("FrtMain.init_pipeline() -> bool")
        except Exception as e:
            results.add_fail("FrtMain.init_pipeline()", str(e))
        
        # Test 4: start_daemon() signature
        try:
            app.start_daemon()  # Should not raise
            results.add_pass("FrtMain.start_daemon() -> None")
        except Exception as e:
            results.add_fail("FrtMain.start_daemon()", str(e))
        
        # Test 5: on_door_event_received() signature
        try:
            app.on_door_event_received("OPEN")
            results.add_pass("FrtMain.on_door_event_received()")
        except Exception as e:
            results.add_fail("FrtMain.on_door_event_received()", str(e))
        
        # Test 6: stop_daemon() signature
        try:
            app.stop_daemon()
            results.add_pass("FrtMain.stop_daemon() -> None")
        except Exception as e:
            results.add_fail("FrtMain.stop_daemon()", str(e))
        
        # Test 7: log_pipeline_metrics() signature
        try:
            app.log_pipeline_metrics(30.0, 50.0)
            results.add_pass("FrtMain.log_pipeline_metrics()")
        except Exception as e:
            results.add_fail("FrtMain.log_pipeline_metrics()", str(e))
        
    except ImportError as e:
        results.add_fail("FrtMain", "Import error: {}".format(e))

# ============================================================================
# TEST 2: FrtDbusInterface - D-Bus Communication
# ============================================================================

def test_frtidbusinterface():
    """Test FrtDbusInterface class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.2: FrtDbusInterface D-Bus Communication")
    logger.info("=" * 80)
    
    try:
        from FrtDbusInterface import FrtDbusInterface
        
        # Test 1: Instantiation
        try:
            interface = FrtDbusInterface()
            results.add_pass("FrtDbusInterface.init()")
        except Exception as e:
            results.add_fail("FrtDbusInterface.init()", str(e))
            return
        
        # Test 2: Service names
        try:
            assert interface.SERVICE_NAME == "vn.edu.uit.FSS.FRTApp"
            assert interface.INTERFACE_NAME == "vn.edu.uit.FSS.FRTApp"
            results.add_pass("FrtDbusInterface.constants")
        except AssertionError:
            results.add_fail("FrtDbusInterface.constants", "Incorrect service names")
        
        # Test 3: init_sdbus_connection() signature
        try:
            result = interface.init_sdbus_connection()
            assert isinstance(result, bool)
            results.add_pass("FrtDbusInterface.init_sdbus_connection() -> bool")
        except Exception as e:
            results.add_fail("FrtDbusInterface.init_sdbus_connection()", str(e))
        
        # Test 4: subscribe_door_events() signature
        try:
            def dummy_callback(state):
                pass
            
            interface.subscribe_door_events(dummy_callback)
            results.add_pass("FrtDbusInterface.subscribe_door_events()")
        except Exception as e:
            results.add_fail("FrtDbusInterface.subscribe_door_events()", str(e))
        
        # Test 5: publish_tracking_results() signature
        try:
            test_data = {"food_items": [], "timestamp": time.time()}
            interface.publish_tracking_results(test_data)
            results.add_pass("FrtDbusInterface.publish_tracking_results()")
        except Exception as e:
            results.add_fail("FrtDbusInterface.publish_tracking_results()", str(e))
        
        # Test 6: handle_dbus_timeout() signature
        try:
            interface.handle_dbus_timeout()
            results.add_pass("FrtDbusInterface.handle_dbus_timeout()")
        except Exception as e:
            results.add_fail("FrtDbusInterface.handle_dbus_timeout()", str(e))
        
        # Test 7: reconnect_bus() signature
        try:
            result = interface.reconnect_bus()
            assert isinstance(result, bool)
            results.add_pass("FrtDbusInterface.reconnect_bus() -> bool")
        except Exception as e:
            results.add_fail("FrtDbusInterface.reconnect_bus()", str(e))
        
    except ImportError as e:
        results.add_fail("FrtDbusInterface", "Import error: {}".format(e))

# ============================================================================
# TEST 3: CameraUvcDriver - Camera Operations
# ============================================================================

def test_camerauvcdriver():
    """Test CameraUvcDriver class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.3: CameraUvcDriver USB Camera")
    logger.info("=" * 80)
    
    try:
        from CameraUvcDriver import CameraUvcDriver
        
        # Test 1: Instantiation
        try:
            driver = CameraUvcDriver("/dev/video0")
            results.add_pass("CameraUvcDriver.init()")
        except Exception as e:
            results.add_fail("CameraUvcDriver.init()", str(e))
            return
        
        # Test 2: check_uvc_connection() - Real hardware check
        try:
            result = driver.check_uvc_connection()
            assert isinstance(result, bool)
            if not result:
                results.add_fail("CameraUvcDriver.check_uvc_connection()",
                               "/dev/video0 not found")
            else:
                results.add_pass("CameraUvcDriver.check_uvc_connection()")
        except Exception as e:
            results.add_fail("CameraUvcDriver.check_uvc_connection()", str(e))
        
        # Test 3: open_camera_stream() - Real camera stream
        try:
            result = driver.open_camera_stream()
            assert isinstance(result, bool)
            if not result:
                results.add_fail("CameraUvcDriver.open_camera_stream()",
                               "Failed to open /dev/video0 stream")
            else:
                results.add_pass("CameraUvcDriver.open_camera_stream()")
        except Exception as e:
            results.add_fail("CameraUvcDriver.open_camera_stream()", str(e))
        
        # Test 4: read_frame() — verify actual frame data from real camera
        try:
            frame = driver.read_frame()
            import numpy as np
            if frame is not None and isinstance(frame, np.ndarray):
                assert frame.shape[-1] == 3, "Expected 3-channel BGR frame"
                assert frame.dtype == np.uint8, "Expected uint8 frame"
                results.add_pass("CameraUvcDriver.read_frame()",
                               "shape={}, dtype={}".format(frame.shape, frame.dtype))
            else:
                results.add_fail("CameraUvcDriver.read_frame()",
                               "frame is None (camera not open or no data)")
        except Exception as e:
            results.add_fail("CameraUvcDriver.read_frame()", str(e))
        
        # Test 5: release_camera()
        try:
            driver.release_camera()
            results.add_pass("CameraUvcDriver.release_camera()")
        except Exception as e:
            results.add_fail("CameraUvcDriver.release_camera()", str(e))
        
        # Test 6: reset_usb_bus() signature
        try:
            driver.reset_usb_bus()
            results.add_pass("CameraUvcDriver.reset_usb_bus()")
        except Exception as e:
            results.add_fail("CameraUvcDriver.reset_usb_bus()", str(e))
        
    except ImportError as e:
        results.add_fail("CameraUvcDriver", "Import error: {}".format(e))

# ============================================================================
# TEST 4: ImagePreprocessor - Image Processing
# ============================================================================

def test_imagepreprocessor():
    """Test ImagePreprocessor class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.4: ImagePreprocessor Image Processing")
    logger.info("=" * 80)
    
    try:
        from ImagePreprocessor import ImagePreprocessor
        
        # Test 1: Instantiation
        try:
            preprocessor = ImagePreprocessor(640, 640)
            results.add_pass("ImagePreprocessor.init()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.init()", str(e))
            return
        
        # Create dummy frame (480, 640, 3) BGR
        dummy_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        
        # Test 2: convert_bgr_to_rgb()
        try:
            rgb = preprocessor.convert_bgr_to_rgb(dummy_frame)
            assert rgb is not None
            assert rgb.shape == dummy_frame.shape
            results.add_pass("ImagePreprocessor.convert_bgr_to_rgb()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.convert_bgr_to_rgb()", str(e))
        
        # Test 3: resize_frame()
        try:
            resized = preprocessor.resize_frame(dummy_frame)
            assert resized is not None
            assert resized.shape == (640, 640, 3)
            results.add_pass("ImagePreprocessor.resize_frame()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.resize_frame()", str(e))
        
        # Test 4: normalize_pixels()
        try:
            normalized = preprocessor.normalize_pixels(dummy_frame)
            assert normalized is not None
            assert normalized.dtype == np.float32
            assert normalized.min() >= 0.0 and normalized.max() <= 1.0
            results.add_pass("ImagePreprocessor.normalize_pixels()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.normalize_pixels()", str(e))
        
        # Test 5: prepare_tensor_input() - Full pipeline
        try:
            tensor = preprocessor.prepare_tensor_input(dummy_frame)
            assert tensor is not None
            assert tensor.shape == (1, 640, 640, 3)
            assert tensor.dtype == np.float32
            results.add_pass("ImagePreprocessor.prepare_tensor_input()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.prepare_tensor_input()", str(e))
        
        # Test 6: catch_shape_error()
        try:
            preprocessor.catch_shape_error((1, 2, 3, 4))
            results.add_pass("ImagePreprocessor.catch_shape_error()")
        except Exception as e:
            results.add_fail("ImagePreprocessor.catch_shape_error()", str(e))
        
    except ImportError as e:
        results.add_fail("ImagePreprocessor", "Import error: {}".format(e))

# ============================================================================
# TEST 5: MotionDetector - Motion Detection
# ============================================================================

def test_motiondetector():
    """Test MotionDetector class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.5: MotionDetector Background Subtraction")
    logger.info("=" * 80)
    
    try:
        from MotionDetector import MotionDetector
        
        # Test 1: Instantiation
        try:
            detector = MotionDetector(threshold_percent=1.0)
            results.add_pass("MotionDetector.init()")
        except Exception as e:
            results.add_fail("MotionDetector.init()", str(e))
            return
        
        # Test 2: init_mog2()
        try:
            detector.init_mog2()
            results.add_pass("MotionDetector.init_mog2()")
        except Exception as e:
            results.add_fail("MotionDetector.init_mog2()", str(e))
        
        # Create dummy frames
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 100
        
        # Test 3: apply_background_subtraction()
        try:
            mask = detector.apply_background_subtraction(frame1)
            assert mask is not None
            results.add_pass("MotionDetector.apply_background_subtraction()")
        except Exception as e:
            results.add_fail("MotionDetector.apply_background_subtraction()", str(e))
        
        # Test 4: is_motion_detected()
        try:
            mask2 = detector.apply_background_subtraction(frame2)
            motion = detector.is_motion_detected(mask2)
            assert isinstance(motion, bool)
            results.add_pass("MotionDetector.is_motion_detected()")
        except Exception as e:
            results.add_fail("MotionDetector.is_motion_detected()", str(e))
        
        # Test 5: reset_background_model()
        try:
            detector.reset_background_model()
            results.add_pass("MotionDetector.reset_background_model()")
        except Exception as e:
            results.add_fail("MotionDetector.reset_background_model()", str(e))
        
    except ImportError as e:
        results.add_fail("MotionDetector", "Import error: {}".format(e))

# ============================================================================
# TEST 6: YoloTfliteEngine - Model Inference
# ============================================================================

def test_yolotfliteengine():
    """Test YoloTfliteEngine class"""
    logger.info("=" * 80)
    logger.info("TEST PHASE 1.6: YoloTfliteEngine YOLO Inference")
    logger.info("=" * 80)
    
    try:
        from YoloTfliteEngine import YoloTfliteEngine
        
        # Test 1: Instantiation
        try:
            engine = YoloTfliteEngine("/opt/fss/models/yolov11n.tflite")
            results.add_pass("YoloTfliteEngine.init()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.init()", str(e))
            return
        
        # Test 2: load_model_mmap() — Real model at /opt/fss/models/yolov11n.tflite
        try:
            result = engine.load_model_mmap()
            assert isinstance(result, bool)
            if not result:
                results.add_fail("YoloTfliteEngine.load_model_mmap()",
                               "Failed to load model from /opt/fss/models/yolov11n.tflite")
            else:
                results.add_pass("YoloTfliteEngine.load_model_mmap()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.load_model_mmap()", str(e))
        
        # Test 3: allocate_tensors()
        try:
            engine.allocate_tensors()
            assert engine.is_initialized
            results.add_pass("YoloTfliteEngine.allocate_tensors()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.allocate_tensors()", str(e))
        
        # Test 4: set_input_tensor()
        try:
            dummy_tensor = np.random.rand(1, 640, 640, 3).astype(np.float32)
            engine.set_input_tensor(dummy_tensor)
            results.add_pass("YoloTfliteEngine.set_input_tensor()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.set_input_tensor()", str(e))
        
        # Test 5: invoke_inference() — Real inference on random input
        try:
            engine.invoke_inference()
            results.add_pass("YoloTfliteEngine.invoke_inference()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.invoke_inference()", str(e))
        
        # Test 6: get_output_boxes() — Verify real model output structure
        try:
            boxes = engine.get_output_boxes()
            assert isinstance(boxes, list)
            if boxes:
                b = boxes[0]
                assert "class_id" in b
                assert "confidence" in b
                assert "bbox" in b
                assert len(b["bbox"]) == 4
                results.add_pass("YoloTfliteEngine.get_output_boxes()",
                               "{} detections".format(len(boxes)))
            else:
                results.add_pass("YoloTfliteEngine.get_output_boxes()",
                               "0 detections on random input (expected)")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.get_output_boxes()", str(e))
        
        # Test 7: handle_tensor_allocation_error()
        try:
            engine.handle_tensor_allocation_error()
            results.add_pass("YoloTfliteEngine.handle_tensor_allocation_error()")
        except Exception as e:
            results.add_fail("YoloTfliteEngine.handle_tensor_allocation_error()", str(e))
        
    except ImportError as e:
        results.add_fail("YoloTfliteEngine", "Import error: {}".format(e))

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all Phase 1 tests"""
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 15 + "FRTApp PHASE 1 UNIT TESTS" + " " * 39 + "║")
    logger.info("║" + " " * 18 + "Python AI Core Components" + " " * 37 + "║")
    logger.info("║" + " " * 20 + "(SDD v1.1.0 Compliance)" + " " * 37 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")
    
    # Run all tests
    test_frtmain()
    test_frtidbusinterface()
    test_camerauvcdriver()
    test_imagepreprocessor()
    test_motiondetector()
    test_yolotfliteengine()
    
    # Print summary
    success = results.summary()
    
    if success:
        logger.info("")
        logger.info("✓ ALL TESTS PASSED - PHASE 1 READY FOR NEXT STAGE")
        logger.info("")
        return 0
    else:
        logger.info("")
        logger.error("✗ SOME TESTS FAILED - REVIEW ERRORS ABOVE")
        logger.info("")
        return 1

if __name__ == "__main__":
    sys.exit(main())
