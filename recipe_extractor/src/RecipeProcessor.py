"""
Recipe Processor - Text Processing Utilities
=============================================

Purpose:
    Provides helper functions for Vietnamese recipe text processing.
    Supports tokenization, normalization, and feature extraction for NLP pipeline.

Functions:
    - tokenize_vietnamese: PyVi-based tokenization (preserves compounds)
    - extract_features: CRF feature extraction for NER
    - normalize_quantities: Unit conversion and standardization

ASPICE Compliance:
    - Unit testable pure functions
    - Detailed docstrings for all exports
    - Error handling with logging
    - Input validation on all public functions

Author: FSS AI Team
Last Modified: 2026-05-23
Version: 1.0.0 (Phase 2 Implementation)
"""

import logging
import re
import unicodedata
from typing import List, Dict, Tuple, Optional

try:
    from pyvi import ViTokenizer
    PYVI_AVAILABLE = True
except ImportError:
    PYVI_AVAILABLE = False
    logging.warning("PyVi not available. Vietnamese tokenization will be simplified.")

logger = logging.getLogger(f"{__name__}")


# ==============================================================================
# Constants
# ==============================================================================

# Vietnamese culinary measurement units
VIETNAMESE_MASS_UNITS = {'g', 'kg', 'gram', 'ki-lô', 'kilogam'}
VIETNAMESE_VOLUME_UNITS = {'ml', 'lít', 'l', 'litter', 'mililit'}
VIETNAMESE_CULINARY_UNITS = {
    'muỗng', 'thìa', 'chén', 'tô', 'cốc', 'hộp', 'gói', 'cơm',
    'miếng', 'lát', 'củ', 'trái', 'quả', 'cái', 'con', 'ký'
}

# Standard unit mappings (for normalization)
UNIT_NORMALIZATIONS = {
    'ki-lô': 'kg',
    'kilogam': 'kg',
    'gram': 'g',
    'liter': 'l',
    'litting': 'l',
    'mililit': 'ml',
}


# ==============================================================================
# Tokenization Functions
# ==============================================================================

def tokenize_vietnamese(text: str) -> List[str]:
    """
    Tokenize Vietnamese text while preserving compound words.
    
    Uses PyVi library (if available) to maintain semantic meaning of
    multi-word tokens (e.g., "ba_chỉ" stays as single token).
    Falls back to simple space-based splitting if PyVi unavailable.
    
    Responsibilities:
        1. Handle compound Vietnamese words (multi-word units)
        2. Preserve underscore-based token grouping from PyVi
        3. Clean leading/trailing whitespace
        4. Filter empty tokens
    
    Args:
        text (str): Vietnamese ingredient text (may contain spaces)
        
    Returns:
        List[str]: List of tokens (including multi-word units with underscores)
        
    Example:
        >>> text = "ba_chỉ thịt lợn tươi"
        >>> tokens = tokenize_vietnamese(text)
        >>> print(tokens)
        ['ba_chỉ', 'thịt', 'lợn', 'tươi']
    
    Note:
        If PyVi is available, compound words are detected automatically.
        Otherwise, tokens are simply split on whitespace.
    """
    logger.debug(f"Tokenizing text: '{text}'")
    
    try:
        # Input validation
        if not isinstance(text, str):
            logger.error(f"Invalid input type: {type(text)}")
            raise TypeError(f"Expected str, got {type(text)}")
        
        # Normalize whitespace first
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text:
            logger.debug("Empty text after normalization")
            return []
        
        # Tokenize with PyVi if available
        if PYVI_AVAILABLE:
            try:
                # PyVi tokenizes and marks compound words with underscores
                tokenized = ViTokenizer.tokenize(text)
                tokens = tokenized.split()
                logger.debug(f"PyVi tokenization: {len(tokens)} tokens")
                return tokens
                
            except Exception as e:
                logger.warning(f"PyVi tokenization failed: {str(e)}. Using fallback.")
                # Fallback to simple splitting
                return text.split()
        else:
            # Fallback: simple whitespace splitting
            tokens = text.split()
            logger.debug(f"Fallback tokenization: {len(tokens)} tokens")
            return tokens
            
    except Exception as e:
        logger.error(f"Error tokenizing Vietnamese text: {str(e)}")
        raise


