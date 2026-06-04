#!/usr/bin/env python3
"""
@file inventory_dbus_listener.py
@brief D-Bus listener for FRT detection with two-tier data fetching.

Two-tier Data Fetching Strategy:
1. PRIMARY: Query SQLite database directly for latest FRT detection results
2. FALLBACK (after 15s): Listen to raw FRTApp D-Bus signals (vn.edu.uit.FSS.FRTApp)

Feature Flag Handling:
- Checks FRT_APP_ENABLED flag - if disabled, outputs status only
- If enabled, queries database for inventory and listens for FRT results
- Graceful degradation when FRTApp not available

Following ASPICE SWE.3 principles with comprehensive error handling.
"""

import sys
import json
import asyncio
import logging
import signal
import sqlite3
import time
import os
from typing import Optional, Dict, Any, List

def get_dbus_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../config.json"))
    try:
        with open(config_path, "r") as f:
            return json.load(f).get("dbus", {})
    except Exception:
        return {}

dbus_config = get_dbus_config()

try:
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async
except ImportError:
    print("ERROR: sdbus package not installed. Install with: pip install python-sdbus", file=sys.stderr)
    sys.exit(1)

# Configure logging to stderr (keep stdout for JSON output)
logging.basicConfig(level=logging.INFO, format="[InventoryListener] %(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "/opt/fss/data/FSS_Inventory.db"
DB_TABLE = "current_inventory"
DB_QUERY_TIMEOUT_S = 15
DB_POLL_INTERVAL_S = 2


class FRTAppProxy(DbusInterfaceCommonAsync, interface_name=dbus_config.get("sensor_interface", "vn.edu.uit.FSS.FRTApp")):
    """D-Bus interface proxy for raw FRT signals from frt_app."""

    @dbus_signal_async("sis")
    def FRTDetectionResult(self) -> None:
        """Signal: Food ID, quantity, image path."""
        pass


class DbDaemonInventoryProxy(DbusInterfaceCommonAsync, interface_name=dbus_config.get("dbdaemon_interface", "vn.edu.uit.FSS.DBDaemon")):
    """D-Bus interface proxy for FRT signals from DBDaemon."""

    @dbus_signal_async("sis")
    def UIUpdateRequired(self) -> None:
        """Signal: FRT result - food_id (string), quantity (int), image_path (string)."""
        pass


class InventoryListener:
    """Main listener for FRT inventory with two-tier fetching strategy."""

    # D-Bus configuration
    DBUS_SERVICE = dbus_config.get("dbdaemon_service", "vn.edu.uit.FSS.DBDaemon")
    DBUS_PATH = dbus_config.get("dbdaemon_path", "/vn/edu/uit/FSS/DBDaemon")
    
    FRT_DBUS_SERVICE = dbus_config.get("sensor_service", "vn.edu.uit.FSS.FRTApp")
    FRT_DBUS_PATH = dbus_config.get("sensor_path", "/vn/edu/uit/FSS/FRTApp")

    def __init__(self, frt_app_enabled: bool = False):
        """Initialize the listener."""
        self.frt_app_enabled = frt_app_enabled
        self.running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.dbus_proxy: Optional[DbDaemonInventoryProxy] = None
        self.frt_proxy: Optional[FRTAppProxy] = None
        self.signal_tasks: list = []
        self.last_db_update_time = 0
        self.in_fallback_mode = False
        self.sent_items: set = set()

    def query_inventory_from_db(self) -> List[Dict[str, Any]]:
        """Query SQLite database for all inventory items."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            cursor = conn.cursor()
            
            # Query all inventory items
            cursor.execute(f"""
                SELECT food_id, quantity, confidence_score, image_path, last_updated
                FROM {DB_TABLE}
                WHERE quantity > 0
                ORDER BY last_updated DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            items = []
            if rows:
                self.last_db_update_time = time.time()
                for row in rows:
                    food_id, qty, conf, img_path, last_upd = row
                    items.append({
                        'food_id': food_id,
                        'quantity': int(qty),
                        'confidence': float(conf),
                        'image_path': img_path,
                        'last_updated': last_upd,
                    })
                logger.debug(f"DB Query: Found {len(items)} inventory items")
            
            return items
            
        except sqlite3.Error as e:
            logger.warning(f"Database query error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying database: {e}")
            return []

    async def poll_database_mode(self):
        """Poll database for inventory changes every 2 seconds."""
        if not self.frt_app_enabled:
            logger.info("FRTApp disabled - not polling inventory")
            return
            
        logger.info("Starting database polling mode for inventory")
        
        while self.running and not self.in_fallback_mode:
            try:
                items = self.query_inventory_from_db()
                
                current_items = {item['food_id'] for item in items}
                
                # Detect new items (added)
                new_items = current_items - self.sent_items
                for item in items:
                    if item['food_id'] in new_items:
                        data = {
                            "type": "FRT_UPDATE",
                            "foodId": str(item['food_id']),
                            "className": str(item['food_id']),
                            "quantity": item['quantity'],
                            "imagePath": str(item['image_path']) if item['image_path'] else "",
                            "action": "added",
                            "source": "database",
                            "timestamp": int(time.time() * 1000),
                        }
                        print(json.dumps(data), flush=True)
                        self.sent_items.add(item['food_id'])
                
                # Detect removed items
                removed_items = self.sent_items - current_items
                for food_id in removed_items:
                    data = {
                        "type": "FRT_UPDATE",
                        "foodId": str(food_id),
                        "className": str(food_id),
                        "quantity": 0,
                        "imagePath": "",
                        "action": "removed",
                        "source": "database",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    self.sent_items.discard(food_id)
                    
            except Exception as e:
                logger.error(f"Error in database polling: {e}")
            
            # Check if we should fall back to raw FRT signals
            time_since_update = time.time() - self.last_db_update_time
            if time_since_update > DB_QUERY_TIMEOUT_S and self.last_db_update_time > 0:
                logger.warning(f"No database updates for {DB_QUERY_TIMEOUT_S}s - switching to fallback mode")
                self.in_fallback_mode = True
                return
            
            await asyncio.sleep(DB_POLL_INTERVAL_S)

    async def connect_dbdaemon_signals(self):
        """Connect to DBDaemon signals (primary data source)."""
        if not self.frt_app_enabled:
            logger.info("FRTApp disabled - skipping DBDaemon connection")
            while self.running:
                await asyncio.sleep(1)
            return
            
        try:
            logger.info(f"Connecting to {self.DBUS_SERVICE} D-Bus signals...")
            
            self.dbus_proxy = DbDaemonInventoryProxy.new_proxy(self.DBUS_SERVICE, self.DBUS_PATH)
            
            logger.info("Connected to DBDaemon - listening for signals")
            print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon"}), flush=True)

            self.reconnect_attempts = 0

            tasks = [
                asyncio.create_task(self._listen_dbdaemon_frt()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"DBDaemon connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_dbdaemon_frt(self):
        """Listen for FRT updates from DBDaemon."""
        if not self.dbus_proxy:
            return
            
        try:
            async for food_id, quantity, image_path in self.dbus_proxy.UIUpdateRequired:
                try:
                    self.last_db_update_time = time.time()
                    action = "added" if quantity > 0 else "removed"
                    
                    data = {
                        "type": "FRT_UPDATE",
                        "foodId": str(food_id),
                        "className": str(food_id),
                        "quantity": int(abs(quantity)),
                        "imagePath": str(image_path),
                        "action": action,
                        "source": "dbus_signal",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"FRT from DBDaemon: {food_id}, qty={quantity}, action={action}")
                except Exception as e:
                    logger.error(f"Error processing FRT data: {e}")
        except asyncio.CancelledError:
            logger.debug("FRT listener task cancelled")
        except Exception as e:
            logger.error(f"Error in FRT listener: {e}")

    async def connect_frtapp_signals(self):
        """Connect to raw FRTApp signals (fallback data source)."""
        try:
            logger.info(f"Connecting to raw FRTApp {self.FRT_DBUS_SERVICE}...")
            
            self.frt_proxy = FRTAppProxy.new_proxy(self.FRT_DBUS_SERVICE, self.FRT_DBUS_PATH)
            
            logger.info("Connected to FRTApp - listening for raw FRT signals")
            print(json.dumps({"type": "STATUS", "message": "Switched to raw FRTApp signals"}), flush=True)

            tasks = [
                asyncio.create_task(self._listen_frtapp_signals()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"FRTApp connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_frtapp_signals(self):
        """Listen for raw FRT signals from frt_app."""
        if not self.frt_proxy:
            return
            
        try:
            async for food_id, quantity, image_path in self.frt_proxy.FRTDetectionResult:
                try:
                    self.last_db_update_time = time.time()
                    action = "added" if quantity > 0 else "removed"
                    
                    data = {
                        "type": "FRT_UPDATE",
                        "foodId": str(food_id),
                        "className": str(food_id),
                        "quantity": int(abs(quantity)),
                        "imagePath": str(image_path),
                        "action": action,
                        "source": "raw_frtapp",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"FRT from raw FRTApp: {food_id}, qty={quantity}, action={action}")
                except Exception as e:
                    logger.error(f"Error processing raw FRT data: {e}")
        except asyncio.CancelledError:
            logger.debug("Raw FRT listener task cancelled")
        except Exception as e:
            logger.error(f"Error in raw FRT listener: {e}")

    async def attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached - exiting")
            self.running = False
            return

        self.reconnect_attempts += 1
        delay = min(1.0 * (2 ** (self.reconnect_attempts - 1)), 30.0)
        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)

        if self.running:
            if self.in_fallback_mode:
                await self.connect_frtapp_signals()
            else:
                await self.connect_dbdaemon_signals()

    async def cleanup(self):
        """Cleanup tasks."""
        for task in self.signal_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def run(self):
        """Main run loop with two-tier strategy."""
        # Emit FRT status
        print(json.dumps({"type": "FRT_APP_ENABLED", "enabled": self.frt_app_enabled}), flush=True)
        logger.info(f"FRTApp enabled: {self.frt_app_enabled}")
        
        if not self.frt_app_enabled:
            logger.info("FRTApp disabled - outputting status only")
            print(json.dumps({"type": "STATUS", "message": "FRTApp disabled"}), flush=True)
            while self.running:
                await asyncio.sleep(1)
            return
        
        while self.running:
            try:
                # Try database polling first
                self.last_db_update_time = time.time()
                self.in_fallback_mode = False
                
                # Run database polling and signal listening concurrently
                db_task = asyncio.create_task(self.poll_database_mode())
                signal_task = asyncio.create_task(self.connect_dbdaemon_signals())
                
                # Wait for either to complete or switch to fallback
                done, pending = await asyncio.wait(
                    [db_task, signal_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # If we fell back to FRTApp signals
                if self.in_fallback_mode:
                    logger.info("Entering fallback mode - connecting to raw FRTApp")
                    await self.connect_frtapp_signals()
                    
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                if self.running:
                    await asyncio.sleep(1)

    def stop(self):
        """Signal the listener to stop gracefully."""
        logger.info("Stop signal received")
        self.running = False


async def main():
    """Main entry point."""
    # Get FRT_APP_ENABLED from command line argument
    frt_enabled = False
    if len(sys.argv) > 1:
        frt_enabled = sys.argv[1].lower() in ("true", "1", "yes")
    
    listener = InventoryListener(frt_app_enabled=frt_enabled)

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum} - initiating graceful shutdown")
        listener.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting Inventory D-Bus Listener (Two-Tier Strategy)")
        await listener.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await listener.cleanup()
        logger.info("Listener stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)