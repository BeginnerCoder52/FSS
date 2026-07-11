import sys, os
from pathlib import Path
FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
print("FSS_ROOT:", FSS_ROOT)
print("NLP_RECIPE_DB_PATH:", os.path.join(FSS_ROOT, "recipe_extractor", "data", "recipes"))