# ==============================================================================
# Feature Extraction (Already defined in RecipeAnalyzerAPI, but included here for reference)
# ==============================================================================

def extract_features(word: str, context: List[str], position: int) -> Dict:
    """
    Extract linguistic features for CRF model from a word in context.
    
    Features extracted:
        - Word form: lowercase, prefix (3 chars), suffix (3 chars)
        - Case indicators: isupper, istitle
        - Character type: isdigit, has_underscore
        - Context: features of previous/next words
        - Positional: beginning of sentence (BOS), end of sentence (EOS)
    
    These features are used by the CRF model to determine BIO tags
    (Begin-Inside-Outside for Named Entity Recognition).
    
    Args:
        word (str): Target word to extract features from
        context (List[str]): Full token list (for context)
        position (int): Position of target word in context
        
    Returns:
        Dict: Feature dictionary mapping feature names to values
        
    Raises:
        IndexError: If position is out of bounds
        TypeError: If inputs are not correct types
        
    Example:
        >>> context = ['Bưởi', 'tươi', '1', 'trái']
        >>> features = extract_features('tươi', context, 1)
        >>> print('word.lower()' in features and 'prev_word.lower()' in features)
        True
    
    Note:
        This function is unit-testable and should be used for feature
        pipeline validation in test_recipe_analyzer.py.
    """
    logger.debug(f"Extracting features for word '{word}' at position {position}")
    
    try:
        # Input validation
        if not isinstance(word, str):
            raise TypeError(f"word must be str, got {type(word)}")
        if not isinstance(context, list):
            raise TypeError(f"context must be list, got {type(context)}")
        if position < 0 or position >= len(context):
            raise IndexError(f"position {position} out of range for context of length {len(context)}")
        
        # Convert word to lowercase
        lower_word = word.lower().replace('_', ' ')
        
        # Core features
        features = {
            'bias': 1.0,
            'word.lower()': lower_word,
            'word[-3:]': word[-3:] if len(word) >= 3 else word,
            'word[:3]': word[:3],
            'word.isupper()': word.isupper(),
            'word.istitle()': word.istitle(),
            'word.isdigit()': word.isdigit(),
            'word.has_underscore()': '_' in word,
        }
        
        # Previous word context
        if position > 0:
            prev_word = context[position - 1]
            features['prev_word.lower()'] = prev_word.lower()
            features['prev_word.isdigit()'] = prev_word.isdigit()
        else:
            features['BOS'] = True  # Beginning of Sentence marker
        
        # Next word context
        if position < len(context) - 1:
            next_word = context[position + 1]
            features['next_word.lower()'] = next_word.lower()
            features['next_word.isdigit()'] = next_word.isdigit()
        else:
            features['EOS'] = True  # End of Sentence marker
        
        logger.debug(f"Extracted {len(features)} features")
        return features
        
    except (IndexError, TypeError) as e:
        logger.error(f"Error extracting features: {str(e)}")
        raise


# ==============================================================================
# Quantity Normalization
# ==============================================================================

def normalize_quantity(quantity_str: str, unit_str: str) -> Tuple[str, str]:
    """
    Normalize ingredient quantity and unit to standardized form.
    
    Normalization rules:
        1. Default to "1" if quantity is missing or empty
        2. Standardize units to Vietnamese culinary terms
        3. Convert text quantities (e.g., "một", "hai") to numerics
        4. Handle fractional quantities (e.g., "1/2")
        5. Trim leading/trailing whitespace
    
    Args:
        quantity_str (str): Quantity value (e.g., "2", "một", "", "1/2")
        unit_str (str): Unit of measurement (e.g., "kg", "muỗng", "trái")
        
    Returns:
        Tuple[str, str]: (normalized_quantity, normalized_unit)
        
    Example:
        >>> normalize_quantity("2", "ki-lô")
        ('2', 'kg')
        
        >>> normalize_quantity("một", "muỗng")
        ('1', 'muỗng')
        
        >>> normalize_quantity("", "")
        ('1', '')
    
    Note:
        Vietnamese number words: "một" (1), "hai" (2), "ba" (3), etc.
        This is handled at a basic level; complex recipes may need manual adjustment.
    """
    logger.debug(f"Normalizing quantity: '{quantity_str}', unit: '{unit_str}'")
    
    try:
        # Input validation and cleaning
        quantity_str = str(quantity_str).strip() if quantity_str else ""
        unit_str = str(unit_str).strip().lower() if unit_str else ""
        
        # Default quantity if missing
        if not quantity_str:
            normalized_qty = "1"
        else:
            # Try to extract numeric value
            numeric_match = re.search(r'\d+(?:/\d+)?', quantity_str)
            if numeric_match:
                normalized_qty = numeric_match.group()
            else:
                # Simple Vietnamese text number mapping
                viet_numbers = {
                    'một': '1', 'hai': '2', 'ba': '3', 'bốn': '4',
                    'năm': '5', 'sáu': '6', 'bảy': '7', 'tám': '8',
                    'chín': '9', 'mười': '10'
                }
                normalized_qty = viet_numbers.get(quantity_str.lower(), "1")
        
        # Normalize unit
        normalized_unit = UNIT_NORMALIZATIONS.get(unit_str, unit_str)
        
        logger.debug(f"Normalized to: qty='{normalized_qty}', unit='{normalized_unit}'")
        return (normalized_qty, normalized_unit)
        
    except Exception as e:
        logger.error(f"Error normalizing quantity: {str(e)}")
        # Return defaults on error
        return ("1", "")


