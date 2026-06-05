"""
Integration Tests - RecipeExtractor ↔ DBDaemon
===============================================

Purpose:
    Validate the data flow between RecipeExtractor's NLP output format and
    DBDaemon's SqliteManager database operations.

Test Coverage:
    1. NLP output field mapping to insert_request_batch schema
    2. FSS_Request.db round-trip via SqliteManager (insert → retrieve)
    3. Batch ID consistency across recipe_extractor and db_daemon
    4. Vietnamese recipe name and ingredient storage
    5. Multiple ingredient batch insertion
    6. Error handling at the DB boundary

Data Flow:
    RecipeAnalyzerEngine.generate_fss_request()
        → {"ingredients": [{"ingredient": str, "quantity": str}, ...]}
        → SqliteManager.insert_request_batch(recipe_name, ingredients_list, batch_id)
        → SqliteManager request table

ASPICE Compliance:
    - Cross-component data format validation
    - Database schema contract verification
    - Unicode/Vietnamese text handling
    - Transaction rollback coverage

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-06-05
"""

import unittest
import logging
import sys
import os
import json
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recipe_extractor" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "db_daemon" / "src"))

logging.disable(logging.CRITICAL)


# ==============================================================================
# Mock RecipeExtractor Output (represents generate_fss_request result)
# ==============================================================================

def create_nlp_output(recipe_name: str) -> Dict:
    normalized = recipe_name.strip().lower()
    recipes = {
        "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c": [
            {"ingredient": "B\u01b0\u1edfi", "quantity": "1"},
            {"ingredient": "M\u1ef1c kh\u00f4", "quantity": "1"},
            {"ingredient": "Th\u1ecbt ba ch\u1ec9", "quantity": "100"},
            {"ingredient": "C\u00e0 r\u1ed1t", "quantity": "2"},
            {"ingredient": "T\u1eafc", "quantity": "3"},
        ],
        "tr\u1ee9ng chi\u00ean": [
            {"ingredient": "Tr\u1ee9ng g\u00e0", "quantity": "2"},
            {"ingredient": "D\u1ea7u \u0103n", "quantity": "2"},
            {"ingredient": "Mu\u1ed1i", "quantity": "1"},
        ],
    }
    if normalized in recipes:
        return {
            "status": "SUCCESS",
            "dish": normalized,
            "ingredients": recipes[normalized],
        }
    return {
        "status": "NOT_FOUND",
        "message": f"Recipe not found: {recipe_name}",
        "dish": normalized,
        "suggestions": [],
    }


