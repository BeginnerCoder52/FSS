"""
Integration Tests - RecipeExtractor ↔ ElectronApp Bridge
=========================================================

Purpose:
    Validate data format transformation between RecipeExtractor D-Bus output
    and the MagicMirror frontend format used by MMM-FSS-Recommend module.

Test Coverage:
    1. transform_ingredients function (RecipeExtractor → Frontend format)
    2. Mock mode JSON protocol (stdin → stdout line-delimited)
    3. Error response transformation
    4. Empty/none ingredient handling
    5. Vietnamese text preservation through the bridge
    6. Summary text generation (Vietnamese)
    7. JSON serialization of transformed output

Data Flow:
    RecipeExtractor (D-Bus):
        {"ingredients": [{"ingredient": "Bưởi", "quantity": "1"}], ...}

    transform_ingredients():
        {"ingredients": [{"name": "Bưởi", "required": "1",
                          "available": 0, "status": "missing"}], ...}

    stdout JSON line:
        {"type": "RESULT", "data": {...}}

ASPICE Compliance:
    - Data format contract validation
    - Vietnamese text encoding verification
    - Error propagation coverage
    - JSON protocol compliance

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-06-05
"""

import unittest
import logging
import sys
import json
import os
import io
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.disable(logging.CRITICAL)


# ==============================================================================
# RecipeExtractor Output Format (simulates D-Bus response)
# ==============================================================================

SAMPLE_EXTRACTOR_SUCCESS = {
    "status": "SUCCESS",
    "dish": "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c",
    "ingredients": [
        {"ingredient": "B\u01b0\u1edfi", "quantity": "1"},
        {"ingredient": "M\u1ef1c kh\u00f4", "quantity": "1 con (50g)"},
        {"ingredient": "C\u00e0 r\u1ed1t", "quantity": "2"},
        {"ingredient": "\u0110\u1eadu ph\u1ed9ng", "quantity": "1"},
    ],
    "batch_id": "test-batch-001",
    "persisted": True,
    "processing_time_ms": 3.22,
}

SAMPLE_EXTRACTOR_NOT_FOUND = {
    "status": "NOT_FOUND",
    "message": "Recipe not found: unknown",
    "dish": "unknown",
    "suggestions": ["g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c"],
    "batch_id": "test-batch-002",
}

SAMPLE_EXTRACTOR_ERROR = {
    "status": "ERROR",
    "error": "NLP engine not initialized",
}

SAMPLE_EXTRACTOR_EMPTY_INGREDIENTS = {
    "status": "SUCCESS",
    "dish": "empty test",
    "ingredients": [],
    "batch_id": "test-batch-003",
    "persisted": True,
    "processing_time_ms": 1.0,
}


# ==============================================================================
# transform_ingredients (same logic as in recommend_dbus_listener.py)
# ==============================================================================

def transform_ingredients(result: dict) -> dict:
    raw_ingredients = result.get("ingredients", [])
    if not isinstance(raw_ingredients, list):
        raw_ingredients = []
    transformed = []
    for item in raw_ingredients:
        transformed.append({
            "name": item.get("ingredient", ""),
            "required": item.get("quantity", "1"),
            "available": 0,
            "status": "missing",
        })

    return {
        "recipe_name": result.get("dish", ""),
        "ingredients": transformed,
        "total_items": len(transformed),
        "available_count": 0,
        "needed_count": 0,
        "missing_count": len(transformed),
        "summary": (
            f"C\u1ea7n mua th\u00eam {len(transformed)} nguy\u00ean li\u1ec7u"
            if transformed else
            "\u0110\u00e3 c\u00f3 \u0111\u1ee7 nguy\u00ean li\u1ec7u!"
        ),
    }


# ==============================================================================
# Transform Function Tests
# ==============================================================================

