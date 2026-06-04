#!/usr/bin/env python3
"""
@file env_dbus_listener.py
@brief D-Bus listener for environmental sensor data with two-tier data fetching.

Two-tier Data Fetching Strategy:
1. PRIMARY: Query SQLite database directly for latest sensor readings
2. FALLBACK (after 15s): Listen to raw sensor D-Bus signals (vn.edu.uit.FSS.Sensor)

This ensures data flows even if DBDaemon signals are not working.
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
logging.basicConfig(level=logging.INFO, format="[EnvListener] %(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "/opt/fss/data/fss_data.db"
DB_QUERY_TIMEOUT_S = 15  # Fall back to raw sensors after 15s without DB updates
DB_POLL_INTERVAL_S = 2   # Poll database every 2 seconds


class SensorDaemonProxy(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.Sensor"):
    """D-Bus interface proxy for raw sensor signals from sensor_daemon."""

    @dbus_signal_async("dd")
    def EnvironmentDataChanged(self) -> None:
        """Signal: Sensor 1 and 2 readings."""
        pass


class DbDaemonEnvProxy(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.DBDaemon"):
    """D-Bus interface proxy for environment signals from DBDaemon."""

    @dbus_signal_async("dd")
    def EnvironmentUpdateRequired(self) -> None:
        """Signal: Sensor 1 (Ngan mat) - temperature and humidity."""
        pass

    @dbus_signal_async("dd")
    def SecondaryEnvironmentUpdateRequired(self) -> None:
        """Signal: Sensor 2 (Ngan dong) - temperature and humidity."""
        pass


class EnvironmentListener:
    """Main listener for environment sensor data with two-tier fetching strategy."""

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
        self.dbus_proxy: Optional[DbDaemonEnvProxy] = None
        self.sensor_proxy: Optional[SensorDaemonProxy] = None
        self.signal_tasks: list = []
        self.last_db_update_time = 0
        self.in_fallback_mode = False

    def query_latest_environment_from_db(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Query SQLite database for latest environment readings."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            cursor = conn.cursor()
            
            # Query latest environment reading (both sensors)
            cursor.execute("""
                SELECT temperature, humidity, temperature_2, humidity_2, timestamp
                FROM environment_log
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                temp1, humid1, temp2, humid2, ts = row
                self.last_db_update_time = time.time()
                logger.debug(f"DB Query: S1_T={temp1:.1f}°C, S1_H={humid1:.1f}%, S2_T={temp2}°C, S2_H={humid2}%")
                return (temp1, humid1, temp2, humid2)
            
            return (None, None, None, None)
            
        except sqlite3.Error as e:
            logger.warning(f"Database query error: {e}")
            return (None, None, None, None)
        except Exception as e:
            logger.error(f"Unexpected error querying database: {e}")
            return (None, None, None, None)

    async def poll_database_mode(self):
        """Poll database for latest environment readings every 2 seconds."""
        logger.info("Starting database polling mode")
        
        while self.running and not self.in_fallback_mode:
            try:
                temp1, humid1, temp2, humid2 = self.query_latest_environment_from_db()
                
                if temp1 is not None and humid1 is not None:
                    # Send Sensor 1 data
                    data = {
                        "type": "ENVIRONMENT_UPDATE",
                        "temperature": float(temp1),
                        "humidity": float(humid1),
                        "source": "database",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                
                if temp2 is not None and humid2 is not None:
                    # Send Sensor 2 data
                    data = {
                        "type": "SECONDARY_ENVIRONMENT_UPDATE",
                        "temperature": float(temp2),
                        "humidity": float(humid2),
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
            
            self.dbus_proxy = DbDaemonEnvProxy.new_proxy(self.DBUS_SERVICE, self.DBUS_PATH)
            
            logger.info("Connected to DBDaemon - listening for signals")
            print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon"}), flush=True)

            self.reconnect_attempts = 0

            # Create tasks to listen for signals
            tasks = [
                asyncio.create_task(self._listen_dbdaemon_env_updates()),
                asyncio.create_task(self._listen_dbdaemon_secondary_updates()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"DBDaemon connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_dbdaemon_env_updates(self):
        """Listen for Sensor 1 environment updates from DBDaemon."""
        if not self.dbus_proxy:
            return
            
        try:
            async for temperature, humidity in self.dbus_proxy.EnvironmentUpdateRequired:
                try:
                    self.last_db_update_time = time.time()
                    data = {
                        "type": "ENVIRONMENT_UPDATE",
                        "temperature": float(temperature),
                        "humidity": float(humidity),
                        "source": "dbus_signal",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Sensor 1 from DBDaemon: T={temperature:.1f}°C, H={humidity:.1f}%")
                except Exception as e:
                    logger.error(f"Error processing Sensor 1 data: {e}")
        except asyncio.CancelledError:
            logger.debug("Sensor 1 listener task cancelled")
        except Exception as e:
            logger.error(f"Error in Sensor 1 listener: {e}")

    async def _listen_dbdaemon_secondary_updates(self):
        """Listen for Sensor 2 environment updates from DBDaemon."""
        if not self.dbus_proxy:
            return
            
        try:
            async for temperature, humidity in self.dbus_proxy.SecondaryEnvironmentUpdateRequired:
                try:
                    self.last_db_update_time = time.time()
                    data = {
                        "type": "SECONDARY_ENVIRONMENT_UPDATE",
                        "temperature": float(temperature),
                        "humidity": float(humidity),
                        "source": "dbus_signal",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Sensor 2 from DBDaemon: T={temperature:.1f}°C, H={humidity:.1f}%")
                except Exception as e:
                    logger.error(f"Error processing Sensor 2 data: {e}")
        except asyncio.CancelledError:
            logger.debug("Sensor 2 listener task cancelled")
        except Exception as e:
            logger.error(f"Error in Sensor 2 listener: {e}")

    async def connect_sensor_daemon_signals(self):
        """Connect to raw sensor daemon signals (fallback data source)."""
        try:
            logger.info(f"Connecting to raw sensor daemon {self.SENSOR_DBUS_SERVICE}...")
            
            self.sensor_proxy = SensorDaemonProxy.new_proxy(self.SENSOR_DBUS_SERVICE, self.SENSOR_DBUS_PATH)
            
            logger.info("Connected to Sensor Daemon - listening for raw sensor signals")
            print(json.dumps({"type": "STATUS", "message": "Switched to raw sensor signals"}), flush=True)

            # Listen for raw sensor signals
            tasks = [
                asyncio.create_task(self._listen_sensor_updates()),
            ]
            self.signal_tasks.extend(tasks)

            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Sensor daemon connection error: {e}")
            if self.running:
                await self.attempt_reconnect()

    async def _listen_sensor_updates(self):
        """Listen for raw sensor readings from sensor_daemon."""
        if not self.sensor_proxy:
            return
            
        try:
            async for temp1, humid1 in self.sensor_proxy.EnvironmentDataChanged:
                try:
                    self.last_db_update_time = time.time()
                    # Send Sensor 1 data from raw sensor signal
                    data1 = {
                        "type": "ENVIRONMENT_UPDATE",
                        "temperature": float(temp1),
                        "humidity": float(humid1),
                        "source": "raw_sensor",
                        "timestamp": int(time.time() * 1000),
                    }
                    print(json.dumps(data1), flush=True)
                    logger.debug(f"Raw Sensor 1: T={temp1:.1f}°C, H={humid1:.1f}%")
                except Exception as e:
                    logger.error(f"Error processing raw sensor data: {e}")
        except asyncio.CancelledError:
            logger.debug("Raw sensor listener task cancelled")
        except Exception as e:
            logger.error(f"Error in raw sensor listener: {e}")

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
    listener = EnvironmentListener()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum} - initiating graceful shutdown")
        listener.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting Environment D-Bus Listener (Two-Tier Strategy)")
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
