#!/usr/bin/env python3
"""
@file run_phase1_tests.py
@brief Standalone test runner for Phase 1 schema validation.

This script runs Phase 1 tests without requiring pytest.
It uses unittest framework (built-in to Python).

Usage:
    python run_phase1_tests.py
    
Output:
    ✓ All tests passed
    ✗ Some tests failed (see detailed output)
"""

import unittest
import sys
import os
import tempfile
import shutil
from datetime import datetime
import uuid

# Add db_daemon source to path
test_dir = os.path.dirname(os.path.abspath(__file__))
fss_root = os.path.dirname(test_dir)
db_daemon_src = os.path.join(fss_root, 'db_daemon', 'src')
sys.path.insert(0, db_daemon_src)

from SqliteManager import SqliteManager, DatabaseType


class TestPhase1SchemaValidation(unittest.TestCase):
    """Test Phase 1 database schema changes."""
    
    @classmethod
    def setUpClass(cls):
        """Setup test database once for all tests."""
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_test_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()
    
    @classmethod
    def tearDownClass(cls):
        """Cleanup test database."""
        cls.db_manager.close_connection()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def test_01_inventory_history_table_exists(self):
        """Verify inventory_history table exists with correct schema."""
        cursor = self.db_manager._cursors[DatabaseType.INVENTORY]
        cursor.execute("PRAGMA table_info(inventory_history)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required = ['id', 'food_id', 'quantity_before', 'quantity_after',
                   'confidence_score', 'image_path', 'change_reason', 'changed_by',
                   'changed_at', 'created_at']
        
        for col in required:
            self.assertIn(col, column_names, f"Missing column: {col}")
        
        print(f"  ✓ inventory_history table valid ({len(column_names)} columns)")
    
    def test_02_inventory_history_indexes(self):
        """Verify indexes on inventory_history table."""
        cursor = self.db_manager._cursors[DatabaseType.INVENTORY]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='inventory_history'")
        indexes = [idx[0] for idx in cursor.fetchall()]
        
        expected = ['idx_inventory_history_food_id', 'idx_inventory_history_timestamp']
        for idx in expected:
            self.assertIn(idx, indexes, f"Missing index: {idx}")
        
        print(f"  ✓ inventory_history indexes created ({len(indexes)})")
    
    def test_03_current_inventory_version_fields(self):
        """Verify current_inventory has version tracking fields."""
        cursor = self.db_manager._cursors[DatabaseType.INVENTORY]
        cursor.execute("PRAGMA table_info(current_inventory)")
        columns = [col[1] for col in cursor.fetchall()]
        
        for col in ['version_id', 'last_change_reason', 'last_changed_by']:
            self.assertIn(col, columns, f"Missing column: {col}")
        
        print(f"  ✓ current_inventory version tracking fields added")
    
    def test_04_request_table_recipe_fields(self):
        """Verify request table has recipe tracking fields."""
        cursor = self.db_manager._cursors[DatabaseType.REQUEST]
        cursor.execute("PRAGMA table_info(request)")
        columns = [col[1] for col in cursor.fetchall()]
        
        for col in ['recipe_name', 'request_batch_id']:
            self.assertIn(col, columns, f"Missing column: {col}")
        
        print(f"  ✓ request table recipe fields added")
    
    def test_05_request_table_indexes(self):
        """Verify request table indexes created."""
        cursor = self.db_manager._cursors[DatabaseType.REQUEST]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='request'")
        indexes = [idx[0] for idx in cursor.fetchall()]
        
        expected = ['idx_request_recipe_name', 'idx_request_batch_id', 'idx_request_food_id']
        for idx in expected:
            self.assertIn(idx, indexes, f"Missing index: {idx}")
        
        print(f"  ✓ request table indexes created ({len(indexes)})")


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility - existing APIs still work."""
    
    @classmethod
    def setUpClass(cls):
        """Setup test database."""
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_test_compat_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()
    
    @classmethod
    def tearDownClass(cls):
        """Cleanup."""
        cls.db_manager.close_connection()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def test_01_update_inventory_works(self):
        """Existing update_inventory() method works."""
        result = self.db_manager.update_inventory(
            food_id="test_item",
            quantity_delta=5,
            confidence_score=0.95,
            image_path="/opt/fss/assets/test.jpg"
        )
        
        self.assertTrue(result)
        item = self.db_manager.get_inventory_item("test_item")
        self.assertIsNotNone(item)
        self.assertEqual(item['quantity'], 5)
        
        print(f"  ✓ update_inventory() works")
    
    def test_02_insert_request_works(self):
        """Existing insert_request() method works."""
        result = self.db_manager.insert_request(
            food_id="test_food",
            quantity=2,
            unit="kg"
        )
        
        self.assertTrue(result)
        requests = self.db_manager.get_all_requests()
        self.assertGreater(len(requests), 0)
        
        print(f"  ✓ insert_request() works")
    
    def test_03_get_all_inventory_works(self):
        """Existing get_all_inventory() method works."""
        self.db_manager.update_inventory("food_a", 3, 0.9)
        self.db_manager.update_inventory("food_b", 5, 0.85)
        
        items = self.db_manager.get_all_inventory()
        self.assertGreaterEqual(len(items), 2)
        
        print(f"  ✓ get_all_inventory() works ({len(items)} items)")
    
    def test_04_compare_inventory_vs_request_works(self):
        """Existing compare_inventory_vs_request() method works."""
        self.db_manager.update_inventory("egg", 2, 0.95)
        self.db_manager.insert_request("egg", 5)
        
        shortage = self.db_manager.compare_inventory_vs_request()
        self.assertGreater(len(shortage), 0)
        
        print(f"  ✓ compare_inventory_vs_request() works")


class TestPhase1NewMethods(unittest.TestCase):
    """Test Phase 1 new methods."""
    
    @classmethod
    def setUpClass(cls):
        """Setup test database."""
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_test_new_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()
    
    @classmethod
    def tearDownClass(cls):
        """Cleanup."""
        cls.db_manager.close_connection()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def test_01_insert_inventory_history(self):
        """Test insert_inventory_history() method."""
        result = self.db_manager.insert_inventory_history(
            food_id="banana",
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.92,
            image_path="/opt/fss/assets/banana.jpg",
            change_reason="FRT_DETECTION",
            changed_by="FRTApp",
            changed_at=datetime.now().isoformat()
        )
        
        self.assertTrue(result)
        print(f"  ✓ insert_inventory_history() works")
    
    def test_02_get_inventory_history(self):
        """Test get_inventory_history() method."""
        # Insert history
        for i in range(3):
            self.db_manager.insert_inventory_history(
                food_id="tomato",
                quantity_before=i,
                quantity_after=i+1,
                confidence_score=0.85,
                image_path=f"/path/tomato_{i}.jpg",
                change_reason="FRT_DETECTION",
                changed_by="FRTApp",
                changed_at=datetime.now().isoformat()
            )
        
        # Retrieve
        history = self.db_manager.get_inventory_history("tomato", limit=10)
        self.assertEqual(len(history), 3)
        self.assertTrue(all(h['food_id'] == 'tomato' for h in history))
        
        print(f"  ✓ get_inventory_history() works ({len(history)} records)")
    
    def test_03_insert_request_batch(self):
        """Test insert_request_batch() method."""
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "egg", "quantity": 2, "unit": "pieces"},
            {"food_id": "flour", "quantity": 100, "unit": "g"},
        ]
        
        result = self.db_manager.insert_request_batch(
            recipe_name="Bánh Trứng",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        self.assertTrue(result)
        requests = self.db_manager.get_all_requests()
        self.assertEqual(len(requests), 2)
        
        print(f"  ✓ insert_request_batch() works ({len(requests)} items)")
    
    def test_04_get_requests_by_recipe(self):
        """Test get_requests_by_recipe() method."""
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "tomato", "quantity": 3, "unit": "pieces"},
            {"food_id": "basil", "quantity": 50, "unit": "g"}
        ]
        
        self.db_manager.insert_request_batch(
            recipe_name="Salad Cà Chua",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        recipe_items = self.db_manager.get_requests_by_recipe("Salad Cà Chua")
        self.assertEqual(len(recipe_items), 2)
        self.assertTrue(all(i['recipe_name'] == 'Salad Cà Chua' for i in recipe_items))
        
        print(f"  ✓ get_requests_by_recipe() works ({len(recipe_items)} items)")
    
    def test_05_clear_request_batch(self):
        """Test clear_request_batch() method."""
        batch_id = str(uuid.uuid4())
        ingredients = [{"food_id": "chicken", "quantity": 1, "unit": "kg"}]
        
        self.db_manager.insert_request_batch(
            recipe_name="Cơm Gà",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        before = self.db_manager.get_requests_by_recipe("Cơm Gà")
        self.assertEqual(len(before), 1)
        
        result = self.db_manager.clear_request_batch(batch_id)
        self.assertTrue(result)
        
        after = self.db_manager.get_requests_by_recipe("Cơm Gà")
        self.assertEqual(len(after), 0)
        
        print(f"  ✓ clear_request_batch() works")


class TestPhase1Integration(unittest.TestCase):
    """Integration tests for Phase 1."""
    
    @classmethod
    def setUpClass(cls):
        """Setup test database."""
        cls.temp_dir = tempfile.mkdtemp(prefix="fss_test_int_")
        cls.db_manager = SqliteManager(db_dir=cls.temp_dir)
        cls.db_manager.connect_all_dbs()
        cls.db_manager.init_tables_if_not_exists()
    
    @classmethod
    def tearDownClass(cls):
        """Cleanup."""
        cls.db_manager.close_connection()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def test_01_complete_workflow(self):
        """Test complete workflow: detect → update → log history."""
        food_id = "detected_apple"
        
        # FRT detects food
        self.db_manager.update_inventory(food_id, 5, 0.96, "/path/apple.jpg")
        
        # Log to history
        self.db_manager.insert_inventory_history(
            food_id=food_id,
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.96,
            image_path="/path/apple.jpg",
            change_reason="FRT_DETECTION",
            changed_by="FRTApp",
            changed_at=datetime.now().isoformat()
        )
        
        # Verify
        item = self.db_manager.get_inventory_item(food_id)
        self.assertEqual(item['quantity'], 5)
        
        history = self.db_manager.get_inventory_history(food_id)
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]['change_reason'], "FRT_DETECTION")
        
        print(f"  ✓ Complete workflow successful")
    
    def test_02_recipe_workflow(self):
        """Test recipe workflow: NLP → batch insert → compare."""
        recipe_name = "Cơm Chiên"
        batch_id = str(uuid.uuid4())
        
        # Setup inventory
        self.db_manager.update_inventory("rice", 2, 0.90)
        self.db_manager.update_inventory("egg", 3, 0.88)
        
        # NLP generates ingredients
        ingredients = [
            {"food_id": "rice", "quantity": 3, "unit": "cups"},
            {"food_id": "egg", "quantity": 2, "unit": "pieces"},
            {"food_id": "onion", "quantity": 1, "unit": "piece"}
        ]
        
        self.db_manager.insert_request_batch(recipe_name, ingredients, batch_id)
        
        # Compare
        shortage = self.db_manager.compare_inventory_vs_request()
        
        # Verify shortage list contains expected items
        shortage_ids = [s['food_id'] for s in shortage]
        self.assertIn('onion', shortage_ids)  # Completely missing
        
        print(f"  ✓ Recipe workflow successful ({len(shortage)} items missing)")


def run_tests():
    """Run all tests and print summary."""
    print("\n" + "="*70)
    print("FSS Phase 1 Database Schema Tests")
    print("="*70 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1SchemaValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1NewMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1Integration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED - Phase 1 Implementation Valid")
        print(f"  Tests run: {result.testsRun}")
        print(f"  Failures: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
    else:
        print("✗ SOME TESTS FAILED - Please review errors below")
        print(f"  Tests run: {result.testsRun}")
        print(f"  Failures: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
    
    print("="*70 + "\n")
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
