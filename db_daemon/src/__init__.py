"""
@package db_daemon
@brief Database Daemon package for the Fridge Supervisor System.

This package provides database management, D-Bus inter-process communication,
and file system operations for the FSS. It handles data persistence from
SensorDaemon and FRTApp, and provides interfaces to the Electron UI.

Modules:
    - SqliteManager: SQLite database operations
    - PosixShmReader: Shared memory management for FRTApp integration
    - DiskFileManager: Filesystem operations for asset storage
    - DbDbusInterface: D-Bus IPC communication
    - DbDaemonMain: Core daemon orchestration

ASPICE Compliance:
    - Structured module organization
    - Comprehensive error handling
    - Clean code principles with proper documentation
    - Logging for debugging and monitoring

Feature Flags:
    - FRT_APP_ENABLED: Enable/disable FRTApp integration (see PosixShmReader)
"""

__version__ = "1.0.0"
__author__ = "FSS Development Team"
__all__ = [
    "SqliteManager",
    "PosixShmReader",
    "DiskFileManager",
    "DbDbusInterface",
    "DbDaemonMain",
]

# Import main classes for convenient access
from SqliteManager import SqliteManager
from PosixShmReader import PosixShmReader, FRT_APP_ENABLED
from DiskFileManager import DiskFileManager
from DbDbusInterface import DbDbusInterface
from DbDaemonMain import DbDaemonMain, DaemonState

__all__.extend(["DaemonState"])
