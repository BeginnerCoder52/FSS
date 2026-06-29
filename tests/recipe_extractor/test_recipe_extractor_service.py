"""
Service Layer Tests - RecipeExtractorDbusService
=================================================

Purpose:
    Validate RecipeExtractorDbusService initialization, D-Bus lifecycle,
    Analyzer persist flow with new original_ingredients format.

Test Coverage:
    1. Service initialization (sdbus available/unavailable)
    2. D-Bus setup event loop management
    3. _handle_extract_and_persist with mocked Analyzer engine (new format)
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
Version: 2.0.0
Last Modified: 2026-06-21
"""

import unittest
import logging
import json
import sys
import asyncio
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recipe_extractor" / "src"))

from recipe_extractor_service import (
    RecipeExtractorDbusService,
    SDBUS_AVAILABLE,
)

logging.disable(logging.CRITICAL)


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
            raise RuntimeError("Simulated Analyzer engine failure")
        return {
            "status": "SUCCESS",
            "dish": normalized,
            "original_ingredients": [
                "B\u01b0\u1edfi : 1 tr\u00e1i",
                "M\u1ef1c kh\u00f4 : 1 con (50g)",
                "C\u00e0 r\u1ed1t : 2 c\u1ee7"
            ],
            "original_spices": ["Mu\u1ed1i", "\u0110\u01b0\u1eddng"],
            "serving": "4 ng\u01b0\u1eddi",
            "times": "30 Ph\u00fat",
            "difficulty": "D\u1ec5",
            "process": ["T\u00f4m lu\u1ed9c ch\u00edn"],
            "cook": ["Pha n\u01b0\u1edbc tr\u1ed9n"],
            "usage": ["B\u00e0y g\u1ecfi ra d\u0129a"],
            "tips": ["Ch\u1ecdn b\u01b0\u1edfi ch\u01b0a ch\u00edn h\u1eb3n"],
            "processing_time_ms": 0.01
        }

    def get_available_recipes(self):
        return ["g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c", "tr\u1ee9ng chi\u00ean"]


class TestRecipeExtractorDbusServiceInit(unittest.TestCase):
    def test_service_initialization_default(self):
        service = RecipeExtractorDbusService()
        self.assertIsNone(service.analyzer_engine)
        self.assertIsNone(service.system_bus)
        self.assertFalse(service.is_connected)
        self.assertIsNone(service.dbus_object)
        self.assertIsNone(service._loop)
        self.assertIsNone(service._event_thread)

    def test_service_initialization_with_engine(self):
        mock_engine = MagicMock()
        service = RecipeExtractorDbusService(analyzer_engine=mock_engine)
        self.assertIs(service.analyzer_engine, mock_engine)

    def test_set_analyzer_engine(self):
        service = RecipeExtractorDbusService()
        mock_engine = MagicMock()
        service.set_analyzer_engine(mock_engine)
        self.assertIs(service.analyzer_engine, mock_engine)

    def test_set_analyzer_engine_replacement(self):
        service = RecipeExtractorDbusService()
        engine1 = MagicMock()
        engine2 = MagicMock()
        service.set_analyzer_engine(engine1)
        service.set_analyzer_engine(engine2)
        self.assertIs(service.analyzer_engine, engine2)

    def test_service_constants(self):
        self.assertEqual(
            RecipeExtractorDbusService.SERVICE_NAME,
            "vn.edu.uit.FSS.RecipeExtractor"
        )
        self.assertEqual(
            RecipeExtractorDbusService.OBJECT_PATH,
            "/vn/edu/uit/FSS/RecipeExtractor"
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


class TestParseOriginalIngredients(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()

    def test_parse_standard_format(self):
        raw = ["B\u01b0\u1edfi : 1 tr\u00e1i", "Mu\u1ed1i : 1"]
        parsed = self.service._parse_original_ingredients(raw)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["ingredient"], "B\u01b0\u1edfi")
        self.assertEqual(parsed[0]["quantity"], "1 tr\u00e1i")

    def test_parse_no_delimiter_fallback(self):
        raw = ["Mu\u1ed1i"]
        parsed = self.service._parse_original_ingredients(raw)
        self.assertEqual(parsed[0]["ingredient"], "Mu\u1ed1i")
        self.assertEqual(parsed[0]["quantity"], "1")

    def test_parse_empty_list(self):
        parsed = self.service._parse_original_ingredients([])
        self.assertEqual(parsed, [])


class TestRecipeExtractorDbusServicePersistFlow(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.analyzer_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_handle_extract_and_persist_success(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["dish"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")
            self.assertIn("original_ingredients", result)
            self.assertEqual(len(result["original_ingredients"]), 3)
            self.assertIn("batch_id", result)
            self.assertIn("persisted", result)
            self.assertIn("processing_time_ms", result)
        asyncio.run(run())

    def test_handle_extract_and_persist_not_found(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("Nonexistent")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "NOT_FOUND")
            self.assertIn("suggestions", result)
            self.assertIn("batch_id", result)
        asyncio.run(run())

    def test_handle_extract_and_persist_invalid_input(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        asyncio.run(run())

    def test_handle_extract_and_persist_no_engine(self):
        self.service.analyzer_engine = None
        async def run():
            result_json = await self.service._handle_extract_and_persist("Test")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("Analyzer engine not initialized", result["error"])
        asyncio.run(run())

    def test_handle_extract_and_persist_engine_error(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("error_test")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
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
        asyncio.run(run())

    def test_extract_and_persist_no_loop(self):
        service_no_loop = RecipeExtractorDbusService()
        service_no_loop.analyzer_engine = MockNlpEngine()
        result_json = service_no_loop.extract_and_persist("Test")
        result = json.loads(result_json)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Event loop not running", result["error"])


class TestResponseFormatValidation(unittest.TestCase):
    def setUp(self):
        self.service = RecipeExtractorDbusService()
        self.service.analyzer_engine = MockNlpEngine()
        self.service._call_dbus_insert_request = AsyncMock(return_value=True)

    def test_success_response_format(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            result = json.loads(result_json)
            required_keys = {
                "status", "dish", "original_ingredients", "original_spices",
                "serving", "times", "difficulty", "process",
                "cook", "usage", "tips",
                "batch_id", "persisted", "processing_time_ms"
            }
            self.assertTrue(required_keys.issubset(result.keys()))
            self.assertIsInstance(result["original_ingredients"], list)
        asyncio.run(run())

    def test_not_found_response_format(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("nonexistent")
            result = json.loads(result_json)
            required_keys = {"status", "message", "dish", "suggestions", "batch_id"}
            self.assertTrue(required_keys.issubset(result.keys()))
            self.assertIsInstance(result["suggestions"], list)
        asyncio.run(run())

    def test_error_response_format(self):
        self.service.analyzer_engine = None
        async def run():
            result_json = await self.service._handle_extract_and_persist("Test")
            result = json.loads(result_json)
            required_keys = {"status", "error"}
            self.assertTrue(required_keys.issubset(result.keys()))
        asyncio.run(run())

    def test_json_serializable_unicode(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist(
                "G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c"
            )
            parsed = json.loads(result_json)
            self.assertEqual(parsed["dish"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")
        asyncio.run(run())

    def test_empty_recipe_name_returns_error(self):
        async def run():
            result_json = await self.service._handle_extract_and_persist("")
            result = json.loads(result_json)
            self.assertEqual(result["status"], "ERROR")
        asyncio.run(run())


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServiceInit))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServiceSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestParseOriginalIngredients))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorDbusServicePersistFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestResponseFormatValidation))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
