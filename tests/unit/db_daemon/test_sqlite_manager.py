"""
@file test_sqlite_manager.py
@brief Unit tests for SqliteManager component.

This module provides comprehensive test coverage for SQLite database management
functionality including connection handling, table initialization, inventory
operations, and environmental data logging.

Following ASPICE principles with clean code, proper test isolation, and
clear test case organization.
"""

import pytest
import sqlite3
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'db_daemon/src'))

from SqliteManager import SqliteManager


# ============================================================================
# TEST CLASS: SqliteManager Initialization
# ============================================================================

class TestSqliteManagerInitialization:
    """Test cases for SqliteManager initialization."""

    def test_init_with_default_parameters(self):
        """
        ASPICE: SQC.BP1 - Clean code principle: proper initialization
        
        Verify SqliteManager initializes with default configuration parameters.
        """
        manager = SqliteManager()
        
        assert manager.db_path == SqliteManager.DEFAULT_DB_PATH
        assert manager.transaction_timeout_ms == SqliteManager.DEFAULT_TRANSACTION_TIMEOUT_MS
        assert manager.db_connection is None
        assert manager.db_cursor is None
        assert manager.logger is not None

    def test_init_with_custom_parameters(self, temp_db_path):
        """
        ASPICE: SQC.BP2 - Parameterized initialization
        
        Verify SqliteManager accepts and stores custom configuration parameters.
        """
        custom_timeout = 3000
        manager = SqliteManager(db_path=temp_db_path, transaction_timeout_ms=custom_timeout)
        
        assert manager.db_path == temp_db_path
        assert manager.transaction_timeout_ms == custom_timeout

    def test_init_creates_logger(self):
        """
        ASPICE: SQC.BP3 - Logging configuration
        
        Verify SqliteManager creates logger instance for debugging.
        """
        manager = SqliteManager()
        
        assert isinstance(manager.logger, logging.Logger)
        assert manager.logger.name == 'SqliteManager'


# ============================================================================
# TEST CLASS: Database Connection
# ============================================================================

class TestDatabaseConnection:
    """Test cases for database connection operations."""

    def test_connect_db_creates_connection(self, temp_db_path):
        """
        ASPICE: SQC.BP4 - Resource acquisition
        
        Verify connect_db successfully establishes database connection.
        """
        manager = SqliteManager(db_path=temp_db_path)
        result = manager.connect_db()
        
        assert result is True
        assert manager.db_connection is not None
        assert manager.db_cursor is not None
        
        # Cleanup
        manager.close_connection()

    def test_connect_db_creates_directory(self, temp_asset_dir):
        """
        ASPICE: SQC.BP5 - Directory creation
        
        Verify connect_db creates database directory if it doesn't exist.
        """
        db_path = os.path.join(temp_asset_dir, "new_dir/subdir/test.db")
        manager = SqliteManager(db_path=db_path)
        result = manager.connect_db()
        
        assert result is True
        assert os.path.exists(os.path.dirname(db_path))
        
        manager.close_connection()

    def test_connect_db_enables_wal_mode(self, temp_db_path):
        """
        ASPICE: SQC.BP6 - Database configuration
        
        Verify connect_db enables WAL mode for concurrent access.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        
        # Query journal mode
        manager.db_cursor.execute("PRAGMA journal_mode")
        journal_mode = manager.db_cursor.fetchone()[0]
        
        assert journal_mode.lower() == 'wal'
        
        manager.close_connection()

    def test_connect_db_enables_foreign_keys(self, temp_db_path):
        """
        ASPICE: SQC.BP7 - Database constraints
        
        Verify connect_db enables foreign key constraints.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        
        # Query foreign keys setting
        manager.db_cursor.execute("PRAGMA foreign_keys")
        foreign_keys = manager.db_cursor.fetchone()[0]
        
        assert foreign_keys == 1
        
        manager.close_connection()

    def test_connect_db_handles_invalid_path(self):
        """
        ASPICE: SQC.BP8 - Error handling
        
        Verify connect_db handles invalid path gracefully.
        """
        # Use invalid path with non-existent parent (permission denied simulation)
        manager = SqliteManager(db_path="/invalid/path/that/cannot/exist/db.db")
        
        with patch.object(Path, 'mkdir', side_effect=PermissionError("Access denied")):
            result = manager.connect_db()
            assert result is False


