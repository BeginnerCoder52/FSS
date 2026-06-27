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

        @dbus_method('', 's')
        def GetAvailableRecipes(self) -> str:
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


# ============================================================
# Local NLP Fallback (used when D-Bus / RecommendDaemon is down)
# Tries to import the recipe_extractor library directly from FSS repo.
# ============================================================
_local_nlp_engine = None
_local_nlp_attempted = False

def _get_local_nlp():
    """Lazy-load RecipeAnalyzerEngine from recipe_extractor if available."""
    global _local_nlp_engine, _local_nlp_attempted
    if _local_nlp_attempted:
        return _local_nlp_engine
    _local_nlp_attempted = True
    try:
        # Resolve path relative to this bridge file: ../../../../../../recipe_extractor/src
        bridge_dir = os.path.dirname(os.path.abspath(__file__))
        # go up: py_bridge -> MMM-FSS-Recommend -> modules -> magicmirror -> electron_app -> FSS
        fss_root = os.path.abspath(os.path.join(bridge_dir, "../../../../../"))
        recipe_src = os.path.join(fss_root, "recipe_extractor", "src")
        recipe_db  = os.path.join(fss_root, "recipe_extractor", "data", "recipes")
        if not os.path.isdir(recipe_db):
            logging.warning(f"[LocalNLP] recipe_db not found at {recipe_db}")
            return None
        if recipe_src not in sys.path:
            sys.path.insert(0, recipe_src)
        from RecipeAnalyzerAPI import RecipeAnalyzerEngine
        _local_nlp_engine = RecipeAnalyzerEngine(recipe_db_path=recipe_db)
        logging.info(f"[LocalNLP] Loaded RecipeAnalyzerEngine with {len(_local_nlp_engine.recipe_names)} recipes")
    except Exception as e:
        logging.warning(f"[LocalNLP] Cannot load RecipeAnalyzerEngine: {e}")
        _local_nlp_engine = None
    return _local_nlp_engine


def _local_nlp_search(recipe):
    """
    Run a local NLP lookup using recipe_extractor as D-Bus fallback.
    Returns a dict in the same format as RecommendDaemon's response.
    """
    engine = _get_local_nlp()
    if engine is None:
        return None

    t0 = time.time()
    # Try exact lookup first, then fuzzy
    result = engine.generate_fss_request(recipe)
    pipeline_ms = round((time.time() - t0) * 1000, 1)

    status = result.get("status", "")
    logging.info(f"[LocalNLP] '{recipe}' -> status={status} pipeline={pipeline_ms}ms")

    if status == "NOT_FOUND":
        # Return suggestions too so the UI can show fuzzy chips
        suggestions = engine._suggest_recipe(recipe)
        return {
            "status": "NOT_FOUND",
            "recipe_name": recipe,
            "message": result.get("message", "Recipe not found"),
            "suggestions": suggestions,
            "pipeline_time_ms": pipeline_ms
        }

    if status != "SUCCESS":
        return None

    # Build ingredients list in the same format as RecommendDaemon format_result_for_ui
    raw_ingredients = result.get("ingredients", [])
    ui_ingredients = []
    for ing in raw_ingredients:
        name = ing.get("ingredient", "")
        qty_str = ing.get("quantity", "1")
        ui_ingredients.append({
            "name": name,
            "required": qty_str,
            "available": 0,
            "shortage": 1,     # no inventory data in local mode
            "unit": None,
            "status": "missing"
        })

    missing_count = len(ui_ingredients)
    return {
        "status": "SUCCESS",
        "recipe_name": result.get("dish", recipe),
        "batch_id": "local-nlp",
        "pipeline_time_ms": pipeline_ms,
        "total_items": missing_count,
        "available_count": 0,
        "needed_count": 0,
        "missing_count": missing_count,
        "ingredients": ui_ingredients,
        "summary": f"\u274c C\u00f2n thi\u1ebfu {missing_count} nguy\u00ean li\u1ec7u (ch\u1ebf \u0111\u1ed9 offline)"
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
            logging.warning(f"D-Bus call failed, falling back to local NLP: {e}")

    # Fallback 1: try local NLP engine (real ingredients, no D-Bus needed)
    local_result = _local_nlp_search(recipe)
    if local_result is not None:
        print(json.dumps({"type": "RESULT", "data": local_result}), flush=True)
        return

    # Fallback 2: D-Bus AND local NLP both unavailable — return NOT_FOUND
    # so the UI shows fuzzy suggestions instead of a fake generic list
    fallback = {
        "status": "NOT_FOUND",
        "recipe_name": recipe,
        "message": "RecommendDaemon and local NLP both unavailable",
        "ingredients": [],
        "pipeline_time_ms": 0
    }
    print(json.dumps({"type": "RESULT", "data": fallback}), flush=True)


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
            _sent = False
            if proxy is not None and wait_for_service(timeout=2):
                try:
                    raw_recipes = proxy.GetAvailableRecipes()
                    recipes = json.loads(raw_recipes)
                    if isinstance(recipes, list) and recipes:
                        print(json.dumps({"type": "RECIPES", "data": recipes}), flush=True)
                        _sent = True
                except Exception as e:
                    logging.warning(f"D-Bus GetAvailableRecipes failed, falling back to static list: {e}")
            if not _sent:
                # Use local NLP engine's full recipe list (250+) if available
                engine = _get_local_nlp()
                local_recipes = engine.get_available_recipes() if engine else []
                print(json.dumps({"type": "RECIPES", "data": local_recipes}), flush=True)
#        elif msg_type == "GET_RECIPE_DETAIL":
#            recipe_name = msg.get("recipe", "")
#            detail = {
#                "recipe_name": recipe_name,
#                "status": "SUCCESS",
#                "serving": "4 người",
#                "times": "30 Phút",
#                "difficulty": "Dễ",
#                "original_ingredients": [
#                    "Nguyên liệu 1 : 100g",
#                    "Nguyên liệu 2 : 200g",
#                    "Nguyên liệu 3 : 1 muỗng",
#                ],
#                "original_spices": ["Muối", "Tiêu", "Đường"],
#                "process": ["Bước sơ chế 1", "Bước sơ chế 2"],
#                "cook": ["Bước nấu 1", "Bước nấu 2"],
#                "usage": ["Dùng nóng với cơm"],
#                "tips": "Mẹo nhỏ cho món ăn thêm ngon",
#                "total_items": 3,
#                "ingredients": [
#                    {"name": "Nguyên liệu 1", "required": "100g", "available": 0, "shortage": 100, "status": "missing"},
#                    {"name": "Nguyên liệu 2", "required": "200g", "available": 0, "shortage": 200, "status": "missing"},
#                    {"name": "Nguyên liệu 3", "required": "1 muỗng", "available": 0, "shortage": 1, "status": "missing"},
#                ],
#                "summary": "❌ Còn thiếu 3 nguyên liệu",
#                "pipeline_time_ms": 0.5,
#            }
#            print(json.dumps({"type": "RESULT", "data": detail}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
