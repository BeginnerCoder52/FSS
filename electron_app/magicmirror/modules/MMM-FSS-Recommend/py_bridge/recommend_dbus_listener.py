#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecipeExtractor D-Bus, relay results."""
import sys, json, asyncio, uuid, os, time, logging, traceback

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
    RECIPE_EXTRACTOR_SERVICE = dbus_config.get("recipe_extractor_service", "vn.edu.uit.FSS.RecipeExtractor")
    RECIPE_EXTRACTOR_INTERFACE = dbus_config.get("recipe_extractor_interface", "vn.edu.uit.FSS.RecipeExtractor")
    RECIPE_EXTRACTOR_PATH = dbus_config.get("recipe_extractor_path", "/vn/edu/uit/FSS/RecipeExtractor")

    class RecipeExtractorInterface(DbusInterfaceCommon, interface_name=RECIPE_EXTRACTOR_INTERFACE):
        @dbus_method('s', 's')
        def ExtractAndPersistRecipe(self, recipe_name: str) -> str:
            pass

    proxy = RecipeExtractorInterface.new_proxy(RECIPE_EXTRACTOR_SERVICE, RECIPE_EXTRACTOR_PATH)
except Exception as e:
    print(f"Warning: D-Bus not available ({e}). Running in MOCK mode.", file=sys.stderr)


def transform_ingredients(result: dict) -> dict:
    """Transform RecipeExtractor format to frontend format.

    RecipeExtractor returns:
        {ingredient: "...", quantity: "500g"}

    Frontend expects:
        {name: "...", required: "500g", available: 0, status: "missing"}
    """
    raw_ingredients = result.get("ingredients", [])
    transformed = []
    for item in raw_ingredients:
        transformed.append({
            "name": item.get("ingredient", ""),
            "required": item.get("quantity", "1"),
            "available": 0,
            "status": "missing"
        })

    return {
        "recipe_name": result.get("dish", ""),
        "ingredients": transformed,
        "total_items": len(transformed),
        "available_count": 0,
        "needed_count": 0,
        "missing_count": len(transformed),
        "summary": f"Cần mua thêm {len(transformed)} nguyên liệu" if transformed else "Đã có đủ nguyên liệu!"
    }


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
                    "dish": recipe,
                    "ingredients": [
                        {"ingredient": "Gạo", "quantity": "1"},
                        {"ingredient": "Mắm", "quantity": "1"},
                        {"ingredient": "Thịt", "quantity": "2"}
                    ]
                }
                time.sleep(1.5)
                result = transform_ingredients(mock_data)
                print(json.dumps({"type": "RESULT", "data": result}), flush=True)
            else:
                if proxy is None:
                    raise Exception("D-Bus proxy is not initialized. Cannot process production request.")
                raw_result = proxy.ExtractAndPersistRecipe(recipe)
                parsed = json.loads(raw_result)
                if parsed.get("status") == "ERROR":
                    print(json.dumps({"type": "ERROR", "message": parsed.get("error", "Unknown error")}), flush=True)
                else:
                    result = transform_ingredients(parsed)
                    print(json.dumps({"type": "RESULT", "data": result}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
