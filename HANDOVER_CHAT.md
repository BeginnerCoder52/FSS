# HANDOVER CHAT — FSS Project

> **Created**: 2026-05-24
> **Last Updated**: 2026-05-30
> **Previous session branch**: `DBDaemon-dev` (Phase 3 — DBDaemon cleanup)
> **Next session branch**: `recommend_daemon` (Phase 4 — Recommend Daemon)
> **Project phase**: Phase 4 of 5 — Re-planned

---

## 1. Architectural Decision Record (ADR-001): Business Logic Independence

### Problem
The original plan embedded `RecommendationEngine` inside `DBDaemon` as an API extension.
This violates **separation of concerns**: DBDaemon is a data controller (SQLite persistence, D-Bus broker),
not a business logic executor. Embedding analysis logic in the data layer breaks extensibility —
future recommendation algorithms would require modifying the database daemon.

### Decision
**Extract all business logic into a standalone `recommend_daemon/` process**
with its own D-Bus service `vn.edu.uit.FSS.RecommendDaemon`.

### Rationale
1. **Extensibility** — New recommendation algorithms (collaborative filtering, transformer-based NER, etc.)
   can be added/replaced without touching DBDaemon or the database layer.
2. **Fault isolation** — NLP model crash (OOM in scikit-crfsuite) won't take down the database.
3. **Independent lifecycle** — DBDaemon starts instantly; recommendation engine loads ~50ms model on demand.
4. **Architecture alignment** — The AGENTS.md component table already lists "Recommend System" as
   a separate row with its own responsibility. This decision makes the code match the architecture.
5. **Clean D-Bus contract** — `vn.edu.uit.FSS.RecommendDaemon` with explicit methods
   (`GenerateShoppingList`, `GetAvailableRecipes`, `RecommendationUpdated`).

### Component Boundaries (Revised)

| Component | Role | D-Bus Service | Data |
|-----------|------|---------------|------|
| **DBDaemon** | Data persistence + IPC broker | `vn.edu.uit.FSS.DBDaemon` | `fss_data.db`, `FSS_Inventory.db`, `FSS_Request.db` |
| **RecommendDaemon** | Business logic: NLP + comparison + shopping list | `vn.edu.uit.FSS.RecommendDaemon` | `FSS_Recommend.db` (NEW) |

---

## 2. Session Summary (2026-05-30)

### What was done (Previous Session — Phase 3 Re-planning)

**Phase 3 Re-planning**:
- Made architectural decision to extract RecommendationEngine from DBDaemon
- Created `recommend_daemon/` folder structure (planned, not yet implemented)
- Defined `FSS-Recommend.db` schema for Bù Trừ (delta/comparison) method
- Wired up D-Bus method placeholders in `DbDbusInterface.py` (may be migrated later)

### Files changed (Previous Session)
- `HANDOVER_CHAT.md` — Updated roadmap, added ADR-001, re-planned phases
- `AGENTS.md` — Added RecommendDaemon to architecture table, D-Bus services, startup

---

### What was done (Current Session — Phase 3 Implementation)

**Phase 3 — DBDaemon Cleanup (Completed)**:
1. **Removed** `db_daemon/src/RecommendationEngine.py` — business logic extracted to future `recommend_daemon/`
2. **Refactored** `DbDbusInterface.py` — removed all recommendation-specific callbacks (`_shopping_list_callback`, `_inventory_update_callback`, `_recipes_callback`). Removed D-Bus methods `GenerateShoppingList`, `GetCurrentInventory`, `GetAvailableRecipes`, `UpdateInventoryFromNotification`. Removed `RecommendationUpdated` signal.
3. **Added** pure database D-Bus methods:
   - `GetInventory()` → JSON of `FSS_Inventory.db` contents
   - `GetRequests()` → JSON of `FSS_Request.db` contents
   - `InsertRequest(recipe_name, ingredients_json, batch_id)` → bool
   - `ClearRequest(batch_id)` → bool
4. **Simplified** `DbDaemonMain.py` — removed `RecommendationEngine` import/init, `NLP_MODEL_PATH`/`NLP_RECIPE_DB_PATH` constants, `_initialize_nlp_engine()`, and all 4 recommendation event handlers. Wired new DB handlers directly to `SqliteManager`.
5. **Updated** `__init__.py` — removed `RecommendationEngine` from exports (v1.1.0)
6. **Created** `db_daemon/tests/test_phase3_cleanup.py` — 34 tests across 6 test classes
7. **Fixed** outdated unit tests in `tests/unit/db_daemon/test_db_dbus_interface.py`

