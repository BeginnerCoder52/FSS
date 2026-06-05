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
    DISTANCE_THRESHOLD_CM = 30.0  # Threshold for distance alert
    
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
            if not self.db_manager.connect_all_dbs():
                self.logger.error("Failed to connect to databases")
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
            self.logger.error("Attempting startup failure recovery...")
            self.reset_on_startup_failure()
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
                                   quantity_delta: int) -> None:
        """
        Process food tracking event from FRTApp.
        
        Core event handler that updates inventory database and notifies UI of changes.
        
        Args:
            food_id: Unique identifier for the food item
            confidence_score: AI model confidence score (0.0 - 1.0)
            quantity_delta: Change in quantity (+1 for ADD, -1 for REMOVE)
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Update inventory in database
            image_path = None  # TODO: Will be set by FRTApp integration
            if not self.db_manager.update_inventory(food_id, quantity_delta, 
                                                    confidence_score, image_path):
                self.logger.error(f"Failed to update inventory for {food_id}")
                self._error_count += 1
                return
            
            # Fetch current total quantity for UI notification
            item = self.db_manager.get_inventory_item(food_id)
            total_qty = item['quantity'] if item else 0
            
            # Notify UI of update
            self.dbus_interface.emit_ui_update_signal(food_id, total_qty, image_path or "", quantity_delta)
            
            self._processed_events_count += 1
            self.logger.info(f"Processed food event: {food_id} (delta={quantity_delta}, "
                           f"total={total_qty}, score={confidence_score:.2f})")
            
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
    
    def process_door_sensor_event(self, door_state: str, timestamp: float) -> None:
        """
        Process door sensor state change from SensorDaemon.
        
        Logs door state changes and notifies UI for fridge access tracking.
        
        Args:
            door_state: Door state string ("DOOR_OPEN" or "DOOR_CLOSE")
            timestamp: Unix timestamp when state was detected
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Log door state to database
            if not self.db_manager.insert_door_sensor_log(door_state, timestamp):
                self.logger.error("Failed to insert door log")
                self._error_count += 1
                return
            
            # Emit door state update to UI
            self.dbus_interface.emit_door_state_update(door_state, timestamp)
            
            self.logger.info(f"Door sensor event: {door_state}")
            self._processed_events_count += 1
            
        except Exception as e:
            self.logger.error(f"Error processing door sensor event: {e}")
            self._error_count += 1
        finally:
            self.current_state = DaemonState.IDLE
    
    def process_distance_sensor_event(self, distance: float, timestamp: float) -> None:
        """
        Process distance sensor reading from SensorDaemon.
        
        Logs distance measurements for tracking refrigerator contents proximity.
        
        Args:
            distance: Distance reading in centimeters
            timestamp: Unix timestamp when measurement was taken
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Log distance reading to database
            if not self.db_manager.insert_distance_sensor_log(distance, timestamp):
                self.logger.error("Failed to insert distance log")
                self._error_count += 1
                return
            
            # Emit distance alert signal to UI
            within_threshold = distance < self.DISTANCE_THRESHOLD_CM
            self.dbus_interface.emit_distance_alert(distance, within_threshold)
            
            self.logger.debug(f"Distance sensor event: {distance}cm (alert={within_threshold})")
            self._processed_events_count += 1
            
        except Exception as e:
            self.logger.error(f"Error processing distance sensor event: {e}")
            self._error_count += 1
        finally:
            self.current_state = DaemonState.IDLE
    
    def process_presence_event(self, detected: bool, timestamp: float) -> None:
        """
        Process user presence detection from SensorDaemon.
        
        Logs presence detection events for security and monitoring.
        
        Args:
            detected: Boolean presence detection result
            timestamp: Unix timestamp when detection occurred
        """
        try:
            self.logger.info(f"Presence event: {'Detected' if detected else 'Not detected'}")
            
            # Log presence to database
            if self.db_manager:
                if not self.db_manager.insert_presence_sensor_log(detected, timestamp):
                    self.logger.error("Failed to insert presence log")
                    # Non-fatal error, continue to emit signal
            
            # Emit user presence update to UI
            if self.dbus_interface:
                self.dbus_interface.emit_user_presence_update(detected)
                
            self._processed_events_count += 1
            
        except Exception as e:
            self.logger.error(f"Error processing presence event: {e}")
            self._error_count += 1
    
    def process_environment_event(self, temperature: float, humidity: float,
                                 timestamp: float, temperature_2: Optional[float] = None,
                                 humidity_2: Optional[float] = None) -> None:
        """
        Process environmental sensor data from SensorDaemon (dual-sensor).
        
        Logs environmental readings from primary sensor (SHT31-1) and optional
        secondary sensor (SHT31-2) to database and notifies UI of updates.
        Includes timestamp from sensor for accurate time synchronization.
        
        Args:
            temperature: Temperature reading in Celsius (Sensor 1)
            humidity: Humidity reading in percentage (Sensor 1)
            timestamp: Unix timestamp when measurement was taken
            temperature_2: Optional temperature from secondary sensor (Sensor 2)
            humidity_2: Optional humidity from secondary sensor (Sensor 2)
        """
        try:
            self.current_state = DaemonState.PROCESSING
            
            if not self.db_manager or not self.dbus_interface:
                self.logger.error("Required managers not initialized")
                self._error_count += 1
                return
            
            # Log environmental data with dual-sensor support
            if not self.db_manager.insert_environment_log(
                temperature, humidity, timestamp, temperature_2, humidity_2
            ):
                self.logger.error("Failed to insert environment log")
                self._error_count += 1
                return
            
            # Notify UI of environment update (primary sensor)
            if temperature is not None and humidity is not None:
                self.dbus_interface.emit_environment_update_signal(temperature, humidity)
            
            # Notify UI of secondary environment update if available
            if temperature_2 is not None and humidity_2 is not None:
                self.dbus_interface.emit_secondary_environment_update_signal(temperature_2, humidity_2)
            
            self._processed_events_count += 1
            log_msg = f"Environment: S1_T={temperature:.1f}°C, S1_H={humidity:.1f}%"
            if temperature_2 is not None and humidity_2 is not None:
                log_msg += f", S2_T={temperature_2:.1f}°C, S2_H={humidity_2:.1f}%"
            self.logger.debug(log_msg)
            
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
    
    def reset_door_sensor(self) -> bool:
        """
        Reset door sensor state and clear any stuck states.
        
        Performs a soft reset of the door sensor state, useful if the sensor
        gets stuck or reports inconsistent state.
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            self.logger.info("Resetting door sensor...")
            # TODO: Send reset signal to SensorDaemon via D-Bus
            # For now, just log the reset attempt
            self.logger.info("Door sensor reset initiated")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset door sensor: {e}")
            return False
    
    def reset_distance_sensor(self) -> bool:
        """
        Reset distance sensor and clear any stuck states.
        
        Performs a soft reset of the distance sensor, useful if the sensor
        gets stuck or reports inconsistent readings.
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            self.logger.info("Resetting distance sensor...")
            # TODO: Send reset signal to SensorDaemon via D-Bus
            # For now, just log the reset attempt
            self.logger.info("Distance sensor reset initiated")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset distance sensor: {e}")
            return False
    
    def reset_on_startup_failure(self) -> bool:
        """
        Perform comprehensive reset if daemon fails to start.
        
        Attempts to reset all components and databases to a clean state
        in case of startup failure. This is a last-resort recovery mechanism.
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            self.logger.warning("Performing comprehensive startup failure reset...")
            
            # Close database connection
            if self.db_manager:
                self.db_manager.close_connection()
            
            # Reset sensor states
            self.reset_door_sensor()
            self.reset_distance_sensor()
            
            # Attempt to reconnect D-Bus
            if self.dbus_interface:
                self.dbus_interface.handle_bus_disconnection()
            
            self.logger.info("Startup failure reset completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Startup failure reset failed: {e}")
            return False
    
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
                # Register sensor and FRT event callbacks
                self.dbus_interface.listen_sensor_dbus_events(self._handle_sensor_event)
                self.dbus_interface.listen_frt_pipeline_events(self._handle_frt_event)
                
                # Register comparison callback for GetMissingIngredients D-Bus method
                self.dbus_interface.set_comparison_callback(self.get_missing_ingredients)
                
                # Register pure database operation callbacks
                self.dbus_interface.set_inventory_callback(self._handle_get_inventory)
                self.dbus_interface.set_requests_callback(self._handle_get_requests)
                self.dbus_interface.set_insert_request_callback(self._handle_insert_request)
                self.dbus_interface.set_clear_request_callback(self._handle_clear_request)
                self.dbus_interface.set_requests_by_recipe_callback(self._handle_get_requests_by_recipe)
                
                self.logger.debug("Event handlers and DB operation callbacks registered")
                
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
    
    def get_missing_ingredients(self) -> list:
        """
        Wrapper for database comparison logic.
        
        Returns:
            List of dictionaries with missing ingredient details
        """
        if self.db_manager:
            return self.db_manager.compare_inventory_vs_request()
        return []

    def _handle_sensor_event(self, event_type: str, *args, **kwargs) -> None:
        """Handle incoming SensorDaemon events."""
        try:
            if event_type == "environment":
                # Args: temperature, humidity, timestamp, temp_2, humid_2
                temp, humid, ts = args[0], args[1], args[2]
                temp_2 = args[3] if len(args) > 3 else None
                humid_2 = args[4] if len(args) > 4 else None
                self.process_environment_event(temp, humid, ts, temp_2, humid_2)
            elif event_type == "door":
                # Args: door_state, timestamp
                door_state, ts = args[0], args[1]
                self.process_door_sensor_event(door_state, ts)
            elif event_type == "distance":
                # Args: distance, timestamp
                distance, ts = args[0], args[1]
                self.process_distance_sensor_event(distance, ts)
            elif event_type == "presence":
                # Args: detected, timestamp
                detected, ts = args[0], args[1]
                self.process_presence_event(detected, ts)
            else:
                self.logger.warning(f"Unknown sensor event type: {event_type}")
        except Exception as e:
            self.logger.error(f"Error handling sensor event: {e}")
    
    def _handle_frt_event(self, event_type: str, *args, **kwargs) -> None:
        """Handle incoming FRTApp pipeline events."""
        try:
            if event_type == "food_detected":
                food_id, score, qty_delta = args[0], args[1], args[2]
                self.process_food_tracking_event(food_id, score, qty_delta)
        except Exception as e:
            self.logger.error(f"Error handling FRT event: {e}")
    
    # -------------------------------------------------------------------------
    # Pure Database D-Bus Method Handlers (Phase 3)
    # -------------------------------------------------------------------------

    def _handle_get_inventory(self) -> list:
        """Handle GetInventory D-Bus method call.
        
        Returns:
            List of all current inventory items, or empty list on error.
        """
        if not self.db_manager:
            return []
        try:
            return self.db_manager.get_all_inventory()
        except Exception as e:
            self.logger.error(f"Error handling GetInventory: {e}")
            return []

    def _handle_get_requests(self) -> list:
        """Handle GetRequests D-Bus method call.
        
        Returns:
            List of all recipe request items, or empty list on error.
        """
        if not self.db_manager:
            return []
        try:
            return self.db_manager.get_all_requests()
        except Exception as e:
            self.logger.error(f"Error handling GetRequests: {e}")
            return []

    def _handle_insert_request(self, recipe_name: str, ingredients: list,
                                batch_id: str) -> bool:
        """Handle InsertRequest D-Bus method call.
        
        Args:
            recipe_name: Vietnamese recipe name
            ingredients: List of {"food_id","quantity","unit"} dicts
            batch_id: UUID to group ingredients from the same recipe

        Returns:
            True if insertion successful.
        """
        if not self.db_manager:
            return False
        try:
            return self.db_manager.insert_request_batch(
                recipe_name, ingredients, batch_id
            )
        except Exception as e:
            self.logger.error(f"Error handling InsertRequest: {e}")
            return False

    def _handle_clear_request(self, batch_id: str) -> bool:
        """Handle ClearRequest D-Bus method call.
        
        Args:
            batch_id: request_batch_id to delete

        Returns:
            True if deletion successful.
        """
        if not self.db_manager:
            return False
        try:
            return self.db_manager.clear_request_batch(batch_id)
        except Exception as e:
            self.logger.error(f"Error handling ClearRequest: {e}")
            return False

    def _handle_get_requests_by_recipe(self, recipe_name: str) -> list:
        """Handle GetRequestList D-Bus method call.

        Args:
            recipe_name: Vietnamese recipe name to filter by

        Returns:
            List of matching request items, or empty list on error.
        """
        if not self.db_manager:
            return []
        try:
            return self.db_manager.get_requests_by_recipe(recipe_name)
        except Exception as e:
            self.logger.error(f"Error handling GetRequestList: {e}")
            return []

    def _handle_signal(self, signum, frame) -> None:
        """Handle system signals for graceful shutdown."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop_daemon()
