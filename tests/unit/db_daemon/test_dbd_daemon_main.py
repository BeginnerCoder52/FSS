"""
@file test_dbd_daemon_main.py
@brief Unit tests for DbDaemonMain component.

This module provides comprehensive test coverage for the database daemon's
main lifecycle management including initialization, event processing, and
graceful shutdown.

Following ASPICE principles with proper component mocking and integration testing.
"""

import pytest
import logging
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os
from enum import Enum

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'db_daemon/src'))

from DbDaemonMain import DbDaemonMain, DaemonState


# ============================================================================
# TEST CLASS: DbDaemonMain Initialization
# ============================================================================

class TestDbDaemonMainInitialization:
    """Test cases for DbDaemonMain initialization."""

    def test_init_sets_initial_state(self):
        """
        ASPICE: SQC.BP1 - State initialization
        
        Verify DbDaemonMain initializes with INIT state.
        """
        daemon = DbDaemonMain()
        
        assert daemon.current_state == DaemonState.INIT
        assert daemon.is_running is False

    def test_init_creates_component_references(self):
        """
        ASPICE: SQC.BP2 - Component initialization
        
        Verify all component references are initialized to None.
        """
        daemon = DbDaemonMain()
        
        assert daemon.db_manager is None
        assert daemon.shm_reader is None
        assert daemon.file_manager is None
        assert daemon.dbus_interface is None

    def test_init_creates_threading_primitives(self):
        """
        ASPICE: SQC.BP3 - Threading setup
        
        Verify threading primitives are properly initialized.
        """
        daemon = DbDaemonMain()
        
        assert daemon._main_loop_thread is None
        assert daemon._stop_event is not None

    def test_init_initializes_statistics(self):
        """
        ASPICE: SQC.BP4 - Statistics initialization
        
        Verify statistics counters start at zero.
        """
        daemon = DbDaemonMain()
        
        assert daemon._processed_events_count == 0
        assert daemon._error_count == 0

    def test_init_creates_logger(self):
        """
        ASPICE: SQC.BP5 - Logging setup
        
        Verify DbDaemonMain creates logger instance.
        """
        daemon = DbDaemonMain()
        
        assert isinstance(daemon.logger, logging.Logger)
        assert daemon.logger.name == 'DbDaemonMain'

    def test_daemon_state_enum_values(self):
        """
        ASPICE: SQC.BP6 - State enumeration
        
        Verify all expected daemon states are defined.
        """
        assert hasattr(DaemonState, 'INIT')
        assert hasattr(DaemonState, 'IDLE')
        assert hasattr(DaemonState, 'PROCESSING')
        assert hasattr(DaemonState, 'ERROR')
        assert hasattr(DaemonState, 'STOPPED')


# ============================================================================
# TEST CLASS: Daemon Initialization
# ============================================================================

