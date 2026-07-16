import logging
import json
import uuid
from typing import Optional, List, Dict, Any
from pathlib import Path


class RecommendEngine:
    def __init__(
        self,
        analyzer_engine: Optional[Any] = None,
        db_manager: Optional[Any] = None
    ):
        self.analyzer_engine = analyzer_engine
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_analyzer_engine(self, analyzer_engine: Any) -> None:
        self.analyzer_engine = analyzer_engine

    def set_db_manager(self, db_manager: Any) -> None:
        self.db_manager = db_manager

    def generate_shopping_list(
        self,
        recipe_name: str,
        batch_id: Optional[str] = None,
        inventory: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if not self.analyzer_engine:
            return {"status": "ERROR", "error": "Recipe analyzer not initialized"}

        if batch_id is None:
            batch_id = str(uuid.uuid4())

        try:
            analyzer_result = self.analyzer_engine.generate_fss_request(recipe_name)
            analysis_status = analyzer_result.get("status", "ERROR")

            if analysis_status != "SUCCESS":
                self.logger.warning(
                    f"Recipe analysis failed for '{recipe_name}': {analysis_status}"
                )
                return {
                    "status": analysis_status,
                    "message": analyzer_result.get(
                        "message", analyzer_result.get("error", "Recipe analysis failed")
                    ),
                    "dish": analyzer_result.get("dish", recipe_name),
                    "suggestions": analyzer_result.get("suggestions", []),
                    "batch_id": batch_id
                }

            pipeline_time_ms = analyzer_result.get("processing_time_ms", None)

            raw_strings = analyzer_result.get("original_ingredients", [])
            ingredients = []
            for item_str in raw_strings:
                parts = item_str.split(" : ", 1)
                name = parts[0].strip()
                qty = parts[1].strip() if len(parts) > 1 else "1"
                ingredients.append({"ingredient": name, "quantity": qty})

            if not ingredients:
                return {
                    "status": "NOT_FOUND",
                    "message": "No ingredients extracted from recipe",
                    "dish": recipe_name,
                    "batch_id": batch_id
                }

            inventory_map = {}
            if inventory:
                for item in inventory:
                    food_id = item.get("food_id", "").lower()
                    qty = item.get("quantity", 0)
                    if qty > 0:
                        inventory_map[food_id] = qty

            available_items = []
            needed_items = []
            missing_items = []
            shopping_items = []

            for ing in ingredients:
                display_name = ing.get("ingredient", "").strip()   # Original name for display
                food_id = display_name.lower()                       # Lowercased for inventory matching
                quantity_str = ing.get("quantity", "1")             # Full quantity string, e.g. "1 trái"
                req_qty = self._parse_quantity(quantity_str)
                inv_qty = inventory_map.get(food_id, 0)
                unit = ing.get("unit")  # Optional separate unit (may be None for Analyzer output)

                shortage = max(0, req_qty - inv_qty)

                entry = {
                    "food_id": food_id,
                    "display_name": display_name,       # Original ingredient name (proper case)
                    "quantity_str": quantity_str,        # Full human-readable quantity, e.g. "1 trái"
                    "required_qty": req_qty,
                    "available_qty": inv_qty,
                    "shortage": shortage,
                    "unit": unit
                }

                if inv_qty >= req_qty:
                    available_items.append(entry)
                elif inv_qty > 0:
                    needed_items.append(entry)
                    shopping_items.append(entry)
                else:
                    missing_items.append(entry)
                    shopping_items.append(entry)

            total_items = len(ingredients)
            available_count = len(available_items)
            needed_count = len(needed_items)
            missing_count = len(missing_items)

            result_snapshot = {
                "recipe_name": recipe_name,
                "batch_id": batch_id,
                "analysis_status": analysis_status,
                "pipeline_time_ms": pipeline_time_ms,
                "total_items": total_items,
                "available_count": available_count,
                "needed_count": needed_count,
                "missing_count": missing_count,
                "available": available_items,
                "needed": needed_items,
                "missing": missing_items,
                "shopping_list": shopping_items
            }

            if self.db_manager:
                rec_id = self.db_manager.insert_recommendation(
                    recipe_name=recipe_name,
                    batch_id=batch_id,
                    analysis_status=analysis_status,
                    total_items=total_items,
                    available_count=available_count,
                    needed_count=needed_count,
                    missing_count=missing_count,
                    result_json=json.dumps(result_snapshot, ensure_ascii=False)
                )
                if rec_id is not None and shopping_items:
                    self.db_manager.insert_shopping_list(rec_id, shopping_items)

            self.logger.info(
                f"Bù Trừ result for '{recipe_name}': "
                f"available={available_count}, needed={needed_count}, "
                f"missing={missing_count}, batch_id={batch_id}"
            )

            return {
                "status": "SUCCESS",
                "batch_id": batch_id,
                "recipe_name": recipe_name,
                "pipeline_time_ms": pipeline_time_ms,
                "total_items": total_items,
                "available_count": available_count,
                "needed_count": needed_count,
                "missing_count": missing_count,
                "available": available_items,
                "needed": needed_items,
                "missing": missing_items,
                "shopping_list": shopping_items
            }

        except Exception as e:
            self.logger.error(f"Error generating shopping list: {e}", exc_info=True)
            return {
                "status": "ERROR",
                "error": str(e),
                "batch_id": batch_id
            }

    def get_available_recipes(self) -> List[str]:
        if not self.analyzer_engine:
            self.logger.error("Recipe analyzer not initialized for recipe lookup")
            return []
        try:
            return self.analyzer_engine.get_available_recipes()
        except Exception as e:
            self.logger.error(f"Error getting available recipes: {e}")
            return []

    def get_shopping_list(self, batch_id: str) -> List[Dict[str, Any]]:
        if not self.db_manager:
            self.logger.error("Database manager not initialized")
            return []
        try:
            return self.db_manager.get_shopping_list(batch_id)
        except Exception as e:
            self.logger.error(f"Error getting shopping list: {e}")
            return []

    def mark_item_purchased(self, item_id: int) -> bool:
        if not self.db_manager:
            self.logger.error("Database manager not initialized")
            return False
        try:
            return self.db_manager.mark_item_purchased(item_id)
        except Exception as e:
            self.logger.error(f"Error marking item purchased: {e}")
            return False

    def format_result_for_ui(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("status") != "SUCCESS":
            return result

        ingredients = []
        for item in result.get("available", []):
            entry = {
                "name": item.get("display_name") or item.get("food_id", ""),
                "required": item.get("quantity_str") or item.get("required_qty", 0),
                "available": item.get("available_qty", 0),
                "shortage": 0,
                "unit": item.get("unit"),
                "status": "available"
            }
            ingredients.append(entry)

        for item in result.get("needed", []):
            entry = {
                "name": item.get("display_name") or item.get("food_id", ""),
                "required": item.get("quantity_str") or item.get("required_qty", 0),
                "available": item.get("available_qty", 0),
                "shortage": item.get("shortage", 0),
                "unit": item.get("unit"),
                "status": "needed"
            }
            ingredients.append(entry)

        for item in result.get("missing", []):
            entry = {
                "name": item.get("display_name") or item.get("food_id", ""),
                "required": item.get("quantity_str") or item.get("required_qty", 0),
                "available": 0,
                "shortage": item.get("shortage", item.get("required_qty", 0)),
                "unit": item.get("unit"),
                "status": "missing"
            }
            ingredients.append(entry)

        missing_count = result.get("missing_count", 0)
        if missing_count > 0:
            summary = f"❌ Còn thiếu {missing_count} nguyên liệu"
        else:
            summary = "✅ Đã có đủ nguyên liệu!"

        ui_result = dict(result)
        ui_result["ingredients"] = ingredients
        ui_result["summary"] = summary
        ui_result["pipeline_time_ms"] = result.get("pipeline_time_ms", None)
        return ui_result

    def _parse_quantity(self, quantity_str: str) -> int:
        if not quantity_str:
            return 1
        try:
            qty = float(quantity_str)
            return max(1, int(round(qty)))
        except (ValueError, TypeError):
            import re
            numbers = re.findall(r'\d+', str(quantity_str))
            if numbers:
                return int(numbers[0])
            return 1
