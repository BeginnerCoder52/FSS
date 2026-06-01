"""
Mock Terminal Test — Simulate user input up to 2 recipes
=========================================================

Purpose:
    Simulate a real user typing recipe names in the terminal.
    The system returns a structured list of ingredients counted by unit
    (trái, quả, cái, con, hộp, gói, ...) — NOT by grams or liters.
    
    This covers the real RecommendDaemon flow:
        User input → NLP extract → Bù Trừ comparison

Usage:
    python tests/mock_terminal_test.py
    python tests/mock_terminal_test.py --recipe "thịt kho"
    python tests/mock_terminal_test.py --recipe "trứng chiên" --recipe "cá kho"

Example Output:
    ┌──────────────────────────────────────────────────────────┐
    │  Recipe: trứng chiên                                     │
    │  ┌──────────┬──────────┬───────┐                        │
    │  │ Món      | SL       | Đơn vị│                        │
    │  ├──────────┼──────────┼───────┤                        │
    │  │ Trứng gà | 2        | quả   │                        │
    │  │ Hành lá  | 1        | cái   │                        │
    │  └──────────┴──────────┴───────┘                        │
    └──────────────────────────────────────────────────────────┘
"""

import json
import sys
import os
import argparse
from typing import List, Dict, Optional
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


COUNT_UNITS = {
    "trái", "quả", "cái", "con", "hộp", "gói",
    "cây", "củ", "bó", "tép", "miếng", "tô",
    "chén", "cốc", "muỗng", "thìa", "lá", "nhánh",
    "bát", "đĩa", "lon", "chai", "lọ", "ống",
}


MASS_UNITS = {"g", "kg", "gram", "ki-lô", "lít", "l", "ml"}


MOCK_RECIPES = {
    "trứng chiên": {
        "serving": "2 người",
        "ingredients": [
            {"ingredient": "Trứng gà", "quantity": "2", "unit": "quả"},
            {"ingredient": "Dầu ăn", "quantity": "2", "unit": "muỗng"},
            {"ingredient": "Hành lá", "quantity": "1", "unit": "cái"},
            {"ingredient": "Muối", "quantity": "1", "unit": "nhúm"},
            {"ingredient": "Tiêu", "quantity": "1", "unit": "nhúm"},
        ],
    },
    "thịt kho": {
        "serving": "4 người",
        "ingredients": [
            {"ingredient": "Thịt ba chỉ", "quantity": "300", "unit": "g"},
            {"ingredient": "Trứng gà", "quantity": "4", "unit": "quả"},
            {"ingredient": "Hành tím", "quantity": "3", "unit": "củ"},
            {"ingredient": "Nước mắm", "quantity": "2", "unit": "muỗng"},
            {"ingredient": "Đường", "quantity": "1", "unit": "muỗng"},
            {"ingredient": "Tiêu", "quantity": "1", "unit": "nhúm"},
            {"ingredient": "Dừa tươi", "quantity": "1", "unit": "trái"},
        ],
    },
    "cá kho": {
        "serving": "3 người",
        "ingredients": [
            {"ingredient": "Cá lóc", "quantity": "1", "unit": "con"},
            {"ingredient": "Hành tím", "quantity": "2", "unit": "củ"},
            {"ingredient": "Ớt", "quantity": "2", "unit": "trái"},
            {"ingredient": "Nước mắm", "quantity": "3", "unit": "muỗng"},
            {"ingredient": "Đường", "quantity": "1", "unit": "muỗng"},
            {"ingredient": "Tiêu", "quantity": "1", "unit": "nhúm"},
        ],
    },
    "gỏi trộn khô mực": {
        "serving": "4 người",
        "ingredients": [
            {"ingredient": "Bưởi", "quantity": "1", "unit": "trái"},
            {"ingredient": "Mực khô", "quantity": "1", "unit": "con"},
            {"ingredient": "Cà rốt", "quantity": "1", "unit": "củ"},
            {"ingredient": "Rau răm", "quantity": "1", "unit": "bó"},
            {"ingredient": "Đậu phộng", "quantity": "1", "unit": "gói"},
            {"ingredient": "Muối", "quantity": "1", "unit": "nhúm"},
            {"ingredient": "Đường", "quantity": "1", "unit": "muỗng"},
            {"ingredient": "Chanh", "quantity": "1", "unit": "trái"},
        ],
    },
    "canh chua": {
        "serving": "4 người",
        "ingredients": [
            {"ingredient": "Cá lóc", "quantity": "1", "unit": "con"},
            {"ingredient": "Me", "quantity": "1", "unit": "hộp"},
            {"ingredient": "Cà chua", "quantity": "2", "unit": "trái"},
            {"ingredient": "Đậu bắp", "quantity": "5", "unit": "trái"},
            {"ingredient": "Giá đỗ", "quantity": "1", "unit": "bó"},
            {"ingredient": "Rau thơm", "quantity": "1", "unit": "bó"},
            {"ingredient": "Ớt", "quantity": "1", "unit": "trái"},
        ],
    },
}


