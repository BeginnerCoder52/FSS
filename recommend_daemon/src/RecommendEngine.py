import logging
import json
import uuid
from typing import Optional, List, Dict, Any
from pathlib import Path


class RecommendEngine:
    def __init__(
        self,
        nlp_engine: Optional[Any] = None,
        db_manager: Optional[Any] = None
    ):
        self.nlp_engine = nlp_engine
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_nlp_engine(self, nlp_engine: Any) -> None:
        self.nlp_engine = nlp_engine

    def set_db_manager(self, db_manager: Any) -> None:
        self.db_manager = db_manager

    def generate_shopping_list(
        self,
        recipe_name: str,
        batch_id: Optional[str] = None,
        inventory: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if not self.nlp_engine:
            return {"status": "ERROR", "error": "NLP engine not initialized"}

        if batch_id is None:
            batch_id = str(uuid.uuid4())

        try:
            nlp_result = self.nlp_engine.generate_fss_request(recipe_name)
            nlp_status = nlp_result.get("status", "ERROR")

            if nlp_status != "SUCCESS":
                self.logger.warning(
                    f"NLP analysis failed for '{recipe_name}': {nlp_status}"
                )
                return {
                    "status": nlp_status,
                    "message": nlp_result.get(
                        "message", nlp_result.get("error", "NLP analysis failed")
                    ),
                    "dish": nlp_result.get("dish", recipe_name),
                    "suggestions": nlp_result.get("suggestions", []),
                    "batch_id": batch_id
                }

            ingredients = nlp_result.get("ingredients", [])
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
                food_id = ing.get("ingredient", "").lower().strip()
                req_qty = self._parse_quantity(ing.get("quantity", "1"))
                inv_qty = inventory_map.get(food_id, 0)
                unit = ing.get("unit")

                shortage = max(0, req_qty - inv_qty)

                entry = {
                    "food_id": food_id,
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
                "nlp_status": nlp_status,
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
                    nlp_status=nlp_status,
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
        if not self.nlp_engine:
            self.logger.error("NLP engine not initialized for recipe lookup")
            return []
        try:
            return self.nlp_engine.get_available_recipes()
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
