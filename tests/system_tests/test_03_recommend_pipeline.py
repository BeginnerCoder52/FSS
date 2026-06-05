import os
import json
import sqlite3
import pytest
import subprocess
import time

DB_PATH = "/opt/fss/data/FSS-Recommend.db"

def check_batch_in_db(batch_id: str) -> bool:
    """Check if the given batch_id exists in the recommendation_log table."""
    if not os.path.exists(DB_PATH):
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM recommendation_log WHERE batch_id = ?", (batch_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except sqlite3.Error:
        return False

@pytest.mark.e2e
@pytest.mark.dbus
def test_recommend_get_available_recipes():
    """Test calling GetAvailableRecipes via D-Bus."""
    try:
        result = subprocess.run([
            "dbus-send", "--system", "--print-reply", 
            "--dest=vn.edu.uit.FSS.RecommendDaemon", 
            "/vn/edu/uit/FSS/RecommendDaemon", 
            "vn.edu.uit.FSS.RecommendDaemon.GetAvailableRecipes"
        ], capture_output=True, text=True, check=True)
        
        # dbus-send output format: string "[...]"
        assert "string" in result.stdout
        # Output should be a JSON array string
        # We can loosely check if the response was successful
    except subprocess.CalledProcessError as e:
        # If RecommendDaemon is not running, this will fail
        pytest.fail(f"D-Bus call failed: {e.stderr}")

@pytest.mark.e2e
@pytest.mark.dbus
def test_recommend_generate_shopping_list():
    """Test the recommendation pipeline by requesting a shopping list."""
    # Use a unique batch ID
    batch_id = f"test_batch_{int(time.time())}"
    recipe_name = "Mock Recipe" # Even if it doesn't exist, it should create an entry with status ERROR or similar
    
    try:
        # GenerateShoppingList takes 2 strings: recipe_name and batch_id
        result = subprocess.run([
            "dbus-send", "--system", "--print-reply", 
            "--dest=vn.edu.uit.FSS.RecommendDaemon", 
            "/vn/edu/uit/FSS/RecommendDaemon", 
            "vn.edu.uit.FSS.RecommendDaemon.GenerateShoppingList",
            f"string:{recipe_name}", f"string:{batch_id}"
        ], capture_output=True, text=True, check=True)
        
        assert "string" in result.stdout
        
        # Give RecommendDaemon a moment to process the NLP and DB insertion
        time.sleep(2.0)
        
        # Verify it was inserted into the database
        assert check_batch_in_db(batch_id), f"Batch {batch_id} not found in database {DB_PATH}"
        
    except subprocess.CalledProcessError as e:
        pytest.fail(f"D-Bus call failed: {e.stderr}")
