"""
FSS Recommendation System Package
==================================

Purpose:
    Provides NLP-based ingredient extraction from Vietnamese recipes using
    Conditional Random Fields (CRF) model. Generates shopping lists by 
    comparing recipe requirements against current inventory.

Module Overview:
    - RecipeAnalyzerAPI: Main interface for recipe ingredient extraction
    - RecipeProcessor: Helper utilities for text processing and normalization

Version: 1.0.0
Status: Production
Author: FSS Team
Last Modified: 2026-05-23

ASPICE Compliance:
    - Clean code with detailed comments
    - Modular design for maintainability
    - Error handling with logging
    - Unit test coverage required

Usage Example:
    >>> from recommend_system.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
    >>> engine = RecipeAnalyzerEngine(model_path, recipe_db_path)
    >>> ingredients = engine.generate_fss_request("Gỏi Trộn Khô Mực")
"""

__version__ = "1.0.0"
__author__ = "FSS Team"
__all__ = ["RecipeAnalyzerAPI", "RecipeProcessor"]