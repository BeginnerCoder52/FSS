#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecommendDaemon D-Bus, relay results."""
import sys, json, asyncio, uuid, os, time

proxy = None

try:
    from sdbus import DbusInterfaceCommon, dbus_method

    def get_dbus_config():
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../config.json"))
        try:
            with open(config_path, "r") as f:
                return json.load(f).get("dbus", {})
        except Exception:
            return {}

    dbus_config = get_dbus_config()
    RECOMMEND_SERVICE = dbus_config.get("recommend_service", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_INTERFACE = dbus_config.get("recommend_interface", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_PATH = dbus_config.get("recommend_path", "/vn/edu/uit/FSS/RecommendDaemon")

    class RecommendDaemonInterface(DbusInterfaceCommon, interface_name=RECOMMEND_INTERFACE):
        @dbus_method('ss', 's')
        def GenerateShoppingList(self, recipe_name: str, batch_id: str) -> str:
            pass

    proxy = RecommendDaemonInterface.new_proxy(RECOMMEND_SERVICE, RECOMMEND_PATH)
except Exception as e:
    print(f"Warning: D-Bus not available ({e}). Running in MOCK mode.", file=sys.stderr)

for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        msg = json.loads(line)
        if msg.get("type") == "SEARCH":
            recipe = msg["recipe"]
            if recipe.lower() in ["test", "dev"]:
                # Mock Mode logic
                mock_data = {
                    "recipe_name": recipe,
                    "ingredients": [
                        {"name": "Gạo", "required": 1.0, "available": 1.0, "status": "available"},
                        {"name": "Mắm", "required": 1.0, "available": 0.0, "status": "missing"},
                        {"name": "Thịt", "required": 2.0, "available": 0.0, "status": "missing"}
                    ]
                }
                time.sleep(1.5) # Simulate processing time
                print(json.dumps({"type": "RESULT", "data": mock_data}), flush=True)
            else:
                if proxy is None:
                    raise Exception("D-Bus proxy is not initialized. Cannot process production request.")
                batch_id = str(uuid.uuid4())
                result = proxy.GenerateShoppingList(recipe, batch_id)
                print(json.dumps({"type": "RESULT", "data": json.loads(result)}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
