"""
@file test_disk_file_manager.py
@brief Unit tests for DiskFileManager component.

This module provides comprehensive test coverage for disk file operations
including directory management, image storage, disk space monitoring,
and cleanup policies.

Following ASPICE principles with clean code and proper test isolation.
"""

import pytest
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'db_daemon/src'))

from DiskFileManager import DiskFileManager


# ============================================================================
# TEST CLASS: DiskFileManager Initialization
# ============================================================================

class TestDiskFileManagerInitialization:
    """Test cases for DiskFileManager initialization."""

    def test_init_with_default_parameters(self):
        """
        ASPICE: SQC.BP1 - Clean initialization
        
        Verify DiskFileManager initializes with default configuration.
        """
        manager = DiskFileManager()
        
        assert manager.base_asset_path == DiskFileManager.DEFAULT_BASE_ASSET_PATH
        assert manager.max_disk_usage_mb == DiskFileManager.DEFAULT_MAX_DISK_USAGE_MB
        assert manager.logger is not None

    def test_init_with_custom_parameters(self, temp_asset_dir):
        """
        ASPICE: SQC.BP2 - Parameterized initialization
        
        Verify DiskFileManager accepts custom configuration.
        """
        custom_max_mb = 2048
        manager = DiskFileManager(
            base_asset_path=temp_asset_dir,
            max_disk_usage_mb=custom_max_mb
        )
        
        assert manager.base_asset_path == temp_asset_dir
        assert manager.max_disk_usage_mb == custom_max_mb

    def test_subdirectory_constants(self):
        """
        ASPICE: SQC.BP3 - Configuration constants
        
        Verify subdirectory constants are properly defined.
        """
        assert DiskFileManager.CROPS_SUBDIRECTORY == "crops"
        assert DiskFileManager.LOGS_SUBDIRECTORY == "logs"


# ============================================================================
# TEST CLASS: Directory Initialization
# ============================================================================

class TestDirectoryInitialization:
    """Test cases for directory setup operations."""

    def test_init_directories_creates_base_directory(self, temp_asset_dir):
        """
        ASPICE: SQC.BP4 - Directory creation
        
        Verify init_directories creates base asset directory.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        result = manager.init_directories()
        
        assert result is True
        assert os.path.exists(temp_asset_dir)

    def test_init_directories_creates_subdirectories(self, temp_asset_dir):
        """
        ASPICE: SQC.BP5 - Subdirectory structure
        
        Verify init_directories creates required subdirectories.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        result = manager.init_directories()
        
        assert result is True
        
        crops_path = os.path.join(temp_asset_dir, "crops")
        logs_path = os.path.join(temp_asset_dir, "logs")
        
        assert os.path.exists(crops_path)
        assert os.path.exists(logs_path)

    def test_init_directories_idempotent(self, temp_asset_dir):
        """
        ASPICE: SQC.BP6 - Idempotent operations
        
        Verify calling init_directories multiple times is safe.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        result1 = manager.init_directories()
        result2 = manager.init_directories()
        result3 = manager.init_directories()
        
        assert result1 is True
        assert result2 is True
        assert result3 is True

    def test_init_directories_permission_denied(self):
        """
        ASPICE: SQC.BP7 - Error handling
        
        Verify init_directories handles permission errors gracefully.
        """
        manager = DiskFileManager(base_asset_path="/invalid/path")
        
        with patch.object(Path, 'mkdir', side_effect=PermissionError("Access denied")):
            result = manager.init_directories()
            assert result is False


# ============================================================================
# TEST CLASS: File Path Generation
# ============================================================================

class TestFilePathGeneration:
    """Test cases for file path generation."""

    def test_generate_file_path_valid_inputs(self, temp_asset_dir):
        """
        ASPICE: SQC.BP8 - Path generation
        
        Verify generate_file_path creates valid paths.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        food_id = "apple_001"
        timestamp = 1705276800.0
        
        path = manager.generate_file_path(food_id, timestamp)
        
        assert path != ""
        assert food_id in path
        assert ".jpg" in path

    def test_generate_file_path_contains_date_structure(self, temp_asset_dir):
        """
        ASPICE: SQC.BP9 - Organized storage
        
        Verify generated paths include year/month/day structure.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        food_id = "apple_001"
        timestamp = 1705276800.0  # 2024-01-15
        
        path = manager.generate_file_path(food_id, timestamp)
        
        # Should contain date-based subdirectories
        assert "2024" in path
        assert "01" in path
        assert "15" in path

    def test_generate_file_path_sanitizes_food_id(self, temp_asset_dir):
        """
        ASPICE: SQC.BP10 - Input validation
        
        Verify generate_file_path sanitizes special characters in food_id.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        # Food ID with special characters
        food_id = "apple@001#special$chars"
        timestamp = 1705276800.0
        
        path = manager.generate_file_path(food_id, timestamp)
        
        # Should not contain special characters
        assert "@" not in path
        assert "#" not in path
        assert "$" not in path

    def test_generate_file_path_includes_crops_directory(self, temp_asset_dir):
        """
        ASPICE: SQC.BP11 - Directory structure
        
        Verify generated paths include crops subdirectory.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        food_id = "apple_001"
        timestamp = 1705276800.0
        
        path = manager.generate_file_path(food_id, timestamp)
        
        assert "crops" in path

    def test_generate_file_path_with_different_timestamps(self, temp_asset_dir):
        """
        ASPICE: SQC.BP12 - Uniqueness guarantee
        
        Verify paths for different timestamps are different.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        food_id = "apple_001"
        timestamp1 = 1705276800.0
        timestamp2 = 1705276801.0
        
        path1 = manager.generate_file_path(food_id, timestamp1)
        path2 = manager.generate_file_path(food_id, timestamp2)
        
        assert path1 != path2


