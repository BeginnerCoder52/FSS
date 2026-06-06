"""
main.py - FRTApp Main Entry Point
Version: 1.0

Purpose:
    Command-line entry point for FRTApp daemon.
    Handles systemd integration, signal handling, and lifecycle management.

Usage:
    python3 main.py [--debug] [--camera /dev/video0] [--model path/to/model.tflite]

Environment Variables:
    FRT_DEBUG: Enable debug logging
    FRT_CAMERA_DEVICE: Override camera device path
    FRT_MODEL_PATH: Override model file path
    
Author: FSS Project Team
License: Proprietary
"""

import sys
import os
import signal
import argparse
from pathlib import Path
import logging
from loguru import logger

# Import FRTApp components
from FrtMain import FrtMain, AppState

# ============================================================================
# GLOBAL STATE
# ============================================================================
app_instance: FrtMain = None
should_exit = False

# ============================================================================
# SIGNAL HANDLERS (ASPICE requirement: Graceful shutdown)
# ============================================================================

def signal_handler(signum, frame):
    """
    Handle OS signals for graceful shutdown.
    
    Signals:
        - SIGTERM: Graceful shutdown (systemd stop)
        - SIGINT: Keyboard interrupt (Ctrl+C)
        - SIGHUP: Hangup (terminal closed)
    """
    global should_exit, app_instance
    
    signal_names = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT",
        signal.SIGHUP: "SIGHUP"
    }
    
    logger.info("Received signal: {} ({})".format(signal_names.get(signum, signum), signum))
    
    should_exit = True
    
    if app_instance:
        app_instance.stop_daemon()

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """
    FRTApp main function.
    
    Process:
        1. Parse command-line arguments
        2. Setup logging
        3. Create FrtMain instance
        4. Initialize pipeline
        5. Start daemon
        6. Wait for shutdown signal
        7. Cleanup resources
    
    Returns:
        int: Exit code (0 = success, 1 = error)
    """
    global app_instance
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="FRTApp - Food Recognition Tracking Application",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    parser.add_argument("--camera", default="/dev/video0",
                       help="Camera device path (default: /dev/video0)")
    parser.add_argument("--model", default="/opt/fss/models/YOLOv11n_260518_best_int8.tflite",
                       help="YOLO model path (default: YOLOv11n_260518_best_int8.tflite)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Logging level (default: INFO)")
    parser.add_argument("--use-c-backend", action="store_true",
                       help="Use C TFLite reader for inference (faster on Pi 4B)")
    parser.add_argument("--c-model-path", default="/opt/fss/models/YOLOv11n_260518_best_int8.tflite",
                       help="Model path for C reader (default: YOLOv11n_260518_best_int8.tflite)")
    parser.add_argument("--model-precision", choices=["fp32", "fp16", "int8"], default="int8",
                       help="Model quantization precision (default: int8)")
    parser.add_argument("--debug-no-distance", action="store_true",
                       help="Disable distance sensor dependency - camera activates on door open alone")
    parser.add_argument("--distance-threshold", type=float, default=60.0,
                       help="Distance threshold in cm (default: 60.0)")
    parser.add_argument("--bypass-door-sensor", action="store_true",
                       help="Bypass MC-38 door sensor (auto-enter TRACKING on start)")
    parser.add_argument("--no-bypass-door-sensor", action="store_true",
                       help="Disable bypass (wait for MC-38 door open signal)")
    parser.add_argument("--confidence", type=float, default=0.85,
                       help="Detection confidence threshold (0.0-1.0, default: 0.85)")
    parser.add_argument("--boundary-y", type=float, default=0.66,
                       help="Virtual boundary as fraction of frame height (default: 0.66)")

    args = parser.parse_args()
    
    # ========================================================================
    # LOGGING SETUP
    # ========================================================================
    
    # Remove default handler
    logger.remove()
    
    # Add console logger
    log_level = "DEBUG" if args.debug else args.log_level
    logger.add(sys.stderr, level=log_level,
               format="<level>{time:YYYY-MM-DD HH:mm:ss.SSS}</level> | "
                      "<level>{level: <8}</level> | "
                      "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                      "<level>{message}</level>")
    
    # Add file logger (rotated daily)
    log_file_path = Path("/var/log/frt_app.log")
    if not log_file_path.parent.exists():
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_file_path = Path.cwd() / "frt_app.log"

    try:
        logger.add(str(log_file_path), level="INFO", rotation="00:00",
                   format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                          "{name}:{function}:{line} - {message}")
    except PermissionError:
        fallback_file = Path.cwd() / "frt_app.log"
        logger.warning("Unable to write to /var/log/frt_app.log, using {}", fallback_file)
        logger.add(str(fallback_file), level="INFO", rotation="00:00",
                   format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                          "{name}:{function}:{line} - {message}")
    
    logger.info("=" * 80)
    logger.info("FRTApp - Food Recognition Tracking Application")
    logger.info("Version: 1.0 (SDD v1.1.0)")
    logger.info("=" * 80)
    logger.info("Camera device: {}".format(args.camera))
    logger.info("Model path: {}".format(args.model))
    logger.info("Log level: {}".format(log_level))
    logger.info("Debug mode: {}".format("ON" if args.debug else "OFF"))
    logger.info("C backend: {}".format("ON" if args.use_c_backend else "OFF"))
    logger.info("Distance sensor: {}".format("OFF (debug)" if args.debug_no_distance else "ON"))
    logger.info("Distance threshold: {} cm".format(args.distance_threshold))
    bypass = args.bypass_door_sensor and not args.no_bypass_door_sensor
    logger.info("Door sensor bypass: {}".format("ON (auto-TRACKING)" if bypass else "OFF (wait for MC-38)"))
    logger.info("Confidence threshold: {}".format(args.confidence))
    logger.info("Boundary Y ratio: {}".format(args.boundary_y))
    
    # ========================================================================
    # SIGNAL HANDLERS
    # ========================================================================
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    
    logger.info("Signal handlers registered")
    
    # ========================================================================
    # APPLICATION INITIALIZATION
    # ========================================================================
    
    try:
        logger.info("Creating FrtMain instance...")
        app_instance = FrtMain(bypass_door_sensor=bypass,
                               confidence_threshold=args.confidence,
                               boundary_ratio=args.boundary_y)
        
        # Override camera device if provided
        app_instance.CAMERA_DEVICE = args.camera
        app_instance.MODEL_PATH = args.model
        app_instance.use_c_backend = args.use_c_backend
        app_instance.c_model_path = args.c_model_path
        app_instance.model_precision = args.model_precision
        app_instance.distance_sensor_enabled = not args.debug_no_distance
        app_instance.distance_threshold_cm = args.distance_threshold
        
        # Initialize pipeline
        logger.info("Initializing pipeline...")
        if not app_instance.init_pipeline():
            logger.error("Pipeline initialization failed")
            return 1
        
        logger.info("Pipeline initialized successfully")
        
        # Start daemon
        logger.info("Starting daemon...")
        app_instance.start_daemon()
        
        logger.info("FRTApp daemon started successfully")
        logger.info("Waiting for events (Ctrl+C to stop)...")
        
        # ====================================================================
        # MAIN LOOP (Wait for shutdown signal)
        # ====================================================================
        
        import time
        while not should_exit:
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt detected")
                break
        
        # ====================================================================
        # CLEANUP
        # ====================================================================
        
        logger.info("Shutting down FRTApp daemon...")
        app_instance.stop_daemon()
        logger.info("FRTApp daemon stopped successfully")
        
        logger.info("=" * 80)
        logger.info("FRTApp exited normally")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.exception("Fatal error: {}".format(e))
        if app_instance:
            try:
                app_instance.stop_daemon()
            except:
                pass
        return 1

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    sys.exit(main())
