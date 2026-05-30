import unittest
import logging
import tempfile
import os
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from RecommendDbManager import RecommendDbManager
from RecommendEngine import RecommendEngine


logging.disable(logging.CRITICAL)


class TestRecommendDbManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_recommend_")
        self.db_mgr = RecommendDbManager(db_dir=self.temp_dir)
        self.assertTrue(self.db_mgr.connect_db())
        self.db_mgr.init_tables()

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_sample_recommendation(self):
        return self.db_mgr.insert_recommendation(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-batch-001",
            nlp_status="SUCCESS",
            total_items=5,
            available_count=2,
            needed_count=1,
            missing_count=2,
            result_json='{"status": "SUCCESS"}'
        )

    def test_connect_db(self):
        mgr = RecommendDbManager(db_dir=self.temp_dir)
        self.assertTrue(mgr.connect_db())
        mgr.close_connection()

    def test_init_tables(self):
        self.assertIsNotNone(self.db_mgr._cursor)
        self.db_mgr._cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in self.db_mgr._cursor.fetchall()]
        self.assertIn("recommendation_log", tables)
        self.assertIn("shopping_list", tables)

    def test_recommendation_log_schema(self):
        self.db_mgr._cursor.execute("PRAGMA table_info(recommendation_log)")
        columns = {row[1]: row[2] for row in self.db_mgr._cursor.fetchall()}
        self.assertIn("id", columns)
        self.assertIn("recipe_name", columns)
        self.assertIn("batch_id", columns)
        self.assertIn("nlp_status", columns)
        self.assertIn("total_items", columns)
        self.assertIn("available_count", columns)
        self.assertIn("needed_count", columns)
        self.assertIn("missing_count", columns)
        self.assertIn("status", columns)
        self.assertIn("result_json", columns)

    def test_shopping_list_schema(self):
        self.db_mgr._cursor.execute("PRAGMA table_info(shopping_list)")
        columns = {row[1]: row[2] for row in self.db_mgr._cursor.fetchall()}
        self.assertIn("id", columns)
        self.assertIn("recommendation_id", columns)
        self.assertIn("food_id", columns)
        self.assertIn("required_qty", columns)
        self.assertIn("available_qty", columns)
        self.assertIn("shortage", columns)
        self.assertIn("purchased", columns)

    def test_insert_recommendation(self):
        row_id = self._insert_sample_recommendation()
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)

    def test_insert_recommendation_no_connection(self):
        mgr = RecommendDbManager(db_dir=self.temp_dir)
        result = mgr.insert_recommendation(
            recipe_name="test", batch_id="b1",
            nlp_status="ERROR", total_items=0,
            available_count=0, needed_count=0,
            missing_count=0, result_json="{}"
        )
        self.assertIsNone(result)

    def test_insert_shopping_item(self):
        row_id = self._insert_sample_recommendation()
        self.assertIsNotNone(row_id)
        result = self.db_mgr.insert_shopping_item(
            recommendation_id=row_id,
            food_id="Bưởi",
            required_qty=2,
            available_qty=0,
            shortage=2,
            unit="trái"
        )
        self.assertTrue(result)

    def test_insert_shopping_list(self):
        row_id = self._insert_sample_recommendation()
        self.assertIsNotNone(row_id)
        items = [
            {"food_id": "Bưởi", "required_qty": 2, "available_qty": 0,
             "shortage": 2, "unit": "trái"},
            {"food_id": "Mực khô", "required_qty": 1, "available_qty": 0,
             "shortage": 1, "unit": "con"}
        ]
        result = self.db_mgr.insert_shopping_list(row_id, items)
        self.assertTrue(result)

    def test_get_shopping_list(self):
        row_id = self._insert_sample_recommendation()
        self.db_mgr.insert_shopping_item(
            row_id, "Bưởi", 2, 0, 2, "trái"
        )
        items = self.db_mgr.get_shopping_list("test-batch-001")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["food_id"], "Bưởi")
        self.assertEqual(items[0]["shortage"], 2)
        self.assertEqual(items[0]["recipe_name"], "Gỏi Trộn Khô Mực")

    def test_get_shopping_list_no_results(self):
        items = self.db_mgr.get_shopping_list("nonexistent-batch")
        self.assertEqual(items, [])

    def test_mark_item_purchased(self):
        row_id = self._insert_sample_recommendation()
        self.db_mgr.insert_shopping_item(
            row_id, "Bưởi", 2, 0, 2, "trái"
        )
        items = self.db_mgr.get_shopping_list("test-batch-001")
        self.assertEqual(len(items), 1)
        item_id = items[0]["id"]
        result = self.db_mgr.mark_item_purchased(item_id)
        self.assertTrue(result)
        items_after = self.db_mgr.get_shopping_list("test-batch-001")
        self.assertTrue(items_after[0]["purchased"])

    def test_mark_item_purchased_not_found(self):
        result = self.db_mgr.mark_item_purchased(9999)
        self.assertFalse(result)

    def test_clear_shopping_list(self):
        row_id = self._insert_sample_recommendation()
        self.db_mgr.insert_shopping_item(row_id, "Bưởi", 2, 0, 2)
        self.assertTrue(self.db_mgr.clear_shopping_list("test-batch-001"))
        items = self.db_mgr.get_shopping_list("test-batch-001")
        self.assertEqual(items, [])

    def test_update_recommendation_status(self):
        self._insert_sample_recommendation()
        result = self.db_mgr.update_recommendation_status(
            "test-batch-001", "fulfilled"
        )
        self.assertTrue(result)
        rec = self.db_mgr.get_recommendation("test-batch-001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["status"], "fulfilled")

    def test_get_recommendation(self):
        self._insert_sample_recommendation()
        rec = self.db_mgr.get_recommendation("test-batch-001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["recipe_name"], "Gỏi Trộn Khô Mực")
        self.assertEqual(rec["nlp_status"], "SUCCESS")
        self.assertEqual(rec["total_items"], 5)
        self.assertEqual(rec["available_count"], 2)
        self.assertEqual(rec["missing_count"], 2)

    def test_get_recommendation_not_found(self):
        rec = self.db_mgr.get_recommendation("nonexistent")
        self.assertIsNone(rec)

    def test_close_connection(self):
        self.db_mgr.close_connection()
        self.assertIsNone(self.db_mgr._connection)
        self.assertIsNone(self.db_mgr._cursor)

    def test_double_close_safe(self):
        self.db_mgr.close_connection()
        self.db_mgr.close_connection()

    def test_init_tables_no_connection(self):
        mgr = RecommendDbManager(db_dir=self.temp_dir)
        mgr.init_tables()


class TestRecommendEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_engine_")
        self.db_mgr = RecommendDbManager(db_dir=self.temp_dir)
        self.db_mgr.connect_db()
        self.db_mgr.init_tables()

        self.mock_nlp = MagicMock()
        self.mock_nlp.generate_fss_request.return_value = {
            "status": "SUCCESS",
            "dish": "gỏi trộn khô mực",
            "ingredients": [
                {"ingredient": "Bưởi", "quantity": "1"},
                {"ingredient": "Mực khô", "quantity": "1"},
                {"ingredient": "Cà rốt", "quantity": "2"},
                {"ingredient": "Tắc", "quantity": "3"},
                {"ingredient": "Đậu phộng", "quantity": "1"}
            ]
        }
        self.mock_nlp.get_available_recipes.return_value = [
            "gỏi trộn khô mực", "phở bò", "bún chả"
        ]

        self.engine = RecommendEngine(
            nlp_engine=self.mock_nlp,
            db_manager=self.db_mgr
        )

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_shopping_list_all_missing(self):
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-001",
            inventory=[]
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_items"], 5)
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["needed_count"], 0)
        self.assertEqual(result["missing_count"], 5)
        self.assertEqual(len(result["shopping_list"]), 5)

    def test_generate_shopping_list_with_inventory(self):
        inventory = [
            {"food_id": "bưởi", "quantity": 2},
            {"food_id": "cà rốt", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-002",
            inventory=inventory
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["available_count"], 1)
        self.assertEqual(result["needed_count"], 1)
        self.assertEqual(result["missing_count"], 3)

    def test_generate_shopping_list_persists_to_db(self):
        inventory = [
            {"food_id": "bưởi", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-003",
            inventory=inventory
        )
        self.assertEqual(result["status"], "SUCCESS")
        rec = self.db_mgr.get_recommendation("test-003")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["recipe_name"], "Gỏi Trộn Khô Mực")
        items = self.db_mgr.get_shopping_list("test-003")
        self.assertGreater(len(items), 0)

    def test_generate_shopping_list_nlp_not_found(self):
        self.mock_nlp.generate_fss_request.return_value = {
            "status": "NOT_FOUND",
            "message": "Recipe not found",
            "dish": "unknown recipe",
            "suggestions": ["gỏi trộn khô mực"]
        }
        result = self.engine.generate_shopping_list(
            recipe_name="Unknown Dish",
            batch_id="test-004",
            inventory=[]
        )
        self.assertEqual(result["status"], "NOT_FOUND")

    def test_generate_shopping_list_nlp_error(self):
        self.mock_nlp.generate_fss_request.return_value = {
            "status": "ERROR",
            "error": "Model loading failed"
        }
        result = self.engine.generate_shopping_list(
            recipe_name="Error Dish",
            batch_id="test-005",
            inventory=[]
        )
        self.assertEqual(result["status"], "ERROR")

    def test_generate_shopping_list_no_engine(self):
        engine = RecommendEngine(nlp_engine=None)
        result = engine.generate_shopping_list(
            recipe_name="Test",
            batch_id="test-006",
            inventory=[]
        )
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("NLP engine not initialized", result["error"])

    def test_generate_shopping_list_auto_batch_id(self):
        inventory = [
            {"food_id": "bưởi", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            inventory=inventory
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("batch_id", result)
        self.assertIsNotNone(result["batch_id"])

    def test_get_available_recipes(self):
        recipes = self.engine.get_available_recipes()
        self.assertEqual(len(recipes), 3)
        self.assertIn("phở bò", recipes)

    def test_get_available_recipes_no_engine(self):
        engine = RecommendEngine(nlp_engine=None)
        recipes = engine.get_available_recipes()
        self.assertEqual(recipes, [])

    def test_get_shopping_list(self):
        self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-007",
            inventory=[]
        )
        items = self.engine.get_shopping_list("test-007")
        self.assertEqual(len(items), 5)

    def test_get_shopping_list_no_db(self):
        engine = RecommendEngine(nlp_engine=self.mock_nlp)
        result = engine.get_shopping_list("test-008")
        self.assertEqual(result, [])

    def test_mark_item_purchased(self):
        self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-009",
            inventory=[]
        )
        items = self.engine.get_shopping_list("test-009")
        self.assertGreater(len(items), 0)
        item_id = items[0]["id"]
        result = self.engine.mark_item_purchased(item_id)
        self.assertTrue(result)

    def test_mark_item_purchased_no_db(self):
        engine = RecommendEngine(nlp_engine=self.mock_nlp)
        result = engine.mark_item_purchased(1)
        self.assertFalse(result)

    def test_bu_tru_algorithm_exact(self):
        inventory = [
            {"food_id": "bưởi", "quantity": 1},
            {"food_id": "mực khô", "quantity": 1},
            {"food_id": "cà rốt", "quantity": 2},
            {"food_id": "tắc", "quantity": 3},
            {"food_id": "đậu phộng", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-010",
            inventory=inventory
        )
        self.assertEqual(result["available_count"], 5)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["needed_count"], 0)
        self.assertEqual(len(result["shopping_list"]), 0)

    def test_bu_tru_algorithm_needed(self):
        inventory = [
            {"food_id": "bưởi", "quantity": 1},
            {"food_id": "mực khô", "quantity": 0},
            {"food_id": "cà rốt", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-011",
            inventory=inventory
        )
        self.assertGreater(result["available_count"], 0)
        self.assertGreaterEqual(result["needed_count"], 0)
        self.assertGreaterEqual(result["missing_count"], 0)

    def test_parse_quantity(self):
        self.assertEqual(self.engine._parse_quantity("1"), 1)
        self.assertEqual(self.engine._parse_quantity("2.5"), 2)
        self.assertEqual(self.engine._parse_quantity("một"), 1)
        self.assertEqual(self.engine._parse_quantity(""), 1)
        self.assertEqual(self.engine._parse_quantity(None), 1)

    def test_set_nlp_engine(self):
        new_mock = MagicMock()
        self.engine.set_nlp_engine(new_mock)
        self.assertIs(self.engine.nlp_engine, new_mock)

    def test_set_db_manager(self):
        new_mgr = MagicMock()
        self.engine.set_db_manager(new_mgr)
        self.assertIs(self.engine.db_manager, new_mgr)

    def test_duplicate_batch_id(self):
        self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-012",
            inventory=[]
        )
        result2 = self.engine.generate_shopping_list(
            recipe_name="Gỏi Trộn Khô Mực",
            batch_id="test-012",
            inventory=[]
        )
        self.assertEqual(result2["status"], "SUCCESS")


class TestDbDbusInteraction(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fss_dbus_test_")
        self.db_mgr = RecommendDbManager(db_dir=self.temp_dir)
        self.db_mgr.connect_db()
        self.db_mgr.init_tables()
        self.mock_nlp = MagicMock()
        self.mock_nlp.generate_fss_request.return_value = {
            "status": "SUCCESS",
            "dish": "phở bò",
            "ingredients": [
                {"ingredient": "Thịt bò", "quantity": "1"},
                {"ingredient": "Bánh phở", "quantity": "1"},
            ]
        }

    def tearDown(self):
        self.db_mgr.close_connection()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_engine_prefers_provided_inventory(self):
        engine = RecommendEngine(
            nlp_engine=self.mock_nlp,
            db_manager=self.db_mgr
        )
        inventory = [
            {"food_id": "thịt bò", "quantity": 0},
        ]
        result = engine.generate_shopping_list(
            recipe_name="Phở Bò",
            batch_id="dbus-test-001",
            inventory=inventory
        )
        self.assertEqual(result["status"], "SUCCESS")
        missing_foods = [i["food_id"] for i in result["missing"]]
        self.assertIn("thịt bò", missing_foods)

    def test_empty_inventory_list(self):
        engine = RecommendEngine(
            nlp_engine=self.mock_nlp,
            db_manager=self.db_mgr
        )
        result = engine.generate_shopping_list(
            recipe_name="Phở Bò",
            batch_id="dbus-test-002",
            inventory=[]
        )
        self.assertEqual(result["missing_count"], 2)

    def test_partial_inventory_units(self):
        engine = RecommendEngine(
            nlp_engine=self.mock_nlp,
            db_manager=self.db_mgr
        )
        inventory = [
            {"food_id": "thịt bò", "quantity": 1},
        ]
        result = engine.generate_shopping_list(
            recipe_name="Phở Bò",
            batch_id="dbus-test-003",
            inventory=inventory
        )
        self.assertEqual(result["available_count"], 1)
        self.assertEqual(result["missing_count"], 1)
        missing_foods = [i["food_id"] for i in result["missing"]]
        self.assertIn("bánh phở", missing_foods)


if __name__ == "__main__":
    unittest.main()
