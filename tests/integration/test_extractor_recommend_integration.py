"""
Integration Tests - RecipeExtractor ↔ RecommendDaemon
======================================================

Purpose:
    Validate data flow and format compatibility between RecipeAnalyzerEngine
    (from recipe_extractor) and RecommendEngine (from recommend_daemon).
    Tests the cross-component import, the Bù Trừ algorithm with new Analyzer
    output format (original_ingredients), and error propagation.

Test Coverage:
    1. Cross-component import path resolution
    2. generate_fss_request -> generate_shopping_list data flow
    3. Bù Trừ algorithm with original_ingredients string format
    4. Recipe suggestion flow (NOT_FOUND -> fuzzy match)
    5. Analyzer error propagation to RecommendEngine
    6. format_result_for_ui with real Analyzer output
    7. Quantity parsing from original_ingredients format

Data Flow:
    RecipeAnalyzerEngine.generate_fss_request()
        -> RecommendEngine.generate_shopping_list(analyzer_result)
        -> Bù Trừ comparison with inventory
        -> format_result_for_ui()

ASPICE Compliance:
    - Cross-component data format validation
    - Interface contract verification
    - Error propagation coverage
    - Mock-based isolation of external deps

Author: FSS QA Team
Version: 2.0.0
Last Modified: 2026-06-21
"""

import unittest
import logging
import sys
import os
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recipe_extractor" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recommend_daemon" / "src"))

logging.disable(logging.CRITICAL)


class MockRecipeAnalyzerEngine:
    def __init__(self):
        self.recipes = {
            "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c": [
                "B\u01b0\u1edfi : 1 tr\u00e1i",
                "M\u1ef1c kh\u00f4 : 1 con (50g)",
                "C\u00e0 r\u1ed1t : 2 c\u1ee7",
                "T\u1eafc : 3 tr\u00e1i",
                "\u0110\u1eadu ph\u1ed9ng : 1"
            ],
            "tr\u1ee9ng chi\u00ean": [
                "Tr\u1ee9ng g\u00e0 : 2 qu\u1ea3",
                "D\u1ea7u \u0103n : 2 mu\u1ed7ng canh",
                "Mu\u1ed1i : 1"
            ],
        }
        self.recipe_names = sorted(self.recipes.keys())

    def generate_fss_request(self, recipe_name: str) -> Dict:
        if not recipe_name or not isinstance(recipe_name, str):
            return {"status": "ERROR", "error": "Invalid recipe name"}
        normalized = recipe_name.strip().lower()
        if normalized in self.recipes:
            return {
                "status": "SUCCESS",
                "dish": normalized,
                "original_ingredients": self.recipes[normalized],
                "processing_time_ms": 0.01,
            }
        if normalized == "error_test":
            return {"status": "ERROR", "error": "Simulated Analyzer error"}
        suggestions = [n for n in self.recipe_names if normalized in n]
        return {
            "status": "NOT_FOUND",
            "message": f"Recipe not found: {recipe_name}",
            "dish": normalized,
            "suggestions": suggestions[:3],
        }

    def get_available_recipes(self) -> List[str]:
        return self.recipe_names.copy()


class TestCrossComponentImport(unittest.TestCase):
    def test_recommend_engine_import_from_daemon(self):
        try:
            from RecommendEngine import RecommendEngine
            self.assertTrue(callable(RecommendEngine))
        except ImportError as e:
            self.fail(f"Cannot import RecommendEngine: {e}")

    def test_recommend_db_manager_import(self):
        try:
            from RecommendDbManager import RecommendDbManager
            self.assertTrue(callable(RecommendDbManager))
        except ImportError as e:
            self.fail(f"Cannot import RecommendDbManager: {e}")


