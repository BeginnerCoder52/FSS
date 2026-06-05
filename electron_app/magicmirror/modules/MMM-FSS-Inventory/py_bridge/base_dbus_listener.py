#!/usr/bin/env python3
"""
@file base_dbus_listener.py
@brief Base class for FSS D-Bus listeners with common error handling and reconnection.

This module centralizes:
- D-Bus connection management
- Signal subscriptions
- JSON output formatting
- Graceful shutdown handling
- Exponential backoff reconnection
"""

import sys
import json
import asyncio
import logging
import signal
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

try:
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async
except ImportError:
    print("ERROR: sdbus package not installed", file=sys.stderr)
    sys.exit(1)


@dataclass
class ListenerConfig:
    """Configuration for D-Bus listener."""
    dbus_service: str = "vn.edu.uit.FSS.DBDaemon"
    dbus_path: str = "/vn/edu/uit/FSS/DBDaemon"
    dbus_interface: str = "vn.edu.uit.FSS.DBDaemon"
    max_reconnect_attempts: int = 10
    max_reconnect_delay: float = 30.0
    reconnect_base_delay: float = 1.0
    log_level: str = "INFO"


class DbusListenerBase(ABC):
    """Base class for FSS D-Bus listeners."""

    def __init__(self, config: ListenerConfig):
        self.config = config
        self.running = True
        self.reconnect_attempts = 0
        self.dbus_proxy: Optional[DbusInterfaceCommonAsync] = None
        self.signal_tasks: List[asyncio.Task] = []

        # Setup logging (stderr only, stdout reserved for JSON)
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format=f"[{self.__class__.__name__}] %(levelname)s: %(message)s",
            stream=sys.stderr,
            force=True,
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        # Register shutdown handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle SIGTERM/SIGINT gracefully."""
        self.logger.info(f"Received signal {signum} - initiating graceful shutdown")
        self.stop()

    def stop(self) -> None:
        """Mark the listener to stop."""
        self.running = False

    def _backoff_delay(self) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.reconnect_base_delay * (2 ** (self.reconnect_attempts - 1))
        return min(delay, self.config.max_reconnect_delay)

    def _emit_json(self, data: Dict[str, Any]) -> None:
        """Emit JSON to stdout with flush."""
        print(json.dumps(data), flush=True)

    def emit_error(self, code: str, message: str) -> None:
        """Emit structured error to frontend via stdout."""
        self._emit_json({
            "type": "ERROR",
            "code": code,
            "message": message,
            "timestamp": int(datetime.now().timestamp() * 1000),
        })
        self.logger.error(f"Error {code}: {message}")

    def emit_status(self, message: str) -> None:
        """Emit status message."""
        self._emit_json({
            "type": "STATUS",
            "message": message,
            "timestamp": int(datetime.now().timestamp() * 1000),
        })

    @abstractmethod
    async def _listen_signals(self) -> None:
        """Implement signal listening logic."""
        pass

    async def connect_dbus(self) -> None:
        """Establish D-Bus connection and subscribe to signals."""
        if not self.running:
            return

        try:
            self.logger.info(f"Connecting to {self.config.dbus_service}...")
            self.dbus_proxy = DbusInterfaceCommonAsync.new_proxy(
                self.config.dbus_service,
                self.config.dbus_path,
            )
            self.reconnect_attempts = 0
            self.emit_status(f"Connected to {self.config.dbus_service}")

            # Start listening tasks
            task = asyncio.create_task(self._listen_signals())
            self.signal_tasks.append(task)
            await asyncio.gather(task)

        except Exception as e:
            self.logger.error(f"D-Bus connection error: {e}")
            if self.running:
                await self._attempt_reconnect()

    async def _attempt_reconnect(self) -> None:
        """Exponential backoff reconnection."""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached - exiting")
            self.stop()
            return

        self.reconnect_attempts += 1
        delay = self._backoff_delay()
        self.logger.info(
            f"Reconnecting in {delay:.1f}s "
            f"(attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        if self.running:
            await self.connect_dbus()

    async def cleanup(self) -> None:
        """Cancel signal tasks."""
        for task in self.signal_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.signal_tasks.clear()

    async def run(self) -> None:
        """Main entry point."""
        self.logger.info("Starting D-Bus listener")
        await self.connect_dbus()

    async def __aenter__(self) -> "DbusListenerBase":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.cleanup()


# Convenience function for listeners that only need one signal
async def run_simple_listener(
    listener_class,
    config: ListenerConfig,
    *signal_names: str,
) -> None:
    """Run a simple listener with one signal subscription."""
    listener = listener_class(config)

    def signal_handler(signum, frame):
        listener.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await listener.run()
    except Exception as e:
        listener.logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await listener.cleanup()