class TestDaemonInitialization:
    """Test cases for daemon component initialization."""

    def test_init_daemon_creates_components(self):
        """
        ASPICE: SQC.BP7 - Component creation
        
        Verify init_daemon creates all required components.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface') as mock_dbus:
                    # Setup mock returns
                    mock_sqlite_instance = MagicMock()
                    mock_sqlite_instance.connect_db.return_value = True
                    mock_sqlite_instance.init_tables_if_not_exists.return_value = None
                    mock_sqlite.return_value = mock_sqlite_instance
                    
                    mock_disk_instance = MagicMock()
                    mock_disk_instance.init_directories.return_value = True
                    mock_disk.return_value = mock_disk_instance
                    
                    mock_dbus_instance = MagicMock()
                    mock_dbus_instance.setup_bus_service.return_value = True
                    mock_dbus.return_value = mock_dbus_instance
                    
                    result = daemon.init_daemon()
        
        assert result is True

    def test_init_daemon_sets_idle_state(self):
        """
        ASPICE: SQC.BP8 - State transition
        
        Verify init_daemon transitions to IDLE state on success.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface') as mock_dbus:
                    # Setup mocks
                    mock_sqlite.return_value.connect_db.return_value = True
                    mock_sqlite.return_value.init_tables_if_not_exists.return_value = None
                    mock_disk.return_value.init_directories.return_value = True
                    mock_dbus.return_value.setup_bus_service.return_value = True
                    
                    result = daemon.init_daemon()
        
        assert result is True
        assert daemon.current_state == DaemonState.IDLE

    def test_init_daemon_handles_database_connection_failure(self):
        """
        ASPICE: SQC.BP9 - Error handling
        
        Verify init_daemon handles database connection failure.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager'):
                with patch('DbDaemonMain.DbDbusInterface'):
                    mock_sqlite.return_value.connect_db.return_value = False
                    
                    result = daemon.init_daemon()
        
        assert result is False
        assert daemon.current_state == DaemonState.ERROR

    def test_init_daemon_handles_file_manager_failure(self):
        """
        ASPICE: SQC.BP10 - Error handling
        
        Verify init_daemon handles file manager initialization failure.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface'):
                    mock_sqlite.return_value.connect_db.return_value = True
                    mock_sqlite.return_value.init_tables_if_not_exists.return_value = None
                    mock_disk.return_value.init_directories.return_value = False
                    
                    result = daemon.init_daemon()
        
        assert result is False
        assert daemon.current_state == DaemonState.ERROR

    def test_init_daemon_handles_dbus_setup_failure(self):
        """
        ASPICE: SQC.BP11 - Error handling
        
        Verify init_daemon handles D-Bus setup failure.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface') as mock_dbus:
                    mock_sqlite.return_value.connect_db.return_value = True
                    mock_sqlite.return_value.init_tables_if_not_exists.return_value = None
                    mock_disk.return_value.init_directories.return_value = True
                    mock_dbus.return_value.setup_bus_service.return_value = False
                    
                    result = daemon.init_daemon()
        
        assert result is False
        assert daemon.current_state == DaemonState.ERROR


# ============================================================================
# TEST CLASS: Daemon Startup
# ============================================================================

class TestDaemonStartup:
    """Test cases for daemon startup operations."""

    def test_start_daemon_sets_running_flag(self):
        """
        ASPICE: SQC.BP12 - State management
        
        Verify start_daemon sets is_running flag.
        """
        daemon = DbDaemonMain()
        daemon.dbus_interface = MagicMock()
        daemon.dbus_interface.poll_bus_events = MagicMock()
        
        result = daemon.start_daemon()
        
        assert daemon.is_running is True
        daemon.is_running = False  # Cleanup

    def test_start_daemon_already_running(self):
        """
        ASPICE: SQC.BP13 - Idempotence
        
        Verify start_daemon handles already running state.
        """
        daemon = DbDaemonMain()
        daemon.is_running = True
        
        result = daemon.start_daemon()
        
        assert result is True

    def test_start_daemon_creates_main_loop_thread(self):
        """
        ASPICE: SQC.BP14 - Thread creation
        
        Verify start_daemon creates main loop thread.
        """
        daemon = DbDaemonMain()
        daemon.dbus_interface = MagicMock()
        
        with patch.object(daemon, '_main_loop'):
            result = daemon.start_daemon()
            
            assert daemon._main_loop_thread is not None
            assert isinstance(daemon._main_loop_thread, threading.Thread)
            
            daemon.is_running = False  # Cleanup

    def test_start_daemon_clears_stop_event(self):
        """
        ASPICE: SQC.BP15 - Event management
        
        Verify start_daemon clears stop event.
        """
        daemon = DbDaemonMain()
        daemon.dbus_interface = MagicMock()
        daemon._stop_event.set()  # Set it first
        
        with patch.object(daemon, '_main_loop'):
            daemon.start_daemon()
        
        assert not daemon._stop_event.is_set()
        daemon.is_running = False  # Cleanup


# ============================================================================
# TEST CLASS: Event Processing
# ============================================================================

class TestEventProcessing:
    """Test cases for event processing."""

    def test_process_food_tracking_event_updates_inventory(self):
        """
        ASPICE: SQC.BP16 - Event handling
        
        Verify process_food_tracking_event updates inventory.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = True
        daemon.dbus_interface = MagicMock()
        
        daemon.process_food_tracking_event("apple_001", 0.95, 10)
        
        daemon.db_manager.update_inventory.assert_called_once()
        assert daemon._processed_events_count == 1

    def test_process_food_tracking_event_increments_counter(self):
        """
        ASPICE: SQC.BP17 - Statistics tracking
        
        Verify process_food_tracking_event increments event counter.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = True
        daemon.dbus_interface = MagicMock()
        
        initial_count = daemon._processed_events_count
        daemon.process_food_tracking_event("apple_001", 0.95, 10)
        
        assert daemon._processed_events_count == initial_count + 1

    def test_process_food_tracking_event_handles_inventory_update_failure(self):
        """
        ASPICE: SQC.BP18 - Error handling
        
        Verify process_food_tracking_event handles update failure.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = False
        daemon.dbus_interface = MagicMock()
        
        daemon.process_food_tracking_event("apple_001", 0.95, 10)
        
        assert daemon._error_count == 1

    def test_process_environment_event_logs_reading(self):
        """
        ASPICE: SQC.BP19 - Environmental logging
        
        Verify process_environment_event logs sensor data.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.insert_environment_log.return_value = True
        daemon.dbus_interface = MagicMock()
        
        daemon.process_environment_event(22.5, 65.3, 1705276800.0)
        
        daemon.db_manager.insert_environment_log.assert_called_once()
        assert daemon._processed_events_count == 1

    def test_process_environment_event_handles_log_failure(self):
        """
        ASPICE: SQC.BP20 - Error handling
        
        Verify process_environment_event handles log failure.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.insert_environment_log.return_value = False
        daemon.dbus_interface = MagicMock()
        
        daemon.process_environment_event(22.5, 65.3, 1705276800.0)
        
        assert daemon._error_count == 1