class TestNlpToRecommendDataFlow(unittest.TestCase):
    def setUp(self):
        self.mock_nlp = MockRecipeAnalyzerEngine()
        from RecommendEngine import RecommendEngine
        self.engine = RecommendEngine(analyzer_engine=self.mock_nlp)

    def test_generate_shopping_list_accepts_nlp_output(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="flow-test-001",
            inventory=[],
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_items"], 5)
        self.assertEqual(result["missing_count"], 5)

    def test_nlp_original_ingredients_parsed_correctly(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="flow-test-002",
            inventory=[],
        )
        self.assertIn("shopping_list", result)
        shopping_foods = [item["food_id"] for item in result["shopping_list"]]
        self.assertIn("b\u01b0\u1edfi", shopping_foods)
        self.assertIn("m\u1ef1c kh\u00f4", shopping_foods)
        self.assertIn("c\u00e0 r\u1ed1t", shopping_foods)

    def test_nlp_quantity_parsed_correctly(self):
        result = self.engine.generate_shopping_list(
            recipe_name="Tr\u1ee9ng Chi\u00ean",
            batch_id="flow-test-003",
            inventory=[],
        )
        shopping = {item["food_id"]: item["required_qty"]
                    for item in result["shopping_list"]}
        self.assertEqual(shopping.get("tr\u1ee9ng g\u00e0"), 2)
        self.assertEqual(shopping.get("d\u1ea7u \u0103n"), 2)

    def test_dish_name_propagation(self):
        result = self.engine.generate_shopping_list(
            recipe_name="Tr\u1ee9ng Chi\u00ean",
            batch_id="flow-test-004",
            inventory=[],
        )
        self.assertEqual(result["recipe_name"], "Tr\u1ee9ng Chi\u00ean")

    def test_processing_time_in_analyzer_result(self):
        analyzer_result = self.mock_nlp.generate_fss_request("G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c")
        self.assertIn("processing_time_ms", analyzer_result)


class TestBuTruWithOriginalIngredients(unittest.TestCase):
    def setUp(self):
        self.mock_nlp = MockRecipeAnalyzerEngine()
        from RecommendEngine import RecommendEngine
        self.engine = RecommendEngine(analyzer_engine=self.mock_nlp)

    def test_bu_tru_all_missing(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="butru-001",
            inventory=[],
        )
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["missing_count"], 5)
        self.assertEqual(result["needed_count"], 0)

    def test_bu_tru_all_available(self):
        inventory = [
            {"food_id": "b\u01b0\u1edfi", "quantity": 2},
            {"food_id": "m\u1ef1c kh\u00f4", "quantity": 3},
            {"food_id": "c\u00e0 r\u1ed1t", "quantity": 5},
            {"food_id": "t\u1eafc", "quantity": 4},
            {"food_id": "\u0111\u1eadu ph\u1ed9ng", "quantity": 2},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="butru-002",
            inventory=inventory,
        )
        self.assertEqual(result["available_count"], 5)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["needed_count"], 0)

    def test_bu_tru_partial(self):
        inventory = [
            {"food_id": "b\u01b0\u1edfi", "quantity": 1},
            {"food_id": "c\u00e0 r\u1ed1t", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="butru-003",
            inventory=inventory,
        )
        self.assertGreater(result["available_count"], 0)
        self.assertGreater(result["missing_count"], 0)
        available_foods = [i["food_id"] for i in result["available"]]
        self.assertIn("b\u01b0\u1edfi", available_foods)

    def test_bu_tru_case_insensitive_matching(self):
        inventory = [
            {"food_id": "B\u01af\u1edeI", "quantity": 1},
        ]
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="butru-005",
            inventory=inventory,
        )
        available_foods = [i["food_id"] for i in result["available"]]
        self.assertIn("b\u01b0\u1edfi", available_foods)