### Files changed (Current Session)
- `db_daemon/src/RecommendationEngine.py` — **Deleted**
- `db_daemon/src/DbDbusInterface.py` — Removed recommend logic, added pure DB methods
- `db_daemon/src/DbDaemonMain.py` — Simplified, removed NLP/recommend engine dependencies
- `db_daemon/src/__init__.py` — Removed `RecommendationEngine` from exports (v1.1.0)
- `db_daemon/tests/test_phase3_cleanup.py` — **Created** (34 tests)
- `tests/unit/db_daemon/test_db_dbus_interface.py` — Fixed signatures for new API

### Verification Results
- Phase 1 backward compatibility: ✅ **16/16 tests pass**
- Phase 3 cleanup tests: ✅ **34/34 tests pass**

---

## 3. Project Phase Roadmap (Revised)

| Phase | Component | Branch | Status |
|-------|-----------|--------|--------|
| Phase 1 | DBDaemon DB schema | `DBDaemon-dev` | ✅ Complete |
| Phase 2 | Recommend System (NLP) | `recommend_system` | ✅ Complete |
| Phase 3 | **DBDaemon cleanup** — Remove RecommendationEngine, expose DB-only D-Bus | `DBDaemon-dev` | ✅ Complete |
| Phase 4 | **Recommend Daemon** — New component `recommend_daemon/` with D-Bus service | `recommend_daemon` | 🔜 Next |
| Phase 5 | **FSS-Recommend DB** — Bù Trừ method + shopping list persistence | `recommend_daemon` | ❌ Not started |

---

## 4. Phase 3 — DBDaemon Cleanup (Completed ✅)

### What was done
1. ✅ **Removed** `db_daemon/src/RecommendationEngine.py`
2. ✅ **Removed** recommendation D-Bus methods from `DbDbusInterface.py`
3. ✅ **Simplified** `DbDaemonMain.py` — no RecommendationEngine init/handlers
4. ✅ **Exposed** pure database D-Bus methods: `GetInventory`, `GetRequests`, `InsertRequest`, `ClearRequest`
5. ✅ **Tests**: 34 tests in `db_daemon/tests/test_phase3_cleanup.py`

### Delivers
- DBDaemon is now a pure **data controller + IPC broker**
- Any future business logic component reads/writes through DBDaemon's D-Bus interface

---

## 4b. Phase 4 — Recommend Daemon (Next)

### Folder Structure
```
recommend_daemon/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Entry point, D-Bus service registration
│   ├── RecommendEngine.py           # Orchestration: NLP → compare → format
│   ├── DbusInterface.py             # D-Bus service vn.edu.uit.FSS.RecommendDaemon
│   └── RecommendDbManager.py        # FSS-Recommend.db CRUD
├── tests/
│   ├── __init__.py
│   └── test_recommend_engine.py
├── requirements.txt
└── systemd/
    └── recommend_daemon.service
```

### What to implement

1. **recommend_daemon/ folder + requirements.txt**:
   - Create directory structure and `requirements.txt` (sdbus, joblib, recommend_system dep)
   - Dependencies: `recommend_system` (local), `sdbus`, `scikit-crfsuite`, `joblib`

2. **RecommendDbManager.py**:
   - Database: `FSS-Recommend.db` in `/opt/fss/data/`
   - Schema: `recommendation_log` table + `shopping_list` table (see Phase 5 schema below)
   - CRUD: `insert_recommendation()`, `get_shopping_list(batch_id)`, `mark_item_purchased(item_id)`, `clear_shopping_list(batch_id)`

3. **RecommendEngine.py**:
   - `generate_shopping_list(recipe_name, batch_id)` → NLP + Bu Tru comparison
   - `get_available_recipes()` → from NLP engine
   - `get_shopping_list(batch_id)` → from FSS-Recommend.db
   - `mark_item_purchased(item_id)` → update shopping_list table
   - Calls `recommend_system.RecipeAnalyzerEngine.generate_fss_request()` for NLP
   - Calls `DBDaemon.GetInventory()` via D-Bus for current stock
   - Runs Bu Tru: `FSS-Request - FSS-Inventory = FSS-Recommend`

4. **DbusInterface.py**:
   - Service: `vn.edu.uit.FSS.RecommendDaemon`
   - Methods:
     - `GenerateShoppingList(recipe_name, batch_id)` → JSON result
     - `GetAvailableRecipes()` → JSON recipe list
     - `GetShoppingList(batch_id)` → JSON shopping list
     - `MarkItemPurchased(item_id)` → bool
   - Signals:
     - `RecommendationUpdated(recipe_name, shopping_list_json)`

5. **main.py**:
   - Entry point with logging setup (similar to DBDaemon)
   - Initializes D-Bus interface, RecommendEngine, RecommendDbManager
   - Lazy-loads NLP engine from `recommend_system/` on first recipe analysis

