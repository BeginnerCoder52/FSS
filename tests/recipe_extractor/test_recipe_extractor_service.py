"""
Service Layer Tests - RecipeExtractorDbusService
=================================================

Purpose:
    Validate RecipeExtractorDbusService initialization, D-Bus lifecycle,
    NLP persist flow, and error handling with mocked dependencies.

Test Coverage:
    1. Service initialization (sdbus available/unavailable)
    2. D-Bus setup event loop management
    3. _handle_extract_and_persist with mocked NLP engine
    4. extract_and_persist synchronous wrapper
    5. D-Bus object ExtractAndPersistRecipe method
    6. Error handling: no engine, no event loop, invalid input
    7. JSON response format validation for all status codes

ASPICE Compliance:
    - Mocked external dependencies (sdbus, asyncio)
    - Comprehensive error case coverage
    - Response format validation
    - Input validation tests

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-06-05
"""

import unittest
import logging
import json
import sys
import asyncio
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recipe_extractor_service import (
    RecipeExtractorDbusService,
    SDBUS_AVAILABLE,
)

logging.disable(logging.CRITICAL)


# ==============================================================================
# Mock NLP Engine
# ==============================================================================

class MockNlpEngine:
    def generate_fss_request(self, recipe_name):
        if not recipe_name or not isinstance(recipe_name, str):
            return {"status": "ERROR", "error": "Invalid recipe name"}
        normalized = recipe_name.strip().lower()
        if normalized == "nonexistent":
            return {
                "status": "NOT_FOUND",
                "message": "Recipe not found",
                "dish": normalized,
                "suggestions": ["g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c"]
            }
        if normalized == "error_test":
            raise RuntimeError("Simulated NLP engine failure")
        return {
            "status": "SUCCESS",
            "dish": normalized,
            "ingredients": [
                {"ingredient": "B\u01b0\u1edfi", "quantity": "1"},
                {"ingredient": "M\u1ef1c kh\u00f4", "quantity": "1"}
            ],
            "processing_time_ms": 3.22
        }

    def get_available_recipes(self):
        return ["g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c", "tr\u1ee9ng chi\u00ean"]


# ==============================================================================
# RecipeExtractorDbusService Tests
# ==============================================================================

class TestRecipeExtractorDbusServiceInit(unittest.TestCase):
    def test_service_initialization_default(self):
        service = RecipeExtractorDbusService()
        self.assertIsNone(service.nlp_engine)
        self.assertIsNone(service.system_bus)
        self.assertFalse(service.is_connected)
        self.assertIsNone(service.dbus_object)
        self.assertIsNone(service._loop)
        self.assertIsNone(service._event_thread)

    def test_service_initialization_with_engine(self):
        mock_engine = MagicMock()
        service = RecipeExtractorDbusService(nlp_engine=mock_engine)
        self.assertIs(service.nlp_engine, mock_engine)

    def test_set_nlp_engine(self):
        service = RecipeExtractorDbusService()
        mock_engine = MagicMock()
        service.set_nlp_engine(mock_engine)
        self.assertIs(service.nlp_engine, mock_engine)

    def test_set_nlp_engine_replacement(self):
        service = RecipeExtractorDbusService()
        engine1 = MagicMock()
        engine2 = MagicMock()
        service.set_nlp_engine(engine1)
        service.set_nlp_engine(engine2)
        self.assertIs(service.nlp_engine, engine2)

    def test_service_constants(self):
        self.assertEqual(
            RecipeExtractorDbusService.SERVICE_NAME,
            "vn.edu.uit.FSS.RecipeExtractor"
        )
        self.assertEqual(
            RecipeExtractorDbusService.OBJECT_PATH,
            "/vn/edu/uit/FSS/RecipeExtractor"
        )
        self.assertEqual(
            RecipeExtractorDbusService.INTERFACE_NAME,
            "vn.edu.uit.FSS.RecipeExtractor"
        )
        self.assertEqual(
            RecipeExtractorDbusService.DBD_SERVICE,
            "vn.edu.uit.FSS.DBDaemon"
        )


