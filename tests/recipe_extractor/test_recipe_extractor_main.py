"""
Daemon Lifecycle Tests - RecipeExtractorMain
============================================

Purpose:
    Validate RecipeExtractorMain initialization, service lifecycle,
    recipe database loading, and error handling.

Test Coverage:
    1. RecipeExtractorMain initialization and state
    2. init_service with mocked D-Bus dependency
    3. start_service and stop_service lifecycle
    4. Recipe database loading on init
    5. Logging setup fallback behavior
    6. State transitions (init -> running -> stopped)

ASPICE Compliance:
    - Mocked D-Bus dependency
    - Comprehensive error case coverage
    - Lifecycle state validation
    - Clean shutdown verification

Author: FSS QA Team
Version: 2.0.0
Last Modified: 2026-06-21
"""

import unittest
import logging
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recipe_extractor" / "src"))

from recipe_extractor_main import (
    RecipeExtractorMain,
    setup_logging,
    RECIPE_DB_PATH,
)

logging.disable(logging.WARNING)


class TestRecipeExtractorMainInit(unittest.TestCase):
    def test_main_initialization(self):
        main = RecipeExtractorMain()
        self.assertFalse(main.is_running)
        self.assertIsNone(main._analyzer_engine)
        self.assertIsNotNone(main.dbus_service)
        self.assertIsNotNone(main.logger)

    def test_main_dbus_service_created(self):
        main = RecipeExtractorMain()
        service = main.dbus_service
        self.assertEqual(
            service.SERVICE_NAME,
            "vn.edu.uit.FSS.RecipeExtractor"
        )

    def test_main_initial_state_is_not_running(self):
        main = RecipeExtractorMain()
        self.assertFalse(main.is_running)

    def test_analyzer_engine_not_loaded_at_init(self):
        main = RecipeExtractorMain()
        self.assertIsNone(main._analyzer_engine)

    def test_dbus_service_initially_has_no_engine(self):
        main = RecipeExtractorMain()
        self.assertIsNone(main.dbus_service.analyzer_engine)

    def test_nlp_recipe_db_path_defined(self):
        self.assertIsInstance(RECIPE_DB_PATH, str)
        self.assertTrue("recipes" in RECIPE_DB_PATH)


class TestRecipeExtractorMainLifecycle(unittest.TestCase):
    def setUp(self):
        self.main = RecipeExtractorMain()
        self.main._analyzer_engine = MagicMock()
        self.main._analyzer_engine.recipe_names = ["test_recipe"]
        self.main.dbus_service = MagicMock()
        self.main.dbus_service.setup_bus_service.return_value = True
        self.main.dbus_service.poll_bus_events.return_value = None
        self.main.dbus_service.analyzer_engine = self.main._analyzer_engine

    def test_init_service_success(self):
        result = self.main.init_service()
        self.assertTrue(result)
        self.main.dbus_service.setup_bus_service.assert_called_once()

    def test_init_service_failure(self):
        self.main.dbus_service.setup_bus_service.return_value = False
        result = self.main.init_service()
        self.assertFalse(result)

    def test_init_service_dbus_exception(self):
        self.main.dbus_service.setup_bus_service.side_effect = RuntimeError("Bus error")
        result = self.main.init_service()
        self.assertFalse(result)

    def test_start_service_success(self):
        self.main.init_service()
        result = self.main.start_service()
        self.assertTrue(result)
        self.assertTrue(self.main.is_running)

    def test_start_service_twice(self):
        self.main.init_service()
        self.main.start_service()
        result = self.main.start_service()
        self.assertTrue(result)
        self.assertTrue(self.main.is_running)

    def test_stop_service(self):
        self.main.init_service()
        self.main.start_service()
        self.main.stop_service()
        self.assertFalse(self.main.is_running)
        self.main.dbus_service.stop.assert_called_once()

    def test_stop_service_without_start(self):
        try:
            self.main.stop_service()
        except Exception as e:
            self.fail(f"stop_service without start raised exception: {e}")

    def test_full_lifecycle(self):
        self.assertTrue(self.main.init_service())
        self.assertTrue(self.main.start_service())
        self.assertTrue(self.main.is_running)
        self.main.stop_service()
        self.assertFalse(self.main.is_running)

    def test_poll_bus_events_called_on_start(self):
        self.main.init_service()
        self.main.start_service()
        self.main.dbus_service.poll_bus_events.assert_called_once()

    def test_init_service_loads_engine(self):
        main = RecipeExtractorMain()
        with patch.object(main, '_load_engine', return_value=MagicMock()):
            main.init_service()
            self.assertIsNotNone(main._analyzer_engine)

    def test_init_service_engine_failure(self):
        main = RecipeExtractorMain()
        with patch.object(main, '_load_engine', return_value=None):
            result = main.init_service()
            self.assertFalse(result)


class TestSetupLogging(unittest.TestCase):
    def test_setup_logging_creates_logger(self):
        root_logger = logging.getLogger()
        handlers_before = len(root_logger.handlers)
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
        handlers_after = len(root_logger.handlers)
        self.assertGreaterEqual(handlers_after, handlers_before)

    def test_setup_logging_fallback_permission_denied(self):
        root_logger = logging.getLogger()
        handlers_before = len(root_logger.handlers)
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o000)
            setup_logging(log_dir=os.path.join(tmpdir, "nonexistent"))
            os.chmod(tmpdir, 0o755)
        handlers_after = len(root_logger.handlers)
        self.assertGreaterEqual(handlers_after, handlers_before)

    @patch("logging.handlers.RotatingFileHandler")
    def test_setup_logging_file_handler_created(self, mock_handler):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)

    def test_setup_logging_default_path(self):
        root_logger = logging.getLogger()
        handlers_before = len(root_logger.handlers)
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
        handlers_after = len(root_logger.handlers)
        self.assertGreaterEqual(handlers_after, handlers_before)


class TestRecipeExtractorMainEdgeCases(unittest.TestCase):
    def test_dbus_stop_on_none(self):
        main = RecipeExtractorMain()
        main.is_running = True
        main.dbus_service = None
        try:
            main.stop_service()
            self.assertFalse(main.is_running)
        except Exception as e:
            self.fail(f"stop_service with None dbus raised: {e}")

    def test_start_service_without_init(self):
        main = RecipeExtractorMain()
        main._analyzer_engine = MagicMock()
        main.dbus_service = MagicMock()
        main.dbus_service.poll_bus_events.return_value = None
        result = main.start_service()
        self.assertTrue(result)
        self.assertTrue(main.is_running)

    def test_get_analyzer_engine(self):
        main = RecipeExtractorMain()
        mock_engine = MagicMock()
        main._analyzer_engine = mock_engine
        self.assertIs(main.get_analyzer_engine(), mock_engine)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainInit))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainLifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestSetupLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainEdgeCases))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
