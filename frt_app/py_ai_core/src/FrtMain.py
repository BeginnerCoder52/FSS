"""
FrtMain.py - FRTApp Main Application Controller
Version: 1.0
SDD v1.1.0 Compliance: All 7 APIs implemented

Purpose:
    Main application controller for Food Recognition Tracking (FRTApp).
    Manages application lifecycle, coordinates AI pipeline components,
    handles D-Bus event subscription, and implements state machine.

States:
    - INIT: Application initializing, loading models
    - IDLE: Ready but camera not streaming (door closed)
    - TRACKING: Camera streaming and inference running (door open)
    - ERROR: Error state, attempting recovery
    - STOPPED: Graceful shutdown

Key Components:
    - CameraUvcDriver: USB camera stream management
    - MotionDetector: Background subtraction filtering
    - ImagePreprocessor: Image normalization
    - YoloTfliteEngine: AI inference engine
    - FrtDbusInterface: IPC communication

Signals:
    - Subscribe: DoorStateChanged (from SensorDaemon)
    - Publish: FoodDetected (to DBDaemon)

Author: FSS Project Team
License: Proprietary
"""

import os
import time
import threading
from enum import Enum
from typing import Optional, Callable
from loguru import logger

# Import all required modules
from ShmReader import ShmReader
from MotionDetector import MotionDetector
from ImagePreprocessor import ImagePreprocessor
from YoloTfliteEngine import YoloTfliteEngine
from FrtDbusInterface import FrtDbusInterface
from CameraUvcDriver import CameraUvcDriver

# ============================================================================
# FOOD CLASS NAME RESOLUTION
# ============================================================================

# Default food class names (COCO-compatible subset + FSS custom classes)
DEFAULT_FOOD_NAMES = {
    0: "apple", 1: "carrot", 2: "egg", 3: "lemon", 4: "tomato",
    5: "banana", 6: "orange", 7: "bottle", 8: "cup", 9: "bowl",
    10: "cake", 11: "donut", 12: "sandwich", 13: "broccoli",
    14: "pizza", 15: "hot dog", 16: "milk", 17: "juice",
    18: "yogurt", 19: "cheese", 20: "meat", 21: "fish",
    22: "bread", 23: "rice", 24: "noodles", 25: "cookie",
}

CLASS_YAML_PATH = "/opt/fss/models/class.yaml"

def _load_class_labels() -> dict:
    """Load food class names from class.yaml, fallback to DEFAULT_FOOD_NAMES."""
    try:
        import yaml
        if os.path.exists(CLASS_YAML_PATH):
            with open(CLASS_YAML_PATH) as f:
                data = yaml.safe_load(f)
            names = data.get("names", {})
            if names:
                return {int(k): v for k, v in names.items()}
    except Exception:
        pass
    return dict(DEFAULT_FOOD_NAMES)


# ============================================================================
# APPLICATION STATE ENUMERATION (ASPICE-compliant state machine)
# ============================================================================
class AppState(Enum):
    """
    Application states for state machine management.
    Transitions follow ASPICE requirements for safety-critical state management.
    """
    INIT = "INIT"              # Initialization phase
    IDLE = "IDLE"              # Ready but dormant (door closed)
    AUTO_CALIBRATION = "AUTO_CALIBRATION" # Detecting virtual line before AI
    TRACKING = "TRACKING"      # Active inference (door open)
    ERROR = "ERROR"            # Error state
    STOPPED = "STOPPED"        # Shutdown


