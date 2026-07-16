import os
import re
import glob

replacements = [
    (r'nlp_status', 'analysis_status'),
    (r'nlp_engine', 'analyzer_engine'),
    (r'set_nlp_engine', 'set_analyzer_engine'),
    (r'nlp_result', 'analyzer_result'),
    (r'NLP_RECIPE_DB_PATH', 'RECIPE_DB_PATH'),
    (r'_lazy_load_nlp_engine', '_lazy_load_analyzer_engine'),
    (r'_nlp_engine', '_analyzer_engine'),
    (r'_nlp_loaded', '_analyzer_loaded'),
    (r'NLP', 'Analyzer')
]

files_to_modify = glob.glob('tests/**/*.py', recursive=True)

for filepath in files_to_modify:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = re.sub(old, new, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Tests renaming completed.")
