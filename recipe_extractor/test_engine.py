import sys, os
from pathlib import Path
FSS_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, FSS_ROOT)
from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
engine = RecipeAnalyzerEngine(os.path.join(FSS_ROOT, "recipe_extractor", "data", "recipes"))
print("Loaded recipes:", len(engine.recipe_db))
if len(engine.recipe_db) > 0:
    print("Example recipe names:", list(engine.recipe_names)[:5])
