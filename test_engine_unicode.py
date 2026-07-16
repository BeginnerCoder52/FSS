import sys, os
from pathlib import Path
FSS_ROOT = "/home/richardmelvin52/FSS"
sys.path.insert(0, FSS_ROOT)
from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
engine = RecipeAnalyzerEngine(os.path.join(FSS_ROOT, "recipe_extractor", "data", "recipes"))

print("Testing un-normalized input strings (simulating user input from some keyboards):")
test_cases = [
    "SườN NấU Đậu", # from JSON (might have decomposed characters)
    "Sườn Nấu Đậu", # NFC version
    "Gà TiềM Hạt Sen",
    "Gà Tiềm Hạt Sen"
]

for tc in test_cases:
    res = engine.generate_fss_request(tc)
    print(f"'{tc}' -> Status: {res['status']}")
