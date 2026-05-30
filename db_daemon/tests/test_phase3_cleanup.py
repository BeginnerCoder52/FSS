"""
@file test_phase3_cleanup.py
@brief Unit tests for Phase 3 DBDaemon cleanup and pure DB D-Bus interface.

This module validates Phase 3 architectural changes:
1. RecommendationEngine has been removed (moved to recommend_daemon/)
2. DbDaemonMain no longer depends on RecommendationEngine
3. Pure database D-Bus methods (GetInventory, GetRequests, InsertRequest, ClearRequest)
4. DbDbusInterface no longer has recommendation-specific callbacks
5. Backward compatibility of SqliteManager operations

ASPICE Compliance:
    - Isolated unit tests (no external dependencies)
    - Comprehensive error case coverage
    - Input validation tests
    - Clear test documentation

Author: FSS QA Team
Version: 1.0.0
"""

import unittest
import logging
import json
import tempfile
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from SqliteManager import SqliteManager, DatabaseType
from DbDbusInterface import DbDbusInterface
from DbDaemonMain import DbDaemonMain, DaemonState
from DiskFileManager import DiskFileManager


class TestRecommendationEngineRemoved(unittest.TestCase):
    """Verify RecommendationEngine has been removed from db_daemon."""

    def test_recommendation_engine_module_missing(self):
        """RecommendationEngine.py must not exist in db_daemon/src/."""
        engine_path = Path(__file__).parent.parent / "src" / "RecommendationEngine.py"
        self.assertFalse(
            engine_path.exists(),
            f"RecommendationEngine.py still exists at {engine_path}"
        )

    def test_import_recommendation_engine_fails(self):
        """Importing RecommendationEngine from db_daemon must raise ImportError."""
        with self.assertRaises(ImportError):
            import RecommendationEngine  # noqa: F401

    def test_db_daemon_main_no_recommendation_engine(self):
        """DbDaemonMain must not have recommendation_engine attribute."""
        daemon = DbDaemonMain()
        self.assertFalse(
            hasattr(daemon, 'recommendation_engine'),
            "DbDaemonMain should not have recommendation_engine attribute"
        )


class TestDbDbusInterfacePureDB(unittest.TestCase):
    """Verify DbDbusInterface has pure DB callbacks instead of recommendation callbacks."""

    def setUp(self):
        self.interface = DbDbusInterface()

    def test_no_recommendation_callbacks(self):
        """DbDbusInterface must not have recommendation-specific callback fields."""
        self.assertFalse(
            hasattr(self.interface, '_shopping_list_callback'),
            "Should not have _shopping_list_callback"
        )
        self.assertFalse(
            hasattr(self.interface, '_inventory_update_callback'),
            "Should not have _inventory_update_callback"
        )
        self.assertFalse(
            hasattr(self.interface, '_recipes_callback'),
            "Should not have _recipes_callback"
        )

    def test_has_new_pure_db_callbacks(self):
        """DbDbusInterface must have pure database operation callbacks."""
        self.assertTrue(
            hasattr(self.interface, '_inventory_callback'),
            "Must have _inventory_callback"
        )
        self.assertTrue(
            hasattr(self.interface, '_requests_callback'),
            "Must have _requests_callback"
        )
        self.assertTrue(
            hasattr(self.interface, '_insert_request_callback'),
            "Must have _insert_request_callback"
        )
        self.assertTrue(
            hasattr(self.interface, '_clear_request_callback'),
            "Must have _clear_request_callback"
        )

    def test_set_inventory_callback(self):
        """set_inventory_callback must register callback."""
        mock = MagicMock()
        self.interface.set_inventory_callback(mock)
        self.assertIs(self.interface._inventory_callback, mock)

    def test_set_requests_callback(self):
        """set_requests_callback must register callback."""
        mock = MagicMock()
        self.interface.set_requests_callback(mock)
        self.assertIs(self.interface._requests_callback, mock)

    def test_set_insert_request_callback(self):
        """set_insert_request_callback must register callback."""
        mock = MagicMock()
        self.interface.set_insert_request_callback(mock)
        self.assertIs(self.interface._insert_request_callback, mock)

    def test_set_clear_request_callback(self):
        """set_clear_request_callback must register callback."""
        mock = MagicMock()
        self.interface.set_clear_request_callback(mock)
        self.assertIs(self.interface._clear_request_callback, mock)

    def test_no_recommendation_updated_signal(self):
        """DbDaemonDbusObject must not have RecommendationUpdated signal."""
        from DbDbusInterface import DbDaemonDbusObject
        self.assertFalse(
            hasattr(DbDaemonDbusObject, 'RecommendationUpdated'),
            "RecommendationUpdated signal must be removed"
        )


