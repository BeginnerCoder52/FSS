import sys
import time
import json
from pathlib import Path

# Fix sys.path for imports
FSS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FSS_ROOT))
sys.path.insert(0, str(FSS_ROOT / "recipe_extractor" / "src"))
sys.path.insert(0, str(FSS_ROOT / "recommend_daemon" / "src"))

from RecipeAnalyzerAPI import RecipeAnalyzerEngine
from RecommendEngine import RecommendEngine

# ANSI Escape Codes for Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_box(text, color=Colors.CYAN):
    print(f"{color}======================================================================{Colors.ENDC}")
    print(f"{color}{text}{Colors.ENDC}")
    print(f"{color}======================================================================{Colors.ENDC}")

def simulate_typing(text, delay=0.03, end='\n'):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()

def main():
    print_box(f"{Colors.BOLD}FSS System - Recipe Extractor & Recommendation Module Demo{Colors.ENDC}")
    
    print(f"[{Colors.BLUE}SYSTEM{Colors.ENDC}] Khởi tạo RecipeAnalyzerEngine (Dữ liệu có cấu trúc)...")
    recipe_db_path = str(FSS_ROOT / "recipe_extractor" / "data" / "recipes")
    
    # Initialize Engine
    t0 = time.time()
    extractor_engine = RecipeAnalyzerEngine(recipe_db_path=recipe_db_path)
    recommend_engine = RecommendEngine(analyzer_engine=extractor_engine, db_manager=None)
    load_time = (time.time() - t0) * 1000
    
    print(f"[{Colors.GREEN}SUCCESS{Colors.ENDC}] Tải dữ liệu công thức hoàn tất. Thời gian: {load_time:.2f}ms\n")
    
    # Available recipes to suggest if they type something wrong
    available = extractor_engine.get_available_recipes()
    suggested_recipes = ["thịt kho tàu", "bún chả", "canh chua cá lóc"]
    print(f"{Colors.WARNING}Gợi ý món ăn: {', '.join(suggested_recipes)}{Colors.ENDC}\n")
    
    while True:
        try:
            dish_name = input(f"{Colors.BOLD}🧑 BẠN MUỐN NẤU MÓN GÌ? (Nhấn Ctrl+C để thoát) > {Colors.ENDC}")
            if not dish_name.strip():
                continue
            
            print(f"\n[{Colors.CYAN}BƯỚC 1: TRÍCH XUẤT CÔNG THỨC{Colors.ENDC}]")
            simulate_typing(f"Đang tìm kiếm công thức cho: '{dish_name}'...", delay=0.01)
            
            t1 = time.time()
            extractor_result = extractor_engine.generate_fss_request(dish_name)
            extractor_time = (time.time() - t1) * 1000
            
            if extractor_result["status"] != "SUCCESS":
                print(f"[{Colors.FAIL}LỖI{Colors.ENDC}] {extractor_result.get('error', 'Không tìm thấy công thức.')}")
                continue
                
            print(f"[{Colors.GREEN}TÌM THẤY{Colors.ENDC}] Tên món (chuẩn hóa): {Colors.BOLD}{extractor_result['dish']}{Colors.ENDC}")
            print(f"Thời gian xử lý: {extractor_time:.2f}ms")
            print(f"Danh sách nguyên liệu ({len(extractor_result['original_ingredients'])} mục):")
            for ing in extractor_result['original_ingredients']:
                print(f"  🍲 {ing}")
                
            print(f"\n[{Colors.CYAN}BƯỚC 2: ĐỐI CHIẾU TỒN KHO & ĐỀ XUẤT MUA SẮM{Colors.ENDC}]")
            simulate_typing(f"Đang kiểm tra cơ sở dữ liệu DBDaemon (Giả lập tồn kho trống)...", delay=0.01)
            
            t2 = time.time()
            recommend_result = recommend_engine.generate_shopping_list(dish_name, inventory=[])
            rec_time = (time.time() - t2) * 1000
            
            print(f"[{Colors.GREEN}HOÀN TẤT{Colors.ENDC}] Thời gian đối chiếu: {rec_time:.2f}ms")
            print(f"Thống kê: Cần {recommend_result['total_items']} | Đã có {recommend_result['available_count']} | {Colors.FAIL}Thiếu {recommend_result['missing_count']}{Colors.ENDC}")
            
            print(f"\n{Colors.WARNING}📋 DANH SÁCH MUA SẮM (SHOPPING LIST):{Colors.ENDC}")
            for item in recommend_result['shopping_list']:
                print(f"  🛒 [ ] {Colors.BOLD}{item['food_id']}{Colors.ENDC} - {item['required_qty']} (Cần bổ sung)")
                
            print("\n" + "-"*60 + "\n")
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.GREEN}Đã thoát chương trình. Chúc một ngày tốt lành!{Colors.ENDC}")
            break

if __name__ == '__main__':
    main()
