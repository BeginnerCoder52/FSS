"""
@file DbDbusInterface.py
@brief Manages D-Bus inter-process communication for DBDaemon.

This module provides D-Bus service registration, signal emission, and event
listening capabilities for communication with SensorDaemon, FRTApp, and UI components.
Updated to support modern sdbus (python-sdbus >= 0.14.0).
"""

import logging
import threading
import time
import json
import asyncio
from typing import Callable, Optional, Any, Dict, List, Union
from abc import ABC

try:
    import sdbus
    from sdbus import (
        DbusInterfaceCommonAsync,
        DbusInterfaceCommon,
        dbus_method_async,
        dbus_signal_async,
        dbus_method
    )
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
    
    # FRTApp service details
    FRT_SERVICE = "vn.edu.uit.FSS.FRTApp"
    FRT_PATH = "/vn/edu/uit/FSS/FRTApp"
    FRT_INTERFACE = "vn.edu.uit.FSS.FRTApp"
    
    def __init__(self):
        """Initialize DbDbusInterface instance."""
        self.system_bus: Optional[Any] = None
        self.is_connected: bool = False
        self.dbus_object: Optional['DbDaemonDbusObject'] = None
        
        # Event loop for D-Bus
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_thread: Optional[threading.Thread] = None
        self._signal_tasks: List[asyncio.Task] = []
        
        # Callbacks storage
        self._frt_event_callbacks: list = []
        self._sensor_event_callbacks: list = []
        
        # External comparison function callback
        self._compare_callback: Optional[Callable] = None

        # Pure database operation callbacks
        self._inventory_callback: Optional[Callable] = None
        self._requests_callback: Optional[Callable] = None
        self._insert_request_callback: Optional[Callable] = None
        self._clear_request_callback: Optional[Callable] = None
        
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
                self.logger.error("Asyncio loop failed to start")
                return False

            # Register service and export object in the loop
            future = asyncio.run_coroutine_threadsafe(
                self._async_setup(), self._loop
            )
            return future.result(timeout=10.0)
            
        except Exception as e:
            self.logger.error(f"Failed to setup D-Bus service: {e}")
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
                sdbus.sd_bus_internals.NameReplaceExistingFlag
            )
            
            # Create and export D-Bus object
            self.dbus_object = DbDaemonDbusObject()
            self.dbus_object.set_interface_instance(self)
            self.dbus_object.export_to_dbus(self.OBJECT_PATH)
            
            self.is_connected = True
            self.logger.info(f"D-Bus service registered on SYSTEM bus: {self.SERVICE_NAME}")
            return True
        except Exception as e:
            import traceback
            self.logger.error(f"Async setup error: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def set_comparison_callback(self, callback: Callable) -> None:
        """Set the callback for GetMissingIngredients method."""
        self._compare_callback = callback

    def set_inventory_callback(self, callback: Callable) -> None:
        """Set the callback for GetInventory method."""
        self._inventory_callback = callback

    def set_requests_callback(self, callback: Callable) -> None:
        """Set the callback for GetRequests method."""
        self._requests_callback = callback

    def set_insert_request_callback(self, callback: Callable) -> None:
        """Set the callback for InsertRequest method."""
        self._insert_request_callback = callback

    def set_clear_request_callback(self, callback: Callable) -> None:
        """Set the callback for ClearRequest method."""
        self._clear_request_callback = callback

    def listen_frt_pipeline_events(self, callback: Callable) -> None:
        """
        Subscribe to FRTApp pipeline events.
        
        Args:
            callback: Function to call when FRTApp events occur
        """
        if not callback:
            self.logger.warning("Received None callback for FRT events")
            return
        
        self._frt_event_callbacks.append(callback)
        self.logger.debug("Registered FRTApp event callback")
        
        # Subscribe to FRTApp D-Bus signals if connected
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_to_frt_signals_async(), self._loop
            )
    
    def listen_sensor_dbus_events(self, callback: Callable) -> None:
        """
        Subscribe to SensorDaemon events.
        
        Args:
            callback: Function to call when sensor events occur
        """
        if not callback:
            self.logger.warning("Received None callback for sensor events")
            return
        
        self._sensor_event_callbacks.append(callback)
        self.logger.debug("Registered SensorDaemon event callback")
        
        # Subscribe to SensorDaemon D-Bus signals
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_to_sensor_signals_async(), self._loop
            )
    
    def emit_ui_update_signal(self, food_id: str, quantity: int, 
                               image_path: str) -> None:
        """Emit signal to update UI with inventory changes."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            # Signals in sdbus are just calling the method on the exported object
            asyncio.run_coroutine_threadsafe(
                self._async_emit_ui_update(food_id, quantity, image_path),
                self._loop
            )
            self.logger.debug(f"Queued UI update signal: {food_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit UI update signal: {e}")

    async def _async_emit_ui_update(self, food_id: str, quantity: int, image_path: str):
        self.dbus_object.UIUpdateRequired(food_id, quantity, image_path)

    def emit_environment_update_signal(self, temperature: float, humidity: float) -> None:
        """Emit signal to update UI with environmental data (Sensor 1)."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._async_emit_env_update(temperature, humidity),
                self._loop
            )
            self.logger.debug(f"Queued environment update signal: T={temperature}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit environment update signal: {e}")

    async def _async_emit_env_update(self, temperature: float, humidity: float):
        self.dbus_object.EnvironmentUpdateRequired(temperature, humidity)

    def emit_secondary_environment_update_signal(self, temperature: float, humidity: float) -> None:
        """Emit signal to update UI with environmental data (Sensor 2)."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._async_emit_secondary_env_update(temperature, humidity),
                self._loop
            )
            self.logger.debug(f"Queued secondary environment update signal: T={temperature}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit secondary environment update signal: {e}")

    async def _async_emit_secondary_env_update(self, temperature: float, humidity: float):
        self.dbus_object.SecondaryEnvironmentUpdateRequired(temperature, humidity)

    def emit_door_state_update(self, door_state: str, timestamp: float) -> None:
        """Emit signal to update UI with door state changes."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._async_emit_door_state_update(door_state, timestamp),
                self._loop
            )
            self.logger.debug(f"Queued door state update signal: {door_state}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit door state update signal: {e}")

    async def _async_emit_door_state_update(self, door_state: str, timestamp: float):
        self.dbus_object.DoorStateUpdate(door_state, timestamp)

    def emit_distance_alert(self, distance: float, within_threshold: bool) -> None:
        """Emit signal to update UI with distance alert."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._async_emit_distance_alert(distance, within_threshold),
                self._loop
            )
            self.logger.debug(f"Queued distance alert signal: {distance}cm")
            
        except Exception as e:
            self.logger.error(f"Failed to emit distance alert signal: {e}")

    async def _async_emit_distance_alert(self, distance: float, within_threshold: bool):
        self.dbus_object.DistanceAlert(distance, within_threshold)

    def emit_user_presence_update(self, detected: bool) -> None:
        """Emit signal to update UI with user presence detection."""
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._async_emit_user_presence_update(detected),
                self._loop
            )
            self.logger.debug(f"Queued user presence update signal: {detected}")
            
        except Exception as e:
            self.logger.error(f"Failed to emit user presence update signal: {e}")

    async def _async_emit_user_presence_update(self, detected: bool):
        self.dbus_object.UserPresenceUpdate(detected)

    def poll_bus_events(self) -> None:
        """Starts polling. In async mode, the loop is already running."""
        self.logger.info("D-Bus event polling active (asyncio loop)")
    
    def handle_bus_disconnection(self) -> None:
        """Handle and attempt recovery from D-Bus disconnection."""
        self.logger.warning("D-Bus disconnection detected, attempting recovery...")
        # Re-setup would go here
    
    def stop(self) -> None:
        """Stop D-Bus service and cleanup resources."""
        try:
            if self._loop and self._loop.is_running():
                # Cancel signal tasks
                for task in self._signal_tasks:
                    self._loop.call_soon_threadsafe(task.cancel)
                
                # Stop the loop
                self._loop.call_soon_threadsafe(self._loop.stop)
            
            if self._event_thread:
                self._event_thread.join(timeout=2.0)
            
            self.is_connected = False
            self.logger.info("D-Bus service stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping D-Bus service: {e}")
    
    def _run_event_loop(self) -> None:
        """Thread target for asyncio loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _subscribe_to_sensor_signals_async(self) -> None:
        """Asynchronously subscribe to SensorDaemon signals."""
        try:
            # Define SensorDaemon service details
            SENSOR_SERVICE = None
            SENSOR_PATH = "/vn/edu/uit/FSS/Sensor"
            SENSOR_INTERFACE = "vn.edu.uit.FSS.Sensor"
            
            class SensorInterface(DbusInterfaceCommonAsync, interface_name=SENSOR_INTERFACE):
                @dbus_signal_async('s')
                def EnvironmentDataUpdated(self, data: str): pass
                
                @dbus_signal_async('s')
                def DoorStateChanged(self, state: str): pass
                
                @dbus_signal_async('b')
                def UserPresenceDetected(self, detected: bool): pass
                
                @dbus_signal_async('d')
                def DistanceDataChanged(self, distance: float): pass

            proxy = SensorInterface.new_proxy(SENSOR_SERVICE, SENSOR_PATH)
            
            tasks = [
                asyncio.create_task(self._listen_env_signals(proxy)),
                asyncio.create_task(self._listen_door_signals(proxy)),
                asyncio.create_task(self._listen_presence_signals(proxy)),
                asyncio.create_task(self._listen_distance_signals(proxy))
            ]
            self._signal_tasks.extend(tasks)
            
            self.logger.info("Subscribed to SensorDaemon signals")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to sensor signals: {e}")

    async def _subscribe_to_frt_signals_async(self) -> None:
        """Asynchronously subscribe to FRTApp signals."""
        try:
            class FrtInterface(DbusInterfaceCommonAsync, interface_name=self.FRT_INTERFACE):
                @dbus_signal_async('s')
                def FoodDetected(self, json_data: str): pass

            proxy = FrtInterface.new_proxy(None, self.FRT_PATH)
            
            task = asyncio.create_task(self._listen_frt_signals(proxy))
            self._signal_tasks.append(task)
            
            self.logger.info("Subscribed to FRTApp signals")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to FRTApp signals: {e}")

    async def _listen_frt_signals(self, proxy):
        async for json_data in proxy.FoodDetected:
            self._handle_food_detected(json_data)

    async def _listen_env_signals(self, proxy):
        async for data in proxy.EnvironmentDataUpdated:
            self._handle_environment_data_updated(data)

    async def _listen_door_signals(self, proxy):
        async for state in proxy.DoorStateChanged:
            self._handle_door_state_changed(state)

    async def _listen_presence_signals(self, proxy):
        async for detected in proxy.UserPresenceDetected:
            self._handle_user_presence_detected(detected)

    async def _listen_distance_signals(self, proxy):
        async for distance in proxy.DistanceDataChanged:
            self._handle_distance_data_changed(distance)

    def _handle_food_detected(self, json_data: str) -> None:
        try:
            data = json.loads(json_data)
            food_id = data.get("id")
            score = data.get("score")
            qty = data.get("qty")
            
            if food_id is not None:
                for callback in self._frt_event_callbacks:
                    try:
                        callback("food_detected", str(food_id), score, qty)
                    except Exception as e:
                        self.logger.error(f"Error in FRT callback: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing food detection data: {e}")

    def _handle_environment_data_updated(self, env_data: Union[str, Dict]) -> None:
        try:
            if isinstance(env_data, dict):
                data = env_data
            else:
                data = json.loads(env_data)
                
            temp = data.get("temp")
            humid = data.get("humid")
            temp_2 = data.get("temp_2")
            humid_2 = data.get("humid_2")
            ts = data.get("timestamp", time.time())
            
            if (temp is not None and humid is not None) or \
               (temp_2 is not None and humid_2 is not None):
                self._invoke_sensor_callbacks(
                    "environment", temp, humid, ts, temp_2, humid_2
                )
        except Exception as e:
            self.logger.error(f"Error handling environment data: {e}")

    def _handle_door_state_changed(self, door_state: str) -> None:
        if door_state in ["DOOR_OPEN", "DOOR_CLOSE"]:
            self._invoke_sensor_callbacks("door", door_state, time.time())

    def _handle_user_presence_detected(self, detected: bool) -> None:
        self._invoke_sensor_callbacks("presence", detected, time.time())

    def _handle_distance_data_changed(self, distance: float) -> None:
        if distance >= 0:
            self._invoke_sensor_callbacks("distance", distance, time.time())

    def _invoke_sensor_callbacks(self, *args, **kwargs) -> None:
        for callback in self._sensor_event_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in sensor callback: {e}")


