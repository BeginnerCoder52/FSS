"""
@file SqliteManager.py
@brief Manages SQLite database operations for the Fridge Supervisor System.

This module provides database connection management, table creation, inventory
updates, and environmental data logging with transaction support and error handling.
Supports multiple databases: fss_data.db (sensors), FSS_Inventory.db (food), 
and FSS_Request.db (recipe requests).
Following ASPICE principles with comprehensive error handling and logging.
"""

import sqlite3
import logging
import os
import time
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from enum import Enum


class DatabaseType(Enum):
    """Enumeration of database types for multi-database support."""
    SENSORS = "sensors"
    INVENTORY = "inventory"
    REQUEST = "request"


class SqliteManager:
    """
    Manages SQLite database operations for FSS data persistence.
    
    Handles database initialization, inventory management, environmental logging,
    and transaction management with proper error handling and locking mechanisms.
    Supports multiple databases for modular data separation.
    """

    # Default configuration constants
    DEFAULT_DB_DIR = "/opt/fss/data"
    DEFAULT_TRANSACTION_TIMEOUT_MS = 5000
    
    # Database file names
    SENSORS_DB_NAME = "fss_data.db"
    INVENTORY_DB_NAME = "FSS_Inventory.db"
    REQUEST_DB_NAME = "FSS_Request.db"
    
    # Flag for recommend_system folder usage (future stage)
    # This flag indicates if the databases should be located in the recommend_system directory
    USE_RECOMMEND_SYSTEM_FOLDER = False
    
    # Table names for sensors database
    ENVIRONMENT_LOG_TABLE_NAME = "environment_log"
    DOOR_SENSOR_TABLE_NAME = "door_sensor_log"
    DISTANCE_SENSOR_TABLE_NAME = "distance_sensor_log"
    PRESENCE_SENSOR_TABLE_NAME = "presence_sensor_log"
    
    # Table names for inventory database
    INVENTORY_TABLE_NAME = "current_inventory"
    INVENTORY_HISTORY_TABLE_NAME = "inventory_history"
    CUSTOM_FOOD_LABELS_TABLE_NAME = "custom_food_labels"
    
    # Table names for request database
    REQUEST_TABLE_NAME = "request"
    RECOMMENDATION_CACHE_TABLE_NAME = "recommendation_cache"

    def __init__(self, db_dir: str = DEFAULT_DB_DIR, 
                 transaction_timeout_ms: int = DEFAULT_TRANSACTION_TIMEOUT_MS):
        """
        Initialize SqliteManager instance.
        
        Args:
            db_dir: Directory path for all database files
            transaction_timeout_ms: Timeout for database lock acquisition (milliseconds)
        """
        self.db_dir: str = db_dir
        self.transaction_timeout_ms: int = transaction_timeout_ms
        
        # Database connections - one per database type
        self._connections: Dict[DatabaseType, Optional[sqlite3.Connection]] = {
            DatabaseType.SENSORS: None,
            DatabaseType.INVENTORY: None,
            DatabaseType.REQUEST: None,
        }
        self._cursors: Dict[DatabaseType, Optional[sqlite3.Cursor]] = {
            DatabaseType.SENSORS: None,
            DatabaseType.INVENTORY: None,
            DatabaseType.REQUEST: None,
        }
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Initialized SqliteManager with db_dir={db_dir}, "
                         f"timeout={transaction_timeout_ms}ms")
    
    def connect_all_dbs(self) -> bool:
        """
        Connect to all three databases (sensors, inventory, request).
        
        Establishes connections to all SQLite databases, enables WAL mode for 
        concurrent access, and sets the transaction timeout.
        
        Returns:
            True if all connections successful, False otherwise
        """
        try:
            # Create database directory if it doesn't exist
            db_dir_path = Path(self.db_dir)
            db_dir_path.mkdir(parents=True, exist_ok=True)
            
            # Connect to all three databases
            success = True
            for db_type in [DatabaseType.SENSORS, DatabaseType.INVENTORY, DatabaseType.REQUEST]:
                if not self.connect_db(db_type):
                    success = False
            
            if success:
                self.logger.info("Successfully connected to all databases")
            return success
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to databases: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during database connection: {e}")
            return False
    
    def connect_db(self, db_type: DatabaseType = DatabaseType.SENSORS) -> bool:
        """
        Open database connection and configure settings.
        
        Establishes connection to SQLite database, enables WAL mode for concurrent
        access, and sets the transaction timeout.
        
        Args:
            db_type: Type of database to connect to (sensors, inventory, or request)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Determine database path based on type
            if db_type == DatabaseType.SENSORS:
                db_path = os.path.join(self.db_dir, self.SENSORS_DB_NAME)
            elif db_type == DatabaseType.INVENTORY:
                db_path = os.path.join(self.db_dir, self.INVENTORY_DB_NAME)
            elif db_type == DatabaseType.REQUEST:
                db_path = os.path.join(self.db_dir, self.REQUEST_DB_NAME)
            else:
                self.logger.error(f"Unknown database type: {db_type}")
                return False
            
            # Create database directory if it doesn't exist
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            # check_same_thread=False is required for multi-threaded access
            connection = sqlite3.connect(
                db_path,
                timeout=self.transaction_timeout_ms / 1000.0,  # Convert ms to seconds
                check_same_thread=False
            )
            cursor = connection.cursor()
            
            # Enable WAL (Write-Ahead Logging) mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys=ON")
            
            self._connections[db_type] = connection
            self._cursors[db_type] = cursor
            
            self.logger.info(f"Successfully connected to {db_type.value} database: {db_path}")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to {db_type.value} database: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during database connection: {e}")
            return False
    
    def init_tables_if_not_exists(self) -> None:
        """
        Create database tables if they don't already exist.
        
        Creates the inventory, request, and environmental log tables with proper schema,
        indexes, and constraints to support FSS operations.
        """
        try:
            # Create tables for sensors database (fss_data.db)
            self._init_sensors_tables()
            
            # Create tables for inventory database (FSS_Inventory.db)
            self._init_inventory_tables()
            
            # Create tables for request database (FSS_Request.db)
            self._init_request_tables()
            
            self.logger.info("All database tables initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize tables: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during table initialization: {e}")
    
    def _init_sensors_tables(self) -> None:
        """Create tables for the sensors database."""
        if not self._connections[DatabaseType.SENSORS] or not self._cursors[DatabaseType.SENSORS]:
            self.logger.error("Sensors database connection not established")
            return
        
        cursor = self._cursors[DatabaseType.SENSORS]
        connection = self._connections[DatabaseType.SENSORS]
        
        try:
            # Create environment log table (Sensor 1)
            cursor.execute(f"""
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
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_env_log_timestamp 
                ON {self.ENVIRONMENT_LOG_TABLE_NAME}(timestamp)
            """)
            
            # Create door sensor log table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.DOOR_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_state TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on door timestamp
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_door_log_timestamp 
                ON {self.DOOR_SENSOR_TABLE_NAME}(timestamp)
            """)
            
            # Create distance sensor log table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.DISTANCE_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    distance REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on distance timestamp
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_distance_log_timestamp 
                ON {self.DISTANCE_SENSOR_TABLE_NAME}(timestamp)
            """)
            
            # Create presence sensor log table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.PRESENCE_SENSOR_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detected INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on presence timestamp
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_presence_log_timestamp 
                ON {self.PRESENCE_SENSOR_TABLE_NAME}(timestamp)
            """)
            
            connection.commit()
            self.logger.info("Sensors tables initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize sensors tables: {e}")
            connection.rollback()
    
    def _init_inventory_tables(self) -> None:
        """Create tables for the inventory database."""
        if not self._connections[DatabaseType.INVENTORY] or not self._cursors[DatabaseType.INVENTORY]:
            self.logger.error("Inventory database connection not established")
            return
        
        cursor = self._cursors[DatabaseType.INVENTORY]
        connection = self._connections[DatabaseType.INVENTORY]
        
        try:
            # Create inventory table for food items from YOLO
            # Phase 1 Update: Added version_id, last_change_reason, last_changed_by for audit tracking
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.INVENTORY_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_id TEXT NOT NULL UNIQUE,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0.0,
                    image_path TEXT,
                    version_id INTEGER NOT NULL DEFAULT 1,
                    last_change_reason TEXT DEFAULT 'INITIAL',
                    last_changed_by TEXT DEFAULT 'SYSTEM',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on food_id for faster lookups
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_inventory_food_id 
                ON {self.INVENTORY_TABLE_NAME}(food_id)
            """)
            
            # Create inventory history table for complete audit trail (Phase 1: NLP Recommendation System)
            # Purpose: Track all inventory changes for compliance, analytics, and undo functionality
            # Schema: Records before/after state, reason, actor, and timestamp for each change
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.INVENTORY_HISTORY_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_id TEXT NOT NULL,
                    quantity_before INTEGER NOT NULL,
                    quantity_after INTEGER NOT NULL,
                    confidence_score REAL NOT NULL,
                    image_path TEXT,
                    change_reason TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    changed_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on food_id for quick history lookups by food item
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_inventory_history_food_id 
                ON {self.INVENTORY_HISTORY_TABLE_NAME}(food_id)
            """)
            
            # Create index on changed_at for time-series queries
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_inventory_history_timestamp 
                ON {self.INVENTORY_HISTORY_TABLE_NAME}(changed_at)
            """)
            
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.CUSTOM_FOOD_LABELS_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_label TEXT NOT NULL,
                    image_path TEXT,
                    feature_hash TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_seen_at TEXT DEFAULT (datetime('now'))
                )
            """)

            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_custom_food_labels_label
                ON {self.CUSTOM_FOOD_LABELS_TABLE_NAME}(user_label)
            """)

            connection.commit()
            self.logger.info("Inventory tables initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize inventory tables: {e}")
            connection.rollback()
    
    def _init_request_tables(self) -> None:
        """Create tables for the request database."""
        if not self._connections[DatabaseType.REQUEST] or not self._cursors[DatabaseType.REQUEST]:
            self.logger.error("Request database connection not established")
            return
        
        cursor = self._cursors[DatabaseType.REQUEST]
        connection = self._connections[DatabaseType.REQUEST]
        
        try:
            # Migration: add recipe_name column if missing (older schema)
            try:
                cursor.execute(f"ALTER TABLE {self.REQUEST_TABLE_NAME} ADD COLUMN recipe_name TEXT")
            except sqlite3.OperationalError:
                pass
            # Migration: add request_batch_id column if missing (older schema)
            try:
                cursor.execute(f"ALTER TABLE {self.REQUEST_TABLE_NAME} ADD COLUMN request_batch_id TEXT")
            except sqlite3.OperationalError:
                pass

            # Create request table for NLP recipe requirements if not exists
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.REQUEST_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_name TEXT,
                    food_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    unit TEXT,
                    request_batch_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on recipe_name for quick recipe lookups
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_request_recipe_name 
                ON {self.REQUEST_TABLE_NAME}(recipe_name)
            """)
            
            # Create index on request_batch_id for batch management (undo/clear recipe)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_request_batch_id 
                ON {self.REQUEST_TABLE_NAME}(request_batch_id)
            """)
            
            # Create index on food_id for cross-reference lookups
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_request_food_id 
                ON {self.REQUEST_TABLE_NAME}(food_id)
            """)
            
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.RECOMMENDATION_CACHE_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_name TEXT NOT NULL,
                    shopping_list TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            connection.commit()
            self.logger.info("Request tables initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize request tables: {e}")
            connection.rollback()
    
    def update_inventory(self, food_id: str, quantity_delta: int, 
                        confidence_score: float, image_path: Optional[str] = None) -> bool:
        """
        Update inventory record for a food item (ADD/REMOVE logic).
        
        Increments or decrements the existing quantity. Replaces the food image
        and updates the confidence score ONLY if the new confidence_score is higher
        than the existing one.
        
        Args:
            food_id: Unique identifier for the food item
            quantity_delta: Change in quantity (+1 for ADD, -1 for REMOVE)
            confidence_score: AI model confidence score (0.0 - 1.0)
            image_path: Optional path to the new food item image
        
        Returns:
            True if update successful, False otherwise
        """
        if not self._connections[DatabaseType.INVENTORY] or not self._cursors[DatabaseType.INVENTORY]:
            self.logger.error("Inventory database connection not established")
            return False
        
        connection = self._connections[DatabaseType.INVENTORY]
        cursor = self._cursors[DatabaseType.INVENTORY]
        
        try:
            # 1. Check if item already exists
            cursor.execute(f"""
                SELECT quantity, confidence_score, image_path 
                FROM {self.INVENTORY_TABLE_NAME} 
                WHERE food_id = ?
            """, (food_id,))
            
            row = cursor.fetchone()
            
            if row:
                # Item exists, update it
                current_qty, current_score, current_image = row
                new_qty = max(0, current_qty + quantity_delta)
                
                # Check if we should update the image and score
                if confidence_score > current_score:
                    new_score = confidence_score
                    new_image = image_path if image_path else current_image
                else:
                    new_score = current_score
                    new_image = current_image
                
                cursor.execute(f"""
                    UPDATE {self.INVENTORY_TABLE_NAME}
                    SET quantity = ?, confidence_score = ?, image_path = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE food_id = ?
                """, (new_qty, new_score, new_image, food_id))
            else:
                # Item doesn't exist, insert new record
                # If quantity_delta is negative, we'll start at 0
                new_qty = max(0, quantity_delta)
                cursor.execute(f"""
                    INSERT INTO {self.INVENTORY_TABLE_NAME}
                    (food_id, quantity, confidence_score, image_path, last_updated)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (food_id, new_qty, confidence_score, image_path))
            
            connection.commit()
            self.logger.debug(f"Updated inventory: {food_id}, delta={quantity_delta}, "
                            f"new_qty={new_qty}, score={confidence_score:.2f}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error updating inventory: {e}")
            self.handle_db_lock_exception(DatabaseType.INVENTORY)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating inventory: {e}")
            connection.rollback()
            return False
    
    def insert_request(self, food_id: str, quantity: int, unit: Optional[str] = None) -> bool:
        """
        Insert a new recipe request into the request database.
        
        Args:
            food_id: Unique identifier for the food item
            quantity: Required quantity of the item
            unit: Optional unit of measurement (e.g., "g", "kg", "pieces")
        
        Returns:
            True if insertion successful, False otherwise
        """
        if not self._connections[DatabaseType.REQUEST] or not self._cursors[DatabaseType.REQUEST]:
            self.logger.error("Request database connection not established")
            return False
        
        connection = self._connections[DatabaseType.REQUEST]
        cursor = self._cursors[DatabaseType.REQUEST]
        
        try:
            cursor.execute(f"""
                INSERT INTO {self.REQUEST_TABLE_NAME}
                (food_id, quantity, unit)
                VALUES (?, ?, ?)
            """, (food_id, quantity, unit))
            
            connection.commit()
            self.logger.debug(f"Inserted request: food_id={food_id}, qty={quantity}, unit={unit}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting request: {e}")
            self.handle_db_lock_exception(DatabaseType.REQUEST)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting request: {e}")
            connection.rollback()
            return False
    
    def get_inventory_item(self, food_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve inventory item by food ID.
        
        Args:
            food_id: Unique identifier for the food item
        
        Returns:
            Dictionary with item data or None if not found
        """
        if not self._cursors[DatabaseType.INVENTORY]:
            return None
        
        try:
            self._cursors[DatabaseType.INVENTORY].execute(f"""
                SELECT food_id, quantity, confidence_score, image_path, last_updated
                FROM {self.INVENTORY_TABLE_NAME}
                WHERE food_id = ?
            """, (food_id,))
            
            row = self._cursors[DatabaseType.INVENTORY].fetchone()
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

    def get_all_inventory(self) -> list:
        """
        Retrieve all inventory items.
        
        Returns:
            List of inventory items as dictionaries
        """
        if not self._cursors[DatabaseType.INVENTORY]:
            return []
        
        try:
            self._cursors[DatabaseType.INVENTORY].execute(f"""
                SELECT food_id, quantity, confidence_score, image_path, last_updated
                FROM {self.INVENTORY_TABLE_NAME}
            """)
            
            rows = self._cursors[DatabaseType.INVENTORY].fetchall()
            return [{
                'food_id': row[0],
                'quantity': row[1],
                'confidence_score': row[2],
                'image_path': row[3],
                'last_updated': row[4]
            } for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving all inventory: {e}")
            return []

    def get_all_requests(self) -> list:
        """
        Retrieve all recipe requests.
        
        Returns:
            List of request items as dictionaries
        """
        if not self._cursors[DatabaseType.REQUEST]:
            return []
        
        try:
            self._cursors[DatabaseType.REQUEST].execute(f"""
                SELECT id, food_id, quantity, unit, created_at
                FROM {self.REQUEST_TABLE_NAME}
            """)
            
            rows = self._cursors[DatabaseType.REQUEST].fetchall()
            return [{
                'id': row[0],
                'food_id': row[1],
                'quantity': row[2],
                'unit': row[3],
                'created_at': row[4]
            } for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving all requests: {e}")
            return []
     
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
        if not self._connections[DatabaseType.SENSORS] or not self._cursors[DatabaseType.SENSORS]:
            self.logger.error("Sensors database connection not established")
            return False
        
        connection = self._connections[DatabaseType.SENSORS]
        cursor = self._cursors[DatabaseType.SENSORS]
        
        try:
            cursor.execute(f"""
                INSERT INTO {self.ENVIRONMENT_LOG_TABLE_NAME}
                (temperature, humidity, temperature_2, humidity_2, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (temperature, humidity, temperature_2, humidity_2, timestamp))
            
            connection.commit()
            log_msg = f"Logged environment: S1_T={temperature}°C, S1_H={humidity}%"
            if temperature_2 is not None and humidity_2 is not None:
                log_msg += f", S2_T={temperature_2}°C, S2_H={humidity_2}%"
            log_msg += f", ts={timestamp}"
            self.logger.debug(log_msg)
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting environment log: {e}")
            self.handle_db_lock_exception(DatabaseType.SENSORS)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting environment log: {e}")
            connection.rollback()
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
        if not self._connections[DatabaseType.SENSORS] or not self._cursors[DatabaseType.SENSORS]:
            self.logger.error("Sensors database connection not established")
            return False
        
        connection = self._connections[DatabaseType.SENSORS]
        cursor = self._cursors[DatabaseType.SENSORS]
        
        try:
            if door_state not in ["DOOR_OPEN", "DOOR_CLOSE"]:
                self.logger.warning(f"Invalid door state: {door_state}")
                return False
            
            cursor.execute(f"""
                INSERT INTO {self.DOOR_SENSOR_TABLE_NAME}
                (door_state, timestamp)
                VALUES (?, ?)
            """, (door_state, timestamp))
            
            connection.commit()
            self.logger.debug(f"Logged door state: {door_state}, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting door log: {e}")
            self.handle_db_lock_exception(DatabaseType.SENSORS)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting door log: {e}")
            connection.rollback()
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
        if not self._connections[DatabaseType.SENSORS] or not self._cursors[DatabaseType.SENSORS]:
            self.logger.error("Sensors database connection not established")
            return False
        
        connection = self._connections[DatabaseType.SENSORS]
        cursor = self._cursors[DatabaseType.SENSORS]
        
        try:
            if distance < 0:
                self.logger.warning(f"Invalid distance value: {distance}")
                return False
            
            cursor.execute(f"""
                INSERT INTO {self.DISTANCE_SENSOR_TABLE_NAME}
                (distance, timestamp)
                VALUES (?, ?)
            """, (distance, timestamp))
            
            connection.commit()
            self.logger.debug(f"Logged distance: {distance}cm, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting distance log: {e}")
            self.handle_db_lock_exception(DatabaseType.SENSORS)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting distance log: {e}")
            connection.rollback()
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
        if not self._connections[DatabaseType.SENSORS] or not self._cursors[DatabaseType.SENSORS]:
            self.logger.error("Sensors database connection not established")
            return False
        
        connection = self._connections[DatabaseType.SENSORS]
        cursor = self._cursors[DatabaseType.SENSORS]
        
        try:
            cursor.execute(f"""
                INSERT INTO {self.PRESENCE_SENSOR_TABLE_NAME}
                (detected, timestamp)
                VALUES (?, ?)
            """, (1 if detected else 0, timestamp))
            
            connection.commit()
            self.logger.debug(f"Logged presence: {detected}, ts={timestamp}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting presence log: {e}")
            self.handle_db_lock_exception(DatabaseType.SENSORS)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting presence log: {e}")
            connection.rollback()
            return False
     
    def commit_transaction(self) -> None:
        """
        Commit pending database changes to persistent storage.
        
        Finalizes all pending insert/update/delete operations across all databases
        to ensure data persistence on disk.
        """
        try:
            for db_type in [DatabaseType.SENSORS, DatabaseType.INVENTORY, DatabaseType.REQUEST]:
                if self._connections.get(db_type):
                    self._connections[db_type].commit()
            self.logger.debug("All database transactions committed")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to commit transaction: {e}")
     
    def rollback_transaction(self) -> None:
        """
        Rollback pending database changes.
        
        Cancels all pending insert/update/delete operations since the last
        commit to maintain data consistency across all databases.
        """
        try:
            for db_type in [DatabaseType.SENSORS, DatabaseType.INVENTORY, DatabaseType.REQUEST]:
                if self._connections.get(db_type):
                    self._connections[db_type].rollback()
            self.logger.warning("All database transactions rolled back")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to rollback transaction: {e}")
     
    def handle_db_lock_exception(self, db_type: DatabaseType = DatabaseType.SENSORS) -> None:
        """
        Handle database lock errors.
        
        Implements recovery strategy for "database is locked" errors by
        attempting to reconnect and retry for the specified database type.
        
        Args:
            db_type: The database type to recover (sensors, inventory, or request)
        """
        self.logger.warning(f"Database lock detected on {db_type.value}, attempting recovery...")
        
        try:
            connection = self._connections.get(db_type)
            if connection:
                connection.close()
            
            self._connections[db_type] = None
            self._cursors[db_type] = None
            
            time.sleep(0.5)
            
            if self.connect_db(db_type):
                self.logger.info(f"Successfully recovered {db_type.value} database from lock")
            else:
                self.logger.error(f"Failed to recover {db_type.value} database from lock")
                 
        except Exception as e:
            self.logger.error(f"Error during lock recovery: {e}")
     
    def close_connection(self) -> None:
        """
        Close all database connections and cleanup resources.
        
        Commits any pending transactions and closes all database connections
        (sensors, inventory, and request) to ensure proper resource cleanup.
        """
        try:
            for db_type in [DatabaseType.SENSORS, DatabaseType.INVENTORY, DatabaseType.REQUEST]:
                connection = self._connections.get(db_type)
                if connection:
                    try:
                        connection.commit()
                    except (sqlite3.ProgrammingError, sqlite3.Error):
                        pass
                    connection.close()
                    self._connections[db_type] = None
                    self._cursors[db_type] = None
            
            self.logger.info("All database connections closed successfully")
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database connection: {e}")
     
    def register_custom_food(self, user_label: str, image_path: str,
                               feature_hash: str = "") -> bool:
        """Register a user-named custom food label."""
        if not self._connections[DatabaseType.INVENTORY]:
            return False
        connection = self._connections[DatabaseType.INVENTORY]
        cursor = self._cursors[DatabaseType.INVENTORY]
        try:
            cursor.execute(f"""
                INSERT OR REPLACE INTO {self.CUSTOM_FOOD_LABELS_TABLE_NAME}
                (user_label, image_path, feature_hash, last_seen_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (user_label, image_path, feature_hash))
            connection.commit()
            self.logger.info(f"Registered custom food: {user_label}")
            return True
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error registering custom food: {e}")
            return False

    def get_all_custom_foods(self) -> list:
        """Get all registered custom food labels."""
        if not self._cursors[DatabaseType.INVENTORY]:
            return []
        try:
            self._cursors[DatabaseType.INVENTORY].execute(f"""
                SELECT id, user_label, image_path, feature_hash, created_at, last_seen_at
                FROM {self.CUSTOM_FOOD_LABELS_TABLE_NAME}
                ORDER BY last_seen_at DESC
            """)
            rows = self._cursors[DatabaseType.INVENTORY].fetchall()
            return [{
                'id': row[0],
                'user_label': row[1],
                'image_path': row[2],
                'feature_hash': row[3],
                'created_at': row[4],
                'last_seen_at': row[5]
            } for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving custom foods: {e}")
            return []

    def update_custom_food_seen(self, user_label: str) -> bool:
        """Update last_seen_at for a custom food label."""
        if not self._connections[DatabaseType.INVENTORY]:
            return False
        connection = self._connections[DatabaseType.INVENTORY]
        cursor = self._cursors[DatabaseType.INVENTORY]
        try:
            cursor.execute(f"""
                UPDATE {self.CUSTOM_FOOD_LABELS_TABLE_NAME}
                SET last_seen_at = datetime('now')
                WHERE user_label = ?
            """, (user_label,))
            connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error updating custom food seen: {e}")
            return False

    @property
    def db_connection(self) -> Optional[sqlite3.Connection]:
        """Backward-compatible property returning sensors database connection."""
        return self._connections.get(DatabaseType.SENSORS)
     
    @property
    def db_cursor(self) -> Optional[sqlite3.Cursor]:
        """Backward-compatible property returning sensors database cursor."""
        return self._cursors.get(DatabaseType.SENSORS)
     
    def compare_inventory_vs_request(self) -> list:
        """
        Compare inventory against request requirements.
        
        Returns a list of items where the inventory quantity is less than
        the requested quantity, indicating what needs to be purchased.
        
        Returns:
            List of dictionaries with food_id, inventory_qty, requested_qty, and shortage
        """
        if not self._cursors[DatabaseType.INVENTORY] or not self._cursors[DatabaseType.REQUEST]:
            return []
         
        try:
            self._cursors[DatabaseType.INVENTORY].execute(f"""
                SELECT food_id, quantity FROM {self.INVENTORY_TABLE_NAME}
            """)
            inventory_items = {row[0]: row[1] for row in self._cursors[DatabaseType.INVENTORY].fetchall()}
             
            self._cursors[DatabaseType.REQUEST].execute(f"""
                SELECT food_id, SUM(quantity) FROM {self.REQUEST_TABLE_NAME}
                GROUP BY food_id
            """)
            request_items = {row[0]: row[1] for row in self._cursors[DatabaseType.REQUEST].fetchall()}
             
            shortage_list = []
            all_food_ids = set(inventory_items.keys()) | set(request_items.keys())
             
            for food_id in all_food_ids:
                inv_qty = inventory_items.get(food_id, 0)
                req_qty = request_items.get(food_id, 0)
                 
                if inv_qty < req_qty:
                    shortage_list.append({
                        'food_id': food_id,
                        'inventory_qty': inv_qty,
                        'requested_qty': req_qty,
                        'shortage': req_qty - inv_qty
                    })
             
            return shortage_list
             
        except sqlite3.Error as e:
            self.logger.error(f"Error comparing inventory vs request: {e}")
            return []
    
    # ========================================================================
    # New Helper Methods for Phase 1: Inventory History Management
    # ========================================================================
    # Purpose: Support NLP Recommendation System audit trail and version tracking
    # IMPORTANT: These are NEW methods and do NOT modify existing core APIs
    # ========================================================================
    
    def insert_inventory_history(self, food_id: str, quantity_before: int, quantity_after: int,
                                  confidence_score: float, image_path: Optional[str],
                                  change_reason: str, changed_by: str, changed_at: str) -> bool:
        """
        Insert a record into inventory history (audit trail).
        
        Purpose:
            Track all inventory changes for compliance, analytics, version control,
            and potential rollback functionality. Supports ASPICE traceability requirements.
        
        Args:
            food_id: Unique identifier for the food item
            quantity_before: Quantity before the change
            quantity_after: Quantity after the change
            confidence_score: AI confidence score for this detection
            image_path: Path to the food item image (if updated)
            change_reason: Reason for change (e.g., "FRT_DETECTION", "RECIPE_COMPARISON", "USER_MANUAL")
            changed_by: Actor who triggered the change (e.g., "FRTApp", "DBDaemon", "ElectronApp")
            changed_at: ISO 8601 timestamp when change occurred
        
        Returns:
            True if insertion successful, False otherwise
            
        ASPICE Compliance:
            - Immutable audit log (INSERT only, no UPDATE/DELETE)
            - Complete traceability with who/what/when/why
            - Support for compliance queries and audits
        """
        if not self._connections[DatabaseType.INVENTORY] or not self._cursors[DatabaseType.INVENTORY]:
            self.logger.error("Inventory database connection not established")
            return False
        
        connection = self._connections[DatabaseType.INVENTORY]
        cursor = self._cursors[DatabaseType.INVENTORY]
        
        try:
            cursor.execute(f"""
                INSERT INTO {self.INVENTORY_HISTORY_TABLE_NAME}
                (food_id, quantity_before, quantity_after, confidence_score, image_path, change_reason, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (food_id, quantity_before, quantity_after, confidence_score, image_path,
                   change_reason, changed_by, changed_at))
            
            connection.commit()
            self.logger.debug(f"Inventory history recorded: {food_id}, delta={quantity_after-quantity_before}, "
                            f"reason={change_reason}, actor={changed_by}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting inventory history: {e}")
            self.handle_db_lock_exception(DatabaseType.INVENTORY)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting inventory history: {e}")
            connection.rollback()
            return False
    
    def get_inventory_history(self, food_id: str, limit: int = 50) -> list:
        """
        Retrieve inventory change history for a specific food item.
        
        Purpose:
            Audit trail retrieval for compliance, analytics, and user notifications.
            Shows complete history of quantity/image/confidence changes.
        
        Args:
            food_id: Unique identifier for the food item
            limit: Maximum number of history records to return (default 50)
        
        Returns:
            List of history records as dictionaries, sorted by most recent first
        """
        if not self._cursors[DatabaseType.INVENTORY]:
            return []
        
        try:
            self._cursors[DatabaseType.INVENTORY].execute(f"""
                SELECT id, food_id, quantity_before, quantity_after, confidence_score, image_path,
                       change_reason, changed_by, changed_at, created_at
                FROM {self.INVENTORY_HISTORY_TABLE_NAME}
                WHERE food_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (food_id, limit))
            
            rows = self._cursors[DatabaseType.INVENTORY].fetchall()
            return [{
                'id': row[0],
                'food_id': row[1],
                'quantity_before': row[2],
                'quantity_after': row[3],
                'confidence_score': row[4],
                'image_path': row[5],
                'change_reason': row[6],
                'changed_by': row[7],
                'changed_at': row[8],
                'created_at': row[9]
            } for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving inventory history: {e}")
            return []
    
    def insert_request_batch(self, recipe_name: str, ingredients_list: list, batch_id: str) -> bool:
        """
        Insert a batch of recipe ingredients into the request table.
        
        Purpose:
            Handle multiple ingredient insertions from NLP inference in a single operation.
            Supports recipe management (view/clear specific recipes).
        
        Args:
            recipe_name: Vietnamese recipe name (e.g., "Gỏi Trộn Khô Mực")
            ingredients_list: List of dicts: [{"food_id": str, "quantity": int, "unit": str}, ...]
            batch_id: Unique identifier to group ingredients from same recipe (UUID recommended)
        
        Returns:
            True if all insertions successful, False if any failed
            
        Note:
            Does NOT modify existing insert_request() API.
            All ingredients use same batch_id for easy recipe management.
        """
        if not self._connections[DatabaseType.REQUEST] or not self._cursors[DatabaseType.REQUEST]:
            self.logger.error("Request database connection not established")
            return False
        
        connection = self._connections[DatabaseType.REQUEST]
        cursor = self._cursors[DatabaseType.REQUEST]
        
        try:
            for ingredient in ingredients_list:
                cursor.execute(f"""
                    INSERT INTO {self.REQUEST_TABLE_NAME}
                    (recipe_name, food_id, quantity, unit, request_batch_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (recipe_name, ingredient.get('food_id'),
                       ingredient.get('quantity', 0), ingredient.get('unit'), batch_id))
            
            connection.commit()
            self.logger.debug(f"Inserted request batch: recipe={recipe_name}, "
                            f"items={len(ingredients_list)}, batch_id={batch_id}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error inserting request batch: {e}")
            self.handle_db_lock_exception(DatabaseType.REQUEST)
            connection.rollback()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error inserting request batch: {e}")
            connection.rollback()
            return False
    
    def clear_request_batch(self, batch_id: str) -> bool:
        """
        Delete all ingredients from a specific recipe batch.
        
        Purpose:
            Support recipe management - allow users to clear requests from previous recipes.
            Enables recipe switching without manual item deletion.
        
        Args:
            batch_id: request_batch_id to delete
        
        Returns:
            True if deletion successful, False otherwise
        """
        if not self._connections[DatabaseType.REQUEST] or not self._cursors[DatabaseType.REQUEST]:
            self.logger.error("Request database connection not established")
            return False
        
        connection = self._connections[DatabaseType.REQUEST]
        cursor = self._cursors[DatabaseType.REQUEST]
        
        try:
            cursor.execute(f"""
                DELETE FROM {self.REQUEST_TABLE_NAME}
                WHERE request_batch_id = ?
            """, (batch_id,))
            
            deleted_count = cursor.rowcount
            connection.commit()
            self.logger.debug(f"Cleared request batch: batch_id={batch_id}, deleted_count={deleted_count}")
            return True
            
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error clearing request batch: {e}")
            self.handle_db_lock_exception(DatabaseType.REQUEST)
            connection.rollback()
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error clearing request batch: {e}")
            connection.rollback()
            return False
    
    def get_requests_by_recipe(self, recipe_name: str) -> list:
        """
        Retrieve all ingredients for a specific recipe.
        
        Purpose:
            Support recipe-level queries for comparison/analytics.
            Alternative to get_all_requests() for specific recipe.
        
        Args:
            recipe_name: Vietnamese recipe name
        
        Returns:
            List of ingredients as dictionaries: [{"food_id": str, "quantity": int, "unit": str}, ...]
        """
        if not self._cursors[DatabaseType.REQUEST]:
            return []
        
        try:
            self._cursors[DatabaseType.REQUEST].execute(f"""
                SELECT id, recipe_name, food_id, quantity, unit, request_batch_id, created_at
                FROM {self.REQUEST_TABLE_NAME}
                WHERE recipe_name = ?
                ORDER BY created_at DESC
            """, (recipe_name,))
            
            rows = self._cursors[DatabaseType.REQUEST].fetchall()
            return [{
                'id': row[0],
                'recipe_name': row[1],
                'food_id': row[2],
                'quantity': row[3],
                'unit': row[4],
                'request_batch_id': row[5],
                'created_at': row[6]
            } for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving requests by recipe: {e}")
            return []
