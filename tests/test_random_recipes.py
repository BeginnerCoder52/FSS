import sys
import random
import logging
import json
from pathlib import Path
from typing import Dict, Any

# Ensure imports work properly
FSS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FSS_ROOT / "recipe_extractor" / "src"))
sys.path.insert(0, str(FSS_ROOT / "recommend_daemon" / "src"))

from RecipeAnalyzerAPI import RecipeAnalyzerEngine
from RecommendEngine import RecommendEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestRandomRecipes")

def test_random_recipes(num_tests: int = 100):
    recipe_db_path = str(FSS_ROOT / "recipe_extractor" / "data" / "recipes")
    logger.info(f"Loading RecipeAnalyzerEngine from {recipe_db_path}...")
    
    nlp_engine = RecipeAnalyzerEngine(recipe_db_path=recipe_db_path)
    recommend_engine = RecommendEngine(nlp_engine=nlp_engine, db_manager=None)
    
    available_recipes = nlp_engine.get_available_recipes()
    if not available_recipes:
        logger.error("No recipes found in the database. Cannot run random tests.")
        return 1
        
    logger.info(f"Loaded {len(available_recipes)} recipes.")
    logger.info(f"Starting to randomly select {num_tests} recipes for testing...\n")
    
    success_count = 0
    failure_count = 0
    
    for i in range(1, num_tests + 1):
        # Pick a random recipe
        recipe_name = random.choice(available_recipes)
        
        try:
            # 1. Test NLP Engine Generation
            nlp_result = nlp_engine.generate_fss_request(recipe_name)
            assert nlp_result["status"] == "SUCCESS", f"NLP Status not SUCCESS: {nlp_result['status']}"
            assert "original_ingredients" in nlp_result, "Missing original_ingredients"
            
            # 2. Test RecommendEngine Generation (with an empty inventory)
            recommend_result = recommend_engine.generate_shopping_list(recipe_name, inventory=[])
            assert recommend_result["status"] == "SUCCESS", f"Recommend Status not SUCCESS: {recommend_result['status']}"
            assert len(recommend_result["missing"]) > 0 or len(recommend_result["available"]) > 0, "No missing or available ingredients returned"
            
            success_count += 1
            if i % 10 == 0 or i == num_tests:
                logger.info(f"[{i}/{num_tests}] Passed - Recipe: '{recipe_name}'")
                
        except Exception as e:
            logger.error(f"[{i}/{num_tests}] Failed - Recipe: '{recipe_name}' - Error: {str(e)}")
            failure_count += 1
            
    logger.info("\n" + "="*50)
    logger.info("RANDOM RECIPE TEST RESULTS")
    logger.info("="*50)
    logger.info(f"Total Tests Run: {num_tests}")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failures: {failure_count}")
    
    if failure_count > 0:
        logger.error(f"Test failed! {failure_count} recipes had errors.")
        return 1
    else:
        logger.info("All random tests passed successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(test_random_recipes(100))
