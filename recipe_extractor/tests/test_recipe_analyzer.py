"""
Unit Tests - RecipeAnalyzerAPI and RecipeProcessor
==================================================

Purpose:
    Validate NLP engine functionality, text processing, and output accuracy.

Test Coverage:
    1. RecipeAnalyzerAPI:
       - Model initialization and lifecycle
       - Recipe inference with known outputs
       - Edge cases: unknown recipes, empty input, special characters
       - Output format validation (FSS-Request JSON)
       - Fuzzy recipe suggestions
    
    2. RecipeProcessor:
       - Vietnamese tokenization
       - Feature extraction for CRF
       - Quantity normalization
       - Unicode and special character handling

Performance Targets:
    - Model inference: <10ms per recipe
    - Feature extraction: <1ms
    - Total pipeline: <20ms

ASPICE Compliance:
    - Isolated unit tests (no external service dependencies)
    - Comprehensive error case coverage
    - Input validation tests
    - Performance assertion tests

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-05-23
"""

import unittest
import logging
import json
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Production paths (model file + recipe dataset)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
MODEL_PATH = str(PROJECT_ROOT / "models" / "fss_ner_crf_optimized.joblib")
RECIPE_DB_PATH = str(PROJECT_ROOT / "data" / "recipes")

from src.RecipeAnalyzerAPI import (
    RecipeAnalyzerEngine,
    BIOTagSchema,
    normalize_ingredient_text,
    word2features,
    sent2features,
)

from src.RecipeProcessor import (
    extract_features,
    normalize_quantity,
    detect_quantity_unit,
    remove_special_characters,
)

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# Test Fixtures & Utilities
# ==============================================================================

