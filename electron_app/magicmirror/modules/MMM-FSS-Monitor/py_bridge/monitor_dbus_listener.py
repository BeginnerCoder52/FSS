#!/usr/bin/env python3
"""
@file monitor_dbus_listener.py
@brief D-Bus listener for distance/door sensors with two-tier data fetching.

Two-tier Data Fetching Strategy:
1. PRIMARY: Query SQLite database directly for latest sensor readings
2. FALLBACK (after 15s): Listen to raw sensor D-Bus signals (vn.edu.uit.FSS.Sensor)

Screen Control Logic:
- If distance < 0.6m (60cm): Activate black screen overlay (user detected)
- If distance >= 0.6m: Deactivate black screen
- Door OPEN event: Log for potential external camera trigger

Following ASPICE SWE.3 principles with comprehensive error handling.
"""

import sys
import json
import asyncio
import logging
import signal
import sqlite3
import time
from typing import Optional, Tuple

try:
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async
except ImportError:
    print("ERROR: sdbus package not installed. Install with: pip install python-sdbus", file=sys.stderr)
    sys.exit(1)

# Configure logging to stderr (keep stdout for JSON output)
logging.basicConfig(level=logging.INFO, format="[MonitorListener] %(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "/opt/fss/data/fss_data.db"
DB_QUERY_TIMEOUT_S = 15
DB_POLL_INTERVAL_S = 2
DISTANCE_THRESHOLD_M = 0.6  # 60cm


class SensorDaemonProxy(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.Sensor"):
    """D-Bus interface proxy for raw sensor signals from sensor_daemon."""

    @dbus_signal_async("d")
    def DistanceDataChanged(self) -> None:
        """Signal: Distance reading."""
        pass

    @dbus_signal_async("s")
    def DoorStateChanged(self) -> None:
        """Signal: Door state."""
        pass


class DbDaemonMonitorProxy(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.DBDaemon"):
    """D-Bus interface proxy for distance and door signals from DBDaemon."""

    @dbus_signal_async("db")
    def DistanceAlert(self) -> None:
        """Signal: Distance value (meters) and within_threshold (boolean)."""
        pass

    @dbus_signal_async("sd")
    def DoorStateUpdate(self) -> None:
        """Signal: Door state (string) and timestamp (double)."""
        pass


class MonitorListener:
    """Main listener for monitor sensors with two-tier fetching strategy."""

    # D-Bus configuration
    DBUS_SERVICE = "vn.edu.uit.FSS.DBDaemon"
    DBUS_PATH = "/vn/edu/uit/FSS/DBDaemon"
    
    SENSOR_DBUS_SERVICE = "vn.edu.uit.FSS.Sensor"
    SENSOR_DBUS_PATH = "/vn/edu/uit/FSS/Sensor"

    def __init__(self):
        """Initialize the listener."""
        self.running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.dbus_proxy: Optional[DbDaemonMonitorProxy] = None
        self.sensor_proxy: Optional[SensorDaemonProxy] = None
        self.signal_tasks: list = []
        self.last_db_update_time = 0
        self.in_fallback_mode = False

    def query_latest_sensors_from_db(self) -> Tuple[Optional[float], Optional[bool], Optional[str]]:
        """Query SQLite database for latest distance and door readings."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            cursor = conn.cursor()
            
            # Query latest distance reading
            cursor.execute("""
                SELECT distance, timestamp FROM distance_sensor_log
                ORDER BY timestamp DESC LIMIT 1
            """)
            distance_row = cursor.fetchone()
            
            # Query latest door state
            cursor.execute("""
                SELECT door_state, timestamp FROM door_sensor_log
                ORDER BY timestamp DESC LIMIT 1
            """)
            door_row = cursor.fetchone()
            
            conn.close()
            
            distance = None
            is_user_detected = None
            door_state = None
            
            if distance_row:
                distance, ts = distance_row
                is_user_detected = distance < DISTANCE_THRESHOLD_M
                self.last_db_update_time = time.time()
                logger.debug(f"DB Query: distance={distance:.2f}m, user_detected={is_user_detected}")
            
            if door_row:
                door_state, ts = door_row
                self.last_db_update_time = time.time()
                logger.debug(f"DB Query: door_state={door_state}")
            
            return (distance, is_user_detected, door_state)
            
        except sqlite3.Error as e:
            logger.warning(f"Database query error: {e}")
            return (None, None, None)
        except Exception as e:
            logger.error(f"Unexpected error querying database: {e}")
            return (None, None, None)

    async def poll_database_mode(self):
        """Poll database for latest sensor readings every 2 seconds."""
        logger.info("Starting database polling mode")
        
        while self.running and not self.in_fallback_mode:
            try:
                distance, is_user_detected, door_state = self.query_latest_sensors_from_db()
                
                if distance is not None:
                    data = {
                        "type": "DISTANCE_ALERT",
                        "distance": float(distance),
                        "withinThreshold": is_user_detected,
                        "isUserDetected": is_user_detected,
                        "source": "database",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                
                if door_state is not None:
                    data = {
                        "type": "DOOR_STATE_UPDATE",
                        "doorState": str(door_state),
                        "source": "database",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    
            except Exception as e:
                logger.error(f"Error in database polling: {e}")
            
            # Check if we should fall back to raw sensor signals
            time_since_update = time.time() - self.last_db_update_time
            if time_since_update > DB_QUERY_TIMEOUT_S and self.last_db_update_time > 0:
                logger.warning(f"No database updates for {DB_QUERY_TIMEOUT_S}s - switching to fallback mode")
                self.in_fallback_mode = True
                return
            
            await asyncio.sleep(DB_POLL_INTERVAL_S)

    async def connect_dbdaemon_signals(self):
        """Connect to DBDaemon signals (primary data source)."""
        try:
            logger.info(f"Connecting to {self.DBUS_SERVICE} D-Bus signals...")
            
            self.dbus_proxy = DbDaemonMonitorProxy.new_proxy(self.DBUS_SERVICE, self.DBUS_PATH)
            
            logger.info("Connected to DBDaemon - listening for signals")
            print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon"}), flush=True)

            self.reconnect_attempts = 0

            tasks = [
                asyncio.create_task(self._listen_dbdaemon_distance()),
                asyncio.create_task(self._listen_dbdaemon_door()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"DBDaemon connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_dbdaemon_distance(self):
        """Listen for distance alerts from DBDaemon."""
        if not self.dbus_proxy:
            return
            
        try:
            async for distance, within_threshold in self.dbus_proxy.DistanceAlert:
                try:
                    self.last_db_update_time = time.time()
                    is_user_detected = distance < DISTANCE_THRESHOLD_M
                    data = {
                        "type": "DISTANCE_ALERT",
                        "distance": float(distance),
                        "withinThreshold": bool(within_threshold),
                        "isUserDetected": is_user_detected,
                        "source": "dbus_signal",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Distance from DBDaemon: {distance:.2f}m, user_detected={is_user_detected}")
                except Exception as e:
                    logger.error(f"Error processing distance data: {e}")
        except asyncio.CancelledError:
            logger.debug("Distance listener task cancelled")
        except Exception as e:
            logger.error(f"Error in distance listener: {e}")

    async def _listen_dbdaemon_door(self):
        """Listen for door state updates from DBDaemon."""
        if not self.dbus_proxy:
            return
            
        try:
            async for door_state, timestamp in self.dbus_proxy.DoorStateUpdate:
                try:
                    self.last_db_update_time = time.time()
                    data = {
                        "type": "DOOR_STATE_UPDATE",
                        "doorState": str(door_state),
                        "source": "dbus_signal",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Door state from DBDaemon: {door_state}")
                except Exception as e:
                    logger.error(f"Error processing door state: {e}")
        except asyncio.CancelledError:
            logger.debug("Door listener task cancelled")
        except Exception as e:
            logger.error(f"Error in door listener: {e}")

    async def connect_sensor_daemon_signals(self):
        """Connect to raw sensor daemon signals (fallback data source)."""
        try:
            logger.info(f"Connecting to raw sensor daemon {self.SENSOR_DBUS_SERVICE}...")
            
            self.sensor_proxy = SensorDaemonProxy.new_proxy(self.SENSOR_DBUS_SERVICE, self.SENSOR_DBUS_PATH)
            
            logger.info("Connected to Sensor Daemon - listening for raw signals")
            print(json.dumps({"type": "STATUS", "message": "Switched to raw sensor signals"}), flush=True)

            tasks = [
                asyncio.create_task(self._listen_sensor_distance()),
                asyncio.create_task(self._listen_sensor_door()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Sensor daemon connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_sensor_distance(self):
        """Listen for raw distance readings from sensor_daemon."""
        if not self.sensor_proxy:
            return
            
        try:
            async for distance in self.sensor_proxy.DistanceDataChanged:
                try:
                    self.last_db_update_time = time.time()
                    is_user_detected = distance < DISTANCE_THRESHOLD_M
                    data = {
                        "type": "DISTANCE_ALERT",
                        "distance": float(distance),
                        "withinThreshold": is_user_detected,
                        "isUserDetected": is_user_detected,
                        "source": "raw_sensor",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Raw distance: {distance:.2f}m, user_detected={is_user_detected}")
                except Exception as e:
                    logger.error(f"Error processing raw distance: {e}")
        except asyncio.CancelledError:
            logger.debug("Raw distance listener task cancelled")
        except Exception as e:
            logger.error(f"Error in raw distance listener: {e}")

    async def _listen_sensor_door(self):
        """Listen for raw door state readings from sensor_daemon."""
        if not self.sensor_proxy:
            return
            
        try:
            async for door_state in self.sensor_proxy.DoorStateChanged:
                try:
                    self.last_db_update_time = time.time()
                    data = {
                        "type": "DOOR_STATE_UPDATE",
                        "doorState": str(door_state),
                        "source": "raw_sensor",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Raw door state: {door_state}")
                except Exception as e:
                    logger.error(f"Error processing raw door state: {e}")
        except asyncio.CancelledError:
            logger.debug("Raw door listener task cancelled")
        except Exception as e:
            logger.error(f"Error in raw door listener: {e}")

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
                await self.connect_sensor_daemon_signals()
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
                
                # If we fell back to sensor daemon mode
                if self.in_fallback_mode:
                    logger.info("Entering fallback mode - connecting to raw sensor daemon")
                    await self.connect_sensor_daemon_signals()
                    
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
    listener = MonitorListener()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum} - initiating graceful shutdown")
        listener.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting Monitor D-Bus Listener (Two-Tier Strategy)")
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