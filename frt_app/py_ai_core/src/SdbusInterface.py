"""
SdbusInterface.py - Backward Compatibility Module
Version: 1.0

DEPRECATED: This module is kept for backward compatibility only.
RENAMED TO: FrtDbusInterface (SDD v1.1.0 requirement)

Migration:
    Old: from SdbusInterface import SdbusInterface
    New: from FrtDbusInterface import FrtDbusInterface

This module now simply imports and re-exports the FrtDbusInterface class.
"""

# Import the actual implementation
from FrtDbusInterface import FrtDbusInterface, SdbusInterface

# Re-export for backward compatibility
__all__ = ["SdbusInterface", "FrtDbusInterface"]

import warnings

warnings.warn(
    "SdbusInterface is deprecated. Use FrtDbusInterface instead.",
    DeprecationWarning,
    stacklevel=2
)