### Key Dependencies
- `recommend_system` (local package) — `from recommend_system.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine`
- `db_daemon` (via D-Bus) — reads `FSS_Inventory.db` and `FSS_Request.db` through DBDaemon's D-Bus interface

### Data Flow
```
User enters recipe in UI
    → D-Bus call to RecommendDaemon.GenerateShoppingList(recipe_name)
    → RecommendDaemon calls RecipeAnalyzerEngine (from recommend_system/)
    → RecommendDaemon calls DBDaemon.GetInventory() via D-Bus
    → RecommendDaemon runs Bu Tru comparison
    → RecommendDaemon stores result in FSS-Recommend.db
    → RecommendDaemon emits RecommendationUpdated signal
    → UI receives signal, displays shopping list
```

---

## 5. Phase 4 — Recommend Daemon (recommend_daemon/)

### Folder Structure
```
recommend_daemon/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Entry point, D-Bus service registration
│   ├── RecommendEngine.py           # Orchestration: NLP → compare → format
│   ├── DbusInterface.py             # D-Bus service vn.edu.uit.FSS.RecommendDaemon
│   └── RecommendDbManager.py        # FSS-Recommend.db CRUD
├── tests/
│   └── test_recommend_engine.py
├── requirements.txt
└── systemd/
    └── recommend_daemon.service
```

### What to implement
1. **RecommendEngine.py** (moved from `db_daemon/src/`):
   - `generate_shopping_list(recipe_name, batch_id)` → NLP + comparison
   - `get_available_recipes()` → from NLP engine
   - `get_shopping_list(batch_id)` → from FSS-Recommend.db
   - `mark_item_purchased(item_id)` → update shopping_list table

2. **DbusInterface.py**:
   - Service: `vn.edu.uit.FSS.RecommendDaemon`
   - Methods:
     - `GenerateShoppingList(recipe_name, batch_id)` → JSON result
     - `GetAvailableRecipes()` → JSON recipe list
     - `GetShoppingList(batch_id)` → JSON shopping list
     - `MarkItemPurchased(item_id)` → bool
   - Signals:
     - `RecommendationUpdated(recipe_name, shopping_list_json)`

3. **RecommendDbManager.py**:
   - Database: `FSS-Recommend.db`
   - See Phase 5 for schema

### Key Dependencies
- `recommend_system` (local package) — `from recommend_system.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine`
- `db_daemon` (via D-Bus) — reads `FSS_Inventory.db` and `FSS_Request.db` through DBDaemon's D-Bus interface

---

## 6. Phase 5 — FSS-Recommend DB (Bù Trừ Method)

### Formula
```
FSS-Request - FSS-Inventory = FSS-Recommend
(what recipe needs) - (what we have) = (shopping list / what to buy)
```

### Database Schema — `FSS-Recommend.db`

#### Table: `recommendation_log`
Stores each recipe analysis result as a persistent snapshot.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK AUTOINCREMENT | Unique ID |
| `recipe_name` | TEXT NOT NULL | Vietnamese recipe name |
| `batch_id` | TEXT NOT NULL | UUID linking to `FSS_Request.request_batch_id` |
| `nlp_status` | TEXT | NLP result status (SUCCESS/NOT_FOUND/ERROR) |
| `total_items` | INTEGER | Total ingredient count from recipe |
| `available_count` | INTEGER | Items fully available in inventory |
| `needed_count` | INTEGER | Items partially available (need more) |
| `missing_count` | INTEGER | Items completely missing |
| `status` | TEXT DEFAULT 'pending' | Lifecycle: `pending` / `fulfilled` / `cancelled` |
| `result_json` | TEXT | Full comparison snapshot as JSON |
| `created_at` | TIMESTAMP | When analysis ran |
| `completed_at` | TIMESTAMP | When shopping was completed |

Index: `idx_recommendation_batch_id` on `batch_id`

#### Table: `shopping_list`
Individual items the user needs to buy.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK AUTOINCREMENT | Unique ID |
| `recommendation_id` | INTEGER FK | → `recommendation_log.id` |
| `food_id` | TEXT NOT NULL | Ingredient name |
| `required_qty` | INTEGER | Quantity needed by recipe |
| `available_qty` | INTEGER | Quantity in inventory at comparison time |
| `shortage` | INTEGER | `required_qty - available_qty` (what to buy) |
| `unit` | TEXT | Measurement unit |
| `purchased` | BOOLEAN DEFAULT 0 | Whether user bought this item |
| `purchased_at` | TIMESTAMP | When user marked it bought |
| `created_at` | TIMESTAMP | Default CURRENT_TIMESTAMP |

Indexes: `idx_shopping_recommendation` on `recommendation_id`, `idx_shopping_purchased` on `purchased`