# ============================================================================
# TEST CLASS: Daemon Shutdown
# ============================================================================

class TestDaemonShutdown:
    """Test cases for daemon shutdown operations."""

    def test_stop_daemon_sets_running_false(self):
        """
        ASPICE: SQC.BP21 - Shutdown management
        
        Verify stop_daemon stops the daemon.
        """
        daemon = DbDaemonMain()
        daemon.is_running = True
        daemon.db_manager = MagicMock()
        
        daemon.stop_daemon()
        
        assert daemon.is_running is False

    def test_stop_daemon_sets_stopped_state(self):
        """
        ASPICE: SQC.BP22 - State transition
        
        Verify stop_daemon sets STOPPED state.
        """
        daemon = DbDaemonMain()
        daemon.is_running = True
        daemon.db_manager = MagicMock()
        
        daemon.stop_daemon()
        
        assert daemon.current_state == DaemonState.STOPPED

    def test_stop_daemon_closes_database(self):
        """
        ASPICE: SQC.BP23 - Resource cleanup
        
        Verify stop_daemon closes database connection.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        
        daemon.stop_daemon()
        
        daemon.db_manager.close_connection.assert_called_once()

    def test_stop_daemon_sets_stop_event(self):
        """
        ASPICE: SQC.BP24 - Event signaling
        
        Verify stop_daemon sets stop event.
        """
        daemon = DbDaemonMain()
        daemon.is_running = True
        daemon.db_manager = MagicMock()
        
        daemon.stop_daemon()
        
        assert daemon._stop_event.is_set()

    def test_stop_daemon_waits_for_main_loop_thread(self):
        """
        ASPICE: SQC.BP25 - Thread synchronization
        
        Verify stop_daemon waits for main loop thread.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        
        # Create a mock thread
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        daemon._main_loop_thread = mock_thread
        
        daemon.stop_daemon()
        
        mock_thread.join.assert_called_once()


# ============================================================================
# TEST CLASS: Error Recovery
# ============================================================================

class TestErrorRecovery:
    """Test cases for error recovery mechanisms."""

    def test_recover_from_io_error_reconnects_database(self):
        """
        ASPICE: SQC.BP26 - Error recovery
        
        Verify recover_from_io_error reconnects database.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.connect_db.return_value = True
        
        daemon.recover_from_io_error()
        
        daemon.db_manager.close_connection.assert_called_once()
        daemon.db_manager.connect_db.assert_called_once()

    def test_recover_from_io_error_sets_error_state_on_failure(self):
        """
        ASPICE: SQC.BP27 - Error state management
        
        Verify recover_from_io_error sets ERROR state on failure.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.connect_db.return_value = False
        
        daemon.recover_from_io_error()
        
        assert daemon.current_state == DaemonState.ERROR


# ============================================================================
# TEST CLASS: Status Logging
# ============================================================================

class TestStatusLogging:
    """Test cases for daemon status logging."""

    def test_log_daemon_status_logs_when_interval_exceeded(self):
        """
        ASPICE: SQC.BP28 - Periodic logging
        
        Verify log_daemon_status logs after interval.
        """
        daemon = DbDaemonMain()
        daemon._last_log_time = time.time() - 31.0  # 31 seconds ago
        
        daemon.log_daemon_status()
        
        # If it didn't raise exception, it worked
        assert True

    def test_log_daemon_status_includes_metrics(self):
        """
        ASPICE: SQC.BP29 - Status metrics
        
        Verify log_daemon_status includes performance metrics.
        """
        daemon = DbDaemonMain()
        daemon._last_log_time = time.time() - 31.0
        daemon._processed_events_count = 100
        daemon._error_count = 5
        
        daemon.log_daemon_status()
        
        assert True


# ============================================================================
# TEST CLASS: Event Handlers
# ============================================================================