class TestRecipeExtractorDbusServiceSetup(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()

    def test_setup_bus_service_sdbus_unavailable(self):
        if SDBUS_AVAILABLE:
            self.skipTest("sdbus is available in this environment")
        result = self.service.setup_bus_service()
        self.assertFalse(result)
        self.assertFalse(self.service.is_connected)

    @patch("recipe_extractor_service.SDBUS_AVAILABLE", False)
    def test_setup_bus_service_no_sdbus_forced(self):
        result = self.service.setup_bus_service()
        self.assertFalse(result)
        self.assertFalse(self.service.is_connected)

    def test_poll_bus_events(self):
        try:
            self.service.poll_bus_events()
        except Exception as e:
            self.fail(f"poll_bus_events raised unexpected exception: {e}")

    def test_stop_without_start(self):
        try:
            self.service.stop()
        except Exception as e:
            self.fail(f"stop without start raised exception: {e}")

    def test_double_stop_safe(self):
        self.service.stop()
        self.service.stop()

    def test_service_name_after_init(self):
        self.assertEqual(
            self.service.SERVICE_NAME,
            "vn.edu.uit.FSS.RecipeExtractor"
        )


class TestRecipeExtractorDbusServicePersistFlow(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.nlp_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_handle_extract_and_persist_success(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["dish"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")
            self.assertIn("ingredients", result)
            self.assertEqual(len(result["ingredients"]), 2)
            self.assertIn("batch_id", result)
            self.assertIn("persisted", result)
            self.assertIn("processing_time_ms", result)
            self.assertEqual(result["ingredients"][0]["ingredient"], "B\u01b0\u1edfi")
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_not_found(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("Nonexistent")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "NOT_FOUND")
            self.assertIn("suggestions", result)
            self.assertIn("batch_id", result)
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_invalid_input(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
            msg = result.get("message", result.get("error", ""))
            self.assertTrue("Invalid recipe name" in msg or "failed" in msg)
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_no_engine(self):
        self.service.nlp_engine = None
        async def run():
            result_json = await self.service._handle_extract_and_persist("Test")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("NLP engine not initialized", result["error"])
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_engine_error(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("error_test")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_unicode_handling(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            dish = result["dish"]
            self.assertIn("g\u1ecfi", dish)
        import asyncio
        asyncio.run(run())

    def test_handle_extract_and_persist_batch_id_uniqueness(self):
        async def run():
            r1 = json.loads(
                await self.service._handle_extract_and_persist("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
            )
            r2 = json.loads(
                await self.service._handle_extract_and_persist("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
            )
            self.assertNotEqual(r1["batch_id"], r2["batch_id"])
        import asyncio
        asyncio.run(run())

    def test_extract_and_persist_no_loop(self):
        service_no_loop = RecipeExtractorDbusService()
        service_no_loop.nlp_engine = MockNlpEngine()
        result_json = service_no_loop.extract_and_persist("Test")
        result = json.loads(result_json)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Event loop not running", result["error"])

    def test_extract_and_persist_no_engine_sync(self):
        service_no_engine = RecipeExtractorDbusService()
        loop = asyncio.new_event_loop()
        service_no_engine._loop = loop
        t = threading.Thread(target=loop.run_forever, daemon=True)
        t.start()
        try:
            result_json = service_no_engine.extract_and_persist("Test")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=3)
            loop.close()


class TestRecipeExtractorDbusServiceLifecycle(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.nlp_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_collback_dbus_insert_request_failure_handling(self):
        self.service._call_dbus_insert_request = AsyncMock(return_value=False)
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertFalse(result["persisted"])
        import asyncio
        asyncio.run(run())

    def test_callback_dbus_insert_request_exception(self):
        self.service._call_dbus_insert_request = AsyncMock(
            side_effect=RuntimeError("D-Bus connection refused")
        )
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        import asyncio
        asyncio.run(run())


@unittest.skipUnless(SDBUS_AVAILABLE, "Requires sdbus package")
class TestRecipeExtractorDbusObject(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.nlp_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_dbus_object_extract_and_persist_service_not_set(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        result = obj.ExtractAndPersistRecipe("test")
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "ERROR")

    def test_dbus_object_set_service_instance(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        obj.set_service_instance(self.service)
        import asyncio
        result_or_coro = obj.ExtractAndPersistRecipe(
            "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
        )
        if asyncio.iscoroutine(result_or_coro):
            async def run():
                result = await result_or_coro
                parsed = json.loads(result)
                self.assertEqual(parsed["status"], "SUCCESS")
            asyncio.run(run())
        else:
            parsed = json.loads(result_or_coro)
            self.assertEqual(parsed["status"], "SUCCESS")

    def test_dbus_object_export_and_unexport(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        try:
            obj.export_to_dbus("/test/path")
            obj.unexport()
        except Exception as e:
            self.fail(f"export/unexport raised exception: {e}")

    def test_dbus_object_not_found_response(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        obj.set_service_instance(self.service)
        import asyncio
        result_or_coro = obj.ExtractAndPersistRecipe("nonexistent")
        if asyncio.iscoroutine(result_or_coro):
            async def run():
                result = await result_or_coro
                parsed = json.loads(result)
                self.assertEqual(parsed["status"], "NOT_FOUND")
                self.assertIn("suggestions", parsed)
                self.assertIn("batch_id", parsed)
            asyncio.run(run())
        else:
            parsed = json.loads(result_or_coro)
            self.assertEqual(parsed["status"], "NOT_FOUND")
            self.assertIn("suggestions", parsed)
            self.assertIn("batch_id", parsed)


class TestFallbackDbusObject(unittest.TestCase):
    @patch("recipe_extractor_service.SDBUS_AVAILABLE", False)
    def test_fallback_class_extract_and_persist(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        result = obj.ExtractAndPersistRecipe("test")
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "ERROR")
        self.assertIn("D-Bus unavailable", parsed["error"])

    @patch("recipe_extractor_service.SDBUS_AVAILABLE", False)
    def test_fallback_class_export_does_nothing(self):
        from recipe_extractor_service import RecipeExtractorDbusObject
        obj = RecipeExtractorDbusObject()
        try:
            obj.export_to_dbus("/test")
            obj.unexport()
            obj.set_service_instance(None)
        except Exception as e:
            self.fail(f"Fallback methods raised exception: {e}")


class TestResponseFormatValidation(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.nlp_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_success_response_format(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            required_keys = {"status", "dish", "ingredients", "batch_id",
                             "persisted", "processing_time_ms"}
            self.assertTrue(required_keys.issubset(result.keys()))
            self.assertIsInstance(result["ingredients"], list)
            if result["ingredients"]:
                ing = result["ingredients"][0]
                self.assertIn("ingredient", ing)
                self.assertIn("quantity", ing)
        import asyncio
        asyncio.run(run())

    def test_not_found_response_format(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("nonexistent")
            result = json.loads(result_json)
            required_keys = {"status", "message", "dish", "suggestions", "batch_id"}
            self.assertTrue(required_keys.issubset(result.keys()))
            self.assertIsInstance(result["suggestions"], list)
        import asyncio
        asyncio.run(run())

    def test_error_response_format(self):
        self.service.nlp_engine = None
        async def run():
            result_json = await self.service._handle_extract_and_persist("Test")
            result = json.loads(result_json)
            required_keys = {"status", "error"}
            self.assertTrue(required_keys.issubset(result.keys()))
        import asyncio
        asyncio.run(run())

    def test_json_serializable_unicode(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            parsed = json.loads(result_json)
            self.assertEqual(parsed["dish"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")
        import asyncio
        asyncio.run(run())

    def test_empty_recipe_name_returns_error(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        import asyncio
        asyncio.run(run())

    def test_none_recipe_name_returns_error(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(None)
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        import asyncio
        asyncio.run(run())


# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServiceInit))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServiceSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServicePersistFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServiceLifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusObject))
    suite.addTests(loader.loadTestsFromTestCase(TestFallbackDbusObject))
    suite.addTests(loader.loadTestsFromTestCase(TestResponseFormatValidation))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
