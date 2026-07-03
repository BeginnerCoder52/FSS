import sys
import random
import logging
import json
import time
from pathlib import Path

# Ensure imports work properly
FSS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FSS_ROOT))
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
    analyzer_engine = RecipeAnalyzerEngine(recipe_db_path=recipe_db_path)
    load_time_ms = (time.time() - start_time) * 1000
    
    recommend_engine = RecommendEngine(analyzer_engine=analyzer_engine, db_manager=None)
    
    available_recipes = analyzer_engine.get_available_recipes()
    
    logger.info("=" * 60)
    logger.info("FSS RECIPE EXTRACTOR - THESIS BENCHMARK REPORT")
    logger.info("=" * 60)
    logger.info(f"Database Loaded: {len(available_recipes)} recipes")
    logger.info(f"Cold Start Load Time: {load_time_ms:.2f} ms")
    logger.info(f"Total Test Iterations: {num_tests}")
    logger.info("-" * 60)

    stats = {
        "extractor_times": [],
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
        # 1. Extraction Pipeline Time
        t0 = time.time()
        extractor_result = analyzer_engine.generate_fss_request(recipe_name)
        extractor_time = (time.time() - t0) * 1000
        stats["extractor_times"].append(extractor_time)
        
        # 2. Bù Trừ Pipeline Time
        t1 = time.time()
        recommend_result = recommend_engine.generate_shopping_list(recipe_name, inventory=[])
        bu_tru_time = (time.time() - t1) * 1000
        stats["bu_tru_times"].append(bu_tru_time)
        
        total_time = extractor_time + bu_tru_time
        stats["total_times"].append(total_time)
        
        stats["input_ingredients_count"].append(len(extractor_result.get("original_ingredients", [])))
        stats["output_missing_count"].append(recommend_result.get("missing_count", 0))
        
        if detailed_example is None:
            detailed_example = {
                "recipe": recipe_name,
                "extractor_output": extractor_result,
                "recommend_output": recommend_result,
                "extractor_time": extractor_time,
                "bu_tru_time": bu_tru_time
            }

    # Calculate aggregations
    avg_extractor = sum(stats["extractor_times"]) / len(stats["extractor_times"])
    max_extractor = max(stats["extractor_times"])
    min_extractor = min(stats["extractor_times"])
    
    avg_bu_tru = sum(stats["bu_tru_times"]) / len(stats["bu_tru_times"])
    avg_total = sum(stats["total_times"]) / len(stats["total_times"])
    
    avg_input = sum(stats["input_ingredients_count"]) / len(stats["input_ingredients_count"])
    avg_output = sum(stats["output_missing_count"]) / len(stats["output_missing_count"])

    logger.info("\n1. PERFORMANCE METRICS (Average over %d runs)", num_tests)
    logger.info("  %-35s : %.3f ms (Max: %.3f ms, Min: %.3f ms)", "Extraction Pipeline (Filter+Parse+Sort)", avg_extractor, max_extractor, min_extractor)
    logger.info("  %-35s : %.3f ms", "Bù Trừ Pipeline (Comparison)", avg_bu_tru)
    logger.info("  %-35s : %.3f ms", "Total Pipeline Latency", avg_total)
    
    logger.info("\n2. DATA FLOW METRICS")
    logger.info("  %-35s : %.1f ingredients", "Average Input Size", avg_input)
    logger.info("  %-35s : %.1f items", "Average Output Missing List", avg_output)

    logger.info("\n" + "=" * 60)
    logger.info("3. FULL DETAILED DEBUG PIPELINE (Single Example)")
    logger.info("=" * 60)
    
    r = detailed_example["recipe"]
    extractor_res = detailed_example["extractor_output"]
    rec = detailed_example["recommend_output"]
    
    logger.info(f"\n[STEP A] USER INPUT")
    logger.info(f"  Query: '{r}'")
    
    logger.info(f"\n[STEP B] EXTRACTION PIPELINE OUTPUT (Time: {detailed_example['extractor_time']:.3f} ms)")
    logger.info(f"  Status: {extractor_res['status']}")
    logger.info(f"  Dish Name (Normalized): {extractor_res['dish']}")
    logger.info(f"  Original Ingredients Parsed: {len(extractor_res['original_ingredients'])} items")
    for ing in extractor_res['original_ingredients']:
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