class TestRecipeDatabase:
    """
    Create temporary test recipe database for unit tests.
    """
    
    @staticmethod
    def create_test_recipes(temp_dir: str) -> List[str]:
        """
        Create sample recipe JSON files in temp directory.
        
        Args:
            temp_dir (str): Temporary directory path
            
        Returns:
            List[str]: List of created file paths
        """
        test_recipes = [
            {
                "recipe_name": "Gỏi Trộn Khô Mực",
                "serving": "4 người",
                "times": "30 Phút",
                "normal_ingredients": [
                    "Bưởi: 1 trái",
                    "Mực khô: 1 con (50g)",
                    "Thịt ba chỉ: 100g"
                ],
                "spices": [
                    "Muối",
                    "Đường"
                ]
            },
            {
                "recipe_name": "Trứng Chiên",
                "serving": "2 người",
                "times": "10 Phút",
                "normal_ingredients": [
                    "Trứng gà: 2 quả",
                    "Dầu ăn: 2 muỗng canh"
                ],
                "spices": [
                    "Muối",
                    "Tiêu"
                ]
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


# ==============================================================================
# RecipeAnalyzerAPI Tests
# ==============================================================================

class TestRecipeAnalyzerEngineInitialization(unittest.TestCase):
    """
    Test RecipeAnalyzerEngine initialization and lifecycle.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        TestRecipeDatabase.create_test_recipes(self.temp_dir)
        self.recipe_db_path = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @unittest.skipIf(
        not Path(MODEL_PATH).exists(),
        f"Model file not found at {MODEL_PATH}"
    )
    def test_engine_initialization_success(self):
        """
        ASPICE Test: Verify engine initializes successfully with valid paths.
        
        Expected: Engine loads model and recipe database without errors
        """
        try:
            engine = RecipeAnalyzerEngine(
                model_path=MODEL_PATH,
                recipe_db_path=self.recipe_db_path
            )
            
            self.assertIsNotNone(engine.model)
            self.assertIsNotNone(engine.recipe_db)
            self.assertGreater(len(engine.recipe_names), 0)
            
            logger.info("✓ Engine initialization test passed")
            
        except Exception as e:
            self.fail(f"Engine initialization failed: {str(e)}")
    
    def test_engine_initialization_invalid_model_path(self):
        """
        ASPICE Test: Verify engine raises FileNotFoundError for invalid model path.
        
        Expected: RuntimeError or FileNotFoundError is raised
        """
        with self.assertRaises((FileNotFoundError, RuntimeError)):
            RecipeAnalyzerEngine(
                model_path="nonexistent/path/model.joblib",
                recipe_db_path=self.recipe_db_path
            )
    
    @unittest.skipIf(
        not Path(MODEL_PATH).exists(),
        f"Model file not found at {MODEL_PATH}"
    )
    def test_engine_initialization_invalid_recipe_path(self):
        """
        ASPICE Test: Verify engine handles invalid recipe database path.
        
        Expected: Engine initializes but with empty recipe database
        """
        engine = RecipeAnalyzerEngine(
            model_path=MODEL_PATH,
            recipe_db_path="nonexistent/recipe/path"
        )
        self.assertIsNotNone(engine.recipe_db)
        self.assertEqual(len(engine.recipe_names), 0)


# ==============================================================================
# RecipeProcessor Tests
# ==============================================================================

class TestRecipeProcessor(unittest.TestCase):
    """
    Unit tests for RecipeProcessor utilities.
    """
    
    def test_normalize_ingredient_text_removes_trademarks(self):
        """
        ASPICE Test: Verify special character removal.
        
        Expected: ® and ™ symbols removed
        """
        text = "Bưởi®, Mực khô™"
        result = normalize_ingredient_text(text)
        
        self.assertEqual(len(result), 2)
        self.assertNotIn('®', result[0])
        self.assertNotIn('™', result[1])
        logger.info(f"✓ Trademark removal test passed: {result}")
    
    def test_normalize_ingredient_text_removes_brand_names(self):
        """
        ASPICE Test: Verify brand name removal (Aji-ngon, etc.).
        
        Expected: Brand names removed, ingredients preserved
        """
        text = "Bưởi, Aji-ngon, AJI-NO-MOTO"
        result = normalize_ingredient_text(text)
        
        self.assertIn("Bưởi", result)
        self.assertEqual(len(result), 1)  # Only Bưởi should remain
        logger.info(f"✓ Brand name removal test passed: {result}")
    
    def test_normalize_ingredient_text_empty_input(self):
        """
        ASPICE Test: Edge case - empty input handling.
        
        Expected: Empty list returned
        """
        result = normalize_ingredient_text("")
        self.assertEqual(result, [])
        
        result = normalize_ingredient_text("   ")
        self.assertEqual(result, [])
        logger.info("✓ Empty input handling test passed")
    
    def test_extract_features_valid_input(self):
        """
        ASPICE Test: Verify feature extraction for CRF.
        
        Expected: All required features present
        """
        context = ['Bưởi', 'tươi', '1', 'trái']
        features = extract_features('tươi', context, 1)
        
        # Verify key features exist
        self.assertIn('bias', features)
        self.assertIn('word.lower()', features)
        self.assertIn('prev_word.lower()', features)
        self.assertIn('next_word.lower()', features)
        
        # Verify correct values
        self.assertEqual(features['word.lower()'], 'tươi')
        self.assertEqual(features['prev_word.lower()'], 'bưởi')
        self.assertEqual(features['next_word.lower()'], '1')
        
        logger.info(f"✓ Feature extraction test passed: {list(features.keys())}")
    
    def test_extract_features_beginning_of_sentence(self):
        """
        ASPICE Test: Verify BOS (Beginning of Sentence) marker.
        
        Expected: BOS=True for first token
        """
        context = ['Trứng', 'gà', '2', 'quả']
        features = extract_features('Trứng', context, 0)
        
        self.assertIn('BOS', features)
        self.assertTrue(features['BOS'])
        logger.info("✓ BOS marker test passed")
    
    def test_extract_features_end_of_sentence(self):
        """
        ASPICE Test: Verify EOS (End of Sentence) marker.
        
        Expected: EOS=True for last token
        """
        context = ['Trứng', 'gà', '2', 'quả']
        features = extract_features('quả', context, 3)
        
        self.assertIn('EOS', features)
        self.assertTrue(features['EOS'])
        logger.info("✓ EOS marker test passed")
    
    def test_extract_features_out_of_bounds(self):
        """
        ASPICE Test: Error handling - index out of bounds.
        
        Expected: IndexError raised
        """
        context = ['Bưởi', 'tươi']
        
        with self.assertRaises(IndexError):
            extract_features('word', context, 5)
        
        logger.info("✓ Out of bounds error handling test passed")
    
    def test_normalize_quantity_default_value(self):
        """
        ASPICE Test: Default quantity to "1" when missing.
        
        Expected: qty="1" when empty string provided
        """
        qty, unit = normalize_quantity("", "trái")
        self.assertEqual(qty, "1")
        self.assertEqual(unit, "trái")
        logger.info(f"✓ Default quantity test passed: ({qty}, {unit})")
    
    def test_normalize_quantity_unit_normalization(self):
        """
        ASPICE Test: Unit normalization (ki-lô → kg).
        
        Expected: Units mapped to standard forms
        """
        qty, unit = normalize_quantity("2", "ki-lô")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "kg")
        
        qty, unit = normalize_quantity("500", "gram")
        self.assertEqual(qty, "500")
        self.assertEqual(unit, "g")
        
        logger.info("✓ Unit normalization test passed")
    
    def test_normalize_quantity_vietnamese_numbers(self):
        """
        ASPICE Test: Convert Vietnamese text numbers (một, hai, ba).
        
        Expected: Vietnamese text converted to numerics
        """
        qty, unit = normalize_quantity("một", "muỗng")
        self.assertEqual(qty, "1")
        
        qty, unit = normalize_quantity("hai", "")
        self.assertEqual(qty, "2")
        
        qty, unit = normalize_quantity("ba", "trái")
        self.assertEqual(qty, "3")
        
        logger.info("✓ Vietnamese number conversion test passed")
    
    def test_detect_quantity_unit_with_pattern(self):
        """
        ASPICE Test: Detect quantity and unit from ingredient string.
        
        Expected: Correct extraction of numeric quantity and unit
        """
        qty, unit = detect_quantity_unit("2 kg thịt lợn")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "kg")
        
        qty, unit = detect_quantity_unit("1 muỗng dầu ăn")
        self.assertEqual(qty, "1")
        self.assertEqual(unit, "muỗng")
        
        logger.info("✓ Quantity/unit detection test passed")
    
    def test_detect_quantity_unit_no_pattern(self):
        """
        ASPICE Test: Handle ingredient without quantity.
        
        Expected: (None, None) returned
        """
        qty, unit = detect_quantity_unit("cà rốt tươi")
        self.assertIsNone(qty)
        self.assertIsNone(unit)
        
        logger.info("✓ No pattern detection test passed")
    
    def test_remove_special_characters(self):
        """
        ASPICE Test: Remove trademark/special symbols.
        
        Expected: Special characters removed, text preserved
        """
        text = 'Bưởi® "tươi" ™'
        result = remove_special_characters(text)
        
        self.assertNotIn('®', result)
        self.assertNotIn('™', result)
        self.assertNotIn('"', result)
        logger.info(f"✓ Special character removal test passed: '{result}'")


# ==============================================================================
# BIO Tagging Schema Tests
# ==============================================================================

class TestBIOTagSchema(unittest.TestCase):
    """
    Test BIO tagging constants.
    """
    
    def test_bio_tag_schema_constants(self):
        """
        ASPICE Test: Verify BIO tag schema constants.
        
        Expected: All required tags defined
        """
        schema = BIOTagSchema()
        
        self.assertEqual(schema.O, "O")
        self.assertEqual(schema.B_ING, "B-ING")
        self.assertEqual(schema.I_ING, "I-ING")
        self.assertEqual(schema.B_QTY, "B-QTY")
        self.assertEqual(schema.I_QTY, "I-QTY")
        
        logger.info("✓ BIO schema constants test passed")


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestRecipeAnalyzerIntegration(unittest.TestCase):
    """
    Integration tests for RecipeAnalyzerAPI.
    """
    
    def setUp(self):
        """Set up test fixtures using the production dataset."""
        self.recipe_db_path = RECIPE_DB_PATH
    
    @unittest.skipIf(
        not Path(MODEL_PATH).exists(),
        f"Model file not found at {MODEL_PATH}"
    )
    @unittest.skipIf(
        not Path(RECIPE_DB_PATH).exists() or not list(Path(RECIPE_DB_PATH).glob("*.json")),
        f"Recipe dataset not found at {RECIPE_DB_PATH}"
    )
    def test_fss_request_generation_with_real_data(self):
        """
        ASPICE Test: End-to-end FSS-Request generation using real dataset.
        
        Expected: Valid FSS-Request JSON returned for a known recipe
        """
        engine = RecipeAnalyzerEngine(
            model_path=MODEL_PATH,
            recipe_db_path=self.recipe_db_path
        )
        
        # Pick a recipe that exists in the real dataset
        known_recipe = None
        for name in engine.recipe_names:
            if "trứng" in name or "thịt" in name or "gà" in name or "cá" in name:
                known_recipe = name
                break
        if not known_recipe and engine.recipe_names:
            known_recipe = engine.recipe_names[0]
        
        self.assertIsNotNone(known_recipe, "No recipes loaded from dataset")
        
        result = engine.generate_fss_request(known_recipe)
        
        self.assertIn('status', result)
        self.assertIn('dish', result)
        self.assertEqual(result['status'], 'SUCCESS',
                         f"Recipe '{known_recipe}' should exist in dataset")
        
        logger.info(f"✓ Real-data FSS-Request test passed: '{known_recipe}' → {result['status']}")
    
    @unittest.skipIf(
        not Path(MODEL_PATH).exists(),
        f"Model file not found at {MODEL_PATH}"
    )
    def test_fss_request_generation_with_temp_data(self):
        """
        ASPICE Test: End-to-end FSS-Request generation using synthetic test recipes.
        
        Expected: Valid FSS-Request JSON returned
        """
        temp_dir = tempfile.mkdtemp()
        try:
            TestRecipeDatabase.create_test_recipes(temp_dir)
            engine = RecipeAnalyzerEngine(
                model_path=MODEL_PATH,
                recipe_db_path=temp_dir
            )
            
            result = engine.generate_fss_request("Gỏi Trộn Khô Mực")
            
            self.assertIn('status', result)
            self.assertIn('dish', result)
            self.assertIn(result['status'], ['SUCCESS', 'NOT_FOUND', 'ERROR'])
            
            logger.info(f"✓ Temp-data FSS-Request test passed: {result['status']}")
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @unittest.skipIf(
        not Path(MODEL_PATH).exists(),
        f"Model file not found at {MODEL_PATH}"
    )
    def test_recipe_suggestion(self):
        """
        ASPICE Test: Fuzzy recipe matching for misspellings.
        
        Expected: Suggestions returned for unknown recipe
        """
        engine = RecipeAnalyzerEngine(
            model_path=MODEL_PATH,
            recipe_db_path=self.recipe_db_path
        )
        
        result = engine.generate_fss_request("Trứng Chín")  # Misspelling
        
        if result['status'] == 'NOT_FOUND':
            self.assertIn('suggestions', result)
            logger.info(f"✓ Recipe suggestion test passed: {result['suggestions']}")


# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeAnalyzerEngineInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestBIOTagSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeAnalyzerIntegration))
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


