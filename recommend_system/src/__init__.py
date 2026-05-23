"""
FSS Recommend System - NLP Recipe Analysis Module
=================================================

This package provides CRF-based NLP pipeline for Vietnamese recipe ingredient
extraction, integrated with D-Bus for FSS DBDaemon communication.

Main Components:
    - RecipeAnalyzerEngine: Core NLP inference engine
    - RecipeProcessor: Text processing utilities
    - Feature extraction: CRF feature vectors

Usage:
    >>> from src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
    >>> engine = RecipeAnalyzerEngine(
    ...     model_path="models/fss_ner_crf_optimized.joblib",
    ...     recipe_db_path="data/recipes"
    ... )
    >>> result = engine.generate_fss_request("Gỏi Trộn Khô Mực")
    >>> print(result['status'])
    'SUCCESS'

ASPICE Compliance:
    - Comprehensive logging and error handling
    - Input validation on all public APIs
    - Thread-safe model loading and inference
    - Detailed docstrings and type hints

Dependencies:
    - scikit-crfsuite: CRF model inference
    - pyvi: Vietnamese text processing
    - joblib: Model serialization

Version: 1.0.0
Status: Phase 2 Implementation Complete
Last Modified: 2026-05-23
"""

from .RecipeAnalyzerAPI import (
    RecipeAnalyzerEngine,
    BIOTagSchema,
    load_model,
    normalize_ingredient_text,
    word2features,
    sent2features,
)

from .RecipeProcessor import (
    tokenize_vietnamese,
    extract_features,
    normalize_quantity,
    detect_quantity_unit,
    remove_special_characters,
    normalize_unicode,
    sentence_to_features,
)

__version__ = "1.0.0"
__author__ = "FSS AI Team"

__all__ = [
    # RecipeAnalyzerAPI
    "RecipeAnalyzerEngine",
    "BIOTagSchema",
    "load_model",
    "normalize_ingredient_text",
    "word2features",
    "sent2features",
    
    # RecipeProcessor
    "tokenize_vietnamese",
    "extract_features",
    "normalize_quantity",
    "detect_quantity_unit",
    "remove_special_characters",
    "normalize_unicode",
    "sentence_to_features",
]