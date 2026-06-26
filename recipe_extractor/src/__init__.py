"""
FSS Recommend System - NLP Recipe Analysis Module
=================================================

This package provides Filter+Parse+Sort NLP pipeline for Vietnamese recipe
ingredient extraction, integrated with D-Bus for FSS DBDaemon communication.

Main Components:
    - RecipeAnalyzerEngine: Core NLP engine (filter+parse+sort on structured JSON)
    - RecipeProcessor: Text processing utilities (normalize_quantity, etc.)

Usage:
    >>> from src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
    >>> engine = RecipeAnalyzerEngine(recipe_db_path="data/recipes")
    >>> result = engine.generate_fss_request("Gỏi Trộn Khô Mực")
    >>> print(result['status'])
    'SUCCESS'

ASPICE Compliance:
    - Comprehensive logging and error handling
    - Input validation on all public APIs
    - Thread-safe recipe lookup (read-only dict)
    - Detailed docstrings and type hints

Dependencies:
    - Standard library only (json, re, logging, time, unicodedata)

Version: 2.0.0
Status: Filter+Sort NLP rewrite
Last Modified: 2026-06-21
"""

from .RecipeAnalyzerAPI import RecipeAnalyzerEngine

from .RecipeProcessor import (
    normalize_quantity,
    detect_quantity_unit,
    remove_special_characters,
    normalize_unicode,
)

__version__ = "2.0.0"
__author__ = "FSS AI Team"

__all__ = [
    "RecipeAnalyzerEngine",
    "normalize_quantity",
    "detect_quantity_unit",
    "remove_special_characters",
    "normalize_unicode",
]