def is_count_unit(unit: str) -> bool:
    """Return True if the unit is a countable unit (not mass/volume)."""
    return unit.lower() in COUNT_UNITS


def suggest_recipes(query: str) -> List[str]:
    """Simple fuzzy matching on recipe names."""
    query = query.lower().strip()
    matches = [name for name in MOCK_RECIPES if query in name]
    if not matches:
        from difflib import get_close_matches
        matches = get_close_matches(query, MOCK_RECIPES.keys(), n=3, cutoff=0.3)
    return matches


def extract_recipe(name: str) -> Optional[Dict]:
    """Look up a recipe by exact or fuzzy name. Returns None if not found."""
    name = name.lower().strip()
    if name in MOCK_RECIPES:
        return MOCK_RECIPES[name]
    suggestions = suggest_recipes(name)
    if suggestions:
        chosen = suggestions[0]
        print(f"  → Không tìm thấy '{name}', dùng '{chosen}' thay thế")
        return MOCK_RECIPES[chosen]
    return None


def filter_count_ingredients(
    ingredients: List[Dict],
) -> List[Dict]:
    """Keep only count-based ingredients, drop mass/volume ones."""
    filtered = []
    dropped = []
    for ing in ingredients:
        unit = ing.get("unit", "").lower()
        qty = ing.get("quantity", "1")
        if is_count_unit(unit):
            filtered.append(ing)
        else:
            dropped.append(ing)
    return filtered, dropped


def display_recipe(name: str, data: Dict) -> None:
    """Pretty-print a recipe's count-based ingredients to terminal."""
    print(f"\n  ┌─ Món: {name.upper():<30}─┐")
    print(f"  │ Khẩu phần: {data['serving']:<28}│")

    count_ings, dropped = filter_count_ingredients(data["ingredients"])

    if not count_ings:
        print("  │ (không có nguyên liệu đếm được)         │")
    else:
        print(f"  ├──────────┬──────────┬──────────┤")
        print(f"  │ Nguyên liệu │ Số lượng │ Đơn vị   │")
        print(f"  ├──────────┼──────────┼──────────┤")
        for ing in count_ings:
            name_col = ing["ingredient"][:14].ljust(14)
            qty_col = ing["quantity"].rjust(6)
            unit_col = ing["unit"].ljust(8)
            print(f"  │ {name_col}│ {qty_col}  │ {unit_col}│")
        print(f"  └──────────┴──────────┴──────────┘")

    if dropped:
        print(f"  ⚠ Bỏ qua nguyên liệu tính bằng khối lượng/thể tích:")
        for d in dropped:
            print(f"    · {d['ingredient']}: {d['quantity']}{d['unit']}")

    total_count = sum(int(ing["quantity"]) for ing in count_ings)
    print(f"  → Tổng số nguyên liệu đếm được: {total_count}")


