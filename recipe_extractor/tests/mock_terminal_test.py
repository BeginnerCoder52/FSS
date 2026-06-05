"""
Real Hardware Terminal Test — Recommend System with real CRF model & recipe DB
==============================================================================

Purpose:
    Simulate a real user typing recipe names in the terminal.
    Uses the actual RecipeAnalyzerEngine with:
      - Real CRF model (fss_ner_crf_optimized.joblib)
      - Real recipe database (2470 Vietnamese recipes)
      - Real NLP inference pipeline

Usage:
    python tests/mock_terminal_test.py
    python tests/mock_terminal_test.py --recipe "thịt kho"
    python tests/mock_terminal_test.py --recipe "trứng chiên" --recipe "cá kho"
"""

import json
import sys
import os
import argparse
import logging
from typing import List, Dict, Optional
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).parent.parent
MODEL_PATH = str(PROJECT_ROOT / "models" / "fss_ner_crf_optimized.joblib")
RECIPE_DB_PATH = str(PROJECT_ROOT / "data" / "recipes")


from RecipeAnalyzerAPI import RecipeAnalyzerEngine


COUNT_UNITS = {
    "trái", "quả", "cái", "con", "hộp", "gói",
    "cây", "củ", "bó", "tép", "miếng", "tô",
    "chén", "cốc", "muỗng", "thìa", "lá", "nhánh",
    "bát", "đĩa", "lon", "chai", "lọ", "ống",
}

MASS_UNITS = {"g", "kg", "gram", "ki-lô", "lít", "l", "ml"}


class RealRecipeEngineWrapper:
    def __init__(self):
        logger.info(f"Loading CRF model: {MODEL_PATH}")
        logger.info(f"Loading recipes from: {RECIPE_DB_PATH}")
        self.engine = RecipeAnalyzerEngine(
            model_path=MODEL_PATH,
            recipe_db_path=RECIPE_DB_PATH,
        )
        self.recipe_names = self.engine.get_available_recipes()
        print(f"  ✓ Loaded {len(self.recipe_names)} real recipes")
        print(f"  ✓ CRF model loaded ({os.path.getsize(MODEL_PATH) // 1024} KB)")

    def extract_recipe(self, name: str) -> Optional[Dict]:
        name = name.strip().lower()
        result = self.engine.generate_fss_request(name)
        if result["status"] == "SUCCESS":
            ingredients = []
            for ing in result.get("ingredients", []):
                ingredients.append({
                    "ingredient": ing["ingredient"],
                    "quantity": ing.get("quantity", "1"),
                    "unit": "",
                })
            return {
                "serving": "N/A",
                "ingredients": ingredients,
            }
        elif result["status"] == "NOT_FOUND":
            suggestions = result.get("suggestions", [])
            if suggestions:
                chosen = suggestions[0]
                print(f"  → Không tìm thấy '{name}', dùng '{chosen}' thay thế")
                return self.extract_recipe(chosen)
            print(f"  ✗ Không tìm thấy '{name}' và không có gợi ý")
            return None
        else:
            print(f"  ✗ Lỗi: {result.get('error', 'Unknown error')}")
            return None

    def search_recipe(self, query: str) -> List[str]:
        matches = [n for n in self.recipe_names if query.lower() in n]
        if not matches:
            from difflib import get_close_matches
            matches = get_close_matches(query.lower(), self.recipe_names, n=3, cutoff=0.3)
        return matches


def is_count_unit(unit: str) -> bool:
    return unit.lower() in COUNT_UNITS


def display_recipe(name: str, data: Dict) -> None:
    print(f"\n  ┌─ Món: {name.upper():<30}─┐")
    print(f"  │ Khẩu phần: {data['serving']:<28}│")

    count_ings = []
    dropped = []
    for ing in data["ingredients"]:
        unit = ing.get("unit", "").lower()
        if not unit or is_count_unit(unit):
            count_ings.append(ing)
        else:
            dropped.append(ing)

    if not count_ings:
        print("  │ (không có nguyên liệu đếm được)         │")
    else:
        print(f"  ├──────────┬──────────┬──────────┤")
        print(f"  │ Nguyên liệu │ Số lượng │ Đơn vị   │")
        print(f"  ├──────────┼──────────┼──────────┤")
        for ing in count_ings:
            name_col = ing["ingredient"][:14].ljust(14)
            qty_col = ing["quantity"].rjust(6)
            unit_col = (ing["unit"] or " ").ljust(8)
            print(f"  │ {name_col}│ {qty_col}  │ {unit_col}│")
        print(f"  └──────────┴──────────┴──────────┘")

    if dropped:
        print(f"  ⚠ Bỏ qua nguyên liệu tính bằng khối lượng/thể tích:")
        for d in dropped:
            print(f"    · {d['ingredient']}: {d['quantity']}{d['unit']}")

    total_count = sum(int(ing["quantity"]) for ing in count_ings if ing["quantity"].isdigit())
    print(f"  → Tổng số nguyên liệu đếm được: {total_count}")


