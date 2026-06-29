#!/usr/bin/env python3
"""
Emit SensorDaemon-compatible door signals for FRTApp demos.

The real SensorDaemon emits DoorStateChanged on:
    service:   vn.edu.uit.FSS.Sensor
    path:      /vn/edu/uit/FSS/Sensor
    interface: vn.edu.uit.FSS.Sensor

Use this when demoing FRTApp + DBDaemon + Electron without physical MC-38 GPIO.
"""

import argparse
import asyncio
import time

try:
    import sdbus
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async
except ImportError as exc:
    raise SystemExit(
        "sdbus-python is required. Activate the FSS Python venv first."
    ) from exc


SERVICE_NAME = "vn.edu.uit.FSS.Sensor"
OBJECT_PATH = "/vn/edu/uit/FSS/Sensor"
INTERFACE_NAME = "vn.edu.uit.FSS.Sensor"


class SensorMockObject(DbusInterfaceCommonAsync, interface_name=INTERFACE_NAME):
    @dbus_signal_async("s")
    def DoorStateChanged(self, state: str) -> None:
        pass

    @dbus_signal_async("d")
    def DistanceDataChanged(self, distance_cm: float) -> None:
        pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Emit mock SensorDaemon D-Bus door signals."
    )
    parser.add_argument(
        "state",
        choices=["open", "close", "DOOR_OPEN", "DOOR_CLOSE"],
        help="Door state to emit.",
    )
    parser.add_argument("--distance", type=float, default=None,
                        help="Optionally emit DistanceDataChanged before the door signal.")
    parser.add_argument("--settle", type=float, default=1.0,
                        help="Seconds to stay alive after emitting. Default: 1.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    state = args.state.upper()
    if state == "OPEN":
        state = "DOOR_OPEN"
    elif state == "CLOSE":
        state = "DOOR_CLOSE"

    sdbus.set_default_bus(sdbus.sd_bus_open_system())
    await sdbus.request_default_bus_name_async(SERVICE_NAME, replace_existing=True)

    obj = SensorMockObject()
    obj.export_to_dbus(OBJECT_PATH)

    # Give already-started subscribers a small window to finish signal matching.
    await asyncio.sleep(0.2)

    if args.distance is not None:
        obj.DistanceDataChanged(args.distance)
        print(f"Emitted DistanceDataChanged({args.distance})", flush=True)
        await asyncio.sleep(0.1)

    obj.DoorStateChanged(state)
    print(f"Emitted DoorStateChanged({state})", flush=True)

    await asyncio.sleep(args.settle)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
