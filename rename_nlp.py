import os
import re

replacements = [
    # RecommendDbManager.py
    (r'nlp_status', 'analysis_status'),
    
    # RecommendEngine.py
    (r'nlp_engine', 'analyzer_engine'),
    (r'set_nlp_engine', 'set_analyzer_engine'),
    (r'nlp_result', 'analyzer_result'),
    (r'NLP analysis', 'Recipe analysis'),
    (r'NLP engine', 'Recipe analyzer'),
    (r'NLP output', 'Analyzer output'),
    
    # main.py
    (r'NLP_RECIPE_DB_PATH', 'RECIPE_DB_PATH'),
    (r'_lazy_load_nlp_engine', '_lazy_load_analyzer_engine'),
    (r'_nlp_engine', '_analyzer_engine'),
    (r'_nlp_loaded', '_analyzer_loaded'),
    
    # recommend_dbus_listener.py
    (r'_local_nlp_engine', '_local_analyzer_engine'),
    (r'_local_nlp_attempted', '_local_analyzer_attempted'),
    (r'_get_local_nlp', '_get_local_analyzer'),
    (r'_local_nlp_search', '_local_analyzer_search'),
    (r'\[LocalNLP\]', '[LocalAnalyzer]'),
    (r'local NLP', 'local analyzer'),
    
    # MMM-FSS-Recommend.js
    (r'NLP pipeline', 'Filter-Sort pipeline'),
    (r'\(NLP\)', '(Filter-Sort)'),
    
    # RecipeAnalyzerAPI.py
    (r'NLP Engine', 'Filter-Sort Engine'),
    (r'NLP engine', 'Filter-Sort engine'),
    (r'NLP rewrite', 'Filter-Sort rewrite')
]

files_to_modify = [
    'recommend_daemon/src/RecommendDbManager.py',
    'recommend_daemon/src/RecommendEngine.py',
    'recommend_daemon/src/main.py',
    'electron_app/magicmirror/modules/MMM-FSS-Recommend/py_bridge/recommend_dbus_listener.py',
    'electron_app/magicmirror/modules/MMM-FSS-Recommend/MMM-FSS-Recommend.js',
    'recipe_extractor/src/RecipeAnalyzerAPI.py'
]

for filepath in files_to_modify:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = re.sub(old, new, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Renaming completed.")
