"""
FSS Recipe Extractor - Test Suite
==================================

Purpose:
    Unit and integration tests for the RecipeExtractor D-Bus service,
    Analyzer pipeline (Filter+Sort), and data transformation.

Test Coverage:
    - RecipeAnalyzerAPI: Filter+Parse+Sort pipeline, recipe lookup, output format
    - RecipeProcessor: Text processing, quantity normalization, ingredient parsing
    - RecipeExtractorDbusService: Service initialization, lifecycle, extraction logic
    - RecipeExtractorMain: Main entry point lifecycle, recipe DB loading
    - Integration: End-to-end recipe -> FSS-Request flow (real recipe DB, 2470 recipes)

ASPICE Compliance:
    - Comprehensive test cases for each module
    - Isolated unit tests (no external D-Bus dependencies)
    - Error scenario coverage
    - Lifecycle state machine testing

Author: FSS QA Team
Last Modified: 2026-06-21
Version: 2.0.0 (Filter+Sort Analyzer rewrite)
"""

__all__ = ["test_recipe_analyzer", "test_recipe_extractor_service", "test_recipe_extractor_main"]