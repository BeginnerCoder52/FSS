import logging
import threading
import time
import json
import asyncio
from typing import Optional, Callable, List
from abc import ABC

try:
    import sdbus
    from sdbus import (
        DbusInterfaceCommonAsync,
        dbus_method_async,
        dbus_signal_async
    )
    SDBUS_AVAILABLE = True
except ImportError:
    SDBUS_AVAILABLE = False


class RecommendDbusInterface:
    SERVICE_NAME = "vn.edu.uit.FSS.RecommendDaemon"
    OBJECT_PATH = "/vn/edu/uit/FSS/RecommendDaemon"
    INTERFACE_NAME = "vn.edu.uit.FSS.RecommendDaemon"

    DBD_SERVICE = "vn.edu.uit.FSS.DBDaemon"
    DBD_PATH = "/vn/edu/uit/FSS/DBDaemon"
    DBD_INTERFACE = "vn.edu.uit.FSS.DBDaemon"

    def __init__(self):
        self.system_bus = None
        self.is_connected = False
        self.dbus_object = None
        self._loop = None
        self._event_thread = None

        self._generate_callback = None
        self._recipes_callback = None
        self._shopping_list_callback = None
        self._mark_purchased_callback = None

        self.logger = logging.getLogger(self.__class__.__name__)
        if SDBUS_AVAILABLE:
            self.logger.info("RecommendDbusInterface initialized (sdbus available)")
        else:
            self.logger.warning("sdbus not available - D-Bus disabled")

    def setup_bus_service(self) -> bool:
        if not SDBUS_AVAILABLE:
            self.logger.error("Cannot setup D-Bus: sdbus not installed")
            return False
        try:
            if not self._event_thread:
                self._loop = asyncio.new_event_loop()
                self._event_thread = threading.Thread(
                    target=self._run_event_loop,
                    daemon=True,
                    name="RecommendDbusLoop"
                )
                self._event_thread.start()

            timeout = 5.0
            start_time = time.time()
            while not self._loop.is_running() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self._loop.is_running():
                self.logger.error("Asyncio loop failed to start")
                return False

            future = asyncio.run_coroutine_threadsafe(
                self._async_setup(), self._loop
            )
            return future.result(timeout=10.0)

        except Exception as e:
            self.logger.error(f"Failed to setup D-Bus service: {e}")
            self.is_connected = False
            return False

    async def _async_setup(self) -> bool:
        try:
            sdbus.set_default_bus(sdbus.sd_bus_open_system())
            await sdbus.request_default_bus_name_async(
                self.SERVICE_NAME,
                sdbus.sd_bus_internals.NameReplaceExistingFlag
            )
            self.dbus_object = RecommendDaemonDbusObject()
            self.dbus_object.set_interface_instance(self)
            self.dbus_object.export_to_dbus(self.OBJECT_PATH)
            self.is_connected = True
            self.logger.info(f"D-Bus service registered: {self.SERVICE_NAME}")
            return True
        except Exception as e:
            import traceback
            self.logger.error(f"Async setup error: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def set_generate_callback(self, callback: Callable) -> None:
        self._generate_callback = callback

    def set_recipes_callback(self, callback: Callable) -> None:
        self._recipes_callback = callback

    def set_shopping_list_callback(self, callback: Callable) -> None:
        self._shopping_list_callback = callback

    def set_mark_purchased_callback(self, callback: Callable) -> None:
        self._mark_purchased_callback = callback

    def emit_recommendation_updated(self, recipe_name: str,
                                    shopping_list_json: str) -> None:
        try:
            if not self.is_connected or not self.dbus_object:
                self.logger.warning("Cannot emit signal: D-Bus not connected")
                return
            asyncio.run_coroutine_threadsafe(
                self._async_emit_recommendation_updated(
                    recipe_name, shopping_list_json
                ),
                self._loop
            )
            self.logger.debug(f"Queued RecommendationUpdated signal: {recipe_name}")
        except Exception as e:
            self.logger.error(f"Failed to emit signal: {e}")

    async def _async_emit_recommendation_updated(
        self, recipe_name: str, shopping_list_json: str
    ):
        self.dbus_object.RecommendationUpdated(recipe_name, shopping_list_json)

    async def _call_dbus_get_inventory(self) -> str:
        try:
            class DbdInterface(DbusInterfaceCommonAsync,
                               interface_name=self.DBD_INTERFACE):
                @dbus_method_async('', 's')
                async def GetInventory(self) -> str:
                    pass

            proxy = DbdInterface.new_proxy(
                self.DBD_SERVICE, self.DBD_PATH
            )
            result = await proxy.GetInventory()
            return result
        except Exception as e:
            self.logger.error(f"D-Bus GetInventory failed: {e}")
            return json.dumps({"status": "error", "message": str(e)})

    def call_get_inventory(self) -> str:
        if not self._loop or not self._loop.is_running():
            self.logger.error("Event loop not running for D-Bus call")
            return json.dumps([])
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._call_dbus_get_inventory(), self._loop
            )
            return future.result(timeout=10.0)
        except Exception as e:
            self.logger.error(f"Failed to call GetInventory: {e}")
            return json.dumps([])

    def poll_bus_events(self) -> None:
        self.logger.info("D-Bus event polling active (asyncio loop)")

    def stop(self) -> None:
        try:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._event_thread:
                self._event_thread.join(timeout=2.0)
            self.is_connected = False
            self.logger.info("D-Bus service stopped")
        except Exception as e:
            self.logger.error(f"Error stopping D-Bus service: {e}")

    def _run_event_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


