"""
FSS Recommendation System - Source Module
==========================================

Purpose:
    Core implementations for NLP-based recipe analysis and ingredient extraction.

Sub-modules:
    - RecipeAnalyzerAPI: Main NLP engine wrapper (CRF model interface)
    - RecipeProcessor: Text processing utilities (tokenization, normalization)

Design Pattern:
    - Singleton pattern for model loading (thread-safe)
    - Factory pattern for creating analysis requests
    - Adapter pattern to bridge NLP output → FSS-Request format

Dependencies:
    - scikit-crfsuite: CRF model inference
    - pyvi: Vietnamese text processing
    - joblib: Model serialization

Status: Development Phase 2
Last Modified: 2026-05-23
"""

__all__ = ["RecipeAnalyzerAPI", "RecipeProcessor"]