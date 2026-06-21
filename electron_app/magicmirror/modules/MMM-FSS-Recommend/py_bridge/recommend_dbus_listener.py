#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecommendDaemon.GenerateShoppingList D-Bus, relay results."""
import sys, json, uuid, os, time, logging

proxy = None
_service_checked = False

try:
    from sdbus import DbusInterfaceCommon, dbus_method
    from sdbus import sd_bus_open_system, set_default_bus

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

    set_default_bus(sd_bus_open_system())

    dbus_config = get_dbus_config()
    RECOMMEND_SERVICE = dbus_config.get("recommend_daemon_service", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_INTERFACE = dbus_config.get("recommend_daemon_interface", "vn.edu.uit.FSS.RecommendDaemon")
    RECOMMEND_PATH = dbus_config.get("recommend_daemon_path", "/vn/edu/uit/FSS/RecommendDaemon")

    class RecommendDaemonInterface(DbusInterfaceCommon, interface_name=RECOMMEND_INTERFACE):
        @dbus_method('ss', 's')
        def GenerateShoppingList(self, recipe_name: str, batch_id: str) -> str:
            pass

    proxy = RecommendDaemonInterface(RECOMMEND_SERVICE, RECOMMEND_PATH)
except Exception as e:
    print(f"Warning: D-Bus not available ({e}). Running in MOCK mode.", file=sys.stderr)


def wait_for_service(timeout=5):
    import subprocess, sys
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["dbus-send", "--system", "--print-reply",
                 "--dest=org.freedesktop.DBus",
                 "/org/freedesktop/DBus", "org.freedesktop.DBus.NameHasOwner",
                 f"string:{RECOMMEND_SERVICE}"],
                capture_output=True, text=True, timeout=3
            )
            if "true" in result.stdout:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


KNOWN_RECIPES = [
    "Phở bò", "Phở gà", "Bún chả", "Bún bò Huế", "Bún riêu cua",
    "Cơm tấm", "Cơm chiên", "Cơm gà", "Cơm rang",
    "Bánh mì", "Bánh xèo", "Bánh cuốn",
    "Gỏi cuốn", "Chả giò", "Nem rán",
    "Thịt kho tàu", "Cá kho tộ", "Gà kho gừng",
    "Canh chua cá", "Canh rau củ", "Canh măng",
    "Rau muống xào tỏi", "Bò xào", "Tôm xào",
    "Lẩu Thái", "Lẩu gà", "Lẩu bò",
    "Trứng chiên", "Đậu hũ sốt cà chua",
    "Bún thịt nướng", "Hủ tiếu Nam Vang",
]

MOCK_DATA_TEMPLATE = {
    "status": "SUCCESS",
    "pipeline_time_ms": 1500,
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


def handle_search(recipe):
    if proxy is not None and wait_for_service(timeout=2):
        try:
            batch_id = str(uuid.uuid4())
            raw_result = proxy.GenerateShoppingList(recipe, batch_id)
            parsed = json.loads(raw_result)
            if parsed.get("status") == "ERROR":
                print(json.dumps({"type": "ERROR",
                    "message": parsed.get("error", "Unknown error")}), flush=True)
            else:
                print(json.dumps({"type": "RESULT", "data": parsed}), flush=True)
            return
        except Exception as e:
            logging.warning(f"D-Bus call failed, falling back to mock: {e}")

    # Fallback: return mock data for any recipe
    result = dict(MOCK_DATA_TEMPLATE)
    result["recipe_name"] = recipe
    result["batch_id"] = "mock-batch-id"
    time.sleep(1.5)
    print(json.dumps({"type": "RESULT", "data": result}), flush=True)


while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
        msg_type = msg.get("type")
        if msg_type == "SEARCH":
            handle_search(msg["recipe"])
        elif msg_type == "GET_RECIPES":
            print(json.dumps({"type": "RECIPES", "data": KNOWN_RECIPES}), flush=True)
        elif msg_type == "GET_RECIPE_DETAIL":
            recipe_name = msg.get("recipe", "")
            detail = {
                "recipe_name": recipe_name,
                "status": "SUCCESS",
                "serving": "4 người",
                "times": "30 Phút",
                "difficulty": "Dễ",
                "original_ingredients": [
                    "Nguyên liệu 1 : 100g",
                    "Nguyên liệu 2 : 200g",
                    "Nguyên liệu 3 : 1 muỗng",
                ],
                "original_spices": ["Muối", "Tiêu", "Đường"],
                "process": ["Bước sơ chế 1", "Bước sơ chế 2"],
                "cook": ["Bước nấu 1", "Bước nấu 2"],
                "usage": ["Dùng nóng với cơm"],
                "tips": "Mẹo nhỏ cho món ăn thêm ngon",
                "total_items": 3,
                "ingredients": [
                    {"name": "Nguyên liệu 1", "required": "100g", "available": 0, "shortage": 100, "status": "missing"},
                    {"name": "Nguyên liệu 2", "required": "200g", "available": 0, "shortage": 200, "status": "missing"},
                    {"name": "Nguyên liệu 3", "required": "1 muỗng", "available": 0, "shortage": 1, "status": "missing"},
                ],
                "summary": "❌ Còn thiếu 3 nguyên liệu",
                "pipeline_time_ms": 0.5,
            }
            print(json.dumps({"type": "RESULT", "data": detail}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