### Bù Trừ Algorithm (pseudocode)
```
def bu_tru(recipe_ingredients, current_inventory):
    result = {
        "available": [],   # have enough
        "needed": [],      # have some, need more
        "missing": []      # have none
    }
    for ingredient in recipe_ingredients:
        inv_qty = lookup_inventory(ingredient.food_id)
        req_qty = ingredient.quantity
        shortage = req_qty - inv_qty

        if inv_qty >= req_qty:
            result.available.append(ingredient)
        elif inv_qty > 0:
            result.needed.append({...shortage...})
        else:
            result.missing.append({...req_qty...})

    persist_to_FSS_Recommend_db(result)
    return result
```

---

## 7. Key Architecture Decisions (Revised)

### D-Bus service ownership
| Component | D-Bus Service | Purpose |
|-----------|---------------|---------|
| SensorDaemon | `vn.edu.uit.FSS.SensorDaemon` | Sensor data broadcast |
| FRTApp | `vn.edu.uit.FSS.FRTApp` | Food detection events |
| DBDaemon | `vn.edu.uit.FSS.DBDaemon` | Data persistence + query |
| RecommendDaemon | `vn.edu.uit.FSS.RecommendDaemon` | Business logic: NLP + comparison + shopping |
| MagicMirror UI | (listener only) | Consumes signals from all daemons |

### Data flow (revised)
```
User enters recipe in UI
    → D-Bus call to RecommendDaemon.GenerateShoppingList(recipe_name)
    → RecommendDaemon calls RecipeAnalyzerEngine (from recommend_system/)
    → RecommendDaemon calls DBDaemon.GetInventory() via D-Bus
    → RecommendDaemon runs Bù Trừ comparison
    → RecommendDaemon stores result in FSS-Recommend.db
    → RecommendDaemon emits RecommendationUpdated signal
    → UI receives signal, displays shopping list
```

### Database ownership
- `DBDaemon` owns: `fss_data.db`, `FSS_Inventory.db`, `FSS_Request.db`
- `RecommendDaemon` owns: `FSS-Recommend.db`

---

## 8. Pending Items / Known Issues

### Phase 3 — Completed ✅
- [x] Remove `RecommendationEngine.py` from `db_daemon/src/`
- [x] Simplify DBDaemon D-Bus interface to pure CRUD methods
- [x] Expose `GetInventory()`, `GetRequests()`, `InsertRequest()`, `ClearRequest()` on DBDaemon
- [x] Tests: 34 integration tests for DB-only operations

### Phase 4 — Recommend Daemon (Next)
- [ ] Create `recommend_daemon/` folder structure and files
- [ ] Implement `RecommendDbManager.py` with FSS-Recommend.db schema
- [ ] Implement `RecommendEngine.py` with Bù Trừ algorithm (re-implement from deleted `RecommendationEngine.py`)
- [ ] Implement `DbusInterface.py` — D-Bus service `vn.edu.uit.FSS.RecommendDaemon`
- [ ] Implement `main.py` — entry point with lazy NLP engine loading
- [ ] Create `tests/test_recommend_engine.py` — unit tests
- [ ] Create `requirements.txt` and `systemd/recommend_daemon.service`

### Phase 5 — FSS-Recommend DB (Follows Phase 4)
- [ ] `shopping_list` table CRUD and `mark_item_purchased()`
- [ ] `recommendation_log` table with full snapshot persistence
- [ ] Bù Trừ delta comparison edge cases

### Integration (After Phase 4+5)
- [ ] Wire ElectronApp UI to call RecommendDaemon instead of DBDaemon
- [ ] Update `startup_fss_system.sh` to include `recommend_daemon`
- [ ] Create `systemd/recommend_daemon.service`

---

## 9. Repository Information

| Property | Value |
|----------|-------|
| Remote | `origin` → `https://github.com/BeginnerCoder52/FSS.git` |
| Current branch | `DBDaemon-dev` (Phase 3 complete) |
| Next branch | `recommend_daemon` (create new from `main` for Phase 4) |
| Project root | `/home/richardmelvin52/FSS` |

### Branches overview
| Branch | Phase | Component |
|--------|-------|-----------|
| `main` | — | Integration/stable |
| `DBDaemon-dev` | 1, 3 | Database + IPC broker |
| `recommend_system` | 2 | NLP library (CRF model + recipes) |
| `FRTApp-dev` | — | Food recognition (C++ + Python) |
| `SensorDaemon-dev` | — | Hardware I/O |
| `ElectronApp-dev` | — | MagicMirror UI |
| `recommend_daemon` (NEW) | 4, 5 | Business logic daemon |

---

*End of handover. Next session should create branch `recommend_daemon` from `main` and implement Phase 4 (Recommend Daemon), followed by Phase 5 (FSS-Recommend DB).*
