#!/usr/bin/env python3
"""
Phase 2 Validation Script
=========================

Simple syntax and structure validation for Phase 2 implementation.
Does not require external dependencies (joblib, scikit-crfsuite, etc.).

Purpose:
    - Verify Python syntax is correct
    - Check that all required classes/functions are defined
    - Validate module exports
    - Verify documentation completeness

Run:
    python3 validate_phase2.py
"""

import sys
import os
import ast
from pathlib import Path


def check_file_syntax(filepath: str) -> tuple[bool, str]:
    """
    Check if Python file has valid syntax.
    
    Returns: (success, message)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, f"✓ Syntax valid ({len(code)} bytes)"
    except SyntaxError as e:
        return False, f"✗ Syntax error: {e}"
    except Exception as e:
        return False, f"✗ Error: {e}"


def check_class_exists(filepath: str, class_name: str) -> tuple[bool, str]:
    """Check if class is defined in file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return True, f"✓ Class '{class_name}' found"
        
        return False, f"✗ Class '{class_name}' not found"
    except Exception as e:
        return False, f"✗ Error: {e}"


def check_function_exists(filepath: str, func_name: str) -> tuple[bool, str]:
    """Check if function is defined in file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return True, f"✓ Function '{func_name}' found"
        
        return False, f"✗ Function '{func_name}' not found"
    except Exception as e:
        return False, f"✗ Error: {e}"


def main():
    """Run Phase 2 validation."""
    print("=" * 70)
    print("PHASE 2 VALIDATION - NLP Pipeline Setup")
    print("=" * 70)
    print()
    
    base_path = Path(__file__).parent
    all_passed = True
    
    # Check 1: RecipeAnalyzerAPI.py
    print("1. RecipeAnalyzerAPI.py")
    print("-" * 70)
    
    api_file = base_path / "src" / "RecipeAnalyzerAPI.py"
    if not api_file.exists():
        print("✗ File not found:", api_file)
        all_passed = False
    else:
        # Syntax check
        success, msg = check_file_syntax(str(api_file))
        print(f"  Syntax: {msg}")
        all_passed = all_passed and success
        
        # Class checks
        classes = ["BIOTagSchema", "RecipeAnalyzerEngine"]
        for cls in classes:
            success, msg = check_class_exists(str(api_file), cls)
            print(f"  {msg}")
            all_passed = all_passed and success
        
        # Function checks
        functions = ["load_model", "normalize_ingredient_text", 
                     "word2features", "sent2features"]
        for func in functions:
            success, msg = check_function_exists(str(api_file), func)
            print(f"  {msg}")
            all_passed = all_passed and success
    
    print()
    
    # Check 2: RecipeProcessor.py
    print("2. RecipeProcessor.py")
    print("-" * 70)
    
    proc_file = base_path / "src" / "RecipeProcessor.py"
    if not proc_file.exists():
        print("✗ File not found:", proc_file)
        all_passed = False
    else:
        # Syntax check
        success, msg = check_file_syntax(str(proc_file))
        print(f"  Syntax: {msg}")
        all_passed = all_passed and success
        
        # Function checks
        functions = ["tokenize_vietnamese", "extract_features",
                     "normalize_quantity", "detect_quantity_unit",
                     "remove_special_characters", "normalize_unicode",
                     "sentence_to_features"]
        for func in functions:
            success, msg = check_function_exists(str(proc_file), func)
            print(f"  {msg}")
            all_passed = all_passed and success
    
    print()
    
    # Check 3: Tests
    print("3. test_recipe_analyzer.py")
    print("-" * 70)
    
    test_file = base_path / "tests" / "test_recipe_analyzer.py"
    if not test_file.exists():
        print("✗ File not found:", test_file)
        all_passed = False
    else:
        # Syntax check
        success, msg = check_file_syntax(str(test_file))
        print(f"  Syntax: {msg}")
        all_passed = all_passed and success
        
        # Class checks
        test_classes = ["TestRecipeAnalyzerEngineInitialization",
                        "TestRecipeProcessor",
                        "TestBIOTagSchema",
                        "TestRecipeAnalyzerIntegration"]
        for cls in test_classes:
            success, msg = check_class_exists(str(test_file), cls)
            print(f"  {msg}")
            all_passed = all_passed and success
    
    print()
    
    # Check 4: Module exports
    print("4. src/__init__.py")
    print("-" * 70)
    
    init_file = base_path / "src" / "__init__.py"
    if not init_file.exists():
        print("✗ File not found:", init_file)
        all_passed = False
    else:
        success, msg = check_file_syntax(str(init_file))
        print(f"  Syntax: {msg}")
        all_passed = all_passed and success
        
        # Check for __all__ export
        try:
            with open(init_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if "__all__" in content:
                print("  ✓ Module exports (__all__) defined")
            else:
                print("  ✗ Module exports (__all__) not defined")
                all_passed = False
        except Exception as e:
            print(f"  ✗ Error: {e}")
            all_passed = False
    
    print()
    
    # Check 5: Model and data files
    print("5. Model and Data Files")
    print("-" * 70)
    
    model_file = base_path / "models" / "fss_ner_crf_optimized.joblib"
    if model_file.exists():
        size_mb = model_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Model file found ({size_mb:.2f} MB)")
    else:
        print(f"  ✗ Model file not found: {model_file}")
        all_passed = False
    
    recipes_dir = base_path / "data" / "recipes"
    if recipes_dir.exists():
        recipe_count = len(list(recipes_dir.glob("*.json")))
        print(f"  ✓ Recipes directory found ({recipe_count} recipe files)")
    else:
        print(f"  ✗ Recipes directory not found: {recipes_dir}")
        all_passed = False
    
    print()
    
    # Check 6: Requirements
    print("6. requirements.txt")
    print("-" * 70)
    
    req_file = base_path / "requirements.txt"
    if req_file.exists():
        with open(req_file, 'r') as f:
            reqs = f.read()
        
        required_packages = ['scikit-crfsuite', 'pyvi', 'joblib']
        for pkg in required_packages:
            if pkg in reqs:
                print(f"  ✓ {pkg} listed")
            else:
                print(f"  ✗ {pkg} not listed")
                all_passed = False
    else:
        print(f"  ✗ File not found: {req_file}")
        all_passed = False
    
    print()
    
    # Check 7: Documentation
    print("7. Documentation")
    print("-" * 70)
    
    doc_file = base_path / "PHASE2_COMPLETION_SUMMARY.md"
    if doc_file.exists():
        size_kb = doc_file.stat().st_size / 1024
        print(f"  ✓ Phase 2 completion summary found ({size_kb:.1f} KB)")
    else:
        print(f"  ✗ Completion summary not found: {doc_file}")
        all_passed = False
    
    print()
    print("=" * 70)
    
    if all_passed:
        print("✓ PHASE 2 VALIDATION: ALL CHECKS PASSED")
        print("=" * 70)
        return 0
    else:
        print("✗ PHASE 2 VALIDATION: SOME CHECKS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
