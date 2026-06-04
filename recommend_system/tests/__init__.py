"""
FSS Recommendation System - Test Suite
======================================

Purpose:
    Unit and integration tests for NLP recipe analysis using REAL hardware.

Test Coverage:
    - RecipeAnalyzerAPI: Model loading, inference accuracy (real CRF model)
    - RecipeProcessor: Text processing edge cases
    - Integration: End-to-end recipe -> FSS-Request flow (real recipe DB, 2470 recipes)
    - mock_terminal_test: Terminal simulation with real RecipeAnalyzerEngine

ASPICE Compliance:
    - Comprehensive test cases for each module
    - Real model validation with fss_ner_crf_optimized.joblib
    - Real recipe database validation (2470 Vietnamese recipes)
    - Error scenario coverage

Author: FSS QA Team
Last Modified: 2026-06-03
"""

__all__ = ["test_recipe_analyzer"]