"""
@file main.py
@brief Entry point for the DBDaemon application.

This module serves as the main entry point for the Fridge Supervisor System
database daemon, handling startup, configuration, and lifecycle management.

FEATURE FLAG: FRT_APP_ENABLED
Configure FRTApp integration status in PosixShmReader module.
"""

import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from DbDaemonMain import DbDaemonMain
from PosixShmReader import FRT_APP_ENABLED


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
def setup_logging(log_dir: str = "/var/log/fss") -> None:
    """
    Configure logging for DBDaemon.
    
    Sets up both console and file logging with appropriate log levels
    and formatting for production and debugging.
    
    Args:
        log_dir: Directory for log file storage
    """
    # Create log directory if needed
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Log format
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler - INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # File handler - DEBUG level with rotation
    log_file = log_path / "db_daemon.log"
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)


# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main() -> int:
    """
    Main entry point for DBDaemon application.
    
    Initializes logging, creates daemon instance, and starts the event loop.
    Handles graceful shutdown on system signals.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger("DbDaemonMain")
    
    logger.info("=" * 80)
    logger.info("FSS Database Daemon Starting")
    logger.info("=" * 80)
    logger.info(f"FRTApp Integration: {'ENABLED' if FRT_APP_ENABLED else 'DISABLED'}")
    
    daemon: Optional[DbDaemonMain] = None
    
    try:
        # Create daemon instance
        daemon = DbDaemonMain()
        
        # Initialize daemon
        if not daemon.init_daemon():
            logger.error("Failed to initialize daemon")
            return 1
        
        # Start daemon
        if not daemon.start_daemon():
            logger.error("Failed to start daemon")
            return 1
        
        logger.info("DBDaemon is running. Press Ctrl+C to stop.")
        
        # Keep main thread alive while daemon runs
        while daemon.is_running:
            try:
                import time
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        return 1
        
    finally:
        # Graceful shutdown
        if daemon:
            daemon.stop_daemon()
        
        logger.info("=" * 80)
        logger.info("FSS Database Daemon Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
