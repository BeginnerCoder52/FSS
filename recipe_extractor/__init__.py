"""
FSS Recipe Extractor - NLP Ingredient Extraction Module
========================================================

Purpose:
    Provides Filter+Parse+Sort NLP ingredient extraction from Vietnamese
    recipes using direct structured JSON lookup. Extracts ingredient lists
    from recipe names via D-Bus service vn.edu.uit.FSS.RecipeExtractor.

Module Overview:
    - RecipeAnalyzerAPI: Main interface for recipe ingredient extraction
    - RecipeProcessor: Helper utilities for text processing and normalization
    - recipe_extractor_service: D-Bus service for remote ingredient extraction
    - recipe_extractor_main: Standalone daemon entry point

Version: 2.0.0
Status: Production
Author: FSS Team
Last Modified: 2026-06-21

ASPICE Compliance:
    - Clean code with detailed comments
    - Modular design for maintainability
    - Error handling with logging
    - Unit test coverage required

Usage Example:
    >>> from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
    >>> engine = RecipeAnalyzerEngine(recipe_db_path)
    >>> ingredients = engine.generate_fss_request("Gỏi Trộn Khô Mực")
"""

__version__ = "2.0.0"
__author__ = "FSS Team"
__all__ = ["RecipeAnalyzerAPI", "RecipeProcessor"]