def nlp_to_batch_format(nlp_ingredients: List[Dict]) -> List[Dict]:
    def _qty(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return 1
    return [
        {
            "food_id": ing["ingredient"],
            "quantity": _qty(ing.get("quantity", "1")),
            "unit": None,
        }
        for ing in nlp_ingredients
    ]


# ==============================================================================
# RecipeExtractor → SqliteManager Integration Tests
# ==============================================================================

class TestExtractorToDbDataFormat(unittest.TestCase):
    def test_nlp_output_has_required_fields(self):
        result = create_nlp_output("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        self.assertIn("status", result)
        self.assertIn("dish", result)
        self.assertIn("ingredients", result)

    def test_nlp_ingredient_format_matches_request_schema(self):
        result = create_nlp_output("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        for ing in result["ingredients"]:
            self.assertIn("ingredient", ing)
            self.assertIn("quantity", ing)
            self.assertIsInstance(ing["ingredient"], str)
            self.assertIsInstance(ing["quantity"], str)

    def test_nlp_to_batch_format_conversion(self):
        nlp_result = create_nlp_output("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        batch_items = nlp_to_batch_format(nlp_result["ingredients"])
        self.assertEqual(len(batch_items), 5)
        for item in batch_items:
            self.assertIn("food_id", item)
            self.assertIn("quantity", item)
            self.assertIsInstance(item["quantity"], int)
            self.assertIn("unit", item)

    def test_batch_format_quantity_string_to_int(self):
        nlp_result = create_nlp_output("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        batch_items = nlp_to_batch_format(nlp_result["ingredients"])
        self.assertEqual(batch_items[0]["quantity"], 1)
        self.assertEqual(batch_items[3]["quantity"], 2)
        self.assertEqual(batch_items[4]["quantity"], 3)

    def test_batch_format_non_numeric_quantity_defaults_to_1(self):
        items = [{"ingredient": "Mu\u1ed1i", "quantity": "v\u1eeba \u0103n"}]
        batch = nlp_to_batch_format(items)
        self.assertEqual(batch[0]["quantity"], 1)


class TestExtractorToDbRoundTrip(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_dbd_int_")
        from SqliteManager import SqliteManager, DatabaseType
        self.db_mgr = SqliteManager(db_dir=self.temp_dir)
        self.db_mgr.connect_all_dbs()
        self.db_mgr.init_tables_if_not_exists()

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_nlp_result(self, recipe_name: str) -> str:
        batch_id = str(uuid.uuid4())
        nlp_result = create_nlp_output(recipe_name)
        if nlp_result["status"] != "SUCCESS":
            return None
        batch_items = nlp_to_batch_format(nlp_result["ingredients"])
        success = self.db_mgr.insert_request_batch(
            recipe_name=nlp_result["dish"],
            ingredients_list=batch_items,
            batch_id=batch_id,
        )
        return batch_id if success else None

    def test_insert_request_batch_with_nlp_output(self):
        batch_id = self._insert_nlp_result("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        self.assertIsNotNone(batch_id)

    def test_retrieve_requests_by_batch_id(self):
        batch_id = self._insert_nlp_result("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT food_id, quantity FROM request WHERE request_batch_id = ?",
            (batch_id,)
        )
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 5)
        food_ids = [row[0] for row in rows]
        self.assertIn("B\u01b0\u1edfi", food_ids)
        self.assertIn("M\u1ef1c kh\u00f4", food_ids)
        self.assertIn("C\u00e0 r\u1ed1t", food_ids)

    def test_retrieve_requests_by_recipe_name(self):
        batch_id = self._insert_nlp_result("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT food_id, quantity FROM request WHERE recipe_name = ?",
            ("g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c",)
        )
        rows = cursor.fetchall()
        self.assertGreater(len(rows), 0)

    def test_recipe_name_stored_correctly(self):
        batch_id = self._insert_nlp_result("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT recipe_name FROM request WHERE request_batch_id = ? LIMIT 1",
            (batch_id,)
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")

    def test_multiple_recipes_in_db(self):
        batch1 = self._insert_nlp_result("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        batch2 = self._insert_nlp_result("Tr\u1ee9ng Chi\u00ean")
        self.assertIsNotNone(batch1)
        self.assertIsNotNone(batch2)
        self.assertNotEqual(batch1, batch2)

    def test_quantity_stored_correctly(self):
        batch_id = self._insert_nlp_result("Tr\u1ee9ng Chi\u00ean")
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT food_id, quantity FROM request WHERE request_batch_id = ?",
            (batch_id,)
        )
        rows = cursor.fetchall()
        qty_map = {row[0]: row[1] for row in rows}
        self.assertEqual(qty_map.get("Tr\u1ee9ng g\u00e0"), 2)
        self.assertEqual(qty_map.get("D\u1ea7u \u0103n"), 2)

    def test_clear_request_batch(self):
        batch_id = self._insert_nlp_result("Tr\u1ee9ng Chi\u00ean")
        self.assertIsNotNone(batch_id)
        result = self.db_mgr.clear_request_batch(batch_id)
        self.assertTrue(result)
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT COUNT(*) FROM request WHERE request_batch_id = ?",
            (batch_id,)
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0)


class TestExtractorToDbSchemaConsistency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_schema_")
        from SqliteManager import SqliteManager
        self.db_mgr = SqliteManager(db_dir=self.temp_dir)
        self.db_mgr.connect_all_dbs()
        self.db_mgr.init_tables_if_not_exists()

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_request_table_has_recipe_name_column(self):
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute("PRAGMA table_info(request)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn("recipe_name", columns)

    def test_request_table_has_batch_id_column(self):
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute("PRAGMA table_info(request)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn("request_batch_id", columns)

    def test_request_table_has_required_columns(self):
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute("PRAGMA table_info(request)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"id", "recipe_name", "food_id", "quantity", "unit",
                    "request_batch_id", "created_at"}
        self.assertTrue(required.issubset(columns))

    def test_request_table_indexes_exist(self):
        from SqliteManager import DatabaseType
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='request'")
        indexes = {row[0] for row in cursor.fetchall()}
        self.assertIn("idx_request_recipe_name", indexes)
        self.assertIn("idx_request_batch_id", indexes)
        self.assertIn("idx_request_food_id", indexes)


class TestExtractorToDbErrorHandling(unittest.TestCase):
    def test_insert_request_batch_no_connection(self):
        from SqliteManager import SqliteManager
        db_mgr = SqliteManager(db_dir="/nonexistent")
        result = db_mgr.insert_request_batch(
            recipe_name="test",
            ingredients_list=[{"food_id": "test", "quantity": 1}],
            batch_id="batch-1",
        )
        self.assertFalse(result)

    def test_insert_request_batch_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from SqliteManager import SqliteManager
            db_mgr = SqliteManager(db_dir=tmpdir)
            db_mgr.connect_all_dbs()
            db_mgr.init_tables_if_not_exists()
            result = db_mgr.insert_request_batch(
                recipe_name="test", ingredients_list=[], batch_id="batch-1"
            )
            self.assertTrue(result)
            db_mgr.close_connection()

    def test_insert_request_batch_none_batch_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from SqliteManager import SqliteManager, DatabaseType
            db_mgr = SqliteManager(db_dir=tmpdir)
            db_mgr.connect_all_dbs()
            db_mgr.init_tables_if_not_exists()
            result = db_mgr.insert_request_batch(
                recipe_name="test",
                ingredients_list=[{"food_id": "item", "quantity": 1}],
                batch_id=None,
            )
            try:
                self.assertTrue(result)
                cursor = db_mgr._cursors[DatabaseType.REQUEST]
                cursor.execute(
                    "SELECT request_batch_id FROM request WHERE recipe_name = ?",
                    ("test",)
                )
                row = cursor.fetchone()
                self.assertIsNone(row[0])
            finally:
                db_mgr.close_connection()


class TestExtractorToDbVietnameseText(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_vn_")
        from SqliteManager import SqliteManager
        self.db_mgr = SqliteManager(db_dir=self.temp_dir)
        self.db_mgr.connect_all_dbs()
        self.db_mgr.init_tables_if_not_exists()

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_vietnamese_diacritics_preserved(self):
        from SqliteManager import DatabaseType
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "Th\u1ecbt heo quay", "quantity": 1, "unit": None},
            {"food_id": "B\u00e1nh tr\u00e1ng", "quantity": 2, "unit": None},
        ]
        self.db_mgr.insert_request_batch(
            recipe_name="b\u00e1nh tr\u00e1ng cu\u1ed1n th\u1ecbt heo",
            ingredients_list=ingredients,
            batch_id=batch_id,
        )
        cursor = self.db_mgr._cursors[DatabaseType.REQUEST]
        cursor.execute(
            "SELECT food_id, recipe_name FROM request WHERE request_batch_id = ?",
            (batch_id,)
        )
        rows = cursor.fetchall()
        food_ids = [row[0] for row in rows]
        self.assertIn("Th\u1ecbt heo quay", food_ids)
        self.assertIn("B\u00e1nh tr\u00e1ng", food_ids)


# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestExtractorToDbDataFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractorToDbRoundTrip))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractorToDbSchemaConsistency))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractorToDbErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractorToDbVietnameseText))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