class TestDbDaemonMainCleanup(unittest.TestCase):
    """Verify DbDaemonMain no longer depends on RecommendationEngine."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_phase3_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(DbDbusInterface, 'setup_bus_service', return_value=True)
    @patch.object(DiskFileManager, 'init_directories', return_value=True)
    @patch.object(SqliteManager, 'connect_all_dbs', return_value=True)
    @patch.object(SqliteManager, 'init_tables_if_not_exists', return_value=None)
    def test_init_daemon_without_recommendation_engine(
        self, mock_tables, mock_connect, mock_dirs, mock_setup
    ):
        """init_daemon must succeed without RecommendationEngine."""
        daemon = DbDaemonMain()
        result = daemon.init_daemon()
        self.assertTrue(result)
        self.assertEqual(daemon.current_state, DaemonState.IDLE)

    def test_no_nlp_model_path_constants(self):
        """DbDaemonMain must not import NLP model path constants."""
        daemon = DbDaemonMain()
        self.assertFalse(
            hasattr(daemon, 'NLP_MODEL_PATH'),
            "NLP_MODEL_PATH must be removed"
        )

    @patch.object(DbDbusInterface, 'setup_bus_service', return_value=True)
    @patch.object(DiskFileManager, 'init_directories', return_value=True)
    @patch.object(SqliteManager, 'connect_all_dbs', return_value=True)
    @patch.object(SqliteManager, 'init_tables_if_not_exists', return_value=None)
    def test_register_event_handlers_pure_db(
        self, mock_tables, mock_connect, mock_dirs, mock_setup
    ):
        """_register_event_handlers must register pure DB callbacks."""
        daemon = DbDaemonMain()
        daemon.init_daemon()
        self.assertIsNotNone(daemon.dbus_interface._inventory_callback)
        self.assertIsNotNone(daemon.dbus_interface._requests_callback)
        self.assertIsNotNone(daemon.dbus_interface._insert_request_callback)
        self.assertIsNotNone(daemon.dbus_interface._clear_request_callback)


class TestSqliteManagerPureDBMethods(unittest.TestCase):
    """Verify SqliteManager pure DB methods work correctly."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_puredb_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()

    @classmethod
    def tearDownClass(cls):
        cls.db_manager.close_connection()
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_get_all_inventory_empty(self):
        """get_all_inventory must return empty list when no items."""
        items = self.db_manager.get_all_inventory()
        self.assertIsInstance(items, list)

    def test_get_all_requests_empty(self):
        """get_all_requests must return empty list when no requests."""
        requests = self.db_manager.get_all_requests()
        self.assertIsInstance(requests, list)

    def test_insert_request_batch_and_get_all(self):
        """insert_request_batch + get_all_requests must work end-to-end."""
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "pork", "quantity": 2, "unit": "kg"},
            {"food_id": "garlic", "quantity": 3, "unit": "cloves"}
        ]
        result = self.db_manager.insert_request_batch(
            "Thịt Kho", ingredients, batch_id
        )
        self.assertTrue(result)
        requests = self.db_manager.get_all_requests()
        self.assertGreaterEqual(len(requests), 2)

    def test_clear_request_batch(self):
        """clear_request_batch must remove all items for batch_id."""
        batch_id = str(uuid.uuid4())
        ingredients = [{"food_id": "chicken", "quantity": 1, "unit": "kg"}]
        self.db_manager.insert_request_batch(
            "Cơm Gà", ingredients, batch_id
        )
        result = self.db_manager.clear_request_batch(batch_id)
        self.assertTrue(result)
        remaining = self.db_manager.get_requests_by_recipe("Cơm Gà")
        self.assertEqual(len(remaining), 0)

    def test_get_requests_by_recipe(self):
        """get_requests_by_recipe must filter by recipe name."""
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "fish", "quantity": 1, "unit": "kg"},
            {"food_id": "salt", "quantity": 1, "unit": "tsp"}
        ]
        self.db_manager.insert_request_batch(
            "Cá Kho", ingredients, batch_id
        )
        items = self.db_manager.get_requests_by_recipe("Cá Kho")
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertEqual(item['recipe_name'], 'Cá Kho')

    def test_compare_inventory_vs_request(self):
        """compare_inventory_vs_request must work after changes."""
        self.db_manager.update_inventory("milk", 5, 0.95)
        batch_id = str(uuid.uuid4())
        ingredients = [{"food_id": "milk", "quantity": 3, "unit": "liters"}]
        self.db_manager.insert_request_batch(
            "Sinh Tố", ingredients, batch_id
        )
        shortage = self.db_manager.compare_inventory_vs_request()
        milk_shortage = [s for s in shortage if s['food_id'] == 'milk']
        self.assertEqual(len(milk_shortage), 0)

    def test_insert_inventory_history(self):
        """insert_inventory_history must create audit trail."""
        result = self.db_manager.insert_inventory_history(
            food_id="apple",
            quantity_before=0,
            quantity_after=10,
            confidence_score=0.95,
            image_path="/path/apple.jpg",
            change_reason="USER_MANUAL",
            changed_by="TEST",
            changed_at=datetime.now().isoformat()
        )
        self.assertTrue(result)

    def test_get_inventory_history(self):
        """get_inventory_history must retrieve audit records."""
        self.db_manager.insert_inventory_history(
            food_id="banana",
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.90,
            image_path=None,
            change_reason="FRT_DETECTION",
            changed_by="FRTApp",
            changed_at=datetime.now().isoformat()
        )
        history = self.db_manager.get_inventory_history("banana")
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]['food_id'], 'banana')
        self.assertEqual(history[0]['change_reason'], 'FRT_DETECTION')


