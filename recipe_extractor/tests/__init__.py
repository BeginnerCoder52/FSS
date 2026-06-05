"""
FSS Recipe Extractor - Test Suite
==================================

Purpose:
    Unit and integration tests for the RecipeExtractor D-Bus service,
    NLP pipeline, and data transformation.

Test Coverage:
    - RecipeAnalyzerAPI: Model loading, inference accuracy (real CRF model)
    - RecipeProcessor: Text processing edge cases
    - RecipeExtractorDbusService: Service initialization, lifecycle, extraction logic
    - RecipeExtractorMain: Main entry point lifecycle, NLP lazy loading
    - Bridge data transformation: RecipeExtractor → frontend format conversion
    - Integration: End-to-end recipe -> FSS-Request flow (real recipe DB, 2470 recipes)

ASPICE Compliance:
    - Comprehensive test cases for each module
    - Isolated unit tests (no external D-Bus dependencies)
    - Error scenario coverage
    - Lifecycle state machine testing

Author: FSS QA Team
Last Modified: 2026-06-05
"""

__all__ = ["test_recipe_analyzer", "test_recipe_extractor_service", "test_recipe_extractor_main"]