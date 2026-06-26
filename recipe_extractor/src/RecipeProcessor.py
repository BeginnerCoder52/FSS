"""
Recipe Processor - Text Processing Utilities
=============================================

Purpose:
    Provides helper functions for Vietnamese recipe text processing.
    Supports text normalization, quantity parsing, and unit detection.

Functions:
    - remove_special_characters: Strip trademark symbols and special chars
    - normalize_unicode: NFC Unicode normalization
    - normalize_quantity: Unit conversion and standardization
    - detect_quantity_unit: Extract quantity and unit from ingredient string

ASPICE Compliance:
    - Unit testable pure functions
    - Detailed docstrings for all exports
    - Error handling with logging
    - Input validation on all public functions

Author: FSS AI Team
Last Modified: 2026-06-21
Version: 2.0.0 (Filter+Sort NLP rewrite)
"""

import logging
import re
import unicodedata
from typing import List, Dict, Tuple, Optional

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
        quantity_str = str(quantity_str).strip() if quantity_str else ""
        unit_str = str(unit_str).strip().lower() if unit_str else ""

        if not quantity_str:
            normalized_qty = "1"
        else:
            numeric_match = re.search(r'\d+(?:/\d+)?', quantity_str)
            if numeric_match:
                normalized_qty = numeric_match.group()
            else:
                viet_numbers = {
                    'một': '1', 'hai': '2', 'ba': '3', 'bốn': '4',
                    'năm': '5', 'sáu': '6', 'bảy': '7', 'tám': '8',
                    'chín': '9', 'mười': '10'
                }
                normalized_qty = viet_numbers.get(quantity_str.lower(), "1")

        normalized_unit = UNIT_NORMALIZATIONS.get(unit_str, unit_str)

        logger.debug(f"Normalized to: qty='{normalized_qty}', unit='{normalized_unit}'")
        return (normalized_qty, normalized_unit)

    except Exception as e:
        logger.error(f"Error normalizing quantity: {str(e)}")
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
# Ingredient Parsing (for original_ingredients format)
# ==============================================================================

def parse_ingredient_string(item_str: str) -> Dict[str, str]:
    """
    Parse an ingredient string in 'name : quantity' format.

    The standard format from recipe JSON files uses ' : ' as delimiter:
        "Bưởi : 1 trái"  →  {"ingredient": "Bưởi", "quantity": "1 trái"}

    Args:
        item_str (str): Raw ingredient string with delimiter

    Returns:
        Dict[str, str]: {"ingredient": str, "quantity": str}

    Example:
        >>> parse_ingredient_string("Bưởi : 1 trái")
        {'ingredient': 'Bưởi', 'quantity': '1 trái'}
    """
    parts = item_str.split(" : ", 1)
    name = parts[0].strip()
    qty = parts[1].strip() if len(parts) > 1 else "1"
    return {"ingredient": name, "quantity": qty}
