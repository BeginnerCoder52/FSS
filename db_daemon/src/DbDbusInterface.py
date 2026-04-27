"""
@file DbDbusInterface.py
@brief Manages D-Bus inter-process communication for DBDaemon.

This module provides D-Bus service registration, signal emission, and event
listening capabilities for communication with SensorDaemon, FRTApp, and UI components.
"""

import logging
import threading
from typing import Callable, Optional, Any, Dict
from abc import ABC

try:
    import sdbus
    from sdbus import DbusObjectBase, dbus_method, dbus_signal
    SDBUS_AVAILABLE = True
except ImportError:
    SDBUS_AVAILABLE = False


class DbDbusInterface:
    """
    Manages D-Bus communication for the DBDaemon component.
    
    Handles service registration, signal emission, and event subscription
    for inter-process communication with other FSS components via D-Bus.
    """

    # D-Bus service configuration
    SERVICE_NAME = "vn.edu.uit.FSS.DBDaemon"
    OBJECT_PATH = "/vn/edu/uit/FSS/DBDaemon"
    INTERFACE_NAME = "vn.edu.uit.FSS.DBDaemon"
    
    # D-Bus signal names
    SIGNAL_UI_UPDATE = "UIUpdateRequired"
    SIGNAL_ENV_UPDATE = "EnvironmentUpdateRequired"
    
    def __init__(self):
        """Initialize DbDbusInterface instance."""
        self.system_bus: Optional[Any] = None
        self.dbus_service_name: str = self.SERVICE_NAME
        self.is_connected: bool = False
        self.dbus_object: Optional[Any] = None
        
        # Event loop for D-Bus
        self._event_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks storage
        self._frt_event_callbacks: list = []
        self._sensor_event_callbacks: list = []
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if SDBUS_AVAILABLE:
            self.logger.info("DbDbusInterface initialized (sdbus-python available)")
        else:
            self.logger.warning("sdbus-python not available - D-Bus communication disabled")
    
    def setup_bus_service(self) -> bool:
        """
        Configure and register D-Bus service.
        
        Registers the DBDaemon service on the system D-Bus and prepares
        for signal emission and method calls.
        
        Returns:
            True if service registration successful, False otherwise
        """
        if not SDBUS_AVAILABLE:
            self.logger.error("Cannot setup D-Bus service: sdbus-python not installed")
            return False
        
        try:
            # Get system bus
            self.system_bus = sdbus.get_system_bus()
            
            # Create D-Bus object
            self.dbus_object = DbDaemonDbusObject()
            
            # Export object on D-Bus
            self.system_bus.export(self.OBJECT_PATH, self.dbus_object)
            
            # Request service name
            self.system_bus.request_name(self.SERVICE_NAME)
            
            self.is_connected = True
            self.logger.info(f"D-Bus service registered: {self.SERVICE_NAME}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup D-Bus service: {e}")
            self.is_connected = False
            return False
    
    def listen_frt_pipeline_events(self, callback: Callable) -> None:
        """
        Subscribe to FRTApp pipeline events.
        
        Registers a callback to be invoked when FRTApp sends food detection
        or image processing events.
        
        Args:
            callback: Function to call when FRTApp events occur
        """
        if not callback:
            self.logger.warning("Received None callback for FRT events")
            return
        
        self._frt_event_callbacks.append(callback)
        self.logger.debug("Registered FRTApp event callback")
        
        # TODO: Subscribe to FRTApp D-Bus signals
        # self._subscribe_to_frt_signals()
    
    def listen_sensor_events(self, callback: Callable) -> None:
        """
        Subscribe to SensorDaemon events.
        
        Registers a callback to be invoked when SensorDaemon sends
        environmental or door sensor data.
        
        Args:
            callback: Function to call when sensor events occur
        """
        if not callback:
            self.logger.warning("Received None callback for sensor events")
            return
        
        self._sensor_event_callbacks.append(callback)
        self.logger.debug("Registered SensorDaemon event callback")
        
        # TODO: Subscribe to SensorDaemon D-Bus signals
        # self._subscribe_to_sensor_signals()
    
    def emit_ui_update_required(self, food_id: str, quantity: int, 
                               image_path: str) -> None:
        """
        Emit signal to update UI with inventory changes.
        
        Notifies the Electron UI component that inventory has been updated
        and requires visual refresh.
        
        Args:
            food_id: Unique identifier for the updated food item
            quantity: Updated quantity
            image_path: Path to the food image
        """
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            # Emit D-Bus signal
            self.dbus_object.emit_ui_update_required(food_id, quantity, image_path)
            self.logger.debug(f"Emitted UI update signal: {food_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit UI update signal: {e}")
    
    def emit_env_update_required(self, temperature: float, humidity: float) -> None:
        """
        Emit signal to update UI with environmental data.
        
        Notifies the Electron UI component that environmental sensor readings
        have been updated.
        
        Args:
            temperature: Current temperature in Celsius
            humidity: Current humidity in percentage
        """
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            # Emit D-Bus signal
            self.dbus_object.emit_env_update_required(temperature, humidity)
            self.logger.debug(f"Emitted environment update signal: "
                            f"T={temperature}°C, H={humidity}%")
            
        except Exception as e:
            self.logger.error(f"Failed to emit environment update signal: {e}")
    
    def poll_bus_events(self) -> None:
        """
        Run background loop to poll D-Bus events.
        
        Starts a background thread that continuously polls D-Bus for incoming
        signals and method calls. This enables asynchronous event handling.
        """
        if not SDBUS_AVAILABLE or not self.is_connected:
            self.logger.warning("Cannot poll bus events: D-Bus not ready")
            return
        
        try:
            # Start event polling thread
            if not self._event_thread or not self._event_thread.is_alive():
                self._stop_event.clear()
                self._event_thread = threading.Thread(
                    target=self._bus_event_loop,
                    daemon=True,
                    name="DbusEventLoop"
                )
                self._event_thread.start()
                self.logger.info("D-Bus event polling started")
            
        except Exception as e:
            self.logger.error(f"Failed to start D-Bus event polling: {e}")
    
    def handle_bus_disconnection(self) -> None:
        """
        Handle and attempt recovery from D-Bus disconnection.
        
        Implements reconnection logic for cases where the D-Bus daemon
        is restarted or connection is lost.
        """
        self.logger.warning("D-Bus disconnection detected, attempting recovery...")
        
        try:
            # Cleanup current connection
            self.is_connected = False
            
            # Brief delay before reconnection
            import time
            time.sleep(1.0)
            
            # Attempt to reconnect
            if self.setup_bus_service():
                self.logger.info("Successfully reconnected to D-Bus")
                self.poll_bus_events()
            else:
                self.logger.error("Failed to reconnect to D-Bus")
                
        except Exception as e:
            self.logger.error(f"Error during D-Bus reconnection: {e}")
    
    def stop(self) -> None:
        """
        Stop D-Bus service and cleanup resources.
        
        Gracefully stops event polling and disconnects from D-Bus.
        """
        try:
            # Stop event loop
            self._stop_event.set()
            if self._event_thread and self._event_thread.is_alive():
                self._event_thread.join(timeout=2.0)
            
            # Unexport D-Bus object
            if self.dbus_object and self.system_bus:
                self.system_bus.unexport(self.OBJECT_PATH)
            
            # Release bus name
            if self.system_bus:
                self.system_bus.release_name(self.SERVICE_NAME)
            
            self.is_connected = False
            self.logger.info("D-Bus service stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping D-Bus service: {e}")
    
    def _bus_event_loop(self) -> None:
        """
        Background thread for D-Bus event polling.
        
        Continuously polls for and processes D-Bus events until stop is signaled.
        """
        try:
            while not self._stop_event.is_set():
                try:
                    if self.system_bus:
                        # Poll for events with timeout
                        self.system_bus.process_queue(timeout=0.1)
                except Exception as e:
                    self.logger.debug(f"Event polling error: {e}")
                    if "disconnected" in str(e).lower():
                        self.handle_bus_disconnection()
        
        except Exception as e:
            self.logger.error(f"D-Bus event loop error: {e}")
    
    def _invoke_frt_callbacks(self, *args, **kwargs) -> None:
        """Invoke all registered FRTApp event callbacks."""
        for callback in self._frt_event_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in FRT callback: {e}")
    
    def _invoke_sensor_callbacks(self, *args, **kwargs) -> None:
        """Invoke all registered SensorDaemon event callbacks."""
        for callback in self._sensor_event_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in sensor callback: {e}")