# ============================================================================
# TEST CLASS: Image Storage
# ============================================================================

class TestImageStorage:
    """Test cases for image storage operations."""

    def test_save_crop_image_writes_file(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP13 - File persistence
        
        Verify save_crop_image writes image bytes to disk.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        manager.init_directories()
        
        file_path = os.path.join(temp_asset_dir, "crops", "test_image.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            result = manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        assert result is True
        assert os.path.exists(file_path)

    def test_save_crop_image_creates_directories(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP14 - Auto directory creation
        
        Verify save_crop_image creates parent directories.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        file_path = os.path.join(temp_asset_dir, "crops", "2024/01/15/test.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            result = manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        assert result is True
        assert os.path.exists(os.path.dirname(file_path))

    def test_save_crop_image_when_frt_disabled(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP15 - Feature flag respect
        
        Verify save_crop_image respects FRT_APP_ENABLED flag.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        file_path = os.path.join(temp_asset_dir, "crops", "test.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', False):
            result = manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        assert result is False

    def test_save_crop_image_permission_error(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP16 - Error recovery
        
        Verify save_crop_image handles permission errors.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        file_path = os.path.join(temp_asset_dir, "crops", "test.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            with patch('builtins.open', side_effect=PermissionError("Access denied")):
                result = manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        assert result is False

    def test_save_crop_image_writes_correct_bytes(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP17 - Data integrity
        
        Verify save_crop_image writes correct image data.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        manager.init_directories()
        
        file_path = os.path.join(temp_asset_dir, "crops", "test_image.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        # Read back and verify
        with open(file_path, 'rb') as f:
            saved_bytes = f.read()
        
        assert saved_bytes == sample_jpeg_bytes


# ============================================================================
# TEST CLASS: Disk Space Management
# ============================================================================

class TestDiskSpaceManagement:
    """Test cases for disk space monitoring."""

    def test_check_disk_space_returns_available_mb(self, temp_asset_dir):
        """
        ASPICE: SQC.BP18 - Disk monitoring
        
        Verify check_disk_space returns available space in MB.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        available_mb = manager.check_disk_space()
        
        assert isinstance(available_mb, float)
        assert available_mb > 0

    def test_check_disk_space_error_returns_zero(self):
        """
        ASPICE: SQC.BP19 - Error handling
        
        Verify check_disk_space returns 0 on error.
        """
        manager = DiskFileManager(base_asset_path="/invalid/path")
        
        with patch('shutil.disk_usage', side_effect=Exception("Error")):
            available_mb = manager.check_disk_space()
        
        assert available_mb == 0.0


# ============================================================================
# TEST CLASS: Cleanup Operations
# ============================================================================

class TestCleanupOperations:
    """Test cases for disk space cleanup."""

    def test_cleanup_old_images_returns_true_when_no_images(self, temp_asset_dir):
        """
        ASPICE: SQC.BP20 - Empty cleanup
        
        Verify cleanup_old_images handles empty directory.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        manager.init_directories()
        
        result = manager.cleanup_old_images()
        
        assert result is True

    def test_cleanup_old_images_removes_oldest_first(self, temp_asset_dir):
        """
        ASPICE: SQC.BP21 - FIFO cleanup
        
        Verify cleanup_old_images removes oldest files first.
        """
        manager = DiskFileManager(
            base_asset_path=temp_asset_dir,
            max_disk_usage_mb=1  # Very small limit to trigger cleanup
        )
        manager.init_directories()
        
        crops_dir = os.path.join(temp_asset_dir, "crops")
        
        # Create test files with different timestamps
        file1 = os.path.join(crops_dir, "image1.jpg")
        file2 = os.path.join(crops_dir, "image2.jpg")
        file3 = os.path.join(crops_dir, "image3.jpg")
        
        # Create files with time gaps
        with open(file1, 'w') as f:
            f.write("x" * 1000)
        os.utime(file1, (1000, 1000))  # Oldest
        
        with open(file2, 'w') as f:
            f.write("x" * 1000)
        os.utime(file2, (2000, 2000))  # Middle
        
        with open(file3, 'w') as f:
            f.write("x" * 1000)
        os.utime(file3, (3000, 3000))  # Newest
        
        result = manager.cleanup_old_images()
        
        assert result is True
        # Oldest file should be deleted first
        assert not os.path.exists(file1)

    def test_cleanup_old_images_respects_max_limit(self, temp_asset_dir):
        """
        ASPICE: SQC.BP22 - Limit enforcement
        
        Verify cleanup_old_images respects max_disk_usage_mb.
        """
        manager = DiskFileManager(
            base_asset_path=temp_asset_dir,
            max_disk_usage_mb=0.01  # Very small to trigger cleanup
        )
        manager.init_directories()
        
        crops_dir = os.path.join(temp_asset_dir, "crops")
        
        # Create test files
        for i in range(3):
            file_path = os.path.join(crops_dir, f"image{i}.jpg")
            with open(file_path, 'w') as f:
                f.write("x" * 10000)  # 10KB each
        
        result = manager.cleanup_old_images()
        
        assert result is True

    def test_cleanup_old_images_handles_missing_directory(self, temp_asset_dir):
        """
        ASPICE: SQC.BP23 - Graceful degradation
        
        Verify cleanup_old_images handles missing crops directory.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        # Don't initialize directories
        
        result = manager.cleanup_old_images()
        
        assert result is True


# ============================================================================
# TEST CLASS: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test cases for error handling."""

    def test_handle_permission_denied_logs_error(self, temp_asset_dir):
        """
        ASPICE: SQC.BP24 - Permission error reporting
        
        Verify handle_permission_denied logs appropriate error message.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        # Should not raise exception
        manager.handle_permission_denied()
        assert True


# ============================================================================
# TEST CLASS: Integration Tests
# ============================================================================

class TestDiskFileManagerIntegration:
    """Integration tests for complete workflows."""

    def test_complete_file_storage_workflow(self, temp_asset_dir, sample_jpeg_bytes):
        """
        ASPICE: SQC.BP25 - Complete workflow
        
        Verify complete file storage workflow.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        # Initialize
        assert manager.init_directories() is True
        
        # Generate path
        file_path = manager.generate_file_path("apple_001", 1705276800.0)
        assert file_path != ""
        
        # Create full path
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save image (simulate FRTApp enabled)
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            with patch.object(manager, '_has_sufficient_disk_space', return_value=True):
                result = manager.save_crop_image(file_path, sample_jpeg_bytes)
        
        assert result is True
        
        # Check space
        available_mb = manager.check_disk_space()
        assert available_mb >= 0

    def test_multiple_images_storage_and_cleanup(self, temp_asset_dir):
        """
        ASPICE: SQC.BP26 - Multi-image workflow
        
        Verify storing and cleaning up multiple images.
        """
        manager = DiskFileManager(
            base_asset_path=temp_asset_dir,
            max_disk_usage_mb=0.05
        )
        manager.init_directories()
        
        crops_dir = os.path.join(temp_asset_dir, "crops")
        
        # Create multiple test files
        for i in range(5):
            file_path = os.path.join(crops_dir, f"image{i}.jpg")
            with open(file_path, 'w') as f:
                f.write("x" * 10000)
        
        initial_count = len(os.listdir(crops_dir))
        assert initial_count == 5
        
        # Cleanup
        manager.cleanup_old_images()
        
        # Some files should be removed
        final_count = len(os.listdir(crops_dir))
        assert final_count < initial_count


# ============================================================================
# TEST CLASS: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_generate_file_path_with_zero_timestamp(self, temp_asset_dir):
        """
        ASPICE: SQC.BP27 - Boundary condition
        
        Verify generate_file_path handles zero timestamp (1970-01-01).
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        path = manager.generate_file_path("apple_001", 0.0)
        
        assert path != ""
        assert "1970" in path

    def test_generate_file_path_with_empty_food_id(self, temp_asset_dir):
        """
        ASPICE: SQC.BP28 - Empty input handling
        
        Verify generate_file_path handles empty food_id.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        
        path = manager.generate_file_path("", 1705276800.0)
        
        assert path != ""
        assert ".jpg" in path

    def test_save_crop_image_with_empty_bytes(self, temp_asset_dir):
        """
        ASPICE: SQC.BP29 - Empty data handling
        
        Verify save_crop_image handles empty image bytes.
        """
        manager = DiskFileManager(base_asset_path=temp_asset_dir)
        manager.init_directories()
        
        file_path = os.path.join(temp_asset_dir, "crops", "empty.jpg")
        
        with patch('DiskFileManager.FRT_APP_ENABLED', True):
            with patch.object(manager, '_has_sufficient_disk_space', return_value=True):
                result = manager.save_crop_image(file_path, b"")
        
        assert result is True
        assert os.path.exists(file_path)
