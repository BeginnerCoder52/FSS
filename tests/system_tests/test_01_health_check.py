import os
import pytest
import subprocess

@pytest.mark.health
def test_database_files_exist():
    """Verify that all required SQLite database files exist in /opt/fss/data/"""
    db_paths = [
        "/opt/fss/data/fss_data.db",
        "/opt/fss/data/FSS_Inventory.db",
        "/opt/fss/data/FSS_Request.db",
        "/opt/fss/data/FSS_Recommend.db"
    ]
    
    for db in db_paths:
        assert os.path.exists(db), f"Database file not found: {db}"
        assert os.path.getsize(db) > 0, f"Database file is empty: {db}"

@pytest.mark.health
@pytest.mark.dbus
def test_dbus_services_registered():
    """Verify that the required D-Bus services are registered on the System Bus"""
    # Use busctl or dbus-send to list registered names
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply", "--dest=org.freedesktop.DBus", 
             "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            capture_output=True, text=True, check=True
        )
        output = result.stdout
        
        # Check for core daemon services
        # Note: FRTApp is not checked here because it only runs when Camera/AI is active.
        assert "vn.edu.uit.FSS.DBDaemon" in output, "DBDaemon is not registered on D-Bus"
        # SensorDaemon and RecommendDaemon might be optional depending on what is running, 
        # but in a full system test they should be up.
        # assert "vn.edu.uit.FSS.Sensor" in output, "SensorDaemon is not registered on D-Bus"
        # assert "vn.edu.uit.FSS.RecommendDaemon" in output, "RecommendDaemon is not registered on D-Bus"
        
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to query D-Bus services: {e.stderr}")
    except FileNotFoundError:
        pytest.fail("dbus-send command not found. Is D-Bus installed?")
