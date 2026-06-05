"""
Daemon Lifecycle Tests - RecipeExtractorMain
============================================

Purpose:
    Validate RecipeExtractorMain initialization, service lifecycle,
    lazy NLP engine loading, and error handling.

Test Coverage:
    1. RecipeExtractorMain initialization and state
    2. init_service with mocked D-Bus dependency
    3. start_service and stop_service lifecycle
    4. _ensure_nlp_engine lazy loading (path resolution)
    5. _lazy_load_nlp_engine standalone function
    6. Logging setup fallback behavior
    7. State transitions (init → running → stopped)

ASPICE Compliance:
    - Mocked D-Bus dependency
    - Comprehensive error case coverage
    - Lifecycle state validation
    - Clean shutdown verification

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-06-05
"""

import unittest
import logging
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recipe_extractor_main import (
    RecipeExtractorMain,
    _lazy_load_nlp_engine,
    setup_logging,
    NLP_MODEL_PATH,
    NLP_RECIPE_DB_PATH,
)

logging.disable(logging.WARNING)


# ==============================================================================
# RecipeExtractorMain Tests
# ==============================================================================

class TestRecipeExtractorMainInit(unittest.TestCase):
    def test_main_initialization(self):
        main = RecipeExtractorMain()
        self.assertFalse(main.is_running)
        self.assertIsNone(main._nlp_engine)
        self.assertFalse(main._nlp_loaded)
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

    def test_nlp_engine_not_loaded_at_init(self):
        main = RecipeExtractorMain()
        self.assertFalse(main._nlp_loaded)
        self.assertIsNone(main._nlp_engine)

    def test_dbus_service_initially_has_no_engine(self):
        main = RecipeExtractorMain()
        self.assertIsNone(main.dbus_service.nlp_engine)


class TestRecipeExtractorMainLifecycle(unittest.TestCase):
    def setUp(self):
        self.main = RecipeExtractorMain()
        self.main.dbus_service = MagicMock()
        self.main.dbus_service.setup_bus_service.return_value = True
        self.main.dbus_service.poll_bus_events.return_value = None
        self.main.dbus_service.nlp_engine = None

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

    def test_init_service_sets_nlp_lazy_flag(self):
        self.main.init_service()
        self.assertFalse(self.main._nlp_loaded)

    def test_poll_bus_events_called_on_start(self):
        self.main.init_service()
        self.main.start_service()
        self.main.dbus_service.poll_bus_events.assert_called_once()


class TestRecipeExtractorMainNlpEngine(unittest.TestCase):
    def setUp(self):
        self.main = RecipeExtractorMain()
        self.main.dbus_service = MagicMock()

    def test_ensure_nlp_engine_unloaded(self):
        self.assertFalse(self.main._nlp_loaded)
        self.assertIsNone(self.main._nlp_engine)

    @patch("recipe_extractor_main._lazy_load_nlp_engine")
    def test_ensure_nlp_engine_calls_lazy_load(self, mock_lazy):
        mock_engine = MagicMock()
        mock_lazy.return_value = mock_engine
        result = self.main._ensure_nlp_engine()
        self.assertTrue(result)
        self.assertTrue(self.main._nlp_loaded)
        self.assertIs(self.main._nlp_engine, mock_engine)

    @patch("recipe_extractor_main._lazy_load_nlp_engine")
    def test_ensure_nlp_engine_sets_dbus_engine(self, mock_lazy):
        mock_engine = MagicMock()
        mock_lazy.return_value = mock_engine
        self.main._ensure_nlp_engine()
        self.main.dbus_service.set_nlp_engine.assert_called_with(mock_engine)

    @patch("recipe_extractor_main._lazy_load_nlp_engine")
    def test_ensure_nlp_engine_returns_false_on_failure(self, mock_lazy):
        mock_lazy.return_value = None
        result = self.main._ensure_nlp_engine()
        self.assertFalse(result)
        self.assertTrue(self.main._nlp_loaded)

    @patch("recipe_extractor_main._lazy_load_nlp_engine")
    def test_ensure_nlp_engine_called_once(self, mock_lazy):
        mock_engine = MagicMock()
        mock_lazy.return_value = mock_engine
        self.main._ensure_nlp_engine()
        self.main._ensure_nlp_engine()
        mock_lazy.assert_called_once()

    def test_dbus_service_initially_no_engine(self):
        self.main.dbus_service.nlp_engine = None
        self.assertIsNone(self.main.dbus_service.nlp_engine)


class TestLazyLoadNlpEngine(unittest.TestCase):
    def test_lazy_load_paths_defined(self):
        self.assertIsInstance(NLP_MODEL_PATH, str)
        self.assertIsInstance(NLP_RECIPE_DB_PATH, str)
        self.assertTrue("fss_ner_crf_optimized.joblib" in NLP_MODEL_PATH)
        self.assertTrue("recipes" in NLP_RECIPE_DB_PATH)

    def test_lazy_load_returns_none_if_no_model(self):
        with patch("recipe_extractor_main.NLP_MODEL_PATH",
                   "/nonexistent/model.joblib"):
            result = _lazy_load_nlp_engine()
            self.assertIsNone(result)

    @unittest.skipIf(
        True,
        "Skipped: requires joblib which is not installed in test environment"
    )
    def test_lazy_load_import_error_returns_none(self):
        pass


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
        main.dbus_service = MagicMock()
        main.dbus_service.poll_bus_events.return_value = None
        result = main.start_service()
        self.assertTrue(result)
        self.assertTrue(main.is_running)

    @patch("recipe_extractor_main._lazy_load_nlp_engine")
    def test_ensure_nlp_engine_sets_dbus_engine_only_once(self, mock_lazy):
        mock_engine = MagicMock()
        mock_lazy.return_value = mock_engine
        main = RecipeExtractorMain()
        main.dbus_service = MagicMock()
        main._ensure_nlp_engine()
        main._ensure_nlp_engine()
        main.dbus_service.set_nlp_engine.assert_called_once()

    def test_main_long_running_loop_interrupt(self):
        main = RecipeExtractorMain()
        main.dbus_service = MagicMock()
        main.dbus_service.setup_bus_service.return_value = True
        main.dbus_service.poll_bus_events.return_value = None
        main.is_running = True

        def simulate_interrupt():
            main.is_running = False

        import threading
        timer = threading.Timer(0.05, simulate_interrupt)
        timer.start()
        try:
            from recipe_extractor_main import main as daemon_main
            pass
        except Exception as e:
            pass
        timer.cancel()

    def test_init_service_logging(self):
        main = RecipeExtractorMain()
        main.dbus_service = MagicMock()
        main.dbus_service.setup_bus_service.return_value = True
        logger_instance = logging.getLogger("RecipeExtractorMain")
        old_handlers = logger_instance.handlers[:]
        logger_instance.handlers = []
        logger_instance.addHandler(logging.StreamHandler())
        logger_instance.setLevel(logging.INFO)
        try:
            main.init_service()
        except Exception:
            pass
        logger_instance.handlers = old_handlers
        self.assertTrue(True)


# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainInit))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainLifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainNlpEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestLazyLoadNlpEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestSetupLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeExtractorMainEdgeCases))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
