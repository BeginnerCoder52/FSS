"""
@file DbDaemonMain.py
@brief Main application class for DBDaemon lifecycle management.

This module coordinates initialization, execution, and lifecycle management
of the database daemon, managing all sub-components including database operations,
D-Bus communication, and event processing.

Following ASPICE principles with comprehensive error handling and state management.
"""

import logging
import signal
import threading
import time
from typing import Optional
from enum import Enum

from SqliteManager import SqliteManager
from PosixShmReader import PosixShmReader, FRT_APP_ENABLED
from DiskFileManager import DiskFileManager
from DbDbusInterface import DbDbusInterface


class DaemonState(Enum):
    """Enumeration of possible daemon states."""
    INIT = "INIT"
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class DbDaemonMain:
    """
    Main application class for the DBDaemon component.
    
    Coordinates initialization, execution, and lifecycle management of the database
    daemon, managing all sub-components including database operations, D-Bus 
    communication, and event processing.
    """

    # Configuration constants
    MAIN_LOOP_INTERVAL_MS = 1000  # 1 second main loop interval
    
    def __init__(self):
        """Initialize DbDaemonMain instance."""
        # State management
        self.current_state: DaemonState = DaemonState.INIT
        self.is_running: bool = False
        
        # Component instances
        self.db_manager: Optional[SqliteManager] = None
        self.shm_reader: Optional[PosixShmReader] = None
        self.file_manager: Optional[DiskFileManager] = None
        self.dbus_interface: Optional[DbDbusInterface] = None
        
        # Threading
        self._main_loop_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Statistics and monitoring
        self._processed_events_count = 0
        self._error_count = 0
        self._last_log_time = time.time()
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("DbDaemonMain initialized")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def init_daemon(self) -> bool:
        """
        Initialize all daemon components and system resources.
        
        Creates and initializes all sub-components including database connection,
        D-Bus service registration, and file system setup.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("=" * 70)
            self.logger.info("DBDaemon initialization starting")
            self.logger.info("=" * 70)
            
            # Initialize SqliteManager
            self.logger.info("Initializing database manager...")
            self.db_manager = SqliteManager()
            if not self.db_manager.connect_db():
                self.logger.error("Failed to connect to database")
                self.current_state = DaemonState.ERROR
                return False
            
            self.db_manager.init_tables_if_not_exists()
            self.logger.info("✓ Database manager initialized")
            
            # Initialize DiskFileManager
            self.logger.info("Initializing file manager...")
            self.file_manager = DiskFileManager()
            if not self.file_manager.init_directories():
                self.logger.error("Failed to initialize file directories")
                self.current_state = DaemonState.ERROR
                return False
            self.logger.info("✓ File manager initialized")
            
            # Initialize PosixShmReader (if FRTApp enabled)
            if FRT_APP_ENABLED:
                self.logger.info("Initializing shared memory reader...")
                self.shm_reader = PosixShmReader()
                # Note: Attachment to shared memory will happen during polling
                self.logger.info("✓ Shared memory reader initialized")
            else:
                self.logger.info("⊘ Shared memory reader skipped (FRTApp disabled)")
            
            # Initialize DbDbusInterface
            self.logger.info("Initializing D-Bus interface...")
            self.dbus_interface = DbDbusInterface()
            if not self.dbus_interface.setup_bus_service():
                self.logger.error("Failed to setup D-Bus service")
                self.current_state = DaemonState.ERROR
                return False
            self.logger.info("✓ D-Bus interface initialized")
            
            # Register event callbacks
            self._register_event_handlers()
            
            self.current_state = DaemonState.IDLE
            self.logger.info("=" * 70)
            self.logger.info("DBDaemon initialization completed successfully")
            self.logger.info("=" * 70)
            return True
            
        except Exception as e:
            self.logger.error(f"Unexpected error during initialization: {e}")
            self.current_state = DaemonState.ERROR
            return False
    
    def start_daemon(self) -> bool:
        """
        Start the daemon's main execution loop.
        
        Launches the GLib Event Loop via D-Bus polling and begins processing
        events from SensorDaemon and FRTApp.
        
        Returns:
            True if startup successful, False otherwise
        """
        if self.is_running:
            self.logger.warning("Daemon already running")
            return True
        
        try:
            self.logger.info("=" * 70)
            self.logger.info("DBDaemon starting main loop")
            self.logger.info("=" * 70)
            
            self.is_running = True
            self._stop_event.clear()
            
            # Start D-Bus event polling
            if self.dbus_interface:
                self.dbus_interface.poll_bus_events()
            
            # Start main event loop thread
            self._main_loop_thread = threading.Thread(
                target=self._main_loop,
                daemon=False,
                name="DbDaemonMainLoop"
            )
            self._main_loop_thread.start()
            
            self.logger.info("DBDaemon main loop started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start daemon: {e}")
            self.is_running = False
            self.current_state = DaemonState.ERROR
            return False
    
    def stop_daemon(self) -> None:
        """
        Gracefully stop the daemon and release resources.
        
        Closes all connections, stops event loops, and performs cleanup to
        ensure data integrity and proper resource release.
        """
        self.logger.info("=" * 70)
        self.logger.info("DBDaemon stopping")
        self.logger.info("=" * 70)
        
        try:
            self.is_running = False
            self._stop_event.set()
            
            # Stop D-Bus interface
            if self.dbus_interface:
                self.dbus_interface.stop()
            
            # Wait for main loop to finish
            if self._main_loop_thread and self._main_loop_thread.is_alive():
                self._main_loop_thread.join(timeout=5.0)
            
            # Close database connection
            if self.db_manager:
                self.db_manager.close_connection()
            
            # Detach shared memory
            if self.shm_reader:
                self.shm_reader.detach_shared_memory()
            
            self.current_state = DaemonState.STOPPED
            self.logger.info("=" * 70)
            self.logger.info("DBDaemon stopped successfully")
            self.logger.info("=" * 70)
            
        except Exception as e:
            self.logger.error(f"Error during daemon shutdown: {e}")
    
    def process_food_tracking_event(self, food_id: str, confidence_score: float,
                                   quantity: int) -> None:
        """
        Process food tracking event from FRTApp.
        
        Core event handler that updates inventory database and notifies UI of changes.
        
        Args:
            food_id: Unique identifier for the food item
            confidence_score: AI model confidence score (0.0 - 1.0)
            quantity: Updated quantity of the item
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Update inventory in database
            image_path = None  # TODO: Will be set by FRTApp integration
            if not self.db_manager.update_inventory(food_id, quantity, 
                                                    confidence_score, image_path):
                self.logger.error(f"Failed to update inventory for {food_id}")
                self._error_count += 1
                return
            
            # Notify UI of update
            self.dbus_interface.emit_ui_update_required(food_id, quantity, image_path or "")
            
            self._processed_events_count += 1
            self.logger.info(f"Processed food event: {food_id} (qty={quantity}, "
                           f"score={confidence_score:.2f})")
            
        except Exception as e:
            self.logger.error(f"Error processing food event: {e}")
            self._error_count += 1
        finally:
            self.current_state = DaemonState.IDLE
    
    def process_food_event(self) -> None:
        """
        Process food event logging.
        
        Handler for food item update events that logs detailed information
        for audit and debugging purposes.
        """
        try:
            self.logger.debug("Processing food event...")
            # TODO: Implement specific food event logic
        except Exception as e:
            self.logger.error(f"Error processing food event: {e}")
    
    def process_environment_event(self, temperature: float, humidity: float,
                                 timestamp: float) -> None:
        """
        Process environmental sensor data from SensorDaemon.
        
        Logs environmental readings to database and notifies UI of updates.
        Includes timestamp from sensor for accurate time synchronization.
        
        Args:
            temperature: Temperature reading in Celsius
            humidity: Humidity reading in percentage
            timestamp: Unix timestamp when measurement was taken
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Log environmental data with sensor timestamp
            if not self.db_manager.insert_environment_log(temperature, humidity, 
                                                         timestamp):
                self.logger.error("Failed to insert environment log")
                self._error_count += 1
                return
            
            # Notify UI of environment update
            self.dbus_interface.emit_env_update_required(temperature, humidity)
            
            self._processed_events_count += 1
            self.logger.debug(f"Environment event: T={temperature:.1f}°C, "
                            f"H={humidity:.1f}%, ts={timestamp}")
            
        except Exception as e:
            self.logger.error(f"Error processing environment event: {e}")
            self._error_count += 1
        finally:
            self.current_state = DaemonState.IDLE
    
    def recover_from_io_error(self) -> None:
        """
        Attempt recovery from I/O errors.
        
        Implements recovery strategy for SD card or disk write failures by
        attempting database reconnection and state restoration.
        """
        self.logger.warning("Attempting recovery from I/O error...")
        
        try:
            # Close and reconnect database
            if self.db_manager:
                self.db_manager.close_connection()
                if not self.db_manager.connect_db():
                    self.logger.error("Failed to recover database connection")
                    self.current_state = DaemonState.ERROR
                    return
            
            self.logger.info("Successfully recovered from I/O error")
            
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            self.current_state = DaemonState.ERROR
    
    def log_daemon_status(self) -> None:
        """
        Log current daemon status and performance metrics.
        
        Periodically logs daemon state, event counters, and error conditions
        for monitoring and debugging purposes.
        """
        try:
            elapsed = time.time() - self._last_log_time
            if elapsed >= 30.0:  # Log every 30 seconds
                self.logger.info(
                    f"Daemon Status - State: {self.current_state.value}, "
                    f"Events: {self._processed_events_count}, "
                    f"Errors: {self._error_count}, "
                    f"Uptime: {int(elapsed)}s"
                )
                self._last_log_time = time.time()
                
                # Log disk usage if available
                if self.file_manager:
                    usage_mb = self.file_manager.get_total_storage_used()
                    self.logger.debug(f"Disk usage: {usage_mb:.1f}MB")
                    
        except Exception as e:
            self.logger.error(f"Error logging daemon status: {e}")
    
    def _main_loop(self) -> None:
        """
        Main event processing loop.
        
        Runs continuously, processing D-Bus events and performing periodic
        maintenance tasks until stop is signaled.
        """
        self.logger.info("Main loop thread started")
        
        try:
            while self.is_running and not self._stop_event.is_set():
                try:
                    # Log status periodically
                    self.log_daemon_status()
                    
                    # Check shared memory if FRTApp enabled
                    if FRT_APP_ENABLED and self.shm_reader:
                        if not self.shm_reader.is_attached:
                            if self.shm_reader.attach_shared_memory():
                                self.logger.info("Attached to FRTApp shared memory")
                    
                    # Sleep for interval
                    time.sleep(self.MAIN_LOOP_INTERVAL_MS / 1000.0)
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop iteration: {e}")
                    self._error_count += 1
                    time.sleep(1.0)  # Back off on error
                    
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}")
            self.current_state = DaemonState.ERROR
    
    def _register_event_handlers(self) -> None:
        """Register callbacks for incoming D-Bus events."""
        try:
            if self.dbus_interface:
                # Register callbacks
                self.dbus_interface.listen_sensor_events(self._handle_sensor_event)
                self.dbus_interface.listen_frt_pipeline_events(self._handle_frt_event)
                
                self.logger.debug("Event handlers registered")
                
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
    
    def _handle_sensor_event(self, event_type: str, *args, **kwargs) -> None:
        """Handle incoming SensorDaemon events."""
        try:
            if event_type == "environment":
                temp, humid, ts = args[0], args[1], args[2]
                self.process_environment_event(temp, humid, ts)
            elif event_type == "door":
                state = args[0]
                self.logger.debug(f"Door sensor event: {state}")
            elif event_type == "presence":
                detected = args[0]
                self.logger.debug(f"Presence event: {detected}")
        except Exception as e:
            self.logger.error(f"Error handling sensor event: {e}")
    
    def _handle_frt_event(self, event_type: str, *args, **kwargs) -> None:
        """Handle incoming FRTApp pipeline events."""
        try:
            if event_type == "food_detected":
                food_id, score, qty = args[0], args[1], args[2]
                self.process_food_tracking_event(food_id, score, qty)
        except Exception as e:
            self.logger.error(f"Error handling FRT event: {e}")
    
    def _handle_signal(self, signum, frame) -> None:
        """Handle system signals for graceful shutdown."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop_daemon()
