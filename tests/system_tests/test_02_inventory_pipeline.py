import os
import time
import json
import sqlite3
import pytest
import subprocess
import tempfile

DB_PATH = "/opt/fss/data/FSS_Inventory.db"

def get_food_quantity(food_id: str) -> int:
    """Helper to get current quantity of a food item from DB."""
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM current_inventory WHERE food_id = ?", (food_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except sqlite3.Error:
        return 0

def emit_food_detected(food_id: str, qty_delta: int):
    """Helper to emit FoodDetected signal via a temporary python script using sdbus."""
    payload = {"id": food_id, "score": 0.99, "qty": qty_delta}
    script = f"""
import asyncio
import json
import sdbus
from sdbus import DbusInterfaceCommonAsync, dbus_signal_async, sd_bus_open_system, set_default_bus, request_default_bus_name_async, sd_bus_internals

class MockFrt(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.FRTApp"):
    @dbus_signal_async('s')
    def FoodDetected(self, json_data: str) -> None:
        pass

async def main():
    set_default_bus(sd_bus_open_system())
    await request_default_bus_name_async("vn.edu.uit.FSS.FRTApp.TestRunner", replace_existing=True)
    mock = MockFrt()
    mock.export_to_dbus("/vn/edu/uit/FSS/FRTApp")
    
    # Emit signal
    mock.FoodDetected.emit(json.dumps({payload}))
    await asyncio.sleep(0.5)

asyncio.run(main())
"""
    # Write to a temporary file and run
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        temp_name = f.name
    
    try:
        # Assuming the test is run in db_daemon's venv where sdbus is installed
        subprocess.run(["python", temp_name], check=True)
    finally:
        os.remove(temp_name)

@pytest.mark.e2e
@pytest.mark.dbus
def test_inventory_pipeline_add_food():
    """Test if FRTApp FoodDetected (add) signal correctly updates SQLite via DBDaemon."""
    food_id = "test_apple_e2e"
    initial_qty = get_food_quantity(food_id)
    
    # Emit signal to add 2 apples
    emit_food_detected(food_id, 2)
    
    # Wait for DBDaemon to process
    time.sleep(2.0)
    
    new_qty = get_food_quantity(food_id)
    assert new_qty == initial_qty + 2, f"Expected {initial_qty + 2}, got {new_qty}"

@pytest.mark.e2e
@pytest.mark.dbus
def test_inventory_pipeline_remove_food():
    """Test if FRTApp FoodDetected (remove) signal correctly updates SQLite via DBDaemon."""
    food_id = "test_apple_e2e"
    initial_qty = get_food_quantity(food_id)
    
    # Ensure there's enough to remove
    if initial_qty < 1:
        emit_food_detected(food_id, 2)
        time.sleep(2.0)
        initial_qty = get_food_quantity(food_id)
        
    # Emit signal to remove 1 apple
    emit_food_detected(food_id, -1)
    
    # Wait for DBDaemon to process
    time.sleep(2.0)
    
    new_qty = get_food_quantity(food_id)
    assert new_qty == initial_qty - 1, f"Expected {initial_qty - 1}, got {new_qty}"
    
    # Cleanup (remove the remaining items)
    if new_qty > 0:
        emit_food_detected(food_id, -new_qty)
        time.sleep(1.0)
