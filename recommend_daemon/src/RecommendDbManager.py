import sqlite3
import logging
import os
import json
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


class RecommendDbManager:
    DEFAULT_DB_DIR = "/opt/fss/data"
    DB_NAME = "FSS-Recommend.db"

    RECOMMENDATION_LOG_TABLE = "recommendation_log"
    SHOPPING_LIST_TABLE = "shopping_list"

    def __init__(self, db_dir: str = DEFAULT_DB_DIR):
        self.db_dir: str = db_dir
        self._connection: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Initialized RecommendDbManager with db_dir={db_dir}")

    def connect_db(self) -> bool:
        try:
            db_path = os.path.join(self.db_dir, self.DB_NAME)
            db_dir_path = Path(self.db_dir)
            db_dir_path.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                db_path, timeout=5.0, check_same_thread=False
            )
            self._cursor = self._connection.cursor()
            self._cursor.execute("PRAGMA journal_mode=WAL")
            self._cursor.execute("PRAGMA foreign_keys=ON")
            self.logger.info(f"Connected to FSS-Recommend database: {db_path}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database: {e}")
            return False

    def init_tables(self) -> None:
        if not self._cursor or not self._connection:
            self.logger.error("Database connection not established")
            return
        try:
            self._create_recommendation_log_table()
            self._create_shopping_list_table()
            self._connection.commit()
            self.logger.info("FSS-Recommend database tables initialized")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize tables: {e}")

    def _create_recommendation_log_table(self) -> None:
        self._cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.RECOMMENDATION_LOG_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_name TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                nlp_status TEXT,
                total_items INTEGER DEFAULT 0,
                available_count INTEGER DEFAULT 0,
                needed_count INTEGER DEFAULT 0,
                missing_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        self._cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_recommendation_batch_id
            ON {self.RECOMMENDATION_LOG_TABLE}(batch_id)
        """)

    def _create_shopping_list_table(self) -> None:
        self._cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.SHOPPING_LIST_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL,
                food_id TEXT NOT NULL,
                required_qty INTEGER DEFAULT 0,
                available_qty INTEGER DEFAULT 0,
                shortage INTEGER DEFAULT 0,
                unit TEXT,
                purchased BOOLEAN DEFAULT 0,
                purchased_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recommendation_id)
                    REFERENCES {self.RECOMMENDATION_LOG_TABLE}(id)
                    ON DELETE CASCADE
            )
        """)
        self._cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_shopping_recommendation
            ON {self.SHOPPING_LIST_TABLE}(recommendation_id)
        """)
        self._cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_shopping_purchased
            ON {self.SHOPPING_LIST_TABLE}(purchased)
        """)

    def insert_recommendation(
        self,
        recipe_name: str,
        batch_id: str,
        nlp_status: str,
        total_items: int,
        available_count: int,
        needed_count: int,
        missing_count: int,
        result_json: str
    ) -> Optional[int]:
        if not self._cursor or not self._connection:
            self.logger.error("Database connection not established")
            return None
        try:
            self._cursor.execute(f"""
                INSERT INTO {self.RECOMMENDATION_LOG_TABLE}
                (recipe_name, batch_id, nlp_status, total_items,
                 available_count, needed_count, missing_count, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (recipe_name, batch_id, nlp_status, total_items,
                  available_count, needed_count, missing_count, result_json))
            self._connection.commit()
            row_id = self._cursor.lastrowid
            self.logger.info(
                f"Inserted recommendation: recipe={recipe_name}, "
                f"batch_id={batch_id}, id={row_id}"
            )
            return row_id
        except sqlite3.Error as e:
            self.logger.error(f"Failed to insert recommendation: {e}")
            return None

    def insert_shopping_item(
        self,
        recommendation_id: int,
        food_id: str,
        required_qty: int,
        available_qty: int,
        shortage: int,
        unit: Optional[str] = None
    ) -> bool:
        if not self._cursor or not self._connection:
            return False
        try:
            self._cursor.execute(f"""
                INSERT INTO {self.SHOPPING_LIST_TABLE}
                (recommendation_id, food_id, required_qty, available_qty, shortage, unit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (recommendation_id, food_id, required_qty,
                  available_qty, shortage, unit))
            self._connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Failed to insert shopping item: {e}")
            return False

    def insert_shopping_list(
        self,
        recommendation_id: int,
        items: List[Dict[str, Any]]
    ) -> bool:
        success = True
        for item in items:
            if not self.insert_shopping_item(
                recommendation_id,
                item.get("food_id", ""),
                item.get("required_qty", 0),
                item.get("available_qty", 0),
                item.get("shortage", 0),
                item.get("unit")
            ):
                success = False
        return success

    def get_shopping_list(self, batch_id: str) -> List[Dict[str, Any]]:
        if not self._cursor:
            return []
        try:
            self._cursor.execute(f"""
                SELECT s.id, s.food_id, s.required_qty, s.available_qty,
                       s.shortage, s.unit, s.purchased, s.purchased_at, s.created_at,
                       r.batch_id, r.recipe_name
                FROM {self.SHOPPING_LIST_TABLE} s
                JOIN {self.RECOMMENDATION_LOG_TABLE} r
                    ON s.recommendation_id = r.id
                WHERE r.batch_id = ?
                ORDER BY s.food_id
            """, (batch_id,))
            rows = self._cursor.fetchall()
            return [{
                "id": row[0],
                "food_id": row[1],
                "required_qty": row[2],
                "available_qty": row[3],
                "shortage": row[4],
                "unit": row[5],
                "purchased": bool(row[6]),
                "purchased_at": row[7],
                "created_at": row[8],
                "batch_id": row[9],
                "recipe_name": row[10]
            } for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Failed to get shopping list: {e}")
            return []

    def mark_item_purchased(self, item_id: int) -> bool:
        if not self._cursor or not self._connection:
            return False
        try:
            now = datetime.now().isoformat()
            self._cursor.execute(f"""
                UPDATE {self.SHOPPING_LIST_TABLE}
                SET purchased = 1, purchased_at = ?
                WHERE id = ?
            """, (now, item_id))
            self._connection.commit()
            if self._cursor.rowcount == 0:
                self.logger.warning(f"Shopping item {item_id} not found")
                return False
            self.logger.info(f"Marked item {item_id} as purchased")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Failed to mark item purchased: {e}")
            return False

    def clear_shopping_list(self, batch_id: str) -> bool:
        if not self._cursor or not self._connection:
            return False
        try:
            self._cursor.execute(f"""
                DELETE FROM {self.SHOPPING_LIST_TABLE}
                WHERE recommendation_id IN (
                    SELECT id FROM {self.RECOMMENDATION_LOG_TABLE}
                    WHERE batch_id = ?
                )
            """, (batch_id,))
            self._connection.commit()
            self.logger.info(f"Cleared shopping list for batch_id={batch_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Failed to clear shopping list: {e}")
            return False

    def update_recommendation_status(self, batch_id: str, status: str) -> bool:
        if not self._cursor or not self._connection:
            return False
        try:
            now = datetime.now().isoformat() if status in ("fulfilled", "cancelled") else None
            if now:
                self._cursor.execute(f"""
                    UPDATE {self.RECOMMENDATION_LOG_TABLE}
                    SET status = ?, completed_at = ?
                    WHERE batch_id = ?
                """, (status, now, batch_id))
            else:
                self._cursor.execute(f"""
                    UPDATE {self.RECOMMENDATION_LOG_TABLE}
                    SET status = ?
                    WHERE batch_id = ?
                """, (status, batch_id))
            self._connection.commit()
            return self._cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Failed to update recommendation status: {e}")
            return False

    def get_recommendation(self, batch_id: str) -> Optional[Dict[str, Any]]:
        if not self._cursor:
            return None
        try:
            self._cursor.execute(f"""
                SELECT id, recipe_name, batch_id, nlp_status, total_items,
                       available_count, needed_count, missing_count, status,
                       result_json, created_at, completed_at
                FROM {self.RECOMMENDATION_LOG_TABLE}
                WHERE batch_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (batch_id,))
            row = self._cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "recipe_name": row[1],
                    "batch_id": row[2],
                    "nlp_status": row[3],
                    "total_items": row[4],
                    "available_count": row[5],
                    "needed_count": row[6],
                    "missing_count": row[7],
                    "status": row[8],
                    "result_json": row[9],
                    "created_at": row[10],
                    "completed_at": row[11]
                }
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Failed to get recommendation: {e}")
            return None

    def close_connection(self) -> None:
        try:
            if self._connection:
                try:
                    self._connection.commit()
                except (sqlite3.ProgrammingError, sqlite3.Error):
                    pass
                self._connection.close()
                self._connection = None
                self._cursor = None
            self.logger.info("FSS-Recommend database connection closed")
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database connection: {e}")