def display_combined(results: List[tuple]) -> None:
    """Display multiple recipes and their combined shopping list."""
    print("\n" + "=" * 60)
    print("  KẾT QUẢ PHÂN TÍCH CÔNG THỨC")
    print("=" * 60)

    all_count_ings = []

    for name, data in results:
        display_recipe(name, data)
        count_ings, _ = filter_count_ingredients(data["ingredients"])
        for ing in count_ings:
            all_count_ings.append({**ing, "recipe": name})

    if len(results) > 1:
        print("\n" + "─" * 60)
        print("  DANH SÁCH ĐI CHỢ (gộp từ nhiều món)")
        print("─" * 60)

        merged: Dict[str, Dict] = {}
        for ing in all_count_ings:
            key = f"{ing['ingredient'].lower()}|{ing['unit'].lower()}"
            if key in merged:
                merged[key]["quantity"] = str(
                    int(merged[key]["quantity"]) + int(ing["quantity"])
                )
                merged[key]["from_recipes"].append(ing["recipe"])
            else:
                merged[key] = {
                    "ingredient": ing["ingredient"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                    "from_recipes": [ing["recipe"]],
                }

        print(f"  ├──────────┬──────────┬──────────┬──────────┤")
        print(f"  │ Nguyên liệu │ SL       │ Đơn vị   │ Dùng cho │")
        print(f"  ├──────────┼──────────┼──────────┼──────────┤")
        for item in merged.values():
            name_col = item["ingredient"][:14].ljust(14)
            qty_col = item["quantity"].rjust(6)
            unit_col = item["unit"].ljust(8)
            recipes_col = ", ".join(item["from_recipes"])[:14]
            print(f"  │ {name_col}│ {qty_col}  │ {unit_col}│ {recipes_col:<10}│")
        print(f"  └──────────┴──────────┴──────────┴──────────┘")


def interactive_mode() -> List[str]:
    """Prompt user for up to 2 recipe names in the terminal."""
    print("\n─── NHẬP CÔNG THỨC (tối đa 2 món) ───")
    print("  Nhập 'q' để thoát, 'ls' để xem danh sách món có sẵn\n")

    recipes = []
    for i in range(1, 3):
        prompt = f"  Món thứ {i}: " if i == 1 else f"  Món thứ {i} (hoặc Enter để kết thúc): "
        raw = input(prompt).strip()
        if raw.lower() in ("q", "quit", "exit"):
            break
        if raw.lower() == "ls":
            print(f"\n  Danh sách món ({len(MOCK_RECIPES)}):")
            for name in sorted(MOCK_RECIPES.keys()):
                print(f"    · {name}")
            print()
            i -= 1
            continue
        if not raw:
            break
        recipes.append(raw)

    return recipes


def main():
    parser = argparse.ArgumentParser(
        description="Mock terminal test for Recommend System — simulate user recipe input"
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

    if args.list:
        print(f"\n  Danh sách món ({len(MOCK_RECIPES)}):")
        for name in sorted(MOCK_RECIPES.keys()):
            print(f"    · {name}")
        print()
        return

    recipe_names: List[str] = args.recipes if args.recipes else []

    if len(recipe_names) > 2:
        print("  ⚠ Chỉ chấp nhận tối đa 2 món. Lấy 2 món đầu tiên.")
        recipe_names = recipe_names[:2]

    if not recipe_names:
        recipe_names = interactive_mode()

    if not recipe_names:
        print("  Không có món nào được nhập.")
        return

    results = []
    for name in recipe_names:
        print(f"\n  🔍 Đang tra cứu: '{name}'...")
        data = extract_recipe(name)
        if data:
            results.append((name, data))
        else:
            print(f"  ✗ Không tìm thấy món '{name}'")
            suggestions = suggest_recipes(name)
            if suggestions:
                print(f"    Gợi ý: {', '.join(suggestions)}")

    if results:
        display_combined(results)
        print()


if __name__ == "__main__":
    main()