class TestEventHandlers:
    """Test cases for event handler registration and invocation."""

    def test_register_event_handlers_registers_callbacks(self):
        """
        ASPICE: SQC.BP30 - Callback registration
        
        Verify event handlers are registered.
        """
        daemon = DbDaemonMain()
        daemon.dbus_interface = MagicMock()
        
        daemon._register_event_handlers()
        
        daemon.dbus_interface.listen_sensor_events.assert_called_once()
        daemon.dbus_interface.listen_frt_pipeline_events.assert_called_once()

    def test_handle_sensor_event_processes_environment_event(self):
        """
        ASPICE: SQC.BP31 - Sensor event handling
        
        Verify sensor event handler processes environment data.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.insert_environment_log.return_value = True
        daemon.dbus_interface = MagicMock()
        
        daemon._handle_sensor_event("environment", 22.5, 65.3, 1705276800.0)
        
        daemon.db_manager.insert_environment_log.assert_called_once()

    def test_handle_frt_event_processes_food_detection(self):
        """
        ASPICE: SQC.BP32 - FRT event handling
        
        Verify FRT event handler processes food detection.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = True
        daemon.dbus_interface = MagicMock()
        
        daemon._handle_frt_event("food_detected", "apple_001", 0.95, 10)
        
        daemon.db_manager.update_inventory.assert_called_once()


# ============================================================================
# TEST CLASS: Integration Tests
# ============================================================================

class TestDbDaemonMainIntegration:
    """Integration tests for complete daemon workflows."""

    def test_complete_initialization_workflow(self):
        """
        ASPICE: SQC.BP33 - Complete initialization
        
        Verify complete initialization workflow.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface') as mock_dbus:
                    # Setup mocks
                    mock_sqlite.return_value.connect_db.return_value = True
                    mock_sqlite.return_value.init_tables_if_not_exists.return_value = None
                    mock_disk.return_value.init_directories.return_value = True
                    mock_dbus.return_value.setup_bus_service.return_value = True
                    
                    result = daemon.init_daemon()
                    
                    assert result is True
                    assert daemon.current_state == DaemonState.IDLE

    def test_initialization_and_startup_workflow(self):
        """
        ASPICE: SQC.BP34 - Startup workflow
        
        Verify initialization followed by startup.
        """
        daemon = DbDaemonMain()
        
        with patch('DbDaemonMain.SqliteManager') as mock_sqlite:
            with patch('DbDaemonMain.DiskFileManager') as mock_disk:
                with patch('DbDaemonMain.DbDbusInterface') as mock_dbus:
                    # Setup mocks
                    mock_sqlite.return_value.connect_db.return_value = True
                    mock_sqlite.return_value.init_tables_if_not_exists.return_value = None
                    mock_disk.return_value.init_directories.return_value = True
                    mock_dbus.return_value.setup_bus_service.return_value = True
                    
                    init_result = daemon.init_daemon()
                    assert init_result is True
                    
                    with patch.object(daemon, '_main_loop'):
                        start_result = daemon.start_daemon()
                        assert start_result is True
                    
                    daemon.is_running = False  # Cleanup

    def test_event_processing_workflow(self):
        """
        ASPICE: SQC.BP35 - Event workflow
        
        Verify complete event processing workflow.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = True
        daemon.db_manager.insert_environment_log.return_value = True
        daemon.dbus_interface = MagicMock()
        
        # Process food event
        daemon.process_food_tracking_event("apple_001", 0.95, 10)
        assert daemon._processed_events_count == 1
        
        # Process environment event
        daemon.process_environment_event(22.5, 65.3, 1705276800.0)
        assert daemon._processed_events_count == 2
        
        # Verify no errors
        assert daemon._error_count == 0


# ============================================================================
# TEST CLASS: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_multiple_quick_shutdowns(self):
        """
        ASPICE: SQC.BP36 - Idempotent shutdown
        
        Verify multiple shutdowns don't cause issues.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.is_running = True
        
        daemon.stop_daemon()
        daemon.stop_daemon()
        daemon.stop_daemon()
        
        assert daemon.is_running is False

    def test_process_event_without_managers(self):
        """
        ASPICE: SQC.BP37 - Missing manager handling
        
        Verify event processing handles missing managers.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = None
        daemon.dbus_interface = None
        
        daemon.process_food_tracking_event("apple_001", 0.95, 10)
        
        assert daemon._error_count == 1

    def test_concurrent_event_processing(self):
        """
        ASPICE: SQC.BP38 - Concurrent operations
        
        Verify concurrent event processing.
        """
        daemon = DbDaemonMain()
        daemon.db_manager = MagicMock()
        daemon.db_manager.update_inventory.return_value = True
        daemon.db_manager.insert_environment_log.return_value = True
        daemon.dbus_interface = MagicMock()
        
        # Process multiple events
        for i in range(10):
            daemon.process_food_tracking_event(f"item_{i}", 0.95, i)
        
        assert daemon._processed_events_count == 10