def detect_quantity_unit(ingredient_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect and extract quantity and unit from ingredient string.
    
    Uses regex patterns to find numeric quantities and known units.
    
    Args:
        ingredient_str (str): Raw ingredient string (e.g., "2 kg thịt lợn")
        
    Returns:
        Tuple[Optional[str], Optional[str]]: (quantity, unit) or (None, None)
        
    Example:
        >>> detect_quantity_unit("2 kg thịt lợn")
        ('2', 'kg')
        
        >>> detect_quantity_unit("1 muỗng dầu ăn")
        ('1', 'muỗng')
    """
    logger.debug(f"Detecting quantity/unit from: '{ingredient_str}'")
    
    try:
        if not ingredient_str:
            return (None, None)
        
        # Pattern: number (possibly fractional) followed by unit
        pattern = r'(\d+(?:/\d+)?)\s*([a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+)?'
        
        match = re.search(pattern, ingredient_str)
        if match:
            quantity = match.group(1)
            unit = match.group(2) or ""
            logger.debug(f"Detected: qty='{quantity}', unit='{unit}'")
            return (quantity, unit)
        
        logger.debug("No quantity/unit pattern matched")
        return (None, None)
        
    except Exception as e:
        logger.error(f"Error detecting quantity/unit: {str(e)}")
        return (None, None)


# ==============================================================================
# Text Cleaning & Normalization (Utility functions)
# ==============================================================================

def remove_special_characters(text: str, keep_underscores: bool = True) -> str:
    """
    Remove special characters and symbols from text.
    
    Args:
        text (str): Input text
        keep_underscores (bool): Whether to preserve underscores (for compound words)
        
    Returns:
        str: Cleaned text
    """
    try:
        # Remove trademark and special symbols
        text = re.sub(r'[\®\™\"]', '', text)
        
        if not keep_underscores:
            text = text.replace('_', ' ')
        
        return text
        
    except Exception as e:
        logger.error(f"Error removing special characters: {str(e)}")
        return text


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode representation (NFC - Canonical Composition).
    
    Ensures consistent representation of Vietnamese diacritics.
    
    Args:
        text (str): Input text
        
    Returns:
        str: Normalized text
    """
    try:
        return unicodedata.normalize('NFC', text)
    except Exception as e:
        logger.error(f"Error normalizing Unicode: {str(e)}")
        return text


# ==============================================================================
# Pipeline Helper Functions
# ==============================================================================

def sentence_to_features(tokens: List[str]) -> List[Dict]:
    """
    Convert sentence (list of tokens) to list of feature dictionaries.
    
    This is a wrapper that calls extract_features for each token.
    
    Args:
        tokens (List[str]): List of tokens
        
    Returns:
        List[Dict]: List of feature dictionaries
    """
    try:
        features_list = []
        for i in range(len(tokens)):
            features = extract_features(tokens[i], tokens, i)
            features_list.append(features)
        
        logger.debug(f"Converted {len(tokens)} tokens to feature dicts")
        return features_list
        
    except Exception as e:
        logger.error(f"Error converting sentence to features: {str(e)}")
        raise