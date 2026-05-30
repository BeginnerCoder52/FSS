#!/usr/bin/env python3
"""Bridge: listen for RECIPE_SEARCH, call RecommendDaemon D-Bus, relay results."""
import sys, json, asyncio, uuid
from sdbus import DbusInterfaceCommon, dbus_method

class RecommendDaemonInterface(DbusInterfaceCommon,
                               interface_name="vn.edu.uit.FSS.RecommendDaemon"):
    @dbus_method('ss', 's')
    def GenerateShoppingList(self, recipe_name: str, batch_id: str) -> str:
        pass

proxy = RecommendDaemonInterface.new_proxy(
    "vn.edu.uit.FSS.RecommendDaemon",
    "/vn/edu/uit/FSS/RecommendDaemon"
)

for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        msg = json.loads(line)
        if msg.get("type") == "SEARCH":
            recipe = msg["recipe"]
            batch_id = str(uuid.uuid4())
            result = proxy.GenerateShoppingList(recipe, batch_id)
            print(json.dumps({"type": "RESULT", "data": json.loads(result)}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