if SDBUS_AVAILABLE:
    class DbDaemonDbusObject(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.DBDaemon"):
        """D-Bus object implementation for DBDaemon service."""
        
        def __init__(self):
            super().__init__()
            self._interface_instance: Optional[DbDbusInterface] = None

        def set_interface_instance(self, instance: DbDbusInterface):
            self._interface_instance = instance

        @dbus_method_async('', 'as')
        async def GetMissingIngredients(self) -> List[str]:
            """
            D-Bus Method: Compare inventory vs request and return missing items.
            """
            if self._interface_instance and self._interface_instance._compare_callback:
                try:
                    shortage_list = self._interface_instance._compare_callback()
                    return [f"{item['food_id']}: {item['shortage']}" for item in shortage_list]
                except Exception as e:
                    logging.error(f"Error in GetMissingIngredients D-Bus method: {e}")
                    return ["Error: Internal server error"]
            return ["Error: Comparison callback not set"]

        # ---------------------------------------------------------------------
        # Phase 3: Pure Database D-Bus Methods
        # ---------------------------------------------------------------------

        @dbus_method_async('', 's')
        async def GetInventory(self) -> str:
            """
            D-Bus Method: Get all current inventory items.
            Returns JSON string of inventory array.
            """
            if self._interface_instance and self._interface_instance._inventory_callback:
                try:
                    result = self._interface_instance._inventory_callback()
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"Error in GetInventory D-Bus method: {e}")
                    return json.dumps({"status": "error", "message": str(e)})
            return json.dumps({"status": "error", "message": "Inventory callback not set"})

        @dbus_method_async('', 's')
        async def GetRequests(self) -> str:
            """
            D-Bus Method: Get all recipe requests.
            Returns JSON string of requests array.
            """
            if self._interface_instance and self._interface_instance._requests_callback:
                try:
                    result = self._interface_instance._requests_callback()
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"Error in GetRequests D-Bus method: {e}")
                    return json.dumps({"status": "error", "message": str(e)})
            return json.dumps({"status": "error", "message": "Requests callback not set"})

        @dbus_method_async('sss', 'b')
        async def InsertRequest(self, recipe_name: str, ingredients_json: str,
                                 batch_id: str) -> bool:
            """
            D-Bus Method: Insert a batch of recipe ingredients as a request.
            Args:
                recipe_name: Vietnamese recipe name
                ingredients_json: JSON array of {"food_id","quantity","unit"} objects
                batch_id: UUID to group ingredients from the same recipe
            Returns: True if successful.
            """
            if self._interface_instance and self._interface_instance._insert_request_callback:
                try:
                    ingredients = json.loads(ingredients_json)
                    return self._interface_instance._insert_request_callback(
                        recipe_name, ingredients, batch_id
                    )
                except Exception as e:
                    logging.error(f"Error in InsertRequest D-Bus method: {e}")
                    return False
            return False

        @dbus_method_async('s', 'b')
        async def ClearRequest(self, batch_id: str) -> bool:
            """
            D-Bus Method: Clear all ingredients from a recipe request batch.
            Args:
                batch_id: request_batch_id to delete
            Returns: True if successful.
            """
            if self._interface_instance and self._interface_instance._clear_request_callback:
                try:
                    return self._interface_instance._clear_request_callback(batch_id)
                except Exception as e:
                    logging.error(f"Error in ClearRequest D-Bus method: {e}")
                    return False
            return False

        @dbus_signal_async('sis')
        def UIUpdateRequired(self, food_id: str, quantity: int, image_path: str) -> None:
            """Signal: UI requires update with new inventory data."""
            pass
        
        @dbus_signal_async('dd')
        def EnvironmentUpdateRequired(self, temperature: float, humidity: float) -> None:
            """Signal: UI requires update with new environmental data."""
            pass

        @dbus_signal_async('dd')
        def SecondaryEnvironmentUpdateRequired(self, temperature: float, humidity: float) -> None:
            """Signal: UI requires update with new environmental data (Sensor 2)."""
            pass

        @dbus_signal_async('sd')
        def DoorStateUpdate(self, door_state: str, timestamp: float) -> None:
            """Signal: UI update for door state change."""
            pass

        @dbus_signal_async('db')
        def DistanceAlert(self, distance: float, within_threshold: bool) -> None:
            """Signal: UI alert for distance threshold."""
            pass

        @dbus_signal_async('b')
        def UserPresenceUpdate(self, detected: bool) -> None:
            """Signal: UI update for user presence detection."""
            pass
else:
    class DbDaemonDbusObject(ABC):
        """Placeholder D-Bus object implementation."""
        def UIUpdateRequired(self, *args, **kwargs): pass
        def EnvironmentUpdateRequired(self, *args, **kwargs): pass
        def SecondaryEnvironmentUpdateRequired(self, *args, **kwargs): pass
        def DoorStateUpdate(self, *args, **kwargs): pass
        def DistanceAlert(self, *args, **kwargs): pass
        def UserPresenceUpdate(self, *args, **kwargs): pass
        def GetInventory(self, *args, **kwargs): pass
        def GetRequests(self, *args, **kwargs): pass
        def InsertRequest(self, *args, **kwargs): pass
        def ClearRequest(self, *args, **kwargs): pass
        def export_to_dbus(self, *args, **kwargs): pass
        def unexport(self, *args, **kwargs): pass
        def set_interface_instance(self, *args, **kwargs): pass
