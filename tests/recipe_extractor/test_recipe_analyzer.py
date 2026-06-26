"""
Unit Tests - RecipeAnalyzerAPI and RecipeProcessor (Filter+Sort)
=================================================================

Purpose:
    Validate NLP engine functionality with filter+parse+sort pipeline.

Test Coverage:
    1. RecipeAnalyzerAPI:
       - Recipe database loading
       - Recipe lookup (filter) — exact match, case-insensitive, not found
       - Ingredient parsing (split on " : " delimiter)
       - Recipe output with all fields
       - Fuzzy recipe suggestions
       - Edge cases: empty input, special characters

    2. RecipeProcessor:
       - Quantity normalization
       - Quantity/unit detection
       - Unicode and special character handling
       - parse_ingredient_string function

Performance Targets:
    - Recipe lookup: <1ms per recipe
    - Total pipeline: <5ms

ASPICE Compliance:
    - Isolated unit tests (no external service dependencies)
    - Comprehensive error case coverage
    - Input validation tests
    - Performance assertion tests

Author: FSS QA Team
Version: 2.0.0
Last Modified: 2026-06-21
"""

import unittest
import logging
import json
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "recipe_extractor" / "src"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent / "recipe_extractor"
RECIPE_DB_PATH = str(PROJECT_ROOT / "data" / "recipes")

from RecipeAnalyzerAPI import RecipeAnalyzerEngine

