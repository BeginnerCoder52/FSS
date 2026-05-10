#!/usr/bin/env python3
"""
@file monitor_dbus_listener.py
@brief D-Bus listener for distance and door sensor data from DBDaemon.

Listens to D-Bus signals from DBDaemon:
  - DistanceAlert(db): Distance in meters and within threshold boolean
  - DoorStateUpdate(sd): Door state (OPEN/CLOSED) and timestamp

Outputs JSON formatted data to stdout for node_helper to consume.

Connection: vn.edu.uit.FSS.DBDaemon @ /vn/edu/uit/FSS/DBDaemon

Screen control logic:
- If distance < 0.6m (60cm) and withinThreshold=True: Activate black screen (user detected)
- If distance >= 0.6m: Deactivate black screen
- Door OPEN event: Trigger external camera system notification

Following ASPICE principles with comprehensive error handling and reconnection logic.
"""

import sys
import json
import logging
import asyncio
import signal
from typing import Optional

try:
    import sdbus
    from sdbus import DbusInterfaceCommon, dbus_signal
    SDBUS_AVAILABLE = True
except ImportError:
    SDBUS_AVAILABLE = False
    print("ERROR: sdbus-python not installed. Install with: pip install sdbus-python", file=sys.stderr)
    sys.exit(1)


# Configure logging to stderr (keep stdout for JSON output)
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("MonitorDBusListener")


class MonitorListener:
    """
    Listens to D-Bus signals from DBDaemon for distance and door sensors.
    """

    # Target SensorDaemon instead of DBDaemon to avoid latency
    DBUS_SERVICE = "vn.edu.uit.FSS.Sensor"
    DBUS_PATH = "/vn/edu/uit/FSS/Sensor"
    DBUS_INTERFACE = "vn.edu.uit.FSS.Sensor"

    def __init__(self):
        """Initialize the listener."""
        self.bus: Optional[sdbus.DbusConnection] = None
        self.remote_object: Optional[sdbus.DbusRemoteObject] = None
        self.running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1.0

    async def connect(self) -> bool:
        """
        Connect to D-Bus and subscribe to signals.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Connecting to system D-Bus...")
            self.bus = await sdbus.get_system_bus()
            logger.info("Connected to system D-Bus")

            logger.info(f"Connecting to D-Bus service: {self.DBUS_SERVICE}")
            self.remote_object = self.bus.get_proxy_object(
                self.DBUS_SERVICE, self.DBUS_PATH
            )
            logger.info(f"Connected to D-Bus object at {self.DBUS_PATH}")

            self.subscribe_to_signals()
            logger.info("Subscribed to monitor signals")

            self.reconnect_attempts = 0
            return True

        except Exception as e:
            logger.error(f"Failed to connect to D-Bus: {e}")
            return False

    def subscribe_to_signals(self):
        """
        Subscribe to distance and door state D-Bus signals.
        """
        try:
            interface = self.remote_object.get_interface(self.DBUS_INTERFACE)

            # Subscribe to DistanceAlert signal
            interface.DistanceDataChanged.connect_to_signal(self.on_distance_alert)
            logger.info("Subscribed to DistanceAlert signal")

            # Subscribe to DoorStateUpdate signal
            interface.DoorStateChanged.connect_to_signal(self.on_door_state_update)
            logger.info("Subscribed to DoorStateUpdate signal")

        except Exception as e:
            logger.error(f"Failed to subscribe to signals: {e}")
            raise

    def on_distance_alert(self, distance: float, within_threshold: bool):
        """
        Handle DistanceAlert signal.

        Args:
            distance: Distance in meters
            within_threshold: Boolean indicating if distance is within threshold
        """
        try:
            data = {
                "type": "DISTANCE_ALERT",
                "distance": float(distance),
                "withinThreshold": bool(within_threshold),
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }
            print(json.dumps(data))
            logger.debug(f"Distance alert: {distance:.2f}m, within_threshold={within_threshold}")
        except Exception as e:
            logger.error(f"Error processing DistanceAlert signal: {e}")

    def on_door_state_update(self, state: str, timestamp: float):
        """
        Handle DoorStateUpdate signal.

        Args:
            state: Door state ("OPEN" or "CLOSED")
            timestamp: Unix timestamp of the state change
        """
        try:
            data = {
                "type": "DOOR_STATE_UPDATE",
                "state": str(state),
                "timestamp": int(timestamp * 1000) if timestamp > 100 else int(asyncio.get_event_loop().time() * 1000),
            }
            print(json.dumps(data))
            logger.debug(f"Door state update: {state}")
        except Exception as e:
            logger.error(f"Error processing DoorStateUpdate signal: {e}")

    async def run(self):
        """
        Main event loop - connect and listen for signals.
        """
        while self.running:
            if not self.bus or not self.remote_object:
                logger.info(f"Attempting to connect (attempt {self.reconnect_attempts + 1})...")
                if not await self.connect():
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= self.max_reconnect_attempts:
                        logger.error("Max reconnection attempts reached")
                        self.running = False
                        break

                    delay = min(
                        self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
                        30.0,
                    )
                    logger.info(f"Reconnecting in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.info("Connected and listening for signals")
                    print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon"}))

            await asyncio.sleep(1)

    def stop(self):
        """Stop the listener."""
        logger.info("Stopping listener...")
        self.running = False

    async def cleanup(self):
        """Cleanup resources."""
        if self.bus:
            await self.bus.close()
            logger.info("D-Bus connection closed")


async def main():
    """
    Entry point for the D-Bus listener.
    """
    listener = MonitorListener()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        listener.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting Monitor D-Bus Listener")
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
