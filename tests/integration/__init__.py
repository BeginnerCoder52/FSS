"""
FSS Integration Test Suite
==========================

Purpose:
    Integration tests validating component interactions between recipe_extractor
    and its dependent services (DBDaemon, RecommendDaemon, ElectronApp).

Test Modules:
    - test_extractor_dbd_integration: recipe_extractor → DBDaemon (SQLite persistence)
    - test_extractor_recommend_integration: recipe_extractor → RecommendDaemon (Bù Trừ)
    - test_extractor_electron_integration: recipe_extractor → Electron bridge (transform)

ASPICE Compliance:
    - Cross-component data format validation
    - End-to-end flow with real/mocked dependencies
    - Interface contract verification between services
    - Error handling at component boundaries

Author: FSS QA Team
Version: 1.0.0
Last Modified: 2026-06-05
"""

__all__ = [
    "test_extractor_dbd_integration",
    "test_extractor_recommend_integration",
    "test_extractor_electron_integration",
]