class TestBackwardCompatibility(unittest.TestCase):
    """Verify existing core operations still work after cleanup."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_bwd_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()

    @classmethod
    def tearDownClass(cls):
        cls.db_manager.close_connection()
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_update_inventory(self):
        """update_inventory must still work."""
        result = self.db_manager.update_inventory("butter", 3, 0.88)
        self.assertTrue(result)
        item = self.db_manager.get_inventory_item("butter")
        self.assertIsNotNone(item)
        self.assertEqual(item['quantity'], 3)

    def test_insert_environment_log(self):
        """insert_environment_log must still work."""
        result = self.db_manager.insert_environment_log(
            22.5, 60.0, 1234567890.0
        )
        self.assertTrue(result)

    def test_insert_door_sensor_log(self):
        """insert_door_sensor_log must still work."""
        result = self.db_manager.insert_door_sensor_log(
            "DOOR_OPEN", 1234567890.0
        )
        self.assertTrue(result)

    def test_insert_distance_sensor_log(self):
        """insert_distance_sensor_log must still work."""
        result = self.db_manager.insert_distance_sensor_log(
            45.0, 1234567890.0
        )
        self.assertTrue(result)

    def test_insert_presence_sensor_log(self):
        """insert_presence_sensor_log must still work."""
        result = self.db_manager.insert_presence_sensor_log(
            True, 1234567890.0
        )
        self.assertTrue(result)


class TestDbDaemonMainDbusMethodHandlers(unittest.TestCase):
    """Verify DbDaemonMain D-Bus method handlers work correctly."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_handlers_")
        cls.daemon = DbDaemonMain()
        cls.daemon.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.daemon.db_manager.connect_all_dbs()
        cls.daemon.db_manager.init_tables_if_not_exists()

    @classmethod
    def tearDownClass(cls):
        cls.daemon.db_manager.close_connection()
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_handle_get_inventory_empty(self):
        """_handle_get_inventory must return list when db_manager exists."""
        result = self.daemon._handle_get_inventory()
        self.assertIsInstance(result, list)

    def test_handle_get_requests_empty(self):
        """_handle_get_requests must return list when db_manager exists."""
        result = self.daemon._handle_get_requests()
        self.assertIsInstance(result, list)

    def test_handle_insert_request(self):
        """_handle_insert_request must insert and return True."""
        batch_id = str(uuid.uuid4())
        ingredients = [{"food_id": "tofu", "quantity": 2, "unit": "blocks"}]
        result = self.daemon._handle_insert_request(
            "Đậu Sốt Cà", ingredients, batch_id
        )
        self.assertTrue(result)
        requests = self.daemon.db_manager.get_requests_by_recipe("Đậu Sốt Cà")
        self.assertEqual(len(requests), 1)

    def test_handle_clear_request(self):
        """_handle_clear_request must clear batch and return True."""
        batch_id = str(uuid.uuid4())
        ingredients = [{"food_id": "shrimp", "quantity": 500, "unit": "g"}]
        self.daemon.db_manager.insert_request_batch(
            "Tôm Xào", ingredients, batch_id
        )
        result = self.daemon._handle_clear_request(batch_id)
        self.assertTrue(result)
        remaining = self.daemon.db_manager.get_requests_by_recipe("Tôm Xào")
        self.assertEqual(len(remaining), 0)

    def test_handle_get_inventory_no_db(self):
        """_handle_get_inventory must return empty list when db_manager is None."""
        saved = self.daemon.db_manager
        self.daemon.db_manager = None
        result = self.daemon._handle_get_inventory()
        self.assertEqual(result, [])
        self.daemon.db_manager = saved

    def test_handle_get_requests_no_db(self):
        """_handle_get_requests must return empty list when db_manager is None."""
        saved = self.daemon.db_manager
        self.daemon.db_manager = None
        result = self.daemon._handle_get_requests()
        self.assertEqual(result, [])
        self.daemon.db_manager = saved

    def test_handle_insert_request_no_db(self):
        """_handle_insert_request must return False when db_manager is None."""
        saved = self.daemon.db_manager
        self.daemon.db_manager = None
        result = self.daemon._handle_insert_request("test", [], "batch")
        self.assertFalse(result)
        self.daemon.db_manager = saved

    def test_handle_clear_request_no_db(self):
        """_handle_clear_request must return False when db_manager is None."""
        saved = self.daemon.db_manager
        self.daemon.db_manager = None
        result = self.daemon._handle_clear_request("batch")
        self.assertFalse(result)
        self.daemon.db_manager = saved


def run_tests():
    """Run all Phase 3 tests and print summary."""
    print("\n" + "=" * 70)
    print("FSS Phase 3 - DBDaemon Cleanup Tests")
    print("=" * 70 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestRecommendationEngineRemoved))
    suite.addTests(loader.loadTestsFromTestCase(TestDbDbusInterfacePureDB))
    suite.addTests(loader.loadTestsFromTestCase(TestDbDaemonMainCleanup))
    suite.addTests(loader.loadTestsFromTestCase(TestSqliteManagerPureDBMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestDbDaemonMainDbusMethodHandlers))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("ALL PHASE 3 TESTS PASSED - DBDaemon cleanup valid")
    else:
        print("SOME PHASE 3 TESTS FAILED - Review errors above")

    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print("=" * 70 + "\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
