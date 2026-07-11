import os, glob, json
import unicodedata

def normalize_unicode(text: str) -> str:
    return unicodedata.normalize('NFC', text)

files = glob.glob('recipe_extractor/data/recipes/*.json')
for f in files:
    data = json.load(open(f))
    name = data.get('recipe_name', '')
    if name != normalize_unicode(name):
        print(f"Mismatch in {f}: {name}")
