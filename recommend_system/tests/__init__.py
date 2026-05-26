"""
FSS Recommendation System - Test Suite
======================================

Purpose:
    Unit and integration tests for NLP recipe analysis.

Test Coverage:
    - RecipeAnalyzerAPI: Model loading, inference accuracy
    - RecipeProcessor: Text processing edge cases
    - Integration: End-to-end recipe → FSS-Request flow

ASPICE Compliance:
    - Comprehensive test cases for each module
    - Mock DBDaemon for integration tests
    - Error scenario coverage

Author: FSS QA Team
Last Modified: 2026-05-23
"""

__all__ = ["test_recipe_analyzer"]