class DbDaemonDbusObject(DbusObjectBase if SDBUS_AVAILABLE else ABC):
    """
    D-Bus object implementation for DBDaemon service.
    
    Provides D-Bus signals and methods for IPC communication with other components.
    """
    
    def __init__(self):
        """Initialize D-Bus object."""
        if SDBUS_AVAILABLE:
            super().__init__()
    
    if SDBUS_AVAILABLE:
        @dbus_signal
        def UIUpdateRequired(self, food_id: 's', quantity: 'i', image_path: 's') -> None:
            """Signal: UI requires update with new inventory data."""
            pass
        
        @dbus_signal
        def EnvironmentUpdateRequired(self, temperature: 'd', humidity: 'd') -> None:
            """Signal: UI requires update with new environmental data."""
            pass
        
        def emit_ui_update_required(self, food_id: str, quantity: int,
                                   image_path: str) -> None:
            """Emit UI update signal."""
            self.UIUpdateRequired(food_id, quantity, image_path)
        
        def emit_env_update_required(self, temperature: float, 
                                    humidity: float) -> None:
            """Emit environment update signal."""
            self.EnvironmentUpdateRequired(temperature, humidity)
    else:
        def emit_ui_update_required(self, *args, **kwargs) -> None:
            """Placeholder: sdbus-python not available."""
            pass
        
        def emit_env_update_required(self, *args, **kwargs) -> None:
            """Placeholder: sdbus-python not available."""
            pass
