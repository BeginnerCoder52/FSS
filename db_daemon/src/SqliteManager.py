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
    DOOR_SENSOR_TABLE_NAME = "door_sensor_log"
    DISTANCE_SENSOR_TABLE_NAME = "distance_sensor_log"
    PRESENCE_SENSOR_TABLE_NAME = "presence_sensor_log"
    
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
            # check_same_thread=False is required for multi-threaded access
            self.db_connection = sqlite3.connect(
                self.db_path,
                timeout=self.transaction_timeout_ms / 1000.0,  # Convert ms to seconds
                check_same_thread=False
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
        
        Creates the inventory and environmental log tables with proper schema,
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
            
            # Create environment log table (Sensor 1)
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.ENVIRONMENT_LOG_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    temperature_2 REAL,
                    humidity_2 REAL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on timestamp for time-based queries
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_env_log_timestamp 
                ON {self.ENVIRONMENT_LOG_TABLE_NAME}(timestamp)
            """)
            
            # Create door sensor log table
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.DOOR_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_state TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on door timestamp
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_door_log_timestamp 
                ON {self.DOOR_SENSOR_TABLE_NAME}(timestamp)
            """)
            
            # Create distance sensor log table
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.DISTANCE_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    distance REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on distance timestamp
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_distance_log_timestamp 
                ON {self.DISTANCE_SENSOR_TABLE_NAME}(timestamp)
            """)

            # Create presence sensor log table
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.PRESENCE_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detected INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on presence timestamp
            self.db_cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_presence_log_timestamp 
                ON {self.PRESENCE_SENSOR_TABLE_NAME}(timestamp)
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
                               timestamp: float, temperature_2: Optional[float] = None,
                               humidity_2: Optional[float] = None) -> bool:
        """
        Log environmental sensor readings to database (dual-sensor support).
        
        Records temperature and humidity measurements from primary sensor (SHT31-1)
        and optional secondary sensor (SHT31-2) along with their acquisition
        timestamp for time-series analysis and monitoring.
        
        Args:
            temperature: Temperature reading in Celsius (Sensor 1)
            humidity: Humidity reading in percentage (Sensor 1)
            timestamp: Unix timestamp when measurement was taken (from SensorDaemon)
            temperature_2: Optional temperature from secondary sensor (Sensor 2)
            humidity_2: Optional humidity from secondary sensor (Sensor 2)
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            self.db_cursor.execute(f"""
                INSERT INTO {self.ENVIRONMENT_LOG_TABLE_NAME}
                (temperature, humidity, temperature_2, humidity_2, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (temperature, humidity, temperature_2, humidity_2, timestamp))
            
            self.db_connection.commit()
            log_msg = f"Logged environment: S1_T={temperature}°C, S1_H={humidity}%"
            if temperature_2 is not None and humidity_2 is not None:
                log_msg += f", S2_T={temperature_2}°C, S2_H={humidity_2}%"
            log_msg += f", ts={timestamp}"
            self.logger.debug(log_msg)
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting environment log: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting environment log: {e}")
            self.db_connection.rollback()
            return False
    
    def insert_door_sensor_log(self, door_state: str, timestamp: float) -> bool:
        """
        Log door sensor state changes to database.
        
        Records door state (DOOR_OPEN / DOOR_CLOSE) and its acquisition timestamp
        for tracking fridge access patterns.
        
        Args:
            door_state: Door state string ("DOOR_OPEN" or "DOOR_CLOSE")
            timestamp: Unix timestamp when state was detected
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            # Validate door state
            if door_state not in ["DOOR_OPEN", "DOOR_CLOSE"]:
                self.logger.warning(f"Invalid door state: {door_state}")
                return False
            
            self.db_cursor.execute(f"""
                INSERT INTO {self.DOOR_SENSOR_TABLE_NAME}
                (door_state, timestamp)
                VALUES (?, ?)
            """, (door_state, timestamp))
            
            self.db_connection.commit()
            self.logger.debug(f"Logged door state: {door_state}, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting door log: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting door log: {e}")
            self.db_connection.rollback()
            return False
    
    def insert_distance_sensor_log(self, distance: float, timestamp: float) -> bool:
        """
        Log distance sensor readings to database.
        
        Records distance measurement (in cm) from ToF sensor and its acquisition
        timestamp for tracking refrigerator contents proximity.
        
        Args:
            distance: Distance reading in centimeters
            timestamp: Unix timestamp when measurement was taken
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            # Validate distance value
            if distance < 0:
                self.logger.warning(f"Invalid distance value: {distance}")
                return False
            
            self.db_cursor.execute(f"""
                INSERT INTO {self.DISTANCE_SENSOR_TABLE_NAME}
                (distance, timestamp)
                VALUES (?, ?)
            """, (distance, timestamp))
            
            self.db_connection.commit()
            self.logger.debug(f"Logged distance: {distance}cm, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting distance log: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting distance log: {e}")
            self.db_connection.rollback()
            return False
    
    def insert_presence_sensor_log(self, detected: bool, timestamp: float) -> bool:
        """
        Log presence sensor detection events to database.
        
        Records user detection status (True/False) and its acquisition timestamp.
        
        Args:
            detected: Boolean presence detection status
            timestamp: Unix timestamp when state was detected
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self.db_connection or not self.db_cursor:
            self.logger.error("Database connection not established")
            return False
        
        try:
            self.db_cursor.execute(f"""
                INSERT INTO {self.PRESENCE_SENSOR_TABLE_NAME}
                (detected, timestamp)
                VALUES (?, ?)
            """, (1 if detected else 0, timestamp))
            
            self.db_connection.commit()
            self.logger.debug(f"Logged presence: {detected}, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting presence log: {e}")
            self.handle_db_lock_exception()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting presence log: {e}")
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
                # Check if connection is still open before committing
                try:
                    self.db_connection.commit()
                except (sqlite3.ProgrammingError, sqlite3.Error):
                    # Connection might already be closed or in invalid state
                    pass
                
                self.db_connection.close()
                self.db_connection = None
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
