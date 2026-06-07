import sys
import os
import time
import json
import sqlite3
import threading
import asyncio

try:
    import sdbus
    from sdbus import DbusInterfaceCommonAsync, dbus_signal_async
except ImportError:
    print("Vui lòng kích hoạt venv và cài đặt sdbus-python: pip install -r requirements.txt")
    sys.exit(1)

# ======================================================================
# 1. Mock D-Bus Classes
# ======================================================================
class MockDbDaemon(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.DBDaemon"):
    @dbus_signal_async('sisi')
    def UIUpdateRequired(self, food_id: str, quantity: int, image_path: str, delta: int) -> None:
        pass

    @dbus_signal_async('sd')
    def DoorStateUpdate(self, door_state: str, timestamp: float) -> None:
        pass

    @dbus_signal_async('dd')
    def EnvironmentUpdateRequired(self, temperature: float, humidity: float) -> None:
        pass

class MockFrtApp(DbusInterfaceCommonAsync, interface_name="vn.edu.uit.FSS.FRTApp"):
    @dbus_signal_async('s')
    def FoodDetected(self, json_data: str) -> None:
        pass

# Global instances
db_daemon_obj = None
frt_app_obj = None
dbus_loop = None

async def setup_dbus_async():
    global db_daemon_obj, frt_app_obj
    sdbus.set_default_bus(sdbus.sd_bus_open_system())
    
    # 1. Register DBDaemon Mock
    await sdbus.request_default_bus_name_async(
        "vn.edu.uit.FSS.DBDaemon", replace_existing=True
    )
    db_daemon_obj = MockDbDaemon()
    db_daemon_obj.export_to_dbus("/vn/edu/uit/FSS/DBDaemon")

    # 2. Register FRTApp Mock
    await sdbus.request_default_bus_name_async(
        "vn.edu.uit.FSS.FRTApp", replace_existing=True
    )
    frt_app_obj = MockFrtApp()
    frt_app_obj.export_to_dbus("/vn/edu/uit/FSS/FRTApp")

def start_dbus_thread():
    global dbus_loop
    dbus_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(dbus_loop)
    dbus_loop.run_until_complete(setup_dbus_async())
    dbus_loop.run_forever()

# Helper for emitting signals safely from main thread
def emit_signal(obj, method_name, *args):
    if obj and dbus_loop:
        signal = getattr(obj, method_name)
        # sdbus signal.emit takes exactly 1 argument (a single value or a tuple of values)
        payload = args[0] if len(args) == 1 else tuple(args)
        if len(args) == 0:
            payload = ()
        dbus_loop.call_soon_threadsafe(signal.emit, payload)

# ======================================================================
# 2. SQLite Update Logic (Standalone)
# ======================================================================
def update_inventory_db(food_id: str, quantity_delta: int, confidence_score: float) -> int:
    """Updates SQLite directly, simulating SqliteManager exactly."""
    db_path = "/opt/fss/data/FSS_Inventory.db"
    
    # Just in case this is running on Windows (testing logic), mock path:
    if os.name == 'nt' and not os.path.exists(db_path):
        os.makedirs("./data", exist_ok=True)
        db_path = "./data/FSS_Inventory.db"

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        
        # Ensure table exists (mimic SqliteManager init)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_id TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL DEFAULT 0,
                confidence_score REAL NOT NULL DEFAULT 0.0,
                image_path TEXT,
                version_id INTEGER NOT NULL DEFAULT 1,
                last_change_reason TEXT DEFAULT 'INITIAL',
                last_changed_by TEXT DEFAULT 'SYSTEM',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT quantity, confidence_score, image_path FROM current_inventory WHERE food_id = ?", (food_id,))
        row = cursor.fetchone()
        
        new_qty = 0
        if row:
            current_qty, current_score, current_image = row
            new_qty = max(0, current_qty + quantity_delta)
            new_score = confidence_score if confidence_score > current_score else current_score
            
            cursor.execute("""
                UPDATE current_inventory
                SET quantity = ?, confidence_score = ?, last_updated = CURRENT_TIMESTAMP
                WHERE food_id = ?
            """, (new_qty, new_score, food_id))
        else:
            new_qty = max(0, quantity_delta)
            cursor.execute("""
                INSERT INTO current_inventory (food_id, quantity, confidence_score, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (food_id, new_qty, confidence_score))
            
        conn.commit()
        conn.close()
        return new_qty
    except Exception as e:
        print(f"Lỗi truy cập SQLite: {e}")
        return 0

# ======================================================================
# 3. Main Menu and Execution
# ======================================================================
def process_food(food_id: str, quantity_delta: int):
    score = 0.95
    print(f"\n[XỬ LÝ] Thay đổi: {food_id} ({quantity_delta})")
    
    # 1. Phát tín hiệu FRTApp (FoodDetected)
    json_data = json.dumps({"id": food_id, "score": score, "qty": quantity_delta})
    emit_signal(frt_app_obj, "FoodDetected", json_data)
    print(" -> [D-Bus] Phát tín hiệu FRTApp (FoodDetected)")
    
    # 2. Cập nhật SQLite
    total_qty = update_inventory_db(food_id, quantity_delta, score)
    print(f" -> [SQLite] Cập nhật thành công: {food_id} tổng = {total_qty}")
    
    # 3. Phát tín hiệu DBDaemon (UIUpdateRequired)
    emit_signal(db_daemon_obj, "UIUpdateRequired", food_id, total_qty, "", quantity_delta)
    print(" -> [D-Bus] Phát tín hiệu DBDaemon (UIUpdateRequired)\n")

def print_menu():
    print("="*50)
    print("FSS Mock CLI (Môi trường Độc lập)")
    print("="*50)
    print("1. Phát hiện thực phẩm (Thêm 3 Apple)")
    print("2. Phát hiện thực phẩm (Bớt 1 Apple)")
    print("3. Phát hiện thực phẩm (Thêm 2 Milk)")
    print("4. Mở cửa (Door Open)")
    print("5. Đóng cửa (Door Close)")
    print("6. Cập nhật Môi trường (Temp/Humid)")
    print("0. Thoát")
    print("="*50)

def main():
    print("Đang khởi tạo D-Bus System Bus cho Môi trường Test...")
    t = threading.Thread(target=start_dbus_thread, daemon=True)
    t.start()
    
    # Đợi bus setup
    time.sleep(1.5)
    
    if not db_daemon_obj or not frt_app_obj:
        print("Lỗi: Không thể khởi tạo D-Bus. Vui lòng chạy với sudo (System Bus).")
        sys.exit(1)
        
    print("Khởi tạo hoàn tất. Đã claim cả 2 service DBDaemon và FRTApp!\n")

    while True:
        print_menu()
        try:
            choice = input("Chọn chức năng (0-6): ").strip()
        except KeyboardInterrupt:
            print("\nĐang thoát...")
            break

        if choice == '1':
            process_food("Apple", 3)
        elif choice == '2':
            process_food("Apple", -1)
        elif choice == '3':
            process_food("Milk", 2)
        elif choice == '4':
            emit_signal(db_daemon_obj, "DoorStateUpdate", "DOOR_OPEN", time.time())
            print("\n -> [D-Bus] Đã gửi Door Open\n")
        elif choice == '5':
            emit_signal(db_daemon_obj, "DoorStateUpdate", "DOOR_CLOSE", time.time())
            print("\n -> [D-Bus] Đã gửi Door Close\n")
        elif choice == '6':
            emit_signal(db_daemon_obj, "EnvironmentUpdateRequired", 24.5, 60.2)
            print("\n -> [D-Bus] Đã gửi thông số Môi trường\n")
        elif choice == '0':
            print("Đang thoát...")
            break
        else:
            print("Lựa chọn không hợp lệ!")
            
    if dbus_loop:
        dbus_loop.call_soon_threadsafe(dbus_loop.stop)
    sys.exit(0)

if __name__ == "__main__":
    main()
