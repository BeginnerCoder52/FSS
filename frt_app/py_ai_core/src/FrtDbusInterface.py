"""
FrtDbusInterface.py - FRTApp D-Bus Communication Interface
Version: 1.0
SDD v1.1.0 Compliance: All 5 APIs implemented
Naming: Renamed from "SdbusInterface" (v1.0) to "FrtDbusInterface" (v1.1.0)
        to prevent scope confusion with other daemon interfaces.

Purpose:
    D-Bus interface for inter-process communication between FRTApp and other
    system daemons (SensorDaemon, DBDaemon). Handles signal subscription and
    result publishing.

D-Bus Service Details:
    - Service Name: vn.edu.uit.FSS.FRTApp
    - Interface Name: vn.edu.uit.FSS.FRTApp
    - Object Path: /vn/edu/uit/FSS/FRTApp
    - Bus Type: System Bus (requires root/systemd)

Signals:
    SUBSCRIBE (Input):
        - DoorStateChanged: From SensorDaemon (vn.edu.uit.FSS.Sensor)
          Payload: {"state": "OPEN" | "CLOSED"}
    
    PUBLISH (Output):
        - FoodDetected: To DBDaemon (vn.edu.uit.FSS.DBDaemon)
          Payload: {"id": int, "score": float, "qty": int}

Author: FSS Project Team
License: Proprietary
"""

import logging
import json
import time
import threading
import asyncio
from typing import Dict, Callable, Optional, List
from loguru import logger

try:
    import sdbus
    from sdbus import (
        DbusInterfaceCommonAsync,
        dbus_signal_async
    )
    SDBUS_AVAILABLE = True
except ImportError:
    SDBUS_AVAILABLE = False

# ============================================================================
# D-Bus Interface Class (ASPICE-compliant)
# ============================================================================

