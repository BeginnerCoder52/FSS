import logging
import threading
import time
import json
import asyncio
import uuid
from typing import Optional
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


class RecommendSystemDbusService:
    SERVICE_NAME = "vn.edu.uit.FSS.RecommendSystem"
    OBJECT_PATH = "/vn/edu/uit/FSS/RecommendSystem"
    INTERFACE_NAME = "vn.edu.uit.FSS.RecommendSystem"

    DBD_SERVICE = "vn.edu.uit.FSS.DBDaemon"
    DBD_PATH = "/vn/edu/uit/FSS/DBDaemon"
    DBD_INTERFACE = "vn.edu.uit.FSS.DBDaemon"

    def __init__(self, nlp_engine=None):
        self.nlp_engine = nlp_engine
        self.system_bus = None
        self.is_connected = False
        self.dbus_object = None
        self._loop = None
        self._event_thread = None

        self.logger = logging.getLogger(self.__class__.__name__)
        if SDBUS_AVAILABLE:
            self.logger.info("RecommendSystemDbusService initialized (sdbus available)")
        else:
            self.logger.warning("sdbus not available - D-Bus disabled")

    def set_nlp_engine(self, engine) -> None:
        self.nlp_engine = engine

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
                    name="RecommendSystemDbusLoop"
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
            self.dbus_object = RecommendSystemDbusObject()
            self.dbus_object.set_service_instance(self)
            self.dbus_object.export_to_dbus(self.OBJECT_PATH)
            self.is_connected = True
            self.logger.info(f"D-Bus service registered: {self.SERVICE_NAME}")
            return True
        except Exception as e:
            import traceback
            self.logger.error(f"Async setup error: {e}")
            self.logger.error(traceback.format_exc())
            return False

    async def _call_dbus_insert_request(
        self, recipe_name: str, ingredients_json: str, batch_id: str
    ) -> bool:
        try:
            class DbdInterface(DbusInterfaceCommonAsync,
                               interface_name=self.DBD_INTERFACE):
                @dbus_method_async('sss', 'b')
                async def InsertRequest(
                    self, recipe_name: str,
                    ingredients_json: str,
                    batch_id: str
                ) -> bool:
                    pass

            proxy = DbdInterface.new_proxy(self.DBD_SERVICE, self.DBD_PATH)
            result = await proxy.InsertRequest(
                recipe_name, ingredients_json, batch_id
            )
            return result
        except Exception as e:
            self.logger.error(f"D-Bus InsertRequest failed: {e}")
            return False

    async def _handle_extract_and_persist(self, recipe_name: str) -> str:
        if not self.nlp_engine:
            return json.dumps({
                "status": "ERROR",
                "error": "NLP engine not initialized"
            }, ensure_ascii=False)

        try:
            batch_id = str(uuid.uuid4())
            nlp_result = self.nlp_engine.generate_fss_request(recipe_name)
            nlp_status = nlp_result.get("status", "ERROR")

            if nlp_status != "SUCCESS":
                return json.dumps({
                    "status": nlp_status,
                    "message": nlp_result.get("message",
                        nlp_result.get("error", "NLP analysis failed")),
                    "dish": nlp_result.get("dish", recipe_name),
                    "suggestions": nlp_result.get("suggestions", []),
                    "batch_id": batch_id
                }, ensure_ascii=False)

            ingredients = nlp_result.get("ingredients", [])
            ingredients_json = json.dumps(ingredients, ensure_ascii=False)

            persist_ok = await self._call_dbus_insert_request(
                recipe_name, ingredients_json, batch_id
            )

            if not persist_ok:
                self.logger.error(
                    f"Failed to persist ingredients for recipe: {recipe_name}"
                )

            return json.dumps({
                "status": "SUCCESS",
                "dish": nlp_result.get("dish", recipe_name),
                "ingredients": ingredients,
                "batch_id": batch_id,
                "persisted": persist_ok,
                "processing_time_ms": nlp_result.get("processing_time_ms", 0)
            }, ensure_ascii=False)

        except Exception as e:
            self.logger.error(
                f"Error in ExtractAndPersistRecipe: {e}", exc_info=True
            )
            return json.dumps({
                "status": "ERROR",
                "error": str(e)
            }, ensure_ascii=False)

    def extract_and_persist(self, recipe_name: str) -> str:
        if not self._loop or not self._loop.is_running():
            return json.dumps({
                "status": "ERROR",
                "error": "Event loop not running"
            })
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._handle_extract_and_persist(recipe_name), self._loop
            )
            return future.result(timeout=30.0)
        except Exception as e:
            self.logger.error(f"Failed to extract and persist: {e}")
            return json.dumps({
                "status": "ERROR",
                "error": str(e)
            })

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
    class RecommendSystemDbusObject(
        DbusInterfaceCommonAsync,
        interface_name="vn.edu.uit.FSS.RecommendSystem"
    ):
        def __init__(self):
            super().__init__()
            self._service_instance = None

        def set_service_instance(self, instance: RecommendSystemDbusService):
            self._service_instance = instance

        @dbus_method_async('s', 's')
        async def ExtractAndPersistRecipe(self, recipe_name: str) -> str:
            if self._service_instance:
                try:
                    result = await self._service_instance._handle_extract_and_persist(
                        recipe_name
                    )
                    return result
                except Exception as e:
                    logging.error(
                        f"Error in ExtractAndPersistRecipe D-Bus method: {e}"
                    )
                    return json.dumps({
                        "status": "ERROR", "error": str(e)
                    })
            return json.dumps({
                "status": "ERROR",
                "error": "Service instance not set"
            })
else:
    class RecommendSystemDbusObject(ABC):
        def ExtractAndPersistRecipe(self, *args, **kwargs):
            return '{"status":"ERROR","error":"D-Bus unavailable"}'

        def export_to_dbus(self, *args, **kwargs):
            pass

        def unexport(self, *args, **kwargs):
            pass

        def set_service_instance(self, *args, **kwargs):
            pass
