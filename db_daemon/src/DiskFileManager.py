"""
@file DiskFileManager.py
@brief Manages disk file operations for storing food images and assets.

This module handles filesystem operations including directory management,
image file persistence, disk space monitoring, and cleanup policies.
Includes feature flag for FRTApp integration.

FEATURE FLAG: FRT_APP_ENABLED
Full image processing features will be enabled after FRTApp implementation.
"""

import logging
import os
import shutil
from typing import Optional, List
from pathlib import Path
from datetime import datetime

# Import shared feature flag
from PosixShmReader import FRT_APP_ENABLED


class DiskFileManager:
    """
    Manages disk file operations for FSS data persistence.
    
    Handles directory creation, image file storage, disk space monitoring,
    and cleanup policies to maintain disk usage within acceptable limits.
    """

    # File system configuration constants
    DEFAULT_BASE_ASSET_PATH = "/opt/fss/assets"
    DEFAULT_MAX_DISK_USAGE_MB = 1024  # 1GB maximum storage
    
    # Subdirectories
    CROPS_SUBDIRECTORY = "crops"
    LOGS_SUBDIRECTORY = "logs"
    
    def __init__(self, base_asset_path: str = DEFAULT_BASE_ASSET_PATH,
                 max_disk_usage_mb: int = DEFAULT_MAX_DISK_USAGE_MB):
        """
        Initialize DiskFileManager instance.
        
        Args:
            base_asset_path: Root directory for asset storage
            max_disk_usage_mb: Maximum disk usage in megabytes
        """
        self.base_asset_path: str = base_asset_path
        self.max_disk_usage_mb: int = max_disk_usage_mb
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Initialized DiskFileManager with base_path={base_asset_path}, "
                         f"max_usage={max_disk_usage_mb}MB")
    
    def init_directories(self) -> bool:
        """
        Initialize directory structure for asset storage.
        
        Creates the base asset directory and required subdirectories
        for organizing crops and logs.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            base_path = Path(self.base_asset_path)
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            (base_path / self.CROPS_SUBDIRECTORY).mkdir(exist_ok=True)
            (base_path / self.LOGS_SUBDIRECTORY).mkdir(exist_ok=True)
            
            self.logger.info(f"Directory structure initialized: {self.base_asset_path}")
            return True
            
        except PermissionError as e:
            self.logger.error(f"Permission denied creating directories: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to initialize directories: {e}")
            return False
    
    def generate_file_path(self, food_id: str, timestamp: float) -> str:
        """
        Generate a unique file path for crop image storage.
        
        Creates a filesystem path based on food ID and timestamp with
        proper directory structure for organization.
        
        Args:
            food_id: Unique identifier for the food item
            timestamp: Unix timestamp of when image was captured
        
        Returns:
            Complete file path for the image
        """
        try:
            # Convert timestamp to readable date-based directory structure
            dt = datetime.fromtimestamp(timestamp)
            date_dir = dt.strftime("%Y/%m/%d")
            
            # Create full path with safe filename
            safe_food_id = "".join(c for c in food_id if c.isalnum() or c in ('-', '_'))
            filename = f"{safe_food_id}_{int(timestamp * 1000)}.jpg"
            
            full_path = os.path.join(
                self.base_asset_path,
                self.CROPS_SUBDIRECTORY,
                date_dir,
                filename
            )
            
            self.logger.debug(f"Generated file path: {full_path}")
            return full_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate file path: {e}")
            return ""
    
    def save_crop_image(self, file_path: str, image_bytes: bytes) -> bool:
        """
        Save JPEG image bytes to disk.
        
        Writes JPEG frame data from FRTApp to persistent storage with
        proper directory creation and error handling.
        
        Args:
            file_path: Target file path for image storage
            image_bytes: JPEG frame data as bytes
        
        Returns:
            True if save successful, False otherwise
        """
        if not FRT_APP_ENABLED:
            self.logger.warning("Cannot save crop image: FRTApp integration disabled")
            return False
        
        try:
            # Create parent directories if needed
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Check disk space before writing
            if not self._has_sufficient_disk_space(len(image_bytes)):
                self.logger.warning("Insufficient disk space for image storage")
                if not self.cleanup_old_images():
                    return False
            
            # Write image bytes to file
            with open(file_path, 'wb') as f:
                f.write(image_bytes)
            
            self.logger.debug(f"Saved crop image: {file_path} ({len(image_bytes)} bytes)")
            return True
            
        except PermissionError as e:
            self.handle_permission_denied()
            return False
        except IOError as e:
            self.logger.error(f"IO error saving image: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to save crop image: {e}")
            return False
    
    def check_disk_space(self) -> float:
        """
        Check available disk space on the storage partition.
        
        Returns:
            Available disk space in megabytes
        """
        try:
            stat = shutil.disk_usage(self.base_asset_path)
            available_mb = stat.free / (1024 * 1024)
            
            self.logger.debug(f"Available disk space: {available_mb:.1f}MB")
            return available_mb
            
        except Exception as e:
            self.logger.error(f"Failed to check disk space: {e}")
            return 0.0
    
    def cleanup_old_images(self) -> bool:
        """
        Remove oldest images to maintain disk usage within limits.
        
        Implements FIFO (First In First Out) cleanup policy by removing
        the oldest image files when disk usage exceeds the maximum limit.
        
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            crops_dir = Path(self.base_asset_path) / self.CROPS_SUBDIRECTORY
            
            if not crops_dir.exists():
                return True
            
            # Get all image files sorted by modification time
            image_files = sorted(
                crops_dir.glob("**/*.jpg"),
                key=lambda p: p.stat().st_mtime
            )
            
            if not image_files:
                self.logger.debug("No image files to cleanup")
                return True
            
            # Calculate current disk usage
            total_size_mb = sum(f.stat().st_size for f in image_files) / (1024 * 1024)
            
            # Remove files until we're under the limit
            removed_count = 0
            for image_file in image_files:
                if total_size_mb <= self.max_disk_usage_mb:
                    break
                
                try:
                    file_size_mb = image_file.stat().st_size / (1024 * 1024)
                    image_file.unlink()
                    total_size_mb -= file_size_mb
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete {image_file}: {e}")
            
            if removed_count > 0:
                self.logger.info(f"Cleanup: Removed {removed_count} old images")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return False
    
    def handle_permission_denied(self) -> None:
        """
        Handle permission denied errors for filesystem operations.
        
        Reports filesystem permission issues that prevent file operations.
        These typically indicate misconfigured directory permissions on the
        Linux system.
        """
        error_msg = (f"Permission denied accessing {self.base_asset_path}. "
                    "Verify ownership and permissions: "
                    "ls -la /opt/fss/assets")
        self.logger.error(error_msg)
    
    def _has_sufficient_disk_space(self, required_bytes: int) -> bool:
        """
        Check if sufficient disk space exists for operation.
        
        Args:
            required_bytes: Number of bytes needed
        
        Returns:
            True if space available, False otherwise
        """
        try:
            stat = shutil.disk_usage(self.base_asset_path)
            return stat.free >= required_bytes
        except Exception:
            return False
    
    def get_total_storage_used(self) -> float:
        """
        Calculate total disk space used by FSS assets.
        
        Returns:
            Total size in megabytes
        """
        try:
            total_size = 0
            for path in Path(self.base_asset_path).rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size
            
            return total_size / (1024 * 1024)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate storage usage: {e}")
            return 0.0
