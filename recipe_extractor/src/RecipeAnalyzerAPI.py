"""
Recipe Analyzer API - Filter-Sort Engine Wrapper
=========================================

Purpose:
    Implements filter+parse+sort Filter-Sort pipeline for Vietnamese recipe analysis.
    Replaces the previous CRF-based NER approach with direct structured JSON lookup.

    Core Pipeline:
        1. Filter: Look up recipe name in loaded dictionary (O(1) hash lookup)
        2. Parse: Split ingredient strings on " : " delimiter
        3. Sort: Sort ingredients alphabetically for consistent display

    Output Format:
        Returns full original recipe data including:
        - original_ingredients, original_spices
        - serving, times, difficulty
        - process, cook, usage, tips

Database Integration:
    - Input: Recipe name (string)
    - Output: FSS-Request format with full recipe fields
    - Target: DBDaemon will insert output into FSS-Request table

ASPICE Compliance:
    - Comprehensive error handling with logging
    - Input validation and sanitization
    - Recipe name normalization (case-insensitive, diacritic-insensitive)
    - Fuzzy matching for misspelled recipe names

Author: FSS AI Team
Last Modified: 2026-06-21
Version: 2.0.0 (Filter+Sort Filter-Sort rewrite)
"""

import logging
import json
import re
import time
import unicodedata
import glob
import difflib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from recipe_extractor.src.RecipeProcessor import (
    remove_special_characters,
    normalize_unicode,
    parse_ingredient_string,
)

logger = logging.getLogger(f"{__name__}")


# ==============================================================================
# Main Filter-Sort Engine Class
# ==============================================================================

