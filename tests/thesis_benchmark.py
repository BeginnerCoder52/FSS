import sys
import random
import logging
import json
import time
from pathlib import Path

# Ensure imports work properly
FSS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FSS_ROOT / "recipe_extractor" / "src"))
sys.path.insert(0, str(FSS_ROOT / "recommend_daemon" / "src"))

from RecipeAnalyzerAPI import RecipeAnalyzerEngine
from RecommendEngine import RecommendEngine

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ThesisBenchmark")

def run_benchmark(num_tests: int = 100):
    recipe_db_path = str(FSS_ROOT / "recipe_extractor" / "data" / "recipes")
    
    # Measure cold start loading time
    start_time = time.time()
    nlp_engine = RecipeAnalyzerEngine(recipe_db_path=recipe_db_path)
    load_time_ms = (time.time() - start_time) * 1000
    
    recommend_engine = RecommendEngine(nlp_engine=nlp_engine, db_manager=None)
    
    available_recipes = nlp_engine.get_available_recipes()
    
    logger.info("=" * 60)
    logger.info("FSS NLP PIPELINE - THESIS BENCHMARK REPORT")
    logger.info("=" * 60)
    logger.info(f"Database Loaded: {len(available_recipes)} recipes")
    logger.info(f"Cold Start Load Time: {load_time_ms:.2f} ms")
    logger.info(f"Total Test Iterations: {num_tests}")
    logger.info("-" * 60)

    stats = {
        "nlp_times": [],
        "bu_tru_times": [],
        "total_times": [],
        "input_ingredients_count": [],
        "output_missing_count": []
    }
    
    # Select random recipes
    test_recipes = random.sample(available_recipes, min(num_tests, len(available_recipes)))
    
    detailed_example = None
    
    # For RecommendEngine, disable logging to prevent spam in benchmark output
    logging.getLogger("RecommendEngine").setLevel(logging.WARNING)
    
    for idx, recipe_name in enumerate(test_recipes, 1):
        # 1. NLP Pipeline Time
        t0 = time.time()
        nlp_result = nlp_engine.generate_fss_request(recipe_name)
        nlp_time = (time.time() - t0) * 1000
        stats["nlp_times"].append(nlp_time)
        
        # 2. Bù Trừ Pipeline Time
        t1 = time.time()
        recommend_result = recommend_engine.generate_shopping_list(recipe_name, inventory=[])
        bu_tru_time = (time.time() - t1) * 1000
        stats["bu_tru_times"].append(bu_tru_time)
        
        total_time = nlp_time + bu_tru_time
        stats["total_times"].append(total_time)
        
        stats["input_ingredients_count"].append(len(nlp_result.get("original_ingredients", [])))
        stats["output_missing_count"].append(recommend_result.get("missing_count", 0))
        
        if detailed_example is None:
            detailed_example = {
                "recipe": recipe_name,
                "nlp_output": nlp_result,
                "recommend_output": recommend_result,
                "nlp_time": nlp_time,
                "bu_tru_time": bu_tru_time
            }

    # Calculate aggregations
    avg_nlp = sum(stats["nlp_times"]) / len(stats["nlp_times"])
    max_nlp = max(stats["nlp_times"])
    min_nlp = min(stats["nlp_times"])
    
    avg_bu_tru = sum(stats["bu_tru_times"]) / len(stats["bu_tru_times"])
    avg_total = sum(stats["total_times"]) / len(stats["total_times"])
    
    avg_input = sum(stats["input_ingredients_count"]) / len(stats["input_ingredients_count"])
    avg_output = sum(stats["output_missing_count"]) / len(stats["output_missing_count"])

    logger.info("\n1. PERFORMANCE METRICS (Average over %d runs)", num_tests)
    logger.info("  %-35s : %.3f ms (Max: %.3f ms, Min: %.3f ms)", "NLP Pipeline (Filter+Parse+Sort)", avg_nlp, max_nlp, min_nlp)
    logger.info("  %-35s : %.3f ms", "Bù Trừ Pipeline (Comparison)", avg_bu_tru)
    logger.info("  %-35s : %.3f ms", "Total Pipeline Latency", avg_total)
    
    logger.info("\n2. DATA FLOW METRICS")
    logger.info("  %-35s : %.1f ingredients", "Average Input Size", avg_input)
    logger.info("  %-35s : %.1f items", "Average Output Missing List", avg_output)

    logger.info("\n" + "=" * 60)
    logger.info("3. FULL DETAILED DEBUG PIPELINE (Single Example)")
    logger.info("=" * 60)
    
    r = detailed_example["recipe"]
    nlp = detailed_example["nlp_output"]
    rec = detailed_example["recommend_output"]
    
    logger.info(f"\n[STEP A] USER INPUT")
    logger.info(f"  Query: '{r}'")
    
    logger.info(f"\n[STEP B] NLP PIPELINE OUTPUT (Time: {detailed_example['nlp_time']:.3f} ms)")
    logger.info(f"  Status: {nlp['status']}")
    logger.info(f"  Dish Name (Normalized): {nlp['dish']}")
    logger.info(f"  Original Ingredients Parsed: {len(nlp['original_ingredients'])} items")
    for ing in nlp['original_ingredients']:
        logger.info(f"    - {ing}")
        
    logger.info(f"\n[STEP C] BÙ TRỪ RECOMMENDATION ALGORITHM (Time: {detailed_example['bu_tru_time']:.3f} ms)")
    logger.info(f"  Total required items: {rec['total_items']}")
    logger.info(f"  Available in fridge: {rec['available_count']}")
    logger.info(f"  Missing to buy: {rec['missing_count']}")
    logger.info("\n  --- Generated Shopping List (Output) ---")
    for item in rec['shopping_list']:
        logger.info(f"    [ ] {item['food_id']} (Need: {item['required_qty']})")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_benchmark(500)