if SDBUS_AVAILABLE:
    class RecommendDaemonDbusObject(
        DbusInterfaceCommonAsync,
        interface_name="vn.edu.uit.FSS.RecommendDaemon"
    ):
        def __init__(self):
            super().__init__()
            self._interface_instance = None

        def set_interface_instance(self, instance: RecommendDbusInterface):
            self._interface_instance = instance

        @dbus_method_async('ss', 's')
        async def GenerateShoppingList(self, recipe_name: str,
                                        batch_id: str) -> str:
            if (self._interface_instance
                    and self._interface_instance._generate_callback):
                try:
                    result = self._interface_instance._generate_callback(
                        recipe_name, batch_id
                    )
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    logging.error(
                        f"Error in GenerateShoppingList D-Bus method: {e}"
                    )
                    return json.dumps({
                        "status": "ERROR", "error": str(e)
                    })
            return json.dumps({
                "status": "ERROR",
                "error": "Generate callback not set"
            })

        @dbus_method_async('', 's')
        async def GetAvailableRecipes(self) -> str:
            if (self._interface_instance
                    and self._interface_instance._recipes_callback):
                try:
                    result = self._interface_instance._recipes_callback()
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    logging.error(
                        f"Error in GetAvailableRecipes D-Bus method: {e}"
                    )
                    return json.dumps([])
            return json.dumps([])

        @dbus_method_async('s', 's')
        async def GetShoppingList(self, batch_id: str) -> str:
            if (self._interface_instance
                    and self._interface_instance._shopping_list_callback):
                try:
                    result = self._interface_instance._shopping_list_callback(
                        batch_id
                    )
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    logging.error(
                        f"Error in GetShoppingList D-Bus method: {e}"
                    )
                    return json.dumps([])
            return json.dumps([])

        @dbus_method_async('i', 'b')
        async def MarkItemPurchased(self, item_id: int) -> bool:
            if (self._interface_instance
                    and self._interface_instance._mark_purchased_callback):
                try:
                    return self._interface_instance._mark_purchased_callback(
                        item_id
                    )
                except Exception as e:
                    logging.error(
                        f"Error in MarkItemPurchased D-Bus method: {e}"
                    )
                    return False
            return False

        @dbus_signal_async('ss')
        def RecommendationUpdated(
            self, recipe_name: str, shopping_list_json: str
        ) -> None:
            pass
else:
    class RecommendDaemonDbusObject(ABC):
        def GenerateShoppingList(self, *args, **kwargs):
            return '{"status":"ERROR","error":"D-Bus unavailable"}'

        def GetAvailableRecipes(self, *args, **kwargs):
            return '[]'

        def GetShoppingList(self, *args, **kwargs):
            return '[]'

        def MarkItemPurchased(self, *args, **kwargs):
            return False

        def RecommendationUpdated(self, *args, **kwargs):
            pass

        def export_to_dbus(self, *args, **kwargs):
            pass

        def unexport(self, *args, **kwargs):
            pass

        def set_interface_instance(self, *args, **kwargs):
            pass