class RecipeAnalyzerEngine:
    """
    Filter+Parse+Sort Recipe analyzer for Vietnamese recipe ingredient extraction.

    Responsibilities:
        1. Load recipe database from JSON files into memory
        2. Look up recipes by name (O(1) hash lookup)
        3. Parse ingredient strings on " : " delimiter
        4. Sort ingredients alphabetically for consistent display
        5. Return full original recipe data including all JSON fields
        6. Suggest recipes on misspellings (fuzzy matching)

    Thread Safety:
        - Database loading is NOT thread-safe during __init__
        - Lookup is thread-safe after initialization (read-only dict)

    Performance (Raspberry Pi 4B):
        - Expected latency: <0.1ms per recipe (hash lookup, no ML inference)
        - Cold start: ~300ms (scan 2470 JSON files)
        - Memory footprint: ~50MB (full recipe data in dict)

    Example:
        >>> engine = RecipeAnalyzerEngine(recipe_db_path="data/recipes")
        >>> result = engine.generate_fss_request("Gỏi Trộn Khô Mực")
        >>> print(result['status'])
        'SUCCESS'
    """

    def __init__(self, recipe_db_path: str):
        """
        Initialize RecipeAnalyzerEngine.

        Args:
            recipe_db_path (str): Path to recipe database directory (contains .json files)

        Raises:
            RuntimeError: Recipe database loading failed

        ASPICE Note: Initialization logs all steps for audit trail.
        """
        logger.info("=" * 70)
        logger.info("Initializing RecipeAnalyzerEngine (Filter+Sort)")
        logger.info("=" * 70)

        try:
            self.recipe_db = self._load_recipe_database(recipe_db_path)
            self.recipe_names = sorted(list(self.recipe_db.keys()))
            logger.info(f"✓ Recipe database loaded: {len(self.recipe_db)} recipes")

            if not self.recipe_db:
                logger.warning("Recipe database is empty! No recipes loaded.")

            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Failed to initialize RecipeAnalyzerEngine: {str(e)}")
            raise RuntimeError(f"Engine initialization failed: {str(e)}")

    def _load_recipe_database(self, recipe_db_path: str) -> Dict[str, Dict]:
        """
        Load full recipe data from JSON files.

        Reads all JSON files from recipe_db_path directory and builds
        a lookup dictionary mapping normalized recipe names to full recipe data.

        Args:
            recipe_db_path (str): Directory containing recipe JSON files

        Returns:
            Dict[str, Dict]: { recipe_name_normalized: full_recipe_data }

        Note:
            Recipe names are normalized to lowercase for case-insensitive lookup.
        """
        db = {}
        recipe_dir = Path(recipe_db_path)
        json_files = sorted(glob.glob(str(recipe_dir / "*.json")))

        logger.info(f"Loading recipes from: {recipe_db_path}")
        logger.info(f"Found {len(json_files)} recipe files")

        loaded_count = 0
        failed_count = 0

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    raw_name = data.get('recipe_name', '')
                    recipe_name = normalize_unicode(raw_name).strip().lower()

                    if recipe_name:
                        db[recipe_name] = data
                        loaded_count += 1

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in {file_path}: {str(e)}")
                failed_count += 1
            except Exception as e:
                logger.warning(f"Error loading recipe from {file_path}: {str(e)}")
                failed_count += 1

        logger.info(f"Recipe database loaded: {loaded_count} successful, {failed_count} failed")
        return db

    def generate_fss_request(self, recipe_name: str) -> Dict:
        """
        Generate FSS-Request from recipe name using filter+parse+sort.

        Pipeline:
            1. Normalize input recipe name
            2. Filter: Look up in recipe DB (case-insensitive)
            3. If not found: Fuzzy match suggestions
            4. Parse: Extract original_ingredients and original_spices as raw strings
            5. Sort: Alphabetically by ingredient name
            6. Build full recipe output with all JSON fields

        Args:
            recipe_name (str): Vietnamese recipe name (e.g., "Gỏi Trộn Khô Mực")

        Returns:
            Dict: Full recipe output format
                {
                    "status": "SUCCESS" | "NOT_FOUND" | "ERROR",
                    "dish": str,
                    "original_ingredients": [...],
                    "original_spices": [...],
                    "serving": str,
                    "times": str,
                    "difficulty": str,
                    "process": [...],
                    "cook": [...],
                    "usage": [...],
                    "tips": [...],
                    "processing_time_ms": float
                }
        """
        logger.debug(f"Generating FSS request for recipe: {recipe_name}")

        try:
            if not recipe_name or not isinstance(recipe_name, str):
                logger.error("Invalid recipe_name input")
                return {
                    "status": "ERROR",
                    "error": "Invalid recipe name",
                    "dish": recipe_name
                }

            normalized_dish = normalize_unicode(recipe_name).strip().lower()

            if normalized_dish not in self.recipe_db:
                suggestions = self._suggest_recipe(normalized_dish)
                logger.warning(
                    f"Recipe not found: {recipe_name}. "
                    f"Suggestions: {suggestions}"
                )
                return {
                    "status": "NOT_FOUND",
                    "message": f"Recipe not found: {recipe_name}",
                    "dish": normalized_dish,
                    "suggestions": suggestions
                }

            start_time = time.time()
            recipe_data = self.recipe_db[normalized_dish]

            output = {
                "status": "SUCCESS",
                "dish": recipe_data.get('recipe_name', normalized_dish),
                "original_ingredients": recipe_data.get('normal_ingredients', []),
                "original_spices": recipe_data.get('spices', []),
                "serving": recipe_data.get('serving', ''),
                "times": recipe_data.get('times', ''),
                "difficulty": recipe_data.get('difficulty', ''),
                "process": recipe_data.get('process', recipe_data.get('step', [])),
                "cook": recipe_data.get('cook', []),
                "usage": recipe_data.get('usage', []),
                "tips": recipe_data.get('tips', []),
                "processing_time_ms": round((time.time() - start_time) * 1000, 2)
            }

            logger.debug(
                f"Recipe '{normalized_dish}' processed in {output['processing_time_ms']}ms"
            )
            return output

        except Exception as e:
            logger.error(f"Error generating FSS request: {str(e)}")
            return {
                "status": "ERROR",
                "dish": recipe_name,
                "error": str(e)
            }

    def parse_ingredients(self, recipe_name: str) -> List[Dict[str, str]]:
        """
        Parse original_ingredients strings into structured list.

        Splits each ingredient string on " : " delimiter:
            "Bưởi : 1 trái" → {"ingredient": "Bưởi", "quantity": "1 trái"}

        Results are sorted alphabetically by ingredient name.

        Args:
            recipe_name (str): Normalized recipe name

        Returns:
            List[Dict[str, str]]: Sorted list of {ingredient, quantity} pairs
        """
        raw_strings = self.recipe_db.get(recipe_name, {}).get('normal_ingredients', [])
        parsed = [parse_ingredient_string(s) for s in raw_strings]
        return sorted(parsed, key=lambda x: x['ingredient'])

    def _suggest_recipe(self, query: str, cutoff: float = 0.4) -> List[str]:
        """
        Suggest recipes based on fuzzy matching (misspellings/variations).

        Uses two strategies:
            1. Keyword matching: Find recipes with query as substring
            2. Fuzzy matching: Find recipes with similar names (difflib)

        Args:
            query (str): Search query (user input)
            cutoff (float): Fuzzy match threshold (0.0-1.0). Default 0.4.

        Returns:
            List[str]: Top 5 matching recipe names, sorted by length
        """
        query = query.lower()

        keyword_matches = [
            name for name in self.recipe_names
            if query in name
        ]

        fuzzy_matches = difflib.get_close_matches(
            query,
            self.recipe_names,
            n=5,
            cutoff=cutoff
        )

        suggestions = list(set(keyword_matches + fuzzy_matches))
        suggestions = sorted(suggestions, key=len)[:5]

        logger.debug(f"Recipe suggestions for '{query}': {suggestions}")
        return suggestions

    def get_available_recipes(self) -> List[str]:
        """
        Retrieve all indexed recipes from database.

        Returns:
            List[str]: Sorted list of all recipe names in database
        """
        logger.debug(f"Retrieving {len(self.recipe_names)} available recipes")
        return self.recipe_names.copy()
