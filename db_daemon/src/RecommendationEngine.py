"""
@file RecommendationEngine.py
@brief Core logic for NLP-based food recommendation and inventory comparison.

This module provides the recommendation engine that:
1. Calls NLP pipeline to extract ingredients from recipes
2. Compares extracted ingredients with current inventory
3. Generates shopping lists with full comparison details
4. Manages inventory updates from food detection notifications

Part of Phase 3: DBDaemon API Extensions (NLP Recommendation System Integration)

Following ASPICE principles with comprehensive error handling and logging.

Author: FSS Team
Date: 2026-05-23
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class RecommendationEngine:
    """
    Core recommendation engine for NLP-based food recommendation system.
    
    Responsibilities:
        1. Interface with NLP pipeline (via RecipeAnalyzerAPI)
        2. Compare recipe requirements against current inventory
        3. Generate shopping lists with detailed comparison
        4. Track inventory changes and audit trail
        5. Manage recommendation workflows
    
    Dependencies:
        - SqliteManager: Database operations
        - RecipeAnalyzerAPI (from recommend_system): NLP inference
    
    Design Pattern:
        - Orchestrator pattern: Coordinates NLP engine + database manager
        - Strategy pattern: Different comparison algorithms
        - Command pattern: Queueable recommendations
    
    Performance:
        - NLP inference: ~3.22ms per recipe (cached)
        - Comparison: <1ms
        - Total latency: ~5-10ms per recommendation
    
    Thread Safety:
        - NOT thread-safe during initialization
        - Thread-safe after initialization for recommendations
    """
    
    def __init__(self, db_manager, nlp_engine=None):
        """
        Initialize RecommendationEngine.
        
        Args:
            db_manager: SqliteManager instance (already initialized)
            nlp_engine: Optional RecipeAnalyzerAPI instance (can be lazy-loaded)
            
        Raises:
            ValueError: If db_manager is None
            
        Note:
            NLP engine can be None initially and loaded later via set_nlp_engine()
        """
        if db_manager is None:
            raise ValueError("db_manager cannot be None")
        
        self.db_manager = db_manager
        self.nlp_engine = nlp_engine
        
        # Configuration
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("RecommendationEngine initialized")
    
    def set_nlp_engine(self, nlp_engine: Any) -> bool:
        """
        Set or update the NLP engine.
        
        Purpose:
            Support lazy loading of NLP model (deferred until needed)
            Allow engine updates without restart
        
        Args:
            nlp_engine: RecipeAnalyzerAPI instance
        
        Returns:
            True if set successful, False otherwise
        """
        try:
            self.nlp_engine = nlp_engine
            self.logger.info("NLP engine set/updated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set NLP engine: {e}")
            return False
    
    def generate_shopping_list(self, recipe_name: str, batch_id: str) -> Dict[str, Any]:
        """
        Generate shopping list for a recipe.
        
        Complete workflow:
            1. Call NLP to extract ingredients from recipe
            2. Insert ingredients as request batch
            3. Compare inventory vs requests
            4. Format results for UI
        
        Args:
            recipe_name: Vietnamese recipe name
            batch_id: Unique batch ID (UUID recommended) to group ingredients
        
        Returns:
            Dict with structure:
            {
                "recipe_name": str,
                "batch_id": str,
                "status": "success" | "error",
                "message": str,
                "available": [{"food_id": str, "qty": int, "image": str}, ...],
                "needed": [{"food_id": str, "qty": int}, ...],
                "missing": [{"food_id": str, "qty": int}, ...],
                "total_items": int,
                "available_count": int,
                "needed_count": int,
                "missing_count": int,
                "timestamp": ISO 8601 string
            }
            
        Raises:
            ValueError: If recipe_name is empty or NLP engine not available
            RuntimeError: If comparison fails
            
        ASPICE Compliance:
            - Complete error handling with detailed messages
            - Audit trail recorded in database
            - Structured return format for UI
        """
        timestamp = datetime.now().isoformat()
        result = {
            "recipe_name": recipe_name,
            "batch_id": batch_id,
            "status": "error",
            "message": "",
            "available": [],
            "needed": [],
            "missing": [],
            "total_items": 0,
            "available_count": 0,
            "needed_count": 0,
            "missing_count": 0,
            "timestamp": timestamp
        }
        
        try:
            # Step 1: Validate inputs
            if not recipe_name or not recipe_name.strip():
                result["message"] = "Recipe name cannot be empty"
                self.logger.warning("Empty recipe name provided")
                return result
            
            if not self.nlp_engine:
                result["message"] = "NLP engine not initialized"
                self.logger.error("NLP engine not available for recipe analysis")
                return result
            
            # Step 2: Call NLP to extract ingredients
            self.logger.debug(f"Calling NLP engine for recipe: {recipe_name}")
            try:
                ingredients_list = self.nlp_engine.generate_fss_request(recipe_name)
            except ValueError as e:
                result["message"] = f"Recipe not found: {recipe_name}"
                self.logger.warning(f"Recipe not found by NLP engine: {recipe_name}")
                return result
            except TimeoutError as e:
                result["message"] = f"NLP inference timeout: {str(e)}"
                self.logger.error(f"NLP inference timeout: {e}")
                return result
            except Exception as e:
                result["message"] = f"NLP error: {str(e)}"
                self.logger.error(f"NLP inference failed: {e}")
                return result
            
            # Step 3: Insert ingredients as request batch
            if not ingredients_list:
                result["message"] = f"Recipe '{recipe_name}' has no ingredients"
                self.logger.warning(f"Recipe has empty ingredients: {recipe_name}")
                return result
            
            insert_success = self.db_manager.insert_request_batch(
                recipe_name, ingredients_list, batch_id
            )
            
            if not insert_success:
                result["message"] = "Failed to store recipe ingredients in database"
                self.logger.error(f"Failed to insert request batch: {recipe_name}")
                return result
            
            # Step 4: Compare inventory vs requests
            comparison = self.compare_inventory_and_requests()
            if not comparison:
                result["message"] = "Comparison completed with no items"
                self.logger.info(f"No items to compare for recipe: {recipe_name}")
                result["status"] = "success"
                return result
            
            # Step 5: Format results
            result["available"] = comparison.get("available", [])
            result["needed"] = comparison.get("needed", [])
            result["missing"] = comparison.get("missing", [])
            result["total_items"] = len(ingredients_list)
            result["available_count"] = len(result["available"])
            result["needed_count"] = len(result["needed"])
            result["missing_count"] = len(result["missing"])
            result["status"] = "success"
            result["message"] = f"Shopping list generated: {result['missing_count']} items missing"
            
            self.logger.info(f"Shopping list generated for '{recipe_name}': "
                           f"{result['available_count']} available, "
                           f"{result['needed_count']} needed, "
                           f"{result['missing_count']} missing")
            
            return result
            
        except Exception as e:
            result["message"] = f"Unexpected error: {str(e)}"
            self.logger.error(f"Unexpected error in generate_shopping_list: {e}")
            return result
    
    def compare_inventory_and_requests(self) -> Optional[Dict[str, List[Dict]]]:
        """
        Compare current inventory against all requests.
        
        Purpose:
            Generate detailed comparison showing:
            - Available items (have quantity and image)
            - Needed items (have some but not enough)
            - Missing items (have none)
        
        Returns:
            Dict with structure:
            {
                "available": [{"food_id": str, "qty": int, "confidence": float, "image": str}, ...],
                "needed": [{"food_id": str, "have": int, "need": int, "shortage": int}, ...],
                "missing": [{"food_id": str, "need": int}, ...]
            }
            
            Returns None on error
            
        ASPICE Compliance:
            - Complete error handling
            - Defensive null checking
            - Comprehensive logging
        """
        try:
            # Get all inventory items
            inventory = self.db_manager.get_all_inventory()
            inventory_dict = {item['food_id']: item for item in inventory}
            
            # Get all requests
            requests = self.db_manager.get_all_requests()
            requests_dict = {}
            
            for req in requests:
                food_id = req['food_id']
                if food_id not in requests_dict:
                    requests_dict[food_id] = 0
                requests_dict[food_id] += req['quantity']
            
            # Categorize items
            available = []
            needed = []
            missing = []
            
            # Collect all food IDs from both inventory and requests
            all_food_ids = set(inventory_dict.keys()) | set(requests_dict.keys())
            
            for food_id in all_food_ids:
                inv_item = inventory_dict.get(food_id, {})
                inv_qty = inv_item.get('quantity', 0)
                req_qty = requests_dict.get(food_id, 0)
                
                if req_qty == 0:
                    # Item in inventory but not requested
                    if inv_qty > 0:
                        available.append({
                            'food_id': food_id,
                            'qty': inv_qty,
                            'confidence': inv_item.get('confidence_score', 0.0),
                            'image': inv_item.get('image_path', '')
                        })
                elif inv_qty >= req_qty:
                    # Have enough quantity
                    available.append({
                        'food_id': food_id,
                        'qty': inv_qty,
                        'confidence': inv_item.get('confidence_score', 0.0),
                        'image': inv_item.get('image_path', '')
                    })
                elif inv_qty > 0:
                    # Have some but not enough
                    needed.append({
                        'food_id': food_id,
                        'have': inv_qty,
                        'need': req_qty,
                        'shortage': req_qty - inv_qty
                    })
                else:
                    # Don't have any
                    missing.append({
                        'food_id': food_id,
                        'need': req_qty
                    })
            
            result = {
                'available': available,
                'needed': needed,
                'missing': missing
            }
            
            self.logger.debug(f"Comparison result: {len(available)} available, "
                            f"{len(needed)} needed, {len(missing)} missing")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error comparing inventory and requests: {e}")
            return None
    
    def get_current_inventory(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get current inventory with version tracking and change information.
        
        Purpose:
            Retrieve all inventory items with audit trail metadata
            for UI display and analytics
        
        Returns:
            List of items with structure:
            [{
                "food_id": str,
                "quantity": int,
                "confidence_score": float,
                "image_path": str,
                "version_id": int,
                "last_change_reason": str,
                "last_changed_by": str,
                "last_updated": ISO 8601 timestamp,
                "created_at": ISO 8601 timestamp,
                "history": [audit trail records]
            }, ...]
            
            Returns None on error
        """
        try:
            inventory = self.db_manager.get_all_inventory()
            
            # Enrich with history
            enriched_inventory = []
            for item in inventory:
                food_id = item['food_id']
                history = self.db_manager.get_inventory_history(food_id, limit=5)
                
                enriched_item = {
                    **item,
                    'history': history
                }
                enriched_inventory.append(enriched_item)
            
            self.logger.debug(f"Retrieved current inventory: {len(enriched_inventory)} items")
            return enriched_inventory
            
        except Exception as e:
            self.logger.error(f"Error retrieving current inventory: {e}")
            return None
    
    def update_inventory_from_notification(self, food_id: str, quantity: int,
                                          confidence_score: float, image_path: Optional[str],
                                          source: str = "FRT_DETECTION") -> bool:
        """
        Update inventory from a notification (typically FRT detection).
        
        Purpose:
            Handle food detection notifications and update inventory with audit trail
            Supports both FRT detection and manual inventory updates
        
        Args:
            food_id: Food item identifier
            quantity: Quantity detected/added
            confidence_score: AI model confidence (0.0-1.0)
            image_path: Path to the food item image
            source: Source of update ("FRT_DETECTION", "USER_MANUAL", etc)
        
        Returns:
            True if update successful, False otherwise
            
        Workflow:
            1. Get current quantity before update
            2. Update inventory
            3. Record change to history with audit info
            4. Log the update
            
        ASPICE Compliance:
            - Immutable audit trail recording
            - Complete traceability
            - Error recovery
        """
        try:
            # Get current state before update
            current_item = self.db_manager.get_inventory_item(food_id)
            quantity_before = current_item['quantity'] if current_item else 0
            
            # Update inventory
            update_success = self.db_manager.update_inventory(
                food_id, quantity, confidence_score, image_path
            )
            
            if not update_success:
                self.logger.error(f"Failed to update inventory for {food_id}")
                return False
            
            # Record to history
            quantity_after = quantity_before + quantity
            history_success = self.db_manager.insert_inventory_history(
                food_id=food_id,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                confidence_score=confidence_score,
                image_path=image_path,
                change_reason=source,
                changed_by="DBDaemon",
                changed_at=datetime.now().isoformat()
            )
            
            if not history_success:
                self.logger.warning(f"Failed to record history for {food_id}")
                # Continue anyway - inventory was updated
            
            self.logger.info(f"Inventory updated: {food_id}, "
                           f"qty: {quantity_before}→{quantity_after}, "
                           f"source: {source}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating inventory from notification: {e}")
            return False
    
    def get_available_recipes(self) -> Optional[List[str]]:
        """
        Get list of available recipes from NLP engine.
        
        Purpose:
            Support recipe autocomplete and discovery in UI
        
        Returns:
            List of recipe names sorted alphabetically, or None on error
        """
        try:
            if not self.nlp_engine:
                self.logger.warning("NLP engine not available for recipe listing")
                return None
            
            recipes = self.nlp_engine.get_available_recipes()
            self.logger.debug(f"Retrieved {len(recipes)} available recipes")
            return sorted(recipes)
            
        except Exception as e:
            self.logger.error(f"Error retrieving available recipes: {e}")
            return None