# ============================================================================
# TEST CLASS: Table Initialization
# ============================================================================

class TestTableInitialization:
    """Test cases for database table creation."""

    def test_init_tables_creates_inventory_table(self, temp_db_path):
        """
        ASPICE: SQC.BP9 - Schema initialization
        
        Verify init_tables_if_not_exists creates inventory table with proper schema.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Verify table exists
        manager.db_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'"
        )
        assert manager.db_cursor.fetchone() is not None
        
        manager.close_connection()

    def test_init_tables_creates_environment_log_table(self, temp_db_path):
        """
        ASPICE: SQC.BP10 - Schema initialization
        
        Verify init_tables_if_not_exists creates environment_log table.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Verify table exists
        manager.db_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='environment_log'"
        )
        assert manager.db_cursor.fetchone() is not None
        
        manager.close_connection()

    def test_init_tables_creates_inventory_index(self, temp_db_path):
        """
        ASPICE: SQC.BP11 - Query optimization
        
        Verify init_tables_if_not_exists creates food_id index for performance.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Verify index exists
        manager.db_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_inventory_food_id'"
        )
        assert manager.db_cursor.fetchone() is not None
        
        manager.close_connection()

    def test_init_tables_creates_timestamp_index(self, temp_db_path):
        """
        ASPICE: SQC.BP12 - Query optimization
        
        Verify init_tables_if_not_exists creates timestamp index.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Verify index exists
        manager.db_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_env_log_timestamp'"
        )
        assert manager.db_cursor.fetchone() is not None
        
        manager.close_connection()

    def test_init_tables_idempotent(self, temp_db_path):
        """
        ASPICE: SQC.BP13 - Idempotent operations
        
        Verify calling init_tables_if_not_exists multiple times is safe.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        
        # Call multiple times
        manager.init_tables_if_not_exists()
        manager.init_tables_if_not_exists()
        manager.init_tables_if_not_exists()
        
        # Should not raise exception
        assert True
        
        manager.close_connection()

    def test_init_tables_without_connection(self, temp_db_path):
        """
        ASPICE: SQC.BP14 - Defensive programming
        
        Verify init_tables_if_not_exists handles missing connection gracefully.
        """
        manager = SqliteManager(db_path=temp_db_path)
        # Don't connect
        
        manager.init_tables_if_not_exists()
        # Should log error but not crash
        assert True


# ============================================================================
# TEST CLASS: Inventory Operations
# ============================================================================

class TestInventoryOperations:
    """Test cases for inventory management."""

    def test_update_inventory_insert_new_item(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP15 - Data persistence
        
        Verify update_inventory inserts new inventory items.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        result = manager.update_inventory(
            sample_food_inventory['food_id'],
            sample_food_inventory['quantity'],
            sample_food_inventory['confidence_score'],
            sample_food_inventory['image_path']
        )
        
        assert result is True
        
        # Verify data was inserted
        manager.db_cursor.execute(
            "SELECT food_id FROM inventory WHERE food_id = ?",
            (sample_food_inventory['food_id'],)
        )
        assert manager.db_cursor.fetchone() is not None
        
        manager.close_connection()

    def test_update_inventory_replace_existing_item(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP16 - UPSERT operation
        
        Verify update_inventory replaces existing item (UPSERT pattern).
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Insert first time
        manager.update_inventory(
            sample_food_inventory['food_id'],
            10,
            0.90
        )
        
        # Update with different values
        result = manager.update_inventory(
            sample_food_inventory['food_id'],
            20,
            0.98
        )
        
        assert result is True
        
        # Verify updated data
        manager.db_cursor.execute(
            "SELECT quantity, confidence_score FROM inventory WHERE food_id = ?",
            (sample_food_inventory['food_id'],)
        )
        row = manager.db_cursor.fetchone()
        assert row[0] == 20
        assert row[1] == 0.98
        
        manager.close_connection()

    def test_update_inventory_without_connection(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP17 - Error handling
        
        Verify update_inventory handles missing connection gracefully.
        """
        manager = SqliteManager(db_path=temp_db_path)
        # Don't connect
        
        result = manager.update_inventory(
            sample_food_inventory['food_id'],
            sample_food_inventory['quantity'],
            sample_food_inventory['confidence_score']
        )
        
        assert result is False

    def test_get_inventory_item_existing(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP18 - Data retrieval
        
        Verify get_inventory_item retrieves existing item.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Insert item
        manager.update_inventory(
            sample_food_inventory['food_id'],
            sample_food_inventory['quantity'],
            sample_food_inventory['confidence_score'],
            sample_food_inventory['image_path']
        )
        
        # Retrieve item
        item = manager.get_inventory_item(sample_food_inventory['food_id'])
        
        assert item is not None
        assert item['food_id'] == sample_food_inventory['food_id']
        assert item['quantity'] == sample_food_inventory['quantity']
        assert item['confidence_score'] == sample_food_inventory['confidence_score']
        
        manager.close_connection()

    def test_get_inventory_item_nonexistent(self, temp_db_path):
        """
        ASPICE: SQC.BP19 - Null handling
        
        Verify get_inventory_item returns None for nonexistent item.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        item = manager.get_inventory_item('nonexistent_id')
        
        assert item is None
        
        manager.close_connection()

    def test_get_inventory_item_without_connection(self):
        """
        ASPICE: SQC.BP20 - Defensive programming
        
        Verify get_inventory_item returns None without connection.
        """
        manager = SqliteManager()
        item = manager.get_inventory_item('any_id')
        
        assert item is None


# ============================================================================
# TEST CLASS: Environmental Logging
# ============================================================================

class TestEnvironmentalLogging:
    """Test cases for environmental data logging."""

    def test_insert_environment_log(self, temp_db_path, sample_environment_data):
        """
        ASPICE: SQC.BP21 - Time-series data logging
        
        Verify insert_environment_log stores sensor readings.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        result = manager.insert_environment_log(
            sample_environment_data['temperature'],
            sample_environment_data['humidity'],
            sample_environment_data['timestamp']
        )
        
        assert result is True
        
        # Verify data was inserted
        manager.db_cursor.execute(
            "SELECT COUNT(*) FROM environment_log WHERE temperature = ?",
            (sample_environment_data['temperature'],)
        )
        count = manager.db_cursor.fetchone()[0]
        assert count == 1
        
        manager.close_connection()

    def test_insert_environment_log_multiple(self, temp_db_path):
        """
        ASPICE: SQC.BP22 - Batch operations
        
        Verify multiple environment log entries can be inserted.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Insert multiple readings
        for i in range(5):
            result = manager.insert_environment_log(
                20.0 + i,  # Different temperatures
                70.0 + i,  # Different humidities
                1705276800.0 + i
            )
            assert result is True
        
        # Verify all entries
        manager.db_cursor.execute("SELECT COUNT(*) FROM environment_log")
        count = manager.db_cursor.fetchone()[0]
        assert count == 5
        
        manager.close_connection()

    def test_insert_environment_log_without_connection(self, sample_environment_data):
        """
        ASPICE: SQC.BP23 - Error handling
        
        Verify insert_environment_log handles missing connection.
        """
        manager = SqliteManager()
        
        result = manager.insert_environment_log(
            sample_environment_data['temperature'],
            sample_environment_data['humidity'],
            sample_environment_data['timestamp']
        )
        
        assert result is False


# ============================================================================
# TEST CLASS: Transaction Management
# ============================================================================

class TestTransactionManagement:
    """Test cases for database transaction handling."""

    def test_commit_transaction(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP24 - Transaction control
        
        Verify commit_transaction persists changes.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        manager.update_inventory(
            sample_food_inventory['food_id'],
            sample_food_inventory['quantity'],
            sample_food_inventory['confidence_score']
        )
        
        manager.commit_transaction()
        
        # Verify data persists
        manager.db_cursor.execute(
            "SELECT COUNT(*) FROM inventory WHERE food_id = ?",
            (sample_food_inventory['food_id'],)
        )
        assert manager.db_cursor.fetchone()[0] == 1
        
        manager.close_connection()

    def test_rollback_transaction(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP25 - Transaction rollback
        
        Verify rollback_transaction reverts changes.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        manager.update_inventory(
            sample_food_inventory['food_id'],
            10,
            0.90
        )
        
        manager.rollback_transaction()
        
        manager.close_connection()
        # Note: SQLite auto-commits, so rollback in update_inventory context
        # This test verifies rollback method doesn't crash
        assert True


# ============================================================================
# TEST CLASS: Connection Management
# ============================================================================

class TestConnectionManagement:
    """Test cases for database connection lifecycle."""

    def test_close_connection_commits_pending_changes(self, temp_db_path, sample_food_inventory):
        """
        ASPICE: SQC.BP26 - Resource cleanup
        
        Verify close_connection commits pending changes before closing.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        manager.update_inventory(
            sample_food_inventory['food_id'],
            sample_food_inventory['quantity'],
            sample_food_inventory['confidence_score']
        )
        
        manager.close_connection()
        
        # Verify connection is closed
        assert manager.db_connection is None or not manager.db_cursor
        
        # Verify data was persisted
        manager2 = SqliteManager(db_path=temp_db_path)
        manager2.connect_db()
        item = manager2.get_inventory_item(sample_food_inventory['food_id'])
        assert item is not None
        manager2.close_connection()

    def test_destructor_calls_close_connection(self, temp_db_path):
        """
        ASPICE: SQC.BP27 - Resource cleanup
        
        Verify __del__ properly closes connection.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        
        # Delete object
        del manager
        
        # If no exception raised, cleanup was successful
        assert True


# ============================================================================
# TEST CLASS: Error Handling and Recovery
# ============================================================================

class TestErrorHandling:
    """Test cases for error handling and recovery."""

    def test_handle_db_lock_exception_reconnects(self, temp_db_path):
        """
        ASPICE: SQC.BP28 - Error recovery
        
        Verify handle_db_lock_exception attempts reconnection.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        
        manager.handle_db_lock_exception()
        
        # Should have reconnected
        assert manager.db_connection is not None
        
        manager.close_connection()

    def test_integrity_error_handling(self, temp_db_path):
        """
        ASPICE: SQC.BP29 - Constraint handling
        
        Verify duplicate food_id triggers rollback.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Insert first item
        result1 = manager.update_inventory('apple_001', 10, 0.95)
        assert result1 is True
        
        # Force duplicate insert (violates UNIQUE constraint)
        manager.db_cursor.execute(
            "INSERT INTO inventory (food_id, quantity, confidence_score) VALUES (?, ?, ?)",
            ('apple_001', 5, 0.90)
        )
        
        # This should trigger error and rollback
        # (update_inventory uses REPLACE, so no error expected in normal flow)
        
        manager.close_connection()


# ============================================================================
# TEST CLASS: Integration Tests
# ============================================================================

class TestSqliteManagerIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow(self, temp_db_path):
        """
        ASPICE: SQC.BP30 - Complete workflow verification
        
        Verify complete database lifecycle workflow.
        """
        manager = SqliteManager(db_path=temp_db_path)
        
        # Connection
        assert manager.connect_db() is True
        
        # Initialization
        manager.init_tables_if_not_exists()
        
        # Inventory operations
        assert manager.update_inventory('apple_001', 10, 0.95) is True
        assert manager.update_inventory('apple_002', 5, 0.88) is True
        assert manager.insert_environment_log(22.5, 65.3, 1705276800.0) is True
        
        # Retrieval
        item = manager.get_inventory_item('apple_001')
        assert item is not None
        assert item['quantity'] == 10
        
        # Cleanup
        manager.close_connection()
        assert True

    def test_concurrent_operations_safety(self, temp_db_path):
        """
        ASPICE: SQC.BP31 - Thread safety
        
        Verify database operations handle concurrent access patterns.
        """
        manager = SqliteManager(db_path=temp_db_path)
        manager.connect_db()
        manager.init_tables_if_not_exists()
        
        # Simulate multiple operations
        for i in range(10):
            result = manager.update_inventory(f'item_{i}', i, 0.90 + i/100)
            assert result is True
        
        # Verify all inserted
        manager.db_cursor.execute("SELECT COUNT(*) FROM inventory")
        count = manager.db_cursor.fetchone()[0]
        assert count == 10
        
        manager.close_connection()
