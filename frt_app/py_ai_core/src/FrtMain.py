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

import time
import threading
from enum import Enum
from typing import Optional
from loguru import logger

# Import all required modules
from ShmReader import ShmReader
from MotionDetector import MotionDetector
from ImagePreprocessor import ImagePreprocessor
from YoloTfliteEngine import YoloTfliteEngine
from FrtDbusInterface import FrtDbusInterface
from CameraUvcDriver import CameraUvcDriver

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
    MODEL_PATH = "/opt/fss/models/yolov11n.tflite"  # Model location
    CAMERA_DEVICE = "/dev/video0"      # USB camera device path

    def __init__(self):
        """
        Initialize FrtMain application controller.
        """
        self.current_state: str = AppState.INIT.value
        self.is_running: bool = False
        self.loop_interval_ms: int = self.DEFAULT_LOOP_INTERVAL_MS

        # Component instances (updated for Phase 2 - now using ShmReader instead of CameraUvcDriver)
        self.shm_reader = None  # POSIX SHM reader (from C++ camera core)
        self.camera_driver = None
        self.motion_detector = None
        self.preprocessor = None
        self.ai_engine = None
        self.dbus_interface = None
        self.tracker = None

        # State management
        self.recovery_count: int = 0
        self.frame_count: int = 0
        self._inference_thread: Optional[threading.Thread] = None

        logger.info("FrtMain initialized (state={})".format(self.current_state))

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
        logger.info("FRTApp daemon started (waiting for door event)")

    def stop_daemon(self) -> None:
        """Stop FRTApp daemon and cleanup resources."""
        logger.info("Stopping FRTApp daemon...")

        self.is_running = False
        self.current_state = AppState.STOPPED.value

        try:
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

        from YoloPipeline import ByteTrack
        self.tracker = ByteTrack(max_age=30)

        frame_count = 0
        fps_start_time = time.time()

        while self.is_running:
            try:
                loop_start = time.time()

                if self.current_state != AppState.TRACKING.value:
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

                # Tracking
                tracked = self.tracker.update(detections)

                # Publish
                if self.dbus_interface and tracked:
                    self.dbus_interface.publish_tracking_results({
                        "food_items": tracked,
                        "timestamp": time.time(),
                        "frame_id": frame_count
                    })

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

    def on_door_event_received(self, door_state: str) -> None:
        """Handle door open/close events from SensorDaemon."""
        logger.info("Door event received: {}".format(door_state))

        if door_state.upper() == "OPEN":
            if self.current_state != AppState.TRACKING.value:
                logger.info("Transitioning to TRACKING state")
                self.current_state = AppState.TRACKING.value
                if (not self.shm_reader or not self.shm_reader.is_ready()) and self.camera_driver and not self.camera_driver.is_camera_open:
                    self.camera_driver.open_camera_stream()

        elif door_state.upper() == "CLOSED":
            if self.current_state == AppState.TRACKING.value:
                logger.info("Transitioning to IDLE state")
                self.current_state = AppState.IDLE.value

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
            from YoloTfliteEngine import YoloTfliteEngine
            self.ai_engine = YoloTfliteEngine(self.MODEL_PATH)
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