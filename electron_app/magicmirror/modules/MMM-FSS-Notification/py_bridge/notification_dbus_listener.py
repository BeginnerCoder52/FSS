#!/usr/bin/env python3
"""
@file notification_dbus_listener.py
@brief D-Bus listener for food added/removed notifications.
"""

import sys
import json
import asyncio
import logging
import signal
import time
import os

def get_dbus_config():
    config_path = os.environ.get("FSS_CONFIG_PATH", "")
    if not config_path:
        candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../config.json")),
            "/opt/fss/config.json",
            "/etc/fss/config.json",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                config_path = candidate
                break
    if config_path:
        try:
            with open(config_path, "r") as f:
                return json.load(f).get("dbus", {})
        except Exception as e:
            logging.warning(f"Failed to load config from {config_path}: {e}")
    return {}

dbus_config = get_dbus_config()

try:
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async, set_default_bus, sd_bus_open_system
    set_default_bus(sd_bus_open_system())
except ImportError:
    print("ERROR: sdbus package not installed. Install with: pip install python-sdbus", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="[NotificationListener] %(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

class DbDaemonNotificationProxy(DbusInterfaceCommonAsync, interface_name=dbus_config.get("dbdaemon_interface", "vn.edu.uit.FSS.DBDaemon")):
    @dbus_signal_async("ss")
    def FoodNotification(self) -> None:
        pass

class NotificationListener:
    DBUS_SERVICE = dbus_config.get("dbdaemon_service", "vn.edu.uit.FSS.DBDaemon")
    DBUS_PATH = dbus_config.get("dbdaemon_path", "/vn/edu/uit/FSS/DBDaemon")

    def __init__(self):
        self.running = True
        self.dbus_proxy = None

    async def connect_and_listen(self):
        try:
            logger.info(f"Connecting to {self.DBUS_SERVICE} D-Bus signals...")
            self.dbus_proxy = DbDaemonNotificationProxy.new_proxy(self.DBUS_SERVICE, self.DBUS_PATH)
            logger.info("Connected to DBDaemon - listening for notifications")
            print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon"}), flush=True)

            async for notif_type, message in self.dbus_proxy.FoodNotification:
                data = {
                    "type": "FSS_NOTIFICATION",
                    "payload": {
                        "type": notif_type,
                        "message": message
                    }
                }
                print(json.dumps(data), flush=True)
                logger.info(f"Notification sent: {message}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in NotificationListener: {e}")
            if self.running:
                await asyncio.sleep(5)
                await self.connect_and_listen()

    def stop(self):
        self.running = False

async def main():
    listener = NotificationListener()
    
    def handle_signal(signum, frame):
        listener.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    await listener.connect_and_listen()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