class TestNlpErrorPropagation(unittest.TestCase):
    def setUp(self):
        self.mock_nlp = MockRecipeAnalyzerEngine()
        from RecommendEngine import RecommendEngine
        self.engine = RecommendEngine(analyzer_engine=self.mock_nlp)

    def test_not_found_propagates_from_nlp(self):
        result = self.engine.generate_shopping_list(
            recipe_name="NonExistentRecipe",
            batch_id="err-001",
            inventory=[],
        )
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertIn("suggestions", result)

    def test_error_propagates_from_nlp(self):
        result = self.engine.generate_shopping_list(
            recipe_name="error_test",
            batch_id="err-002",
            inventory=[],
        )
        self.assertEqual(result["status"], "ERROR")

    def test_no_engine_returns_error(self):
        from RecommendEngine import RecommendEngine
        engine_no_nlp = RecommendEngine(analyzer_engine=None)
        result = engine_no_nlp.generate_shopping_list(
            recipe_name="Test", batch_id="err-003", inventory=[]
        )
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Analyzer engine not initialized", result["error"])

    def test_nlp_empty_original_ingredients_handled(self):
        mock_empty = MagicMock()
        mock_empty.generate_fss_request.return_value = {
            "status": "SUCCESS", "dish": "test", "original_ingredients": []
        }
        self.engine.set_analyzer_engine(mock_empty)
        result = self.engine.generate_shopping_list(
            recipe_name="test", batch_id="err-004", inventory=[]
        )
        self.assertEqual(result["status"], "NOT_FOUND")

    def test_nlp_exception_caught_by_recommend_engine(self):
        mock_exception = MagicMock()
        mock_exception.generate_fss_request.side_effect = RuntimeError("Analyzer crash")
        self.engine.set_analyzer_engine(mock_exception)
        result = self.engine.generate_shopping_list(
            recipe_name="test", batch_id="err-005", inventory=[]
        )
        self.assertEqual(result["status"], "ERROR")


class TestFormatResultForUi(unittest.TestCase):
    def setUp(self):
        self.mock_nlp = MockRecipeAnalyzerEngine()
        from RecommendEngine import RecommendEngine
        self.engine = RecommendEngine(analyzer_engine=self.mock_nlp)

    def test_format_result_ui_ingredients(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="ui-001",
            inventory=[],
        )
        ui_result = self.engine.format_result_for_ui(result)
        self.assertIn("ingredients", ui_result)
        self.assertEqual(len(ui_result["ingredients"]), 5)
        for item in ui_result["ingredients"]:
            self.assertIn("name", item)
            self.assertIn("status", item)
            self.assertIn("shortage", item)

    def test_format_result_ui_summary(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="ui-002",
            inventory=[],
        )
        ui_result = self.engine.format_result_for_ui(result)
        self.assertIn("summary", ui_result)

    def test_format_result_ui_status_mapping(self):
        result = self.engine.generate_shopping_list(
            recipe_name="G\u1ecfi Tr\u1ed9n Kh\u00f4 M\u1ef1c",
            batch_id="ui-004",
            inventory=[],
        )
        ui_result = self.engine.format_result_for_ui(result)
        for item in ui_result["ingredients"]:
            self.assertIn(item["status"], ["available", "needed", "missing"])


class TestNlpGetAvailableRecipes(unittest.TestCase):
    def setUp(self):
        self.mock_nlp = MockRecipeAnalyzerEngine()
        from RecommendEngine import RecommendEngine
        self.engine = RecommendEngine(analyzer_engine=self.mock_nlp)

    def test_get_available_recipes_from_nlp(self):
        recipes = self.engine.get_available_recipes()
        self.assertGreater(len(recipes), 0)
        self.assertIn("g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c", recipes)

    def test_get_available_recipes_no_engine(self):
        from RecommendEngine import RecommendEngine
        engine = RecommendEngine(analyzer_engine=None)
        recipes = engine.get_available_recipes()
        self.assertEqual(recipes, [])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCrossComponentImport))
    suite.addTests(loader.loadTestsFromTestCase(TestNlpToRecommendDataFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestBuTruWithOriginalIngredients))
    suite.addTests(loader.loadTestsFromTestCase(TestNlpErrorPropagation))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatResultForUi))
    suite.addTests(loader.loadTestsFromTestCase(TestNlpGetAvailableRecipes))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
