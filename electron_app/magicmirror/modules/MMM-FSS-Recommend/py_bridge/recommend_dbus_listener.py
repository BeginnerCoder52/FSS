#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecommendDaemon.GenerateShoppingList D-Bus, relay results."""
import sys, json, uuid, os, time, logging

proxy = None

try:
    from sdbus import DbusInterfaceCommon, dbus_method

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
    RECOMMEND_SERVICE = dbus_config.get("recommend_daemon_service", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_INTERFACE = dbus_config.get("recommend_daemon_interface", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_PATH = dbus_config.get("recommend_daemon_path", "/vn/edu/uit/FSS/RecommendDaemon")

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
                mock_data = {
                    "status": "SUCCESS",
                    "recipe_name": recipe,
                    "batch_id": "mock-batch-id",
                    "total_items": 3,
                    "available_count": 0,
                    "needed_count": 0,
                    "missing_count": 3,
                    "ingredients": [
                        {"name": "Gạo", "required": "1", "available": 0, "shortage": 1, "status": "missing"},
                        {"name": "Mắm", "required": "1", "available": 0, "shortage": 1, "status": "missing"},
                        {"name": "Thịt", "required": "2", "available": 0, "shortage": 2, "status": "missing"},
                    ],
                    "summary": "\u274c Còn thiếu 3 nguyên liệu"
                }
                time.sleep(1.5)
                print(json.dumps({"type": "RESULT", "data": mock_data}), flush=True)
            else:
                if proxy is None:
                    raise Exception("D-Bus proxy is not initialized. Cannot process production request.")
                batch_id = str(uuid.uuid4())
                raw_result = proxy.GenerateShoppingList(recipe, batch_id)
                parsed = json.loads(raw_result)
                if parsed.get("status") == "ERROR":
                    print(json.dumps({"type": "ERROR", "message": parsed.get("error", "Unknown error")}), flush=True)
                else:
                    print(json.dumps({"type": "RESULT", "data": parsed}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
