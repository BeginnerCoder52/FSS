"""
@file conftest.py
@brief Pytest configuration and fixtures for DBDaemon unit tests.

This module provides shared fixtures, mocks, and test utilities for all
DBDaemon unit tests. Enables clean test isolation and configuration management.

Following ASPICE principles with proper test setup/teardown and resource cleanup.
"""

import pytest
import logging
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import sqlite3
import sys
import os


# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class TemporaryTestEnvironment:
    """Context manager for isolated test environment with temporary directories."""

    def __init__(self):
        """Initialize temporary environment."""
        self.temp_db_dir = None
        self.temp_asset_dir = None
        self.original_db_path = None

    def __enter__(self):
        """Create temporary directories for testing."""
        self.temp_db_dir = tempfile.mkdtemp(prefix="test_db_")
        self.temp_asset_dir = tempfile.mkdtemp(prefix="test_assets_")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary directories."""
        if self.temp_db_dir and os.path.exists(self.temp_db_dir):
            shutil.rmtree(self.temp_db_dir)
        if self.temp_asset_dir and os.path.exists(self.temp_asset_dir):
            shutil.rmtree(self.temp_asset_dir)

    def get_temp_db_path(self):
        """Get temporary database file path."""
        return os.path.join(self.temp_db_dir, "test_fss_data.db")

    def get_temp_asset_path(self):
        """Get temporary asset directory path."""
        return self.temp_asset_dir


# ============================================================================
# FIXTURES - DATABASE
# ============================================================================

@pytest.fixture
def temp_environment():
    """Provide temporary environment for isolated test execution."""
    with TemporaryTestEnvironment() as env:
        yield env


@pytest.fixture
def mock_sqlite_connection():
    """Provide mock SQLite connection."""
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_conn.cursor.return_value = MagicMock(spec=sqlite3.Cursor)
    return mock_conn


@pytest.fixture
def temp_db_path():
    """Provide temporary database path."""
    temp_dir = tempfile.mkdtemp(prefix="test_db_")
    db_path = os.path.join(temp_dir, "test_fss.db")
    yield db_path
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def real_sqlite_db(temp_db_path):
    """Provide real SQLite database for integration tests."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    yield conn, cursor
    # Cleanup
    conn.close()
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)


# ============================================================================
# FIXTURES - FILE SYSTEM
# ============================================================================

@pytest.fixture
def temp_asset_dir():
    """Provide temporary asset directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_assets_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_crop_dir(temp_asset_dir):
    """Provide temporary crop image directory."""
    crops_dir = os.path.join(temp_asset_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)
    return crops_dir


# ============================================================================
# FIXTURES - MOCKS
# ============================================================================

@pytest.fixture
def mock_logger():
    """Provide mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_dbus_system_bus():
    """Provide mock D-Bus system bus."""
    mock_bus = MagicMock()
    return mock_bus


@pytest.fixture
def mock_sdbus():
    """Provide mock sdbus module."""
    with patch.dict('sys.modules', {'sdbus': MagicMock()}):
        yield sys.modules['sdbus']


# ============================================================================
# FIXTURES - TEST DATA
# ============================================================================

@pytest.fixture
def sample_food_inventory():
    """Provide sample food inventory data."""
    return {
        'food_id': 'apple_001',
        'quantity': 10,
        'confidence_score': 0.95,
        'image_path': '/opt/fss/assets/crops/2024/01/15/apple_001_1705276800000.jpg'
    }


@pytest.fixture
def sample_environment_data():
    """Provide sample environmental sensor data."""
    return {
        'temperature': 4.5,
        'humidity': 75.3,
        'timestamp': 1705276800.123
    }


@pytest.fixture
def sample_jpeg_bytes():
    """Provide sample JPEG data (minimal valid JPEG header)."""
    # Minimal JPEG file (1x1 pixel)
    jpeg_data = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01'
        b'\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07'
        b'\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14'
        b'\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f'
        b"'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff"
        b'\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x0c\xff\xc4\x00\x14\x10\x01\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda'
        b'\x00\x08\x01\x01\x00\x00?\x00\x00\x00\x01\xff\xd9'
    )
    return jpeg_data


@pytest.fixture
def mock_path_operations(monkeypatch):
    """Provide mock path operations for file tests."""
    mock_exists = MagicMock(return_value=True)
    mock_mkdir = MagicMock()
    mock_rmdir = MagicMock()
    
    return {
        'exists': mock_exists,
        'mkdir': mock_mkdir,
        'rmdir': mock_rmdir
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_in_memory_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    return conn


def create_test_inventory_table(cursor):
    """Create test inventory table."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id TEXT NOT NULL UNIQUE,
            quantity INTEGER NOT NULL DEFAULT 0,
            confidence_score REAL NOT NULL DEFAULT 0.0,
            image_path TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def create_test_environment_log_table(cursor):
    """Create test environment log table."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS environment_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            timestamp REAL NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


# ============================================================================
# AUTOUSE FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for each test."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    yield
    # Cleanup - clear handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
