# §1 NLP Filter+Sort — Test Results Summary

**Date**: 2026-06-21  
**Branch**: feat/nlp-filter-sort  
**Commit**: df941db  

---

## Test Results

| Suite | Dir | Tests | Passed | Failed | File |
|-------|-----|-------|--------|--------|------|
| Recipe Extractor Unit | `tests/recipe_extractor/` | 90 | 90 | 0 | `recipe_extractor/test_recipe_analyzer.log` |
| Recommend Daemon Unit | `tests/recommend_daemon/` | 41 | 41 | 0 | `recommend_daemon/test_recommend_engine.log` |
| Integration | `tests/integration/` | 65 | 65 | 0 | `integration/test_integration.log` |
| System Health | `tests/system_tests/` | 1* | 0 | 1** | `system_tests/test_system_health.log` |
| **Total** | | **197** | **196** | **1** | |

\* 5 E2E/D-Bus tests skipped (daemons not running)  
\*\* `test_database_files_exist` — expected failure: `/opt/fss/data/` only present on deployed RPi4B

---

## What Was Fixed

1. **`tests/recommend_daemon/test_recommend_engine.py`** — stale `sys.path` (pointed to wrong dir); mock NLP return values used old `ingredients` dict format instead of new `original_ingredients` string format. Updated both mock data in `TestRecommendEngine.setUp()` and `TestDbDbusInteraction.setUp()`.

2. **No stale CRF references** in any test code — verified with ripgrep across all `tests/*.py` for `CRF`, `crf_model`, `NLP_MODEL_PATH`, `sklearn-crfsuite`, `joblib`, `pyvi`, `fss_ner_crf`. Zero matches.

---

## Folder Structure

```
tests/logs/
├── TEST_SUMMARY.md
├── recipe_extractor/
│   └── test_recipe_analyzer.log       (90 tests)
├── recommend_daemon/
│   └── test_recommend_engine.log      (41 tests)
├── integration/
│   └── test_integration.log           (65 tests)
└── system_tests/
    └── test_system_health.log         (1 run, 5 skipped)
```