class FrtDbusInterface:
    """
    FRTApp D-Bus Communication Interface
    
    SDD v1.1.0 Requirements (Bảng 2 - Package FRTApp, FrtDbusInterface class):
        Attribute bus_connection: object - System Bus connection
        Attribute db_daemon_dest: str - DBDaemon service name
        Attribute sensor_interface: str - SensorDaemon interface name
        Attribute is_connected: bool - Connection status flag
        Attribute dropped_messages_count: int - Dropped message counter
    
    Methods (5 total):
        ✓ init_sdbus_connection() -> bool
        ✓ subscribe_door_events(callback) -> void
        ✓ publish_tracking_results(diff: dict) -> void
        ✓ handle_dbus_timeout() -> void
        ✓ reconnect_bus() -> bool
    """
    
    # ========================================================================
    # CONSTANTS (D-Bus Service Configuration)
    # ========================================================================
    SERVICE_NAME = "vn.edu.uit.FSS.FRTApp"
    INTERFACE_NAME = "vn.edu.uit.FSS.FRTApp"
    OBJECT_PATH = "/vn/edu/uit/FSS/FRTApp"
    
    # Remote services
    SENSOR_SERVICE = "vn.edu.uit.FSS.Sensor"
    SENSOR_INTERFACE = "vn.edu.uit.FSS.Sensor"
    SENSOR_OBJECT_PATH = "/vn/edu/uit/FSS/Sensor"
    
    DB_SERVICE = "vn.edu.uit.FSS.DBDaemon"
    DB_INTERFACE = "vn.edu.uit.FSS.DBDaemon"
    DB_OBJECT_PATH = "/vn/edu/uit/FSS/DBDaemon"
    
    # Signal names
    SIGNAL_DOOR_STATE_CHANGED = "DoorStateChanged"
    SIGNAL_FOOD_DETECTED = "FoodDetected"
    
    # Timeout and retry configuration
    BUS_TIMEOUT_SECONDS = 5.0
    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_BACKOFF_MS = [100, 500, 1000]  # Exponential backoff: 100ms, 500ms, 1s
    
    def __init__(self):
        """
        Initialize FrtDbusInterface.
        
        Purpose:
            Prepare D-Bus interface state variables.
        
        Attributes initialized:
            - bus_connection: None (not connected yet)
            - is_connected: False
            - dropped_messages_count: 0
            - door_state_callback: None (will be set by subscribe)
            - last_ping_time: Current time (for timeout detection)
        """
        self.bus_connection = None
        self.is_connected: bool = False
        self.dropped_messages_count: int = 0
        
        # Event loop for D-Bus
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_thread: Optional[threading.Thread] = None
        self._signal_tasks: List[asyncio.Task] = []
        
        # Callback registration
        self.door_state_callback: Optional[Callable] = None
        
        # Timing
        self.last_ping_time: float = time.time()
        self.reconnect_attempt_count: int = 0
        
        logger.info("FrtDbusInterface initialized (service={})".format(self.SERVICE_NAME))
    
    def init_sdbus_connection(self) -> bool:
        """
        Initialize D-Bus connection and register service.
        """
        logger.info("Initializing D-Bus connection")
        
        if not SDBUS_AVAILABLE:
            logger.error("Cannot setup D-Bus service: sdbus-python not installed")
            return False
            
        try:
            # Start asyncio loop in a separate thread if not already running
            if not self._event_thread:
                self._loop = asyncio.new_event_loop()
                self._event_thread = threading.Thread(
                    target=self._run_event_loop,
                    daemon=True,
                    name="DbusEventLoop"
                )
                self._event_thread.start()
            
            # Wait for loop to be ready
            timeout = 5.0
            start_time = time.time()
            while not self._loop.is_running() and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self._loop.is_running():
                logger.error("Asyncio loop failed to start")
                return False

            future = asyncio.run_coroutine_threadsafe(
                self._async_setup(), self._loop
            )
            return future.result(timeout=10.0)
            
        except Exception as e:
            logger.exception("D-Bus initialization failed: {}".format(e))
            self.is_connected = False
            return False

    async def _async_setup(self) -> bool:
        """Asynchronous setup internal method."""
        try:
            # Set default bus to system bus
            sdbus.set_default_bus(sdbus.sd_bus_open_system())
            
            # Request bus name
            await sdbus.request_default_bus_name_async(
                self.SERVICE_NAME,
                replace_existing=True
            )
            
            # Create and export D-Bus object
            self.bus_connection = FrtDaemonDbusObject()
            self.bus_connection.export_to_dbus(self.OBJECT_PATH)
            
            self.is_connected = True
            self.reconnect_attempt_count = 0
            logger.info("D-Bus connection initialized (service={})".format(self.SERVICE_NAME))
            return True
        except Exception as e:
            logger.error(f"Async setup error: {e}")
            return False

    def _run_event_loop(self) -> None:
        """Thread target for asyncio loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def subscribe_door_events(self, callback: Callable) -> None:
        """
        Subscribe to door state change events from SensorDaemon.
        """
        logger.info("Subscribing to door state events")
        
        if not self.is_connected:
            logger.warning("D-Bus not connected, cannot subscribe to signals")
            return
        
        if callback is None:
            logger.error("Callback function is None, subscription rejected")
            return
        
        try:
            self.door_state_callback = callback
            
            asyncio.run_coroutine_threadsafe(
                self._subscribe_to_sensor_signals_async(), self._loop
            )
            
            logger.debug("Door state callback registered: {}".format(callback.__name__))
            logger.info("Successfully subscribed to door state events")
            
        except Exception as e:
            logger.exception("Failed to subscribe to door events: {}".format(e))
            self.dropped_messages_count += 1
            
    async def _subscribe_to_sensor_signals_async(self) -> None:
        """Asynchronously subscribe to SensorDaemon signals."""
        try:
            proxy = SensorInterface.new_proxy(self.SENSOR_SERVICE, self.SENSOR_OBJECT_PATH)
            
            task = asyncio.create_task(self._listen_door_signals(proxy))
            self._signal_tasks.append(task)
            
            logger.info("Subscribed to SensorDaemon signals asynchronously")
        except Exception as e:
            logger.error(f"Failed to subscribe to sensor signals: {e}")

    async def _listen_door_signals(self, proxy):
        async for state in proxy.DoorStateChanged:
            self._handle_door_signal(state)
    
    def publish_tracking_results(self, diff: Dict) -> None:
        """
        Publish food detection results to DBDaemon.
        """
        logger.debug("Publishing tracking results: {}".format(diff))
        
        if not self.is_connected or not self.bus_connection:
            logger.warning("D-Bus not connected, cannot publish results")
            self.dropped_messages_count += 1
            return
        
        try:
            # Input validation (ASPICE requirement)
            if not isinstance(diff, dict):
                logger.error("Invalid tracking results type: {}".format(type(diff)))
                return
            
            json_str = json.dumps(diff)
            asyncio.run_coroutine_threadsafe(
                self._async_emit_food_detected(json_str),
                self._loop
            )
            
            logger.debug("Tracking results published successfully")
            
        except Exception as e:
            logger.exception("Failed to publish tracking results: {}".format(e))
            self.dropped_messages_count += 1

    async def _async_emit_food_detected(self, json_data: str):
        self.bus_connection.FoodDetected(json_data)

    def emit_camera_state(self, state: str) -> None:
        """
        Emit CameraStateChanged signal ('ON' | 'OFF').
        """
        if not self.is_connected or not self.bus_connection:
            logger.warning("D-Bus not connected, cannot emit camera state")
            return

        if state not in ("ON", "OFF"):
            logger.error("Invalid camera state: {}".format(state))
            return

        try:
            asyncio.run_coroutine_threadsafe(
                self._async_emit_camera_state(state), self._loop
            )
            logger.info("Camera state emitted: {}".format(state))
        except Exception as e:
            logger.exception("Failed to emit camera state: {}".format(e))

    async def _async_emit_camera_state(self, state: str):
        self.bus_connection.CameraStateChanged(state)

    def subscribe_distance_events(self, callback: Callable) -> None:
        """
        Subscribe to DistanceDataChanged from SensorDaemon.
        """
        logger.info("Subscribing to distance events")

        if not self.is_connected:
            logger.warning("D-Bus not connected, cannot subscribe to distance events")
            return

        if callback is None:
            logger.error("Callback function is None, subscription rejected")
            return

        try:
            self.distance_callback = callback
            asyncio.run_coroutine_threadsafe(
                self._subscribe_to_distance_async(), self._loop
            )
            logger.debug("Distance callback registered: {}".format(callback.__name__))
        except Exception as e:
            logger.exception("Failed to subscribe to distance events: {}".format(e))

    async def _subscribe_to_distance_async(self) -> None:
        """Asynchronously subscribe to SensorDaemon distance signals."""
        try:
            proxy = SensorInterface.new_proxy(self.SENSOR_SERVICE, self.SENSOR_OBJECT_PATH)

            task = asyncio.create_task(self._listen_distance_signals(proxy))
            self._signal_tasks.append(task)

            logger.info("Subscribed to distance events asynchronously")
        except Exception as e:
            logger.error("Failed to subscribe to distance events: {}".format(e))

    async def _listen_distance_signals(self, proxy):
        async for distance_cm in proxy.DistanceDataChanged:
            self._handle_distance_signal(distance_cm)

    def _handle_distance_signal(self, distance_cm: float) -> None:
        """
        Internal handler for distance data signal from SensorDaemon.
        """
        logger.debug("Distance signal received: {:.1f}cm".format(distance_cm))

        if hasattr(self, 'distance_callback') and self.distance_callback:
            try:
                self.distance_callback(distance_cm)
            except Exception as e:
                logger.exception("Error in distance callback: {}".format(e))

        self.last_ping_time = time.time()

    def handle_dbus_timeout(self) -> None:
        """
        Handle D-Bus communication timeout.
        """
        logger.warning("D-Bus timeout detected")
        
        try:
            current_time = time.time()
            time_since_ping = current_time - self.last_ping_time
            
            if time_since_ping > self.BUS_TIMEOUT_SECONDS:
                logger.warning("No D-Bus communication for {:.1f}s, attempting recovery".format(
                    time_since_ping))
                
                # Attempt to reconnect
                if not self.reconnect_bus():
                    logger.critical("D-Bus reconnection failed after timeout")
            
        except Exception as e:
            logger.exception("Error in timeout handler: {}".format(e))
    
    def reconnect_bus(self) -> bool:
        """
        Attempt to reconnect to D-Bus system bus.
        """
        logger.info("Attempting D-Bus reconnection (attempt {}/{})".format(
            self.reconnect_attempt_count + 1, self.MAX_RECONNECT_ATTEMPTS))
        
        if self.reconnect_attempt_count >= self.MAX_RECONNECT_ATTEMPTS:
            logger.critical("Maximum reconnection attempts exceeded")
            return False
        
        try:
            # Calculate backoff delay
            backoff_ms = self.RECONNECT_BACKOFF_MS[self.reconnect_attempt_count]
            wait_time = backoff_ms / 1000.0
            logger.debug("Waiting {:.1f}s before reconnect attempt".format(wait_time))
            time.sleep(wait_time)
            
            # Attempt to reconnect
            self.reconnect_attempt_count += 1
            
            if not self.init_sdbus_connection():
                logger.warning("Reconnection attempt failed")
                return False
            
            # Re-subscribe if callback was registered
            if self.door_state_callback:
                logger.debug("Re-subscribing to door events after reconnect")
                self.subscribe_door_events(self.door_state_callback)
            
            logger.info("D-Bus reconnection successful")
            self.last_ping_time = time.time()
            return True
            
        except Exception as e:
            logger.exception("Reconnection error: {}".format(e))
            return False
    
    # ========================================================================
    # INTERNAL SIGNAL HANDLERS (ASPICE: Internal implementation)
    # ========================================================================
    
    def _handle_door_signal(self, door_state: str) -> None:
        """
        Internal handler for door state signal from SensorDaemon.
        
        Arguments:
            door_state (str): "OPEN" or "CLOSED"
        """
        logger.debug("Door signal received: {}".format(door_state))
        
        if self.door_state_callback:
            try:
                self.door_state_callback(door_state)
            except Exception as e:
                logger.exception("Error in door callback: {}".format(e))
        
        self.last_ping_time = time.time()


if SDBUS_AVAILABLE:
    class SensorInterface(DbusInterfaceCommonAsync, interface_name=FrtDbusInterface.SENSOR_INTERFACE):
        @dbus_signal_async('s')
        def DoorStateChanged(self, state: str): pass

        @dbus_signal_async('d')
        def DistanceDataChanged(self, distance_cm: float): pass

    class FrtDaemonDbusObject(DbusInterfaceCommonAsync, interface_name=FrtDbusInterface.INTERFACE_NAME):
        @dbus_signal_async('s')
        def FoodDetected(self, json_data: str) -> None:
            """Signal: Food detection results."""
            pass

        @dbus_signal_async('s')
        def CameraStateChanged(self, state: str) -> None:
            """Signal: Camera on/off state. Payload: 'ON' | 'OFF'."""
            pass

# ============================================================================
# BACKWARD COMPATIBILITY ALIAS
# ============================================================================
# For code using old "SdbusInterface" name, maintain compatibility
SdbusInterface = FrtDbusInterface

if __name__ == "__main__":
    logger.info("FrtDbusInterface Module - Test Entry Point")
    interface = FrtDbusInterface()
    interface.init_sdbus_connection()
