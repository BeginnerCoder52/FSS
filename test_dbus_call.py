import sys, os, time, uuid
sys.path.insert(0, "/home/richardmelvin52/FSS/recommend_daemon/src")
from RecommendEngine import RecommendEngine

def test_engine():
    try:
        from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
        nlp_engine = RecipeAnalyzerEngine("/home/richardmelvin52/FSS/recipe_extractor/data/recipes")
        engine = RecommendEngine(nlp_engine=nlp_engine, db_manager=None)
        
        # Fake inventory
        inventory = [{"food_id": "đậu hũ", "quantity": 1}]
        
        res = engine.generate_shopping_list("Sườn Nấu Đậu", inventory=inventory)
        print("Test Result:", res['status'])
        if res['status'] != "SUCCESS":
            print(res)
    except Exception as e:
        print("Error:", e)

test_engine()