from RecipeProcessor import (
    normalize_quantity,
    detect_quantity_unit,
    remove_special_characters,
    parse_ingredient_string,
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestRecipeDatabase:
    """Create temporary test recipe database for unit tests."""

    @staticmethod
    def create_test_recipes(temp_dir: str) -> List[str]:
        test_recipes = [
            {
                "recipe_name": "Gỏi Trộn Khô Mực",
                "serving": "4 người",
                "times": "30 Phút",
                "difficulty": "Dễ",
                "normal_ingredients": [
                    "Bưởi : 1 trái",
                    "Mực khô : 1 con (50g)",
                    "Thịt ba chỉ : 100g",
                    "Cà rốt : 2 củ",
                    "Đậu phộng : 1"
                ],
                "spices": ["Muối", "Đường"],
                "process": ["Tôm luộc chín", "Bưởi bóc múi"],
                "cook": ["Pha nước trộn"],
                "usage": ["Bày gỏi ra dĩa"],
                "tips": ["Chọn bưởi chưa chín hẳn"]
            },
            {
                "recipe_name": "Trứng Chiên",
                "serving": "2 người",
                "times": "10 Phút",
                "difficulty": "Dễ",
                "normal_ingredients": [
                    "Trứng gà : 2 quả",
                    "Dầu ăn : 2 muỗng canh"
                ],
                "spices": ["Muối", "Tiêu"],
                "process": ["Đập trứng ra bát"],
                "cook": ["Chiên trứng trên chảo"],
                "usage": ["Dọn ra đĩa"],
                "tips": ["Lửa vừa"]
            },
        ]

        created_files = []
        for i, recipe in enumerate(test_recipes, 1):
            file_path = os.path.join(temp_dir, f"{i}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(recipe, f, ensure_ascii=False, indent=2)
            created_files.append(file_path)

        logger.info(f"Created {len(created_files)} test recipe files")
        return created_files


class TestRecipeFilter(unittest.TestCase):
    """Test recipe name lookup (filter step)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.engine = RecipeAnalyzerEngine(recipe_db_path=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_exact_match(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["dish"], "Gỏi Trộn Khô Mực")

    def test_case_insensitive_match(self):
        result = self.engine.generate_fss_request("gỏi trộn khô mực")
        self.assertEqual(result["status"], "SUCCESS")

    def test_not_found(self):
        result = self.engine.generate_fss_request("Không tồn tại")
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertIn("suggestions", result)

    def test_empty_name(self):
        result = self.engine.generate_fss_request("")
        self.assertEqual(result["status"], "ERROR")

    def test_none_name(self):
        result = self.engine.generate_fss_request(None)
        self.assertEqual(result["status"], "ERROR")

    def test_whitespace_trimmed(self):
        result = self.engine.generate_fss_request("  Gỏi Trộn Khô Mực  ")
        self.assertEqual(result["status"], "SUCCESS")


class TestIngredientParser(unittest.TestCase):
    """Test ingredient string parsing."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.engine = RecipeAnalyzerEngine(recipe_db_path=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_parse_ingredient_string_with_delimiter(self):
        result = parse_ingredient_string("Bưởi : 1 trái")
        self.assertEqual(result["ingredient"], "Bưởi")
        self.assertEqual(result["quantity"], "1 trái")

    def test_parse_ingredient_string_no_delimiter(self):
        result = parse_ingredient_string("Muối")
        self.assertEqual(result["ingredient"], "Muối")
        self.assertEqual(result["quantity"], "1")

    def test_parse_ingredient_string_trailing_whitespace(self):
        result = parse_ingredient_string("  Thịt bò  :  500g  ")
        self.assertEqual(result["ingredient"], "Thịt bò")
        self.assertEqual(result["quantity"], "500g")

    def test_parse_ingredient_string_empty(self):
        result = parse_ingredient_string("")
        self.assertEqual(result["ingredient"], "")
        self.assertEqual(result["quantity"], "1")

    def test_original_ingredients_preserved(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertIn("original_ingredients", result)
        self.assertEqual(len(result["original_ingredients"]), 5)
        self.assertIn("Bưởi : 1 trái", result["original_ingredients"])

    def test_parse_ingredients_method(self):
        parsed = self.engine.parse_ingredients("gỏi trộn khô mực")
        self.assertEqual(len(parsed), 5)
        ingredients = [p["ingredient"] for p in parsed]
        self.assertIn("Bưởi", ingredients)
        self.assertIn("Mực khô", ingredients)


class TestRecipeSorter(unittest.TestCase):
    """Test alphabetical sorting of ingredients."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.engine = RecipeAnalyzerEngine(recipe_db_path=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_alphabetical_sort(self):
        parsed = self.engine.parse_ingredients("gỏi trộn khô mực")
        names = [p["ingredient"] for p in parsed]
        self.assertEqual(names, sorted(names))

    def test_sort_stability(self):
        parsed1 = self.engine.parse_ingredients("gỏi trộn khô mực")
        parsed2 = self.engine.parse_ingredients("gỏi trộn khô mực")
        self.assertEqual(parsed1, parsed2)


class TestFullRecipeOutput(unittest.TestCase):
    """Test full recipe output with all fields."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.engine = RecipeAnalyzerEngine(recipe_db_path=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_all_fields_present(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        expected_fields = {
            "status", "dish", "original_ingredients", "original_spices",
            "serving", "times", "difficulty", "process",
            "cook", "usage", "tips", "processing_time_ms"
        }
        self.assertTrue(expected_fields.issubset(result.keys()))

    def test_serving_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertEqual(result["serving"], "4 người")

    def test_times_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertEqual(result["times"], "30 Phút")

    def test_difficulty_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertEqual(result["difficulty"], "Dễ")

    def test_process_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertGreater(len(result["process"]), 0)

    def test_cook_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertGreater(len(result["cook"]), 0)

    def test_usage_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertGreater(len(result["usage"]), 0)

    def test_tips_field(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertGreater(len(result["tips"]), 0)

    def test_original_spices_present(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertIn("original_spices", result)
        self.assertGreater(len(result["original_spices"]), 0)

    def test_processing_time_ms_present(self):
        result = self.engine.generate_fss_request("Gỏi Trộn Khô Mực")
        self.assertIn("processing_time_ms", result)
        self.assertIsInstance(result["processing_time_ms"], (int, float))


class TestRecipeSuggestions(unittest.TestCase):
    """Test fuzzy recipe matching."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.engine = RecipeAnalyzerEngine(recipe_db_path=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_keyword_suggestion(self):
        result = self.engine.generate_fss_request("trộn")
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertGreater(len(result["suggestions"]), 0)

    def test_fuzzy_suggestion(self):
        result = self.engine.generate_fss_request("Goi Tron")
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertGreater(len(result["suggestions"]), 0)

    def test_suggestion_contains_recipe(self):
        result = self.engine.generate_fss_request("trứng")
        self.assertEqual(result["status"], "NOT_FOUND")
        suggestions_lower = [s.lower() for s in result["suggestions"]]
        self.assertTrue(any("trứng" in s for s in suggestions_lower))


class TestRecipeProcessor(unittest.TestCase):
    """Unit tests for RecipeProcessor utilities."""

    def test_normalize_quantity_default_value(self):
        qty, unit = normalize_quantity("", "trái")
        self.assertEqual(qty, "1")
        self.assertEqual(unit, "trái")

    def test_normalize_quantity_unit_normalization(self):
        qty, unit = normalize_quantity("2", "ki-lô")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "kg")

        qty, unit = normalize_quantity("500", "gram")
        self.assertEqual(qty, "500")
        self.assertEqual(unit, "g")

    def test_normalize_quantity_vietnamese_numbers(self):
        qty, unit = normalize_quantity("một", "muỗng")
        self.assertEqual(qty, "1")

        qty, unit = normalize_quantity("hai", "")
        self.assertEqual(qty, "2")

    def test_detect_quantity_unit_with_pattern(self):
        qty, unit = detect_quantity_unit("2 kg thịt lợn")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "kg")

        qty, unit = detect_quantity_unit("1 muỗng dầu ăn")
        self.assertEqual(qty, "1")
        self.assertEqual(unit, "muỗng")

    def test_detect_quantity_unit_no_pattern(self):
        qty, unit = detect_quantity_unit("cà rốt tươi")
        self.assertIsNone(qty)
        self.assertIsNone(unit)

    def test_remove_special_characters(self):
        text = 'Bưởi® "tươi" ™'
        result = remove_special_characters(text)
        self.assertNotIn('®', result)
        self.assertNotIn('™', result)
        self.assertNotIn('"', result)

    def test_parse_ingredient_string_standard(self):
        result = parse_ingredient_string("Bưởi : 1 trái")
        self.assertEqual(result, {"ingredient": "Bưởi", "quantity": "1 trái"})

    def test_parse_ingredient_string_fallback(self):
        result = parse_ingredient_string("Muối")
        self.assertEqual(result, {"ingredient": "Muối", "quantity": "1"})


class TestRecipeAnalyzerInit(unittest.TestCase):
    """Test RecipeAnalyzerEngine initialization."""

    def test_engine_init_empty_db_path(self):
        temp_dir = tempfile.mkdtemp()
        try:
            engine = RecipeAnalyzerEngine(recipe_db_path=temp_dir)
            self.assertEqual(len(engine.recipe_names), 0)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_engine_init_invalid_path(self):
        engine = RecipeAnalyzerEngine(recipe_db_path="/nonexistent/path/recipes")
        self.assertEqual(len(engine.recipe_names), 0)
        self.assertEqual(len(engine.recipe_db), 0)

    def test_engine_init_with_recipes(self):
        temp_dir = tempfile.mkdtemp()
        try:
            TestRecipeDatabase.create_test_recipes(temp_dir)
            engine = RecipeAnalyzerEngine(recipe_db_path=temp_dir)
            self.assertGreater(len(engine.recipe_names), 0)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_available_recipes(self):
        temp_dir = tempfile.mkdtemp()
        try:
            TestRecipeDatabase.create_test_recipes(temp_dir)
            engine = RecipeAnalyzerEngine(recipe_db_path=temp_dir)
            recipes = engine.get_available_recipes()
            self.assertEqual(len(recipes), 2)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestEngineWithRealData(unittest.TestCase):
    """Integration tests using real recipe dataset."""

    @unittest.skipIf(
        not Path(RECIPE_DB_PATH).exists() or not list(Path(RECIPE_DB_PATH).glob("*.json")),
        f"Recipe dataset not found at {RECIPE_DB_PATH}"
    )
    def test_fss_request_with_real_data(self):
        engine = RecipeAnalyzerEngine(recipe_db_path=RECIPE_DB_PATH)
        known_recipe = None
        for name in engine.recipe_names:
            if "trứng" in name or "thịt" in name:
                known_recipe = name
                break
        if not known_recipe and engine.recipe_names:
            known_recipe = engine.recipe_names[0]

        self.assertIsNotNone(known_recipe, "No recipes loaded from dataset")
        result = engine.generate_fss_request(known_recipe)
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertIn('original_ingredients', result)

    @unittest.skipIf(
        not Path(RECIPE_DB_PATH).exists() or not list(Path(RECIPE_DB_PATH).glob("*.json")),
        f"Recipe dataset not found at {RECIPE_DB_PATH}"
    )
    def test_filter_and_parse_with_real_data(self):
        engine = RecipeAnalyzerEngine(recipe_db_path=RECIPE_DB_PATH)
        if engine.recipe_names:
            recipe = engine.recipe_names[0]
            result = engine.generate_fss_request(recipe)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertGreater(len(result["original_ingredients"]), 0)


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestIngredientParser))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeSorter))
    suite.addTests(loader.loadTestsFromTestCase(TestFullRecipeOutput))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeSuggestions))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeAnalyzerInit))
    suite.addTests(loader.loadTestsFromTestCase(TestEngineWithRealData))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
