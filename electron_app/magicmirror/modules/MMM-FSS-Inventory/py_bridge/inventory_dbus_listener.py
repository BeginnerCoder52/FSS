#!/usr/bin/env python3
"""
@file inventory_dbus_listener.py
@brief D-Bus listener for FRT detection results and inventory from DBDaemon.

Listens to D-Bus signals from DBDaemon:
  - UIUpdateRequired(sis): FoodID, Quantity, ImagePath (FRT detection results)

Also outputs FRT_APP_ENABLED feature flag status.

Outputs JSON formatted data to stdout for node_helper to consume.

Connection: vn.edu.uit.FSS.DBDaemon @ /vn/edu/uit/FSS/DBDaemon

Feature Flag Handling:
- Checks FRT_APP_ENABLED flag from PosixShmReader pattern
- If disabled, outputs FRT_APP_ENABLED: false
- If enabled, listens for FRT results and forwards them

Following ASPICE principles with comprehensive error handling and reconnection logic.
"""

import sys
import json
import logging
import asyncio
import signal
from typing import Optional
from pathlib import Path

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
logger = logging.getLogger("InventoryDBusListener")


class InventoryListener:
    """
    Listens to D-Bus signals from DBDaemon for FRT detection results.
    """

    # D-Bus configuration
    DBUS_SERVICE = "vn.edu.uit.FSS.DBDaemon"
    DBUS_PATH = "/vn/edu/uit/FSS/DBDaemon"
    DBUS_INTERFACE = "vn.edu.uit.FSS.DBDaemon"

    def __init__(self):
        """Initialize the listener."""
        self.bus: Optional[sdbus.DbusConnection] = None
        self.remote_object: Optional[sdbus.DbusRemoteObject] = None
        self.running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1.0
        self.frt_app_enabled = self.check_frt_enabled()

    def check_frt_enabled(self) -> bool:
        """
        Check if FRTApp is enabled.
        For now, return False as FRTApp is not yet implemented.
        This will check the feature flag from DBDaemon or config in the future.

        Returns:
            bool: FRT_APP_ENABLED status
        """
        # TODO: Read from config file or D-Bus interface
        # For now, hardcode to False since FRTApp not implemented
        return False

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

            # Emit FRT_APP_ENABLED status
            print(json.dumps({"type": "FRT_APP_ENABLED", "enabled": self.frt_app_enabled}))
            logger.info(f"FRT App enabled status: {self.frt_app_enabled}")

            if self.frt_app_enabled:
                self.subscribe_to_signals()
                logger.info("Subscribed to FRT signals")
            else:
                logger.info("FRTApp disabled - not subscribing to FRT signals")

            self.reconnect_attempts = 0
            return True

        except Exception as e:
            logger.error(f"Failed to connect to D-Bus: {e}")
            return False

    def subscribe_to_signals(self):
        """
        Subscribe to FRT-related D-Bus signals.
        """
        if not self.frt_app_enabled:
            logger.info("FRTApp not enabled - skipping signal subscription")
            return

        try:
            interface = self.remote_object.get_interface(self.DBUS_INTERFACE)

            # Subscribe to UIUpdateRequired signal (FRT results)
            interface.UIUpdateRequired.connect_to_signal(self.on_ui_update_required)
            logger.info("Subscribed to UIUpdateRequired signal")

        except Exception as e:
            logger.error(f"Failed to subscribe to signals: {e}")
            # Don't raise - FRTApp may not be connected yet

    def on_ui_update_required(self, food_id: str, quantity: int, image_path: str):
        """
        Handle UIUpdateRequired signal (FRT detection results).

        Args:
            food_id: Unique food identifier
            quantity: Quantity of food detected
            image_path: Path to detected food image
        """
        if not self.frt_app_enabled:
            logger.warning("Received FRT signal but FRTApp is disabled")
            return

        try:
            data = {
                "type": "FRT_UPDATE",
                "foodId": str(food_id),
                "className": str(food_id),  # Use foodId as class name for now
                "quantity": int(quantity),
                "imagePath": str(image_path),
                "action": "added",  # Determine action from context (added/removed/updated)
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }
            print(json.dumps(data))
            logger.debug(f"FRT update: {quantity} of {food_id} at {image_path}")
        except Exception as e:
            logger.error(f"Error processing UIUpdateRequired signal: {e}")

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
    listener = InventoryListener()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        listener.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting Inventory D-Bus Listener")
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