def display_combined(results: List[tuple]) -> None:
    print("\n" + "=" * 60)
    print("  KẾT QUẢ PHÂN TÍCH CÔNG THỨC")
    print("=" * 60)

    all_count_ings = []
    for name, data in results:
        display_recipe(name, data)
        for ing in data["ingredients"]:
            unit = ing.get("unit", "").lower()
            if not unit or is_count_unit(unit):
                all_count_ings.append({**ing, "recipe": name})

    if len(results) > 1:
        print("\n" + "─" * 60)
        print("  DANH SÁCH ĐI CHỢ (gộp từ nhiều món)")
        print("─" * 60)

        merged: Dict[str, Dict] = {}
        for ing in all_count_ings:
            key = f"{ing['ingredient'].lower()}"
            if key in merged:
                q1 = int(merged[key]["quantity"]) if merged[key]["quantity"].isdigit() else 0
                q2 = int(ing["quantity"]) if ing["quantity"].isdigit() else 0
                merged[key]["quantity"] = str(q1 + q2)
                merged[key]["from_recipes"].append(ing["recipe"])
            else:
                merged[key] = {
                    "ingredient": ing["ingredient"],
                    "quantity": ing["quantity"],
                    "unit": ing.get("unit", ""),
                    "from_recipes": [ing["recipe"]],
                }

        print(f"  ├──────────┬──────────┬──────────┬──────────┤")
        print(f"  │ Nguyên liệu │ SL       │ Đơn vị   │ Dùng cho │")
        print(f"  ├──────────┼──────────┼──────────┼──────────┤")
        for item in merged.values():
            name_col = item["ingredient"][:14].ljust(14)
            qty_col = item["quantity"].rjust(6)
            unit_col = (item["unit"] or " ").ljust(8)
            recipes_col = ", ".join(item["from_recipes"])[:14]
            print(f"  │ {name_col}│ {qty_col}  │ {unit_col}│ {recipes_col:<10}│")
        print(f"  └──────────┴──────────┴──────────┴──────────┘")


def interactive_mode(wrapper: RealRecipeEngineWrapper) -> List[str]:
    print("\n─── NHẬP CÔNG THỨC (tối đa 2 món) ───")
    print("  Nhập 'q' để thoát, 'ls' để xem danh sách món có sẵn\n")

    recipes = []
    for i in range(1, 3):
        prompt = f"  Món thứ {i}: " if i == 1 else f"  Món thứ {i} (hoặc Enter để kết thúc): "
        raw = input(prompt).strip()
        if raw.lower() in ("q", "quit", "exit"):
            break
        if raw.lower() == "ls":
            print(f"\n  Danh sách món ({len(wrapper.recipe_names)}):")
            for name in sorted(wrapper.recipe_names)[:30]:
                print(f"    · {name}")
            print(f"    ... (+ {len(wrapper.recipe_names) - 30} món khác)")
            print()
            i -= 1
            continue
        if not raw:
            break
        recipes.append(raw)
    return recipes


def main():
    parser = argparse.ArgumentParser(
        description="Real hardware terminal test for Recommend System — uses real CRF model + recipe DB"
    )
    parser.add_argument(
        "--recipe",
        action="append",
        dest="recipes",
        help="Recipe name (can be used up to 2 times)",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available recipes and exit"
    )
    args = parser.parse_args()

    print("\n  ╔══════════════════════════════════════════════╗")
    print("  ║   RECOMMEND SYSTEM — REAL HARDWARE TEST      ║")
    print("  ║   CRF model + 2470 Vietnamese recipes        ║")
    print("  ╚══════════════════════════════════════════════╝")

    wrapper = RealRecipeEngineWrapper()

    if args.list:
        print(f"\n  Danh sách món ({len(wrapper.recipe_names)}):")
        for name in sorted(wrapper.recipe_names):
            print(f"    · {name}")
        print()
        return

    recipe_names: List[str] = args.recipes if args.recipes else []

    if len(recipe_names) > 2:
        print("  ⚠ Chỉ chấp nhận tối đa 2 món. Lấy 2 món đầu tiên.")
        recipe_names = recipe_names[:2]

    if not recipe_names:
        recipe_names = interactive_mode(wrapper)

    if not recipe_names:
        print("  Không có món nào được nhập.")
        return

    results = []
    for name in recipe_names:
        print(f"\n  🔍 Đang tra cứu: '{name}'...")
        data = wrapper.extract_recipe(name)
        if data:
            results.append((name, data))
        else:
            suggestions = wrapper.search_recipe(name)
            if suggestions:
                print(f"    Gợi ý: {', '.join(suggestions)}")

    if results:
        display_combined(results)
        print()


if __name__ == "__main__":
    main()