class FrtMain:
    """
    FRTApp Main Application Controller

    SDD v1.1.0 Requirements (Bảng 2 - Package FRTApp, FrtMain class):
        Attribute current_state: str - Current application state
        Attribute is_running: bool - Main loop flag
        Attribute camera_driver: CameraUvcDriver - Camera stream manager
        Attribute motion_detector: MotionDetector - Background subtraction
        Attribute preprocessor: ImagePreprocessor - Image normalization
        Attribute ai_engine: YoloTfliteEngine - Inference engine
        Attribute dbus_interface: FrtDbusInterface - D-Bus IPC

    Methods (7 total):
        ✓ init_pipeline() -> bool
        ✓ start_daemon() -> void
        ✓ stop_daemon() -> void
        ✓ run_inference_loop() -> void
        ✓ on_door_event_received(door_state: str) -> void
        ✓ recover_from_crash() -> void
        ✓ log_pipeline_metrics(fps: float, load: float) -> void
    """

    # ========================================================================
    # CONSTANTS (ASPICE: Configuration management)
    # ========================================================================
    DEFAULT_LOOP_INTERVAL_MS = 33      # ~30 FPS target frame rate
    MAX_RECOVERY_ATTEMPTS = 3          # Maximum crash recovery attempts
    MODEL_PATH = "/opt/fss/models/YOLOv11n_260518_best_int8.tflite"  # Model location
    CAMERA_DEVICE = "/dev/video0"      # USB camera device path

    def __init__(self, bypass_door_sensor: bool = True,
                 confidence_threshold: float = 0.85,
                 boundary_ratio: float = 0.66):
        """
        Initialize FrtMain application controller.

        Args:
            bypass_door_sensor: If True, auto-enter TRACKING on start (no MC-38 needed).
            confidence_threshold: Min confidence for YOLO + ByteTrack high/low split.
            boundary_ratio: Virtual boundary line position as fraction of frame height.
        """
        self.current_state: str = AppState.INIT.value
        self.is_running: bool = False
        self.loop_interval_ms: int = self.DEFAULT_LOOP_INTERVAL_MS

        # Door sensor bypass flag (True = auto-TRACKING, no MC-38; False = wait for door signal)
        self.bypass_door_sensor: bool = bypass_door_sensor

        # Component instances (updated for Phase 2 - now using ShmReader instead of CameraUvcDriver)
        self.shm_reader = None  # POSIX SHM reader (from C++ camera core)
        self.camera_driver = None
        self.motion_detector = None
        self.preprocessor = None
        self.ai_engine = None
        self.dbus_interface = None
        self.tracker = None
        self.virtual_line_detector = None
        self.virtual_line_ready = False
        self.frames_without_line = 0

        # C backend configuration (Phase 1 upgrade)
        self.use_c_backend: bool = True
        self.c_model_path: str = "/opt/fss/models/YOLOv11n_260518_best_int8.tflite"
        self.model_precision: str = "int8"

        # Distance sensor configuration (Phase 1 upgrade)
        self.distance_sensor_enabled: bool = True
        self.distance_threshold_cm: float = 60.0
        self.last_distance_cm: Optional[float] = None

        # Confidence and boundary config
        self.confidence_threshold: float = confidence_threshold
        self.boundary_ratio: float = boundary_ratio
        self._boundary_event_callback: Optional[Callable] = None

        # Food class name lookup (from class.yaml or built-in defaults)
        self.class_names: dict = _load_class_labels()

        # State management
        self.recovery_count: int = 0
        self.frame_count: int = 0
        self._inference_thread: Optional[threading.Thread] = None

        logger.info("FrtMain initialized (state={}, bypass={}, confidence={})".format(
            self.current_state, self.bypass_door_sensor, self.confidence_threshold))
        logger.info("  Food classes loaded: {} names (from {})".format(
            len(self.class_names), CLASS_YAML_PATH if os.path.exists(CLASS_YAML_PATH) else "built-in defaults"))

    def _get_food_name(self, class_id: int) -> str:
        """Resolve a numeric class_id to a human-readable food name."""
        return self.class_names.get(class_id, "food_class_{}".format(class_id))

    def init_pipeline(self) -> bool:
        """Initialize AI pipeline and all component modules."""
        logger.info("Initializing FRTApp pipeline...")

        try:
            # Step 1: Initialize D-Bus interface
            if not self._init_dbus_interface():
                logger.error("Failed to initialize D-Bus interface")
                self.current_state = AppState.ERROR.value
                return False

            # Step 2: Load AI model
            if not self._init_ai_engine():
                logger.warning("Failed to initialize AI engine - model missing. Running in degraded mode.")
                # Continue anyway since model is not provided yet

            # Step 3: Initialize SHM reader (reads frames from C++ camera core)
            if not self._init_shm_reader():
                logger.warning("SHM reader unavailable - camera core may not be running")
                # Continue anyway - graceful degradation
                
            self.camera_driver = CameraUvcDriver(self.CAMERA_DEVICE)

            # Step 4: Initialize motion detector
            if not self._init_motion_detector():
                logger.error("Failed to initialize motion detector")
                self.current_state = AppState.ERROR.value
                return False

            # Step 5: Initialize image preprocessor
            if not self._init_preprocessor():
                logger.error("Failed to initialize preprocessor")
                self.current_state = AppState.ERROR.value
                return False

            # Step 6: Subscribe to D-Bus signals
            self._subscribe_dbus_signals()

            self.current_state = AppState.IDLE.value
            self.recovery_count = 0
            logger.info("Pipeline initialization complete (state={})".format(self.current_state))
            return True

        except Exception as e:
            logger.exception("Critical error during pipeline initialization: {}".format(e))
            self.current_state = AppState.ERROR.value
            return False

    def start_daemon(self) -> None:
        """Start FRTApp daemon and inference loop."""
        logger.info("Starting FRTApp daemon...")

        if self.current_state == AppState.ERROR.value:
            logger.error("Cannot start: pipeline in ERROR state")
            return

        if self.is_running:
            logger.warning("Daemon already running")
            return

        self.is_running = True
        self.current_state = AppState.IDLE.value

        self._inference_thread = threading.Thread(
            target=self.run_inference_loop,
            name="FRT-InferenceThread",
            daemon=False
        )
        self._inference_thread.start()

        if self.bypass_door_sensor:
            self.current_state = AppState.TRACKING.value
            logger.info("BYPASS DOOR SENSOR: Auto-entered TRACKING state")
            logger.info(">>> notify start tracking: ByteTrack activated (virtual boundary line at y={})".format(
                int(480 * self.boundary_ratio)))
            logger.info(">>> Wave hand or food item in front of camera to test check-in/check-out!")
            if self.dbus_interface:
                self.dbus_interface.emit_camera_state("ON")
            if (not self.shm_reader or not self.shm_reader.is_ready()) and self.camera_driver:
                self.camera_driver.open_camera_stream()
        else:
            logger.info("FRTApp daemon started (waiting for door event)")

    def stop_daemon(self) -> None:
        """Stop FRTApp daemon and cleanup resources."""
        logger.info("Stopping FRTApp daemon...")

        self.is_running = False
        self.current_state = AppState.STOPPED.value

        try:
            if hasattr(self, 'tracker') and self.tracker and hasattr(self.tracker, 'line_detector'):
                line_det = self.tracker.line_detector
                logger.info("=" * 60)
                logger.info("BOUNDARY CROSSING SUMMARY")
                logger.info("  Boundary line: {} at pos {}".format(
                    line_det.boundary_line.get('type', '?'),
                    int(line_det.boundary_line.get('pos', 0)),
                ))
                changes = line_det.get_and_clear_changes()
                if changes:
                    logger.info("  Net quantity changes (class_id → delta):")
                    for cid, delta in changes.items():
                        logger.info("    Class {}: {:+.0f}".format(cid, delta))
                total_entries = sum(1 for v in changes.values() if v > 0) if changes else 0
                total_exits = sum(abs(v) for v in changes.values() if v < 0) if changes else 0
                logger.info("  Total entries (CHECK_IN):  {}".format(total_entries))
                logger.info("  Total exits  (CHECK_OUT): {}".format(total_exits))
                logger.info("=" * 60)

            if self.camera_driver:
                self.camera_driver.release_camera()

            if self._inference_thread and self._inference_thread.is_alive():
                self._inference_thread.join(timeout=5.0)

            logger.info("FRTApp daemon stopped gracefully")
        except Exception as e:
            logger.exception("Error during daemon shutdown: {}".format(e))

    def run_inference_loop(self) -> None:
        """Main inference loop: process frames and perform food detection."""
        logger.info("Starting inference loop")

        from ByteTracker import ByteTracker
        self.tracker = ByteTracker(max_age=30, high_thresh=self.confidence_threshold)
        
        from VirtualLineDetector import VirtualLineDetector
        self.virtual_line_detector = VirtualLineDetector()

        # If bypass enabled and no door signal triggers AUTO_CALIBRATION,
        # set a default boundary line so crossing detection works immediately.
        if self.bypass_door_sensor:
            default_y = int(480 * self.boundary_ratio)  # 480 as default frame height
            self.tracker.line_detector.boundary_line = {
                'type': 'horizontal',
                'pos': default_y
            }
            logger.info("Default boundary line set at y={} (ratio={})".format(
                default_y, self.boundary_ratio))

        frame_count = 0
        fps_start_time = time.time()

        while self.is_running:
            try:
                loop_start = time.time()

                if self.current_state not in (AppState.TRACKING.value, AppState.AUTO_CALIBRATION.value):
                    time.sleep(0.1)
                    continue

                # Capture frame
                frame = None
                if self.shm_reader and self.shm_reader.is_ready():
                    frame = self.shm_reader.read_frame()
                
                # Fallback to direct USB camera if SHM is not available
                if frame is None and self.camera_driver and self.camera_driver.is_camera_open:
                    frame = self.camera_driver.read_frame()
                elif frame is None and self.camera_driver and not self.camera_driver.is_camera_open:
                    self.camera_driver.open_camera_stream()
                    frame = self.camera_driver.read_frame()
                    
                if frame is None:
                    time.sleep(0.033)
                    continue

                # Print user instructions once at frame 5 (auto-detect mode)
                if frame_count == 5 and self.bypass_door_sensor:
                    logger.info("=" * 60)
                    logger.info("FRTApp AUTO-DETECT MODE (door sensor bypassed)")
                    logger.info("Default boundary at y={} (horizontal)".format(
                        self.tracker.line_detector.boundary_line.get('pos', '?')))
                    logger.info("  CHECK_IN  = object moves top → bottom (enter fridge)")
                    logger.info("  CHECK_OUT = object moves bottom → top (leave fridge)")
                    logger.info("Wave a hand or object past the camera to test!")
                    logger.info("=" * 60)
                    
                # ============================================================
                # Phase 1: Auto-Calibration (Run OpenCV only, yield CPU)
                # ============================================================
                if self.current_state == AppState.AUTO_CALIBRATION.value:
                    if self.virtual_line_detector is not None:
                        line_info = self.virtual_line_detector.detect_virtual_line(frame)
                        if line_info:
                            self.tracker.line_detector.set_virtual_line(line_info)
                            self.virtual_line_ready = True
                            self.current_state = AppState.TRACKING.value
                            logger.info("Auto-Calibration complete. Virtual Line saved. Transitioning to TRACKING state.")
                            logger.info(">>> notify start tracking: ByteTrack activated (virtual line at {})".format(
                                line_info.get('pos', '?')))
                            continue
                        else:
                            self.frames_without_line += 1
                            if self.frames_without_line > 5:
                                logger.warning("Auto-Calibration timeout after 5 frames, using default. Transitioning to TRACKING state.")
                                self.virtual_line_ready = True
                                self.current_state = AppState.TRACKING.value
                                logger.info(">>> notify start tracking: ByteTrack activated (default boundary)")
                                continue
                            else:
                                time.sleep(0.01)
                                continue

                # ============================================================
                # Phase 2: AI Vision Core (MOG2 + YOLO + ByteTrack + Boundary)
                # ============================================================
                # Motion detection
                motion_mask = self.motion_detector.apply_background_subtraction(frame)
                if not self.motion_detector.is_motion_detected(motion_mask):
                    continue

                # Preprocess
                tensor_input = self.preprocessor.prepare_tensor_input(frame)
                if tensor_input is None:
                    continue

                # Inference
                self.ai_engine.set_input_tensor(tensor_input)
                self.ai_engine.invoke_inference()
                detections = self.ai_engine.get_output_boxes()

                # Tracking (ByteTrack: Kalman + 2-stage + line crossing)
                tracked = self.tracker.update(detections)

                # Log boundary crossing events for user notification
                changes = self.tracker.get_quantity_change()
                for cid, delta in changes.items():
                    event_type = "CHECK_IN" if delta > 0 else "CHECK_OUT"
                    food_name = self._get_food_name(cid)
                    abs_delta = abs(delta)
                    if delta > 0:
                        logger.info(">>> ✅ CHECK_IN: {} x {} has been added to inventory".format(
                            abs_delta, food_name))
                    else:
                        logger.info(">>> ✅ CHECK_OUT: {} x {} has been removed from inventory".format(
                            abs_delta, food_name))
                    logger.info(">>> real detected checkout: {} {} (class_id={}, delta={:+d})".format(
                        abs_delta, food_name, cid, delta))
                    if self._boundary_event_callback:
                        self._boundary_event_callback({"event_type": event_type, "class_id": cid, "delta": delta})

                # Publish
                if self.dbus_interface and tracked:
                    self.dbus_interface.publish_tracking_results({
                        "food_items": tracked,
                        "timestamp": time.time(),
                        "frame_id": frame_count,
                        "boundary_events": [{
                            "track_id": t.get('track_id'),
                            "class_id": t.get('class_id'),
                            "score": t.get('confidence'),
                        } for t in tracked],
                    })

                # Write preview frame for LivePreview UI (every 3rd frame)
                if frame_count % 3 == 0:
                    try:
                        import cv2
                        preview_path = "/opt/fss/latest_preview.jpg"
                        cv2.imwrite(preview_path, frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 70])
                    except Exception:
                        pass

                frame_count += 1
                elapsed = time.time() - fps_start_time
                if elapsed >= 1.0:
                    self.log_pipeline_metrics(frame_count / elapsed, 0.0)
                    frame_count = 0
                    fps_start_time = time.time()

                loop_time = (time.time() - loop_start) * 1000
                sleep_time = max(0, self.loop_interval_ms - loop_time) / 1000.0
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.exception("Error in inference loop: {}".format(e))
                if not self.recover_from_crash():
                    self.is_running = False
                    self.current_state = AppState.ERROR.value

    def on_distance_event_received(self, distance_cm: float) -> None:
        """
        Handle distance sensor data from SensorDaemon.
        """
        self.last_distance_cm = distance_cm
        logger.debug("Distance updated: {:.1f}cm".format(distance_cm))

    def on_door_event_received(self, door_state: str) -> None:
        """Handle door open/close events from SensorDaemon."""
        # If bypass is active, ignore physical door events so MC-38 can be attached later
        if self.bypass_door_sensor:
            logger.debug("Door sensor bypassed — ignoring D-Bus door event")
            return

        logger.info("Door event received: {}".format(door_state))

        if door_state.upper() == "OPEN":
            can_track = False
            if not self.distance_sensor_enabled:
                can_track = True
            elif self.last_distance_cm is not None and self.last_distance_cm < self.distance_threshold_cm:
                can_track = True

            if can_track and self.current_state not in (AppState.TRACKING.value, AppState.AUTO_CALIBRATION.value):
                logger.info("Transitioning to AUTO_CALIBRATION state")
                self.current_state = AppState.AUTO_CALIBRATION.value
                if self.tracker:
                    self.tracker.reset()
                self.virtual_line_ready = False
                self.frames_without_line = 0
                
                if self.dbus_interface:
                    self.dbus_interface.emit_camera_state("ON")
                if (not self.shm_reader or not self.shm_reader.is_ready()) and self.camera_driver and not self.camera_driver.is_camera_open:
                    self.camera_driver.open_camera_stream()

        elif door_state.upper() == "CLOSED":
            if self.current_state == AppState.TRACKING.value:
                logger.info("Transitioning to IDLE state")
                self.current_state = AppState.IDLE.value
                if self.dbus_interface:
                    self.dbus_interface.emit_camera_state("OFF")

                if self.tracker and self.dbus_interface:
                    changes = self.tracker.get_quantity_change()
                    if changes:
                        self.dbus_interface.publish_tracking_results({
                            "food_items": [{"id": k, "qty": v} for k, v in changes.items()],
                            "timestamp": time.time(),
                            "event": "door_closed"
                        })

                if self.motion_detector:
                    self.motion_detector.reset_background_model()

                if self.camera_driver:
                    self.camera_driver.release_camera()

        else:
            logger.warning("Unknown door state: {}".format(door_state))

    def set_boundary_event_callback(self, callback: Callable) -> None:
        """Register callback fired on each new boundary crossing event."""
        self._boundary_event_callback = callback

    def recover_from_crash(self) -> bool:
        """Attempt to recover from inference crash or memory overflow."""
        self.recovery_count += 1
        logger.warning("Attempting crash recovery (attempt {}/{})".format(
            self.recovery_count, self.MAX_RECOVERY_ATTEMPTS))

        if self.recovery_count > self.MAX_RECOVERY_ATTEMPTS:
            logger.critical("Maximum recovery attempts exceeded")
            return False

        try:
            if self.recovery_count == 1 and self.ai_engine:
                self.ai_engine.handle_tensor_allocation_error()
            elif self.recovery_count == 2 and self.motion_detector:
                self.motion_detector.reset_background_model()
            elif self.recovery_count == 3 and self.camera_driver:
                self.camera_driver.reset_usb_bus()
                if self.current_state == AppState.TRACKING.value:
                    self.camera_driver.open_camera_stream()

            logger.info("Recovery attempt {} successful".format(self.recovery_count))
            return True
        except Exception as e:
            logger.exception("Recovery attempt {} failed: {}".format(self.recovery_count, e))
            return False

    def log_pipeline_metrics(self, fps: float, load: float) -> None:
        """Log performance metrics of inference pipeline."""
        fps = max(0.0, min(60.0, fps))
        load = max(0.0, min(100.0, load))
        logger.info("Pipeline Metrics | FPS: {:.2f} | Load: {:.1f}% | State: {}".format(
            fps, load, self.current_state))

    # ========================================================================
    # INTERNAL HELPER METHODS
    # ========================================================================

    def _init_dbus_interface(self) -> bool:
        """Initialize D-Bus interface for IPC communication."""
        try:
            from FrtDbusInterface import FrtDbusInterface
            self.dbus_interface = FrtDbusInterface()
            return self.dbus_interface.init_sdbus_connection()
        except Exception as e:
            logger.exception("D-Bus initialization failed: {}".format(e))
            return False

    def _init_ai_engine(self) -> bool:
        """Initialize YOLOv11 TFLite inference engine."""
        try:
            precision_map = {"fp32": 0, "fp16": 1, "int8": 2}
            c_precision = precision_map.get(self.model_precision, 2)
            from YoloTfliteEngine import YoloTfliteEngine
            self.ai_engine = YoloTfliteEngine(
                self.MODEL_PATH,
                use_c_backend=self.use_c_backend,
                c_precision=c_precision
            )
            # DO NOT override YOLO's threshold with ByteTrack's high threshold!
            # Let YOLO use its internal threshold (e.g. 0.2) to pass low-confidence boxes to ByteTrack.
            # self.ai_engine.CONFIDENCE_THRESHOLD = self.confidence_threshold
            return self.ai_engine.load_model_mmap()
        except Exception as e:
            logger.exception("AI engine initialization failed: {}".format(e))
            return False

    def _init_shm_reader(self) -> bool:
        """
        Initialize POSIX shared memory reader.
        
        ASPICE Comments:
            - Attaches to /fss_video_frame shared memory
            - Verifies C++ camera core is writing frames
            - Falls back gracefully if camera core unavailable
        
        Returns:
            true: SHM reader ready
            false: SHM reader unavailable (camera core not running)
        """
        try:
            self.shm_reader = ShmReader()
            success = self.shm_reader.attach()
            
            if success:
                logger.info("SHM reader initialized and attached")
            else:
                logger.warning("SHM reader attach failed: {}".format(self.shm_reader.last_error_))
            
            return success
        except Exception as e:
            logger.exception("SHM reader initialization failed: {}".format(e))
            return False

    def _init_motion_detector(self) -> bool:
        """Initialize motion detector with MOG2."""
        try:
            from MotionDetector import MotionDetector
            self.motion_detector = MotionDetector(threshold_percent=1.0)
            self.motion_detector.init_mog2()
            return True
        except Exception as e:
            logger.exception("Motion detector initialization failed: {}".format(e))
            return False

    def _init_preprocessor(self) -> bool:
        """Initialize image preprocessor."""
        try:
            from ImagePreprocessor import ImagePreprocessor
            self.preprocessor = ImagePreprocessor(640, 640)
            return True
        except Exception as e:
            logger.exception("Preprocessor initialization failed: {}".format(e))
            return False

    def _subscribe_dbus_signals(self) -> bool:
        """Subscribe to D-Bus signals from SensorDaemon."""
        try:
            if self.dbus_interface:
                self.dbus_interface.subscribe_door_events(self.on_door_event_received)
                if self.distance_sensor_enabled:
                    self.dbus_interface.subscribe_distance_events(self.on_distance_event_received)
            return True
        except Exception as e:
            logger.exception("D-Bus subscription failed: {}".format(e))
            return False


if __name__ == "__main__":
    logger.info("FRTApp Main Module - Test Entry Point")
    app = FrtMain()

    logger.info("=== PHASE 1: INITIALIZATION TEST ===")
    if app.init_pipeline():
        logger.info("✓ Pipeline initialization successful")
    else:
        logger.error("✗ Pipeline initialization failed")

    logger.info("=== PHASE 2: DAEMON START TEST ===")
    app.start_daemon()

    logger.info("=== PHASE 3: DOOR EVENT TEST ===")
    time.sleep(1)
    app.on_door_event_received("OPEN")
    time.sleep(2)
    app.on_door_event_received("CLOSED")

    logger.info("=== PHASE 4: DAEMON STOP TEST ===")
    app.stop_daemon()
    logger.info("Test completed")
    logger.info("Test completed")