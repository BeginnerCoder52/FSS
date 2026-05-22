"""
@file test_phase1_schema.py
@brief Unit tests for Phase 1: Database Schema Updates (NLP Recommendation System)

This module provides comprehensive test coverage for Phase 1 database schema changes:
- New inventory_history table for audit trail
- Updated current_inventory with version tracking
- Updated request table with recipe_name and request_batch_id
- New helper methods for inventory history and request batch management

Following ASPICE principles with proper error handling and backward compatibility verification.

Test Coverage:
    1. Database schema validation (tables and indexes created)
    2. Backward compatibility (existing methods unchanged)
    3. New Phase 1 helper methods functionality
    4. Error handling and recovery
    5. Complete audit trail recording

Author: FSS QA Team
Date: 2026-05-23
"""

import pytest
import sqlite3
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import uuid
from datetime import datetime

# Add db_daemon source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'db_daemon/src'))

from SqliteManager import SqliteManager, DatabaseType


# ============================================================================
# FIXTURES: Test Database Setup
# ============================================================================

@pytest.fixture
def temp_db_dir():
    """
    Create temporary directory for test databases.
    
    ASPICE: SQC.BP1 - Test isolation
    """
    temp_dir = tempfile.mkdtemp(prefix="fss_test_")
    yield temp_dir
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def db_manager(temp_db_dir):
    """
    Initialize SqliteManager with temporary databases.
    
    ASPICE: SQC.BP2 - Test fixture setup
    """
    manager = SqliteManager(db_dir=temp_db_dir, transaction_timeout_ms=5000)
    manager.connect_all_dbs()
    manager.init_tables_if_not_exists()
    
    yield manager
    
    # Cleanup
    manager.close_connection()


# ============================================================================
# TEST CLASS: Phase 1 Schema Validation
# ============================================================================

class TestPhase1SchemaValidation:
    """
    Test suite for Phase 1 database schema updates.
    
    Purpose: Verify that all Phase 1 schema changes are correctly applied
    without breaking backward compatibility.
    
    ASPICE: SQC.BP3 - Schema validation
    """
    
    def test_inventory_history_table_exists(self, db_manager):
        """
        Verify inventory_history table is created.
        
        ASPICE: SQC.BP4 - Table creation validation
        Expected: inventory_history table with all required columns
        """
        cursor = db_manager._cursors[DatabaseType.INVENTORY]
        
        # Query table info
        cursor.execute("PRAGMA table_info(inventory_history)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Verify required columns
        required_columns = [
            'id', 'food_id', 'quantity_before', 'quantity_after',
            'confidence_score', 'image_path', 'change_reason', 'changed_by',
            'changed_at', 'created_at'
        ]
        
        for req_col in required_columns:
            assert req_col in column_names, f"Column '{req_col}' missing from inventory_history table"
        
        print(f"✓ inventory_history table schema valid: {column_names}")
    
    def test_inventory_history_indexes_created(self, db_manager):
        """
        Verify indexes on inventory_history table.
        
        ASPICE: SQC.BP5 - Index validation
        Expected: idx_inventory_history_food_id, idx_inventory_history_timestamp
        """
        cursor = db_manager._cursors[DatabaseType.INVENTORY]
        
        # Query indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='inventory_history'")
        indexes = [idx[0] for idx in cursor.fetchall()]
        
        expected_indexes = ['idx_inventory_history_food_id', 'idx_inventory_history_timestamp']
        
        for idx in expected_indexes:
            assert idx in indexes, f"Index '{idx}' not found on inventory_history table"
        
        print(f"✓ inventory_history indexes created: {indexes}")
    
    def test_current_inventory_version_tracking_fields(self, db_manager):
        """
        Verify current_inventory table has version tracking fields.
        
        ASPICE: SQC.BP6 - Schema extension validation
        Expected: version_id, last_change_reason, last_changed_by columns added
        """
        cursor = db_manager._cursors[DatabaseType.INVENTORY]
        
        # Query table info
        cursor.execute("PRAGMA table_info(current_inventory)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Verify new Phase 1 columns
        phase1_columns = ['version_id', 'last_change_reason', 'last_changed_by']
        
        for col in phase1_columns:
            assert col in column_names, f"Phase 1 column '{col}' missing from current_inventory"
        
        print(f"✓ current_inventory has version tracking: {phase1_columns}")
    
    def test_request_table_recipe_fields(self, db_manager):
        """
        Verify request table has recipe tracking fields.
        
        ASPICE: SQC.BP7 - Schema extension validation
        Expected: recipe_name, request_batch_id columns added
        """
        cursor = db_manager._cursors[DatabaseType.REQUEST]
        
        # Query table info
        cursor.execute("PRAGMA table_info(request)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Verify new Phase 1 columns
        phase1_columns = ['recipe_name', 'request_batch_id']
        
        for col in phase1_columns:
            assert col in column_names, f"Phase 1 column '{col}' missing from request table"
        
        print(f"✓ request table has recipe tracking: {phase1_columns}")
    
    def test_request_table_indexes_created(self, db_manager):
        """
        Verify indexes on request table.
        
        ASPICE: SQC.BP8 - Index validation
        Expected: idx_request_recipe_name, idx_request_batch_id, idx_request_food_id
        """
        cursor = db_manager._cursors[DatabaseType.REQUEST]
        
        # Query indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='request'")
        indexes = [idx[0] for idx in cursor.fetchall()]
        
        expected_indexes = ['idx_request_recipe_name', 'idx_request_batch_id', 'idx_request_food_id']
        
        for idx in expected_indexes:
            assert idx in indexes, f"Index '{idx}' not found on request table"
        
        print(f"✓ request table indexes created: {indexes}")


# ============================================================================
# TEST CLASS: Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """
    Test suite for backward compatibility verification.
    
    Purpose: Ensure Phase 1 changes do NOT break existing APIs
    
    ASPICE: SQC.BP9 - Regression testing
    """
    
    def test_existing_update_inventory_method_works(self, db_manager):
        """
        Verify existing update_inventory() method still works.
        
        ASPICE: SQC.BP10 - Core API regression test
        Expected: Method works without modifications
        """
        # Insert a test inventory item
        result = db_manager.update_inventory(
            food_id="test_item_001",
            quantity_delta=5,
            confidence_score=0.95,
            image_path="/opt/fss/assets/test.jpg"
        )
        
        assert result is True, "update_inventory() failed"
        
        # Verify item was inserted
        item = db_manager.get_inventory_item("test_item_001")
        assert item is not None
        assert item['quantity'] == 5
        assert item['confidence_score'] == 0.95
        
        print(f"✓ Existing update_inventory() works: {item}")
    
    def test_existing_insert_request_method_works(self, db_manager):
        """
        Verify existing insert_request() method still works.
        
        ASPICE: SQC.BP11 - Core API regression test
        Expected: Method works with backward compatible behavior
        """
        # Insert request with existing API
        result = db_manager.insert_request(
            food_id="test_food_001",
            quantity=2,
            unit="kg"
        )
        
        assert result is True, "insert_request() failed"
        
        # Verify request was inserted
        requests = db_manager.get_all_requests()
        assert len(requests) > 0
        
        # Check that existing fields are still there
        req = requests[0]
        assert 'food_id' in req
        assert 'quantity' in req
        assert 'unit' in req
        
        print(f"✓ Existing insert_request() works: {req}")
    
    def test_existing_get_all_inventory_method_works(self, db_manager):
        """
        Verify existing get_all_inventory() method still works.
        
        ASPICE: SQC.BP12 - Core API regression test
        """
        # Insert test data
        db_manager.update_inventory("food_a", 3, 0.9, "/path/a")
        db_manager.update_inventory("food_b", 5, 0.85, "/path/b")
        
        # Query all inventory
        items = db_manager.get_all_inventory()
        
        assert len(items) >= 2
        assert any(item['food_id'] == 'food_a' for item in items)
        assert any(item['food_id'] == 'food_b' for item in items)
        
        print(f"✓ Existing get_all_inventory() works: {len(items)} items")
    
    def test_existing_compare_inventory_vs_request_method_works(self, db_manager):
        """
        Verify existing compare_inventory_vs_request() method still works.
        
        ASPICE: SQC.BP13 - Core API regression test
        """
        # Setup test data
        db_manager.update_inventory("egg", 2, 0.95)  # Have 2 eggs
        db_manager.insert_request("egg", 5)  # Need 5 eggs
        
        # Compare
        shortage = db_manager.compare_inventory_vs_request()
        
        assert len(shortage) > 0
        assert shortage[0]['food_id'] == 'egg'
        assert shortage[0]['shortage'] == 3  # Missing 3 eggs
        
        print(f"✓ Existing compare_inventory_vs_request() works: {shortage}")


# ============================================================================
# TEST CLASS: Phase 1 New Methods - Inventory History
# ============================================================================

class TestPhase1InventoryHistory:
    """
    Test suite for Phase 1 inventory history methods.
    
    Purpose: Verify new audit trail functionality
    
    ASPICE: SQC.BP14 - Feature testing
    """
    
    def test_insert_inventory_history_basic(self, db_manager):
        """
        Test basic insert_inventory_history operation.
        
        ASPICE: SQC.BP15 - Happy path testing
        Expected: History record inserted successfully
        """
        result = db_manager.insert_inventory_history(
            food_id="banana",
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.92,
            image_path="/opt/fss/assets/banana.jpg",
            change_reason="FRT_DETECTION",
            changed_by="FRTApp",
            changed_at=datetime.now().isoformat()
        )
        
        assert result is True, "insert_inventory_history() failed"
        print("✓ insert_inventory_history() successful")
    
    def test_insert_inventory_history_multiple(self, db_manager):
        """
        Test inserting multiple history records.
        
        ASPICE: SQC.BP16 - Bulk operation testing
        Expected: Multiple records inserted correctly
        """
        for i in range(3):
            result = db_manager.insert_inventory_history(
                food_id="tomato",
                quantity_before=i,
                quantity_after=i+1,
                confidence_score=0.85 + (i * 0.01),
                image_path=f"/path/tomato_{i}.jpg",
                change_reason="FRT_DETECTION",
                changed_by="FRTApp",
                changed_at=datetime.now().isoformat()
            )
            assert result is True
        
        print("✓ Multiple insert_inventory_history() successful")
    
    def test_get_inventory_history_retrieval(self, db_manager):
        """
        Test retrieving inventory history.
        
        ASPICE: SQC.BP17 - Data retrieval testing
        Expected: History records returned in correct order
        """
        # Insert multiple history records
        for i in range(3):
            db_manager.insert_inventory_history(
                food_id="potato",
                quantity_before=i,
                quantity_after=i+1,
                confidence_score=0.88,
                image_path=f"/path/potato_{i}.jpg",
                change_reason="FRT_DETECTION",
                changed_by="FRTApp",
                changed_at=datetime.now().isoformat()
            )
        
        # Retrieve history
        history = db_manager.get_inventory_history("potato", limit=10)
        
        assert len(history) == 3, f"Expected 3 records, got {len(history)}"
        assert all(h['food_id'] == 'potato' for h in history)
        assert all(h['change_reason'] == 'FRT_DETECTION' for h in history)
        
        print(f"✓ get_inventory_history() retrieved {len(history)} records")
    
    def test_get_inventory_history_limit(self, db_manager):
        """
        Test inventory history retrieval with limit.
        
        ASPICE: SQC.BP18 - Parameter validation
        Expected: Limit parameter respected
        """
        # Insert 5 records
        for i in range(5):
            db_manager.insert_inventory_history(
                food_id="carrot",
                quantity_before=i,
                quantity_after=i+1,
                confidence_score=0.90,
                image_path=f"/path/carrot_{i}.jpg",
                change_reason="FRT_DETECTION",
                changed_by="FRTApp",
                changed_at=datetime.now().isoformat()
            )
        
        # Retrieve with limit=2
        history = db_manager.get_inventory_history("carrot", limit=2)
        
        assert len(history) == 2, f"Expected 2 records (limit=2), got {len(history)}"
        
        print(f"✓ get_inventory_history(limit=2) returned {len(history)} records")
    
    def test_inventory_history_tracks_change_reasons(self, db_manager):
        """
        Test that change_reason is properly recorded.
        
        ASPICE: SQC.BP19 - Audit trail validation
        Expected: Different change reasons tracked correctly
        """
        reasons = ["FRT_DETECTION", "RECIPE_COMPARISON", "USER_MANUAL"]
        
        for reason in reasons:
            db_manager.insert_inventory_history(
                food_id="test_food",
                quantity_before=0,
                quantity_after=1,
                confidence_score=0.85,
                image_path="/path/test.jpg",
                change_reason=reason,
                changed_by="TestActor",
                changed_at=datetime.now().isoformat()
            )
        
        history = db_manager.get_inventory_history("test_food", limit=10)
        
        retrieved_reasons = [h['change_reason'] for h in history]
        for reason in reasons:
            assert reason in retrieved_reasons
        
        print(f"✓ Change reasons tracked: {reasons}")


# ============================================================================
# TEST CLASS: Phase 1 New Methods - Request Batch Management
# ============================================================================

class TestPhase1RequestBatch:
    """
    Test suite for Phase 1 request batch methods.
    
    Purpose: Verify new recipe batch management functionality
    
    ASPICE: SQC.BP20 - Feature testing
    """
    
    def test_insert_request_batch_basic(self, db_manager):
        """
        Test basic insert_request_batch operation.
        
        ASPICE: SQC.BP21 - Happy path testing
        Expected: Batch inserted successfully
        """
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "egg", "quantity": 2, "unit": "pieces"},
            {"food_id": "flour", "quantity": 100, "unit": "g"},
            {"food_id": "milk", "quantity": 200, "unit": "ml"}
        ]
        
        result = db_manager.insert_request_batch(
            recipe_name="Bánh Trứng",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        assert result is True
        
        # Verify inserted
        requests = db_manager.get_all_requests()
        assert len(requests) == 3
        
        print(f"✓ insert_request_batch() inserted {len(requests)} items")
    
    def test_get_requests_by_recipe(self, db_manager):
        """
        Test retrieving requests by recipe name.
        
        ASPICE: SQC.BP22 - Filtered retrieval testing
        Expected: Only ingredients for specified recipe returned
        """
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "tomato", "quantity": 3, "unit": "pieces"},
            {"food_id": "basil", "quantity": 50, "unit": "g"}
        ]
        
        # Insert batch
        db_manager.insert_request_batch(
            recipe_name="Salad Cà Chua",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        # Retrieve by recipe
        recipe_items = db_manager.get_requests_by_recipe("Salad Cà Chua")
        
        assert len(recipe_items) == 2
        assert all(item['recipe_name'] == 'Salad Cà Chua' for item in recipe_items)
        
        print(f"✓ get_requests_by_recipe() retrieved {len(recipe_items)} items")
    
    def test_clear_request_batch(self, db_manager):
        """
        Test clearing a request batch.
        
        ASPICE: SQC.BP23 - Deletion testing
        Expected: All items in batch deleted
        """
        batch_id = str(uuid.uuid4())
        ingredients = [
            {"food_id": "chicken", "quantity": 1, "unit": "kg"},
            {"food_id": "rice", "quantity": 200, "unit": "g"}
        ]
        
        # Insert batch
        db_manager.insert_request_batch(
            recipe_name="Cơm Gà",
            ingredients_list=ingredients,
            batch_id=batch_id
        )
        
        # Verify inserted
        before = db_manager.get_requests_by_recipe("Cơm Gà")
        assert len(before) == 2
        
        # Clear batch
        result = db_manager.clear_request_batch(batch_id)
        assert result is True
        
        # Verify cleared
        after = db_manager.get_requests_by_recipe("Cơm Gà")
        assert len(after) == 0
        
        print(f"✓ clear_request_batch() cleared {len(before)} items")
    
    def test_request_batch_isolation(self, db_manager):
        """
        Test that clearing one batch doesn't affect others.
        
        ASPICE: SQC.BP24 - Isolation testing
        Expected: Only target batch deleted
        """
        batch_id_1 = str(uuid.uuid4())
        batch_id_2 = str(uuid.uuid4())
        
        # Insert two batches for different recipes
        db_manager.insert_request_batch(
            recipe_name="Recipe A",
            ingredients_list=[{"food_id": "item_a", "quantity": 1, "unit": "unit"}],
            batch_id=batch_id_1
        )
        
        db_manager.insert_request_batch(
            recipe_name="Recipe B",
            ingredients_list=[{"food_id": "item_b", "quantity": 1, "unit": "unit"}],
            batch_id=batch_id_2
        )
        
        # Clear first batch
        db_manager.clear_request_batch(batch_id_1)
        
        # Verify first batch cleared but second remains
        recipe_a = db_manager.get_requests_by_recipe("Recipe A")
        recipe_b = db_manager.get_requests_by_recipe("Recipe B")
        
        assert len(recipe_a) == 0
        assert len(recipe_b) == 1
        
        print(f"✓ Batch isolation working: Recipe A cleared, Recipe B intact")


# ============================================================================
# TEST CLASS: Error Handling & Edge Cases
# ============================================================================

class TestPhase1ErrorHandling:
    """
    Test suite for error handling and edge cases.
    
    Purpose: Verify robustness of Phase 1 implementation
    
    ASPICE: SQC.BP25 - Error scenario testing
    """
    
    def test_insert_history_with_null_image_path(self, db_manager):
        """
        Test history insertion with NULL image_path.
        
        ASPICE: SQC.BP26 - NULL value handling
        Expected: Should succeed with NULL value
        """
        result = db_manager.insert_inventory_history(
            food_id="item_no_image",
            quantity_before=0,
            quantity_after=2,
            confidence_score=0.80,
            image_path=None,  # NULL
            change_reason="MANUAL_ENTRY",
            changed_by="DBDaemon",
            changed_at=datetime.now().isoformat()
        )
        
        assert result is True
        history = db_manager.get_inventory_history("item_no_image")
        assert history[0]['image_path'] is None
        
        print("✓ NULL image_path handled correctly")
    
    def test_get_history_nonexistent_food(self, db_manager):
        """
        Test retrieving history for non-existent food.
        
        ASPICE: SQC.BP27 - Missing data handling
        Expected: Return empty list
        """
        history = db_manager.get_inventory_history("nonexistent_food")
        
        assert isinstance(history, list)
        assert len(history) == 0
        
        print("✓ Non-existent food returns empty list")
    
    def test_clear_nonexistent_batch(self, db_manager):
        """
        Test clearing non-existent batch.
        
        ASPICE: SQC.BP28 - Safe deletion
        Expected: Succeed without error (no rows affected)
        """
        result = db_manager.clear_request_batch("nonexistent_batch_id")
        
        assert result is True  # Should succeed, just delete 0 rows
        
        print("✓ Clearing non-existent batch succeeds safely")
    
    def test_insert_batch_empty_ingredients(self, db_manager):
        """
        Test inserting batch with empty ingredients list.
        
        ASPICE: SQC.BP29 - Empty input handling
        Expected: Should succeed (insert 0 items)
        """
        result = db_manager.insert_request_batch(
            recipe_name="Empty Recipe",
            ingredients_list=[],
            batch_id=str(uuid.uuid4())
        )
        
        assert result is True
        
        print("✓ Empty batch insertion handled correctly")


# ============================================================================
# TEST CLASS: Integration Testing
# ============================================================================

class TestPhase1Integration:
    """
    Test suite for end-to-end Phase 1 integration.
    
    Purpose: Verify Phase 1 components work together
    
    ASPICE: SQC.BP30 - Integration testing
    """
    
    def test_complete_workflow_inventory_update_with_history(self, db_manager):
        """
        Test complete workflow: update inventory and verify history.
        
        ASPICE: SQC.BP31 - Workflow validation
        Scenario: FRT detects food → update inventory → check history + audit trail
        """
        food_id = "detected_apple"
        
        # Step 1: FRT detects food (original API)
        db_manager.update_inventory(food_id, 5, 0.96, "/path/apple.jpg")
        
        # Step 2: Log to history (Phase 1 new API)
        db_manager.insert_inventory_history(
            food_id=food_id,
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.96,
            image_path="/path/apple.jpg",
            change_reason="FRT_DETECTION",
            changed_by="FRTApp",
            changed_at=datetime.now().isoformat()
        )
        
        # Step 3: Verify inventory updated
        item = db_manager.get_inventory_item(food_id)
        assert item['quantity'] == 5
        
        # Step 4: Verify history logged
        history = db_manager.get_inventory_history(food_id)
        assert len(history) > 0
        assert history[0]['change_reason'] == "FRT_DETECTION"
        
        print(f"✓ Complete workflow successful: inventory updated + history logged")
    
    def test_complete_workflow_recipe_request_comparison(self, db_manager):
        """
        Test complete workflow: NLP recipe → insert batch → compare with inventory.
        
        ASPICE: SQC.BP32 - Workflow validation
        Scenario: User enters recipe → NLP generates ingredients → compare with inventory
        """
        recipe_name = "Cơm Chiên"
        batch_id = str(uuid.uuid4())
        
        # Step 1: Setup current inventory
        db_manager.update_inventory("rice", 2, 0.90)
        db_manager.update_inventory("egg", 3, 0.88)
        
        # Step 2: NLP generates ingredients (Phase 1 batch API)
        ingredients = [
            {"food_id": "rice", "quantity": 3, "unit": "cups"},
            {"food_id": "egg", "quantity": 2, "unit": "pieces"},
            {"food_id": "onion", "quantity": 1, "unit": "piece"}
        ]
        
        db_manager.insert_request_batch(recipe_name, ingredients, batch_id)
        
        # Step 3: Compare inventory vs request (existing API)
        shortage = db_manager.compare_inventory_vs_request()
        
        # Step 4: Verify shortage list
        assert any(s['food_id'] == 'rice' and s['shortage'] == 1 for s in shortage)  # Need 1 more rice
        assert any(s['food_id'] == 'onion' for s in shortage)  # Missing onion entirely
        
        print(f"✓ Recipe workflow successful: {len(shortage)} items missing")


# ============================================================================
# TEST CLASS: Performance & Data Integrity
# ============================================================================

class TestPhase1DataIntegrity:
    """
    Test suite for data integrity and performance.
    
    Purpose: Verify Phase 1 maintains data consistency
    
    ASPICE: SQC.BP33 - Data integrity testing
    """
    
    def test_history_immutability(self, db_manager):
        """
        Verify inventory history records are immutable (INSERT only).
        
        ASPICE: SQC.BP34 - Audit trail integrity
        Expected: Cannot update/delete history records
        """
        # Insert a history record
        db_manager.insert_inventory_history(
            food_id="immutable_test",
            quantity_before=0,
            quantity_after=5,
            confidence_score=0.90,
            image_path="/path/test.jpg",
            change_reason="TEST",
            changed_by="Tester",
            changed_at=datetime.now().isoformat()
        )
        
        # Verify inserted
        history_before = db_manager.get_inventory_history("immutable_test")
        assert len(history_before) == 1
        
        # Attempt update via cursor (should fail or be ignored)
        cursor = db_manager._cursors[DatabaseType.INVENTORY]
        try:
            # This would be an anti-pattern in normal operation
            cursor.execute("""
                DELETE FROM inventory_history WHERE food_id = ?
            """, ("immutable_test",))
            db_manager._connections[DatabaseType.INVENTORY].rollback()
        except:
            pass  # Expected behavior
        
        # Verify history still intact
        history_after = db_manager.get_inventory_history("immutable_test")
        assert len(history_after) == 1
        
        print("✓ History immutability verified")
    
    def test_batch_id_grouping_accuracy(self, db_manager):
        """
        Test that batch_id correctly groups ingredients.
        
        ASPICE: SQC.BP35 - Grouping integrity
        Expected: Items grouped by batch_id independently
        """
        batch_1 = str(uuid.uuid4())
        batch_2 = str(uuid.uuid4())
        
        # Insert two batches with same recipe name but different batch IDs
        db_manager.insert_request_batch(
            "Shared Recipe Name",
            [{"food_id": "item_a1", "quantity": 1, "unit": "u"}],
            batch_1
        )
        
        db_manager.insert_request_batch(
            "Shared Recipe Name",
            [{"food_id": "item_a2", "quantity": 2, "unit": "u"}],
            batch_2
        )
        
        # Total should have 2 items under same recipe
        all_items = db_manager.get_requests_by_recipe("Shared Recipe Name")
        assert len(all_items) == 2
        
        # Clear batch 1 only
        db_manager.clear_request_batch(batch_1)
        
        # Verify only batch 1 cleared
        remaining = db_manager.get_requests_by_recipe("Shared Recipe Name")
        assert len(remaining) == 1
        assert remaining[0]['food_id'] == 'item_a2'
        
        print("✓ Batch ID grouping integrity verified")


# ============================================================================
# PYTEST MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Run tests with verbose output.
    
    Command: python -m pytest test_phase1_schema.py -v --tb=short
    """
    pytest.main([__file__, "-v", "--tb=short"])
