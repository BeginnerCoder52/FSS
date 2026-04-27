"""
@file SqliteManager.py
@brief Manages SQLite database operations for the Fridge Supervisor System.

This module provides database connection management, table creation, inventory
updates, and environmental data logging with transaction support and error handling.
Following ASPICE principles with comprehensive error handling and logging.
"""

import sqlite3
import logging
import os
import time
from typing import Optional, Tuple, Dict, Any
from pathlib import Path


class SqliteManager:
    """
    Manages SQLite database operations for FSS data persistence.
    
    Handles database initialization, inventory management, environmental logging,
    and transaction management with proper error handling and locking mechanisms.
    """

    # Default configuration constants
    DEFAULT_DB_PATH = "/opt/fss/data/fss_data.db"
    DEFAULT_TRANSACTION_TIMEOUT_MS = 5000
    INVENTORY_TABLE_NAME = "inventory"
    ENVIRONMENT_LOG_TABLE_NAME = "environment_log"
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH, 
                 transaction_timeout_ms: int = DEFAULT_TRANSACTION_TIMEOUT_MS):
        """
        Initialize SqliteManager instance.
        
        Args:
            db_path: Path to SQLite database file
            transaction_timeout_ms: Timeout for database lock acquisition (milliseconds)
        """
        self.db_path: str = db_path
        self.db_connection: Optional[sqlite3.Connection] = None
        self.db_cursor: Optional[sqlite3.Cursor] = None
        self.transaction_timeout_ms: int = transaction_timeout_ms
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Initialized SqliteManager with db_path={db_path}, "
                         f"timeout={transaction_timeout_ms}ms")
    
    def connect_db(self) -> bool:
        """
        Open database connection and configure settings.
        
        Establishes connection to SQLite database, enables WAL mode for concurrent
        access, and sets the transaction timeout.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create database directory if it doesn't exist
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.db_connection = sqlite3.connect(
                self.db_path,
                timeout=self.transaction_timeout_ms / 1000.0  # Convert ms to seconds
            )
            self.db_cursor = self.db_connection.cursor()
            
            # Enable WAL (Write-Ahead Logging) mode for better concurrency
            self.db_cursor.execute("PRAGMA journal_mode=WAL")
            
            # Enable foreign keys
            self.db_cursor.execute("PRAGMA foreign_keys=ON")
            
            self.logger.info(f"Successfully connected to database: {self.db_path}")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during database connection: {e}")
            return False
    
    def init_tables_if_not_exists(self) -> None:
        """
        Create database tables if they don't already exist.
        
        Creates the inventory and environment_log tables with proper schema,
        indexes, and constraints to support FSS operations.
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return
        
        try:
            # Create inventory table
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.INVENTORY_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_id TEXT NOT NULL UNIQUE,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0.0,
                    image_path TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on food_id for faster lookups
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_inventory_food_id 
                ON {self.INVENTORY_TABLE_NAME}(food_id)
            """)
            
            # Create environment log table
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.ENVIRONMENT_LOG_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on timestamp for time-based queries
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_env_log_timestamp 
                ON {self.ENVIRONMENT_LOG_TABLE_NAME}(timestamp)
            """)
            
            self.db_connection.commit()
            self.logger.info("Database tables initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize tables: {e}")
            self.db_connection.rollback()
        except Exception as e:
            self.logger.error(f"Unexpected error during table initialization: {e}")
    
    def update_inventory(self, food_id: str, quantity: int, 
                        confidence_score: float, image_path: Optional[str] = None) -> bool:
        """
        Update or insert inventory record for a food item.
        
        Args:
            food_id: Unique identifier for the food item
            quantity: Updated quantity of the item
            confidence_score: AI model confidence score (0.0 - 1.0)
            image_path: Optional path to the food item image
        
        Returns:
            True if update successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            # Use INSERT OR REPLACE (UPSERT) pattern
            self.db_cursor.execute(f"""
                INSERT OR REPLACE INTO {self.INVENTORY_TABLE_NAME}
                (food_id, quantity, confidence_score, image_path, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (food_id, quantity, confidence_score, image_path))
            
            self.db_connection.commit()
            self.logger.debug(f"Updated inventory: food_id={food_id}, qty={quantity}, "
                            f"score={confidence_score:.2f}")
            return True
            
        except sqlite3.IntegrityError as e:
            self.logger.error(f"Integrity error updating inventory: {e}")
            self.db_connection.rollback()
            return False
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error updating inventory: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating inventory: {e}")
            self.db_connection.rollback()
            return False
    
    def insert_environment_log(self, temperature: float, humidity: float, 
                               timestamp: float) -> bool:
        """
        Log environmental sensor readings to database.
        
        Records temperature and humidity measurements along with their acquisition
        timestamp for time-series analysis and monitoring.
        
        Args:
            temperature: Temperature reading in Celsius
            humidity: Humidity reading in percentage
            timestamp: Unix timestamp when measurement was taken (from SensorDaemon)
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            self.db_cursor.execute(f"""
                INSERT INTO {self.ENVIRONMENT_LOG_TABLE_NAME}
                (temperature, humidity, timestamp)
                VALUES (?, ?, ?)
            """, (temperature, humidity, timestamp))
            
            self.db_connection.commit()
            self.logger.debug(f"Logged environment data: temp={temperature}°C, "
                            f"humid={humidity}%, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting environment log: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting environment log: {e}")
            self.db_connection.rollback()
            return False
    
    def commit_transaction(self) -> None:
        """
        Commit pending database changes to persistent storage.
        
        Finalizes all pending insert/update/delete operations to ensure
        data persistence on disk.
        """
        try:
            if self.db_connection:
                self.db_connection.commit()
                self.logger.debug("Database transaction committed")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to commit transaction: {e}")
    
    def rollback_transaction(self) -> None:
        """
        Rollback pending database changes.
        
        Cancels all pending insert/update/delete operations since the last
        commit to maintain data consistency.
        """
        try:
            if self.db_connection:
                self.db_connection.rollback()
                self.logger.warning("Database transaction rolled back")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to rollback transaction: {e}")
    
    def handle_db_lock_exception(self) -> None:
        """
        Handle database lock errors.
        
        Implements recovery strategy for "database is locked" errors by
        attempting to reconnect and retry. This handles cases where another
        process holds an exclusive lock.
        """
        self.logger.warning("Database lock detected, attempting recovery...")
        
        try:
            # Attempt to close current connection
            if self.db_connection:
                self.db_connection.close()
                self.db_connection = None
                self.db_cursor = None
            
            # Brief delay before reconnection
            time.sleep(0.5)
            
            # Attempt to reconnect
            if self.connect_db():
                self.logger.info("Successfully recovered from database lock")
            else:
                self.logger.error("Failed to recover from database lock")
                
        except Exception as e:
            self.logger.error(f"Error during lock recovery: {e}")
    
    def close_connection(self) -> None:
        """
        Close database connection and cleanup resources.
        
        Commits any pending transactions and closes the database connection
        to ensure proper resource cleanup.
        """
        try:
            if self.db_connection:
                self.db_connection.commit()
                self.db_connection.close()
                self.db_cursor = None
                self.logger.info("Database connection closed successfully")
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database connection: {e}")
    
    def get_inventory_item(self, food_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve inventory item by food ID.
        
        Args:
            food_id: Unique identifier for the food item
        
        Returns:
            Dictionary with item data or None if not found
        """
        if not self.db_cursor:
            return None
        
        try:
            self.db_cursor.execute(f"""
                SELECT food_id, quantity, confidence_score, image_path, last_updated
                FROM {self.INVENTORY_TABLE_NAME}
                WHERE food_id = ?
            """, (food_id,))
            
            row = self.db_cursor.fetchone()
            if row:
                return {
                    'food_id': row[0],
                    'quantity': row[1],
                    'confidence_score': row[2],
                    'image_path': row[3],
                    'last_updated': row[4]
                }
            return None
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving inventory item: {e}")
            return None
    
    def __del__(self):
        """Cleanup resources on object destruction."""
        self.close_connection()