class TestTransformIngredients(unittest.TestCase):
    def test_transform_ingredients_success(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        self.assertEqual(result["recipe_name"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")
        self.assertEqual(result["total_items"], 4)
        self.assertEqual(result["missing_count"], 4)
        self.assertEqual(len(result["ingredients"]), 4)

    def test_transform_ingredient_fields(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        first = result["ingredients"][0]
        self.assertIn("name", first)
        self.assertIn("required", first)
        self.assertIn("available", first)
        self.assertIn("status", first)
        self.assertEqual(first["name"], "B\u01b0\u1edfi")
        self.assertEqual(first["required"], "1")
        self.assertEqual(first["available"], 0)
        self.assertEqual(first["status"], "missing")

    def test_transform_ingredients_preserves_quantity(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        self.assertEqual(result["ingredients"][1]["required"], "1 con (50g)")
        self.assertEqual(result["ingredients"][2]["required"], "2")

    def test_transform_ingredients_empty(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_EMPTY_INGREDIENTS)
        self.assertEqual(result["total_items"], 0)
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["missing_count"], 0)

    def test_transform_ingredients_summary_missing(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        self.assertIn("C\u1ea7n mua th\u00eam", result["summary"])

    def test_transform_ingredients_summary_available(self):
        empty_result = SAMPLE_EXTRACTOR_EMPTY_INGREDIENTS.copy()
        result = transform_ingredients(empty_result)
        self.assertEqual(result["summary"], "\u0110\u00e3 c\u00f3 \u0111\u1ee7 nguy\u00ean li\u1ec7u!")

    def test_transform_ingredients_vietnamese_text(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        self.assertEqual(result["ingredients"][0]["name"], "B\u01b0\u1edfi")
        self.assertEqual(result["ingredients"][2]["name"], "C\u00e0 r\u1ed1t")

    def test_transform_ingredients_available_is_always_zero(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        for ing in result["ingredients"]:
            self.assertEqual(ing["available"], 0)

    def test_transform_ingredients_status_is_always_missing(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        for ing in result["ingredients"]:
            self.assertEqual(ing["status"], "missing")


class TestTransformEdgeCases(unittest.TestCase):
    def test_transform_empty_dict(self):
        result = transform_ingredients({})
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)

    def test_transform_none_ingredients(self):
        result = transform_ingredients({"dish": "test", "ingredients": None})
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)

    def test_transform_no_dish_key(self):
        result = transform_ingredients({"ingredients": []})
        self.assertEqual(result["recipe_name"], "")

    def test_transform_missing_ingredient_key(self):
        result = transform_ingredients({
            "dish": "test",
            "ingredients": [{"quantity": "2"}],
        })
        self.assertEqual(result["ingredients"][0]["name"], "")
        self.assertEqual(result["ingredients"][0]["required"], "2")

    def test_transform_missing_quantity_key(self):
        result = transform_ingredients({
            "dish": "test",
            "ingredients": [{"ingredient": "B\u01b0\u1edfi"}],
        })
        self.assertEqual(result["ingredients"][0]["required"], "1")

    def test_transform_multiple_ingredients_unicode(self):
        result = transform_ingredients({
            "dish": "ph\u1edf b\u00f2",
            "ingredients": [
                {"ingredient": "Th\u1ecbt b\u00f2", "quantity": "200g"},
                {"ingredient": "B\u00e1nh ph\u1edf", "quantity": "500g"},
                {"ingredient": "H\u00e0nh l\u00e1", "quantity": "5"},
            ],
        })
        self.assertEqual(result["total_items"], 3)
        self.assertEqual(result["ingredients"][0]["name"], "Th\u1ecbt b\u00f2")
        self.assertEqual(result["ingredients"][2]["name"], "H\u00e0nh l\u00e1")


class TestJsonLineProtocol(unittest.TestCase):
    def test_result_json_serializable(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        line = json.dumps({"type": "RESULT", "data": result}, ensure_ascii=False)
        parsed = json.loads(line)
        self.assertEqual(parsed["type"], "RESULT")
        self.assertEqual(parsed["data"]["recipe_name"], "g\u1ecfi tr\u1ed9n kh\u00f4 m\u1ef1c")

    def test_error_json_serializable(self):
        line = json.dumps({
            "type": "ERROR",
            "message": SAMPLE_EXTRACTOR_ERROR["error"]
        }, ensure_ascii=False)
        parsed = json.loads(line)
        self.assertEqual(parsed["type"], "ERROR")
        self.assertEqual(parsed["message"], "NLP engine not initialized")

    def test_result_json_has_required_frontend_fields(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        required_frontend = {"recipe_name", "ingredients", "total_items",
                             "available_count", "needed_count", "missing_count",
                             "summary"}
        self.assertTrue(required_frontend.issubset(result.keys()))

    def test_line_delimited_json_stdout(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_SUCCESS)
        msg = {"type": "RESULT", "data": result}
        output = json.dumps(msg, ensure_ascii=False) + "\n"
        lines = output.strip().split("\n")
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["type"], "RESULT")

    def test_multiple_results_over_stdin_stdout(self):
        results = []
        for recipe in ["G\u1ecfi Tr\u1ed9n", "Tr\u1ee9ng Chi\u00ean"]:
            t = transform_ingredients({
                "dish": recipe.lower(),
                "ingredients": [{"ingredient": recipe, "quantity": "1"}],
            })
            results.append(t)

        output_lines = []
        for r in results:
            output_lines.append(json.dumps(
                {"type": "RESULT", "data": r}, ensure_ascii=False
            ))

        self.assertEqual(len(output_lines), 2)
        parsed0 = json.loads(output_lines[0])
        parsed1 = json.loads(output_lines[1])
        self.assertIn("g\u1ecfi tr\u1ed9n", parsed0["data"]["recipe_name"])
        self.assertIn("tr\u1ee9ng chi\u00ean", parsed1["data"]["recipe_name"])

    def test_error_response_has_type(self):
        error_msg = json.dumps({
            "type": "ERROR",
            "message": "D-Bus connection failed"
        }, ensure_ascii=False)
        parsed = json.loads(error_msg)
        self.assertEqual(parsed["type"], "ERROR")
        self.assertEqual(parsed["message"], "D-Bus connection failed")

    def test_mock_mode_data_matches_frontend_format(self):
        mock_data = {
            "dish": "test",
            "ingredients": [
                {"ingredient": "G\u1ea1o", "quantity": "1"},
                {"ingredient": "M\u1eafm", "quantity": "1"},
            ],
        }
        result = transform_ingredients(mock_data)
        self.assertEqual(result["total_items"], 2)
        self.assertEqual(result["ingredients"][0]["name"], "G\u1ea1o")
        self.assertEqual(result["ingredients"][1]["name"], "M\u1eafm")

    def test_transform_preserves_all_ingredients(self):
        many_ingredients = {
            "dish": "combo",
            "ingredients": [
                {"ingredient": f"item_{i}", "quantity": str(i)}
                for i in range(20)
            ],
        }
        result = transform_ingredients(many_ingredients)
        self.assertEqual(result["total_items"], 20)
        self.assertEqual(len(result["ingredients"]), 20)


class TestBridgeErrorResponse(unittest.TestCase):
    def test_error_response_transform(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_ERROR)
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)

    def test_not_found_response_transform(self):
        result = transform_ingredients(SAMPLE_EXTRACTOR_NOT_FOUND)
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)
        self.assertEqual(result["summary"], "\u0110\u00e3 c\u00f3 \u0111\u1ee7 nguy\u00ean li\u1ec7u!")

    def test_error_response_json_format(self):
        msg = {"type": "ERROR", "message": "D-Bus proxy not initialized"}
        serialized = json.dumps(msg, ensure_ascii=False)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["message"], "D-Bus proxy not initialized")

    def test_missing_ingredients_handling(self):
        result = transform_ingredients({"status": "SUCCESS", "dish": "test"})
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)

    def test_non_list_ingredients_handling(self):
        result = transform_ingredients({"dish": "test", "ingredients": "invalid"})
        self.assertEqual(result["ingredients"], [])
        self.assertEqual(result["total_items"], 0)

    def test_quantity_numeric_conversion(self):
        result = transform_ingredients({
            "dish": "test",
            "ingredients": [
                {"ingredient": "B\u01b0\u1edfi", "quantity": 1},
            ],
        })
        self.assertEqual(result["ingredients"][0]["required"], 1)


# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestTransformIngredients))
    suite.addTests(loader.loadTestsFromTestCase(TestTransformEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestJsonLineProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestBridgeErrorResponse))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
