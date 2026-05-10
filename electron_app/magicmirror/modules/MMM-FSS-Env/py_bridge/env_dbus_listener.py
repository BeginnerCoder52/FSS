#!/usr/bin/env python3
"""
/**
 * @file env_dbus_listener.py
 * @brief Context Bridge for Environmental signals (Dual SHT3x).
 *
 * ASPICE SWE.3 Detailed Design:
 * Listens to vn.edu.uit.FSS.DBDaemon on the System D-Bus for the 
 * 'EnvUpdateRequired' signal.
 * * Extracts both Sensor 1 (Ngan mat) and Sensor 2 (Ngan dong) data from the 
 * JSON payload and relays them via stdout to the Node.js helper.
 */
"""

import sys, json, asyncio
import sdbus
from sdbus import DbusInterfaceClientAsync, dbus_signal_async

class DbDaemonEnvClient(DbusInterfaceClientAsync):
    def __init__(self):
        super().__init__('vn.edu.uit.FSS.DBDaemon')

    @dbus_signal_async('dd')
    def EnvironmentUpdateRequired(self) -> sdbus.SignalMatch: pass

    @dbus_signal_async('dd')
    def SecondaryEnvironmentUpdateRequired(self) -> sdbus.SignalMatch: pass

async def main():
    try:
        # Open system bus and connect to DBDaemon proxy
        bus = sdbus.sd_bus_open_system()
        remote_object = sdbus.DbusRemoteObject(bus, "vn.edu.uit.FSS.DBDaemon", "/vn/edu/uit/FSS/DBDaemon")
        client = DbDaemonEnvClient()
        remote_object.add_interface(client)

        # Callbacks
        async def on_env_update(temp, humid):
            print(json.dumps({"type": "ENVIRONMENT_UPDATE", "temperature": float(temp), "humidity": float(humid)}), flush=True)

        async def on_sec_env_update(temp, humid):
            print(json.dumps({"type": "SECONDARY_ENVIRONMENT_UPDATE", "temperature": float(temp), "humidity": float(humid)}), flush=True)

        client.EnvironmentUpdateRequired.attach(on_env_update)
        client.SecondaryEnvironmentUpdateRequired.attach(on_sec_env_update)

        print(json.dumps({"type": "STATUS", "message": "Connected to DBDaemon Env"}), flush=True)
        
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())