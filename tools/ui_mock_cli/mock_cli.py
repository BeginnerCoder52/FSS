import sys
import os
import time

# Add db_daemon/src to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_daemon_src = os.path.join(script_dir, "../../db_daemon/src")
frt_app_src = os.path.join(script_dir, "../../frt_app/py_ai_core/src")
sys.path.append(db_daemon_src)
sys.path.append(frt_app_src)

try:
    from DbDaemonMain import DbDaemonMain
    from FrtDbusInterface import FrtDbusInterface
except ImportError as e:
    print(f"Lỗi khi import modules: {e}")
    print("Vui lòng đảm bảo bạn đang chạy script này với venv của db_daemon!")
    sys.exit(1)

def print_menu():
    print("\n" + "="*50)
    print("FSS Mock CLI (Direct DbDaemon Call)")
    print("="*50)
    print("1. [FRTApp] Phát hiện thực phẩm (Thêm 3 Apple)")
    print("2. [FRTApp] Phát hiện thực phẩm (Bớt 1 Apple)")
    print("3. [FRTApp] Phát hiện thực phẩm (Thêm 2 Milk)")
    print("4. [Sensor] Mở cửa (Door Open)")
    print("5. [Sensor] Đóng cửa (Door Close)")
    print("6. [Sensor] Cập nhật Môi trường (Temp/Humid)")
    print("0. Thoát")
    print("="*50)

def main():
    print("Đang khởi tạo DbDaemon (kết nối SQLite & D-Bus)...")
    db_daemon = DbDaemonMain()
    
    # Chỉ gọi init_daemon để setup DB và đăng ký D-Bus, không chạy vòng lặp start_daemon()
    if not db_daemon.init_daemon():
        print("Lỗi: Không thể khởi tạo DbDaemon. Vui lòng chạy với sudo (D-Bus System Bus).")
        sys.exit(1)
        
    print("DbDaemon khởi tạo thành công!")

    print("Đang khởi tạo FRTApp D-Bus Interface...")
    frt_daemon = FrtDbusInterface()
    if not frt_daemon.init_sdbus_connection():
        print("Cảnh báo: Không thể khởi tạo FRTApp D-Bus Interface. Bỏ qua.")
    else:
        print("FRTApp D-Bus khởi tạo thành công!")

    while True:
        print_menu()
        try:
            choice = input("Chọn chức năng (0-6): ").strip()
        except KeyboardInterrupt:
            print("\nĐang thoát...")
            db_daemon.stop_daemon()
            break

        if choice == '1':
            print("Đang thêm 3 quả Apple...")
            db_daemon.process_food_tracking_event(food_id="Apple", confidence_score=0.95, quantity_delta=3)
            frt_daemon.publish_tracking_results({"id": "Apple", "score": 0.95, "qty": 3})
            print("Đã gọi hàm cập nhật database và phát tín hiệu (DBDaemon & FRTApp).")
        elif choice == '2':
            print("Đang bớt 1 quả Apple...")
            db_daemon.process_food_tracking_event(food_id="Apple", confidence_score=0.95, quantity_delta=-1)
            frt_daemon.publish_tracking_results({"id": "Apple", "score": 0.95, "qty": -1})
            print("Đã gọi hàm cập nhật database và phát tín hiệu (DBDaemon & FRTApp).")
        elif choice == '3':
            print("Đang thêm 2 chai Milk...")
            db_daemon.process_food_tracking_event(food_id="Milk", confidence_score=0.98, quantity_delta=2)
            frt_daemon.publish_tracking_results({"id": "Milk", "score": 0.98, "qty": 2})
            print("Đã gọi hàm cập nhật database và phát tín hiệu (DBDaemon & FRTApp).")
        elif choice == '4':
            print("Gửi sự kiện Door Open...")
            db_daemon.process_door_sensor_event("DOOR_OPEN", time.time())
        elif choice == '5':
            print("Gửi sự kiện Door Close...")
            db_daemon.process_door_sensor_event("DOOR_CLOSE", time.time())
        elif choice == '6':
            print("Gửi sự kiện Cập nhật Môi trường...")
            db_daemon.process_environment_event(temperature=24.5, humidity=60.2, timestamp=time.time())
        elif choice == '0':
            print("Đang thoát...")
            db_daemon.stop_daemon()
            break
        else:
            print("Lựa chọn không hợp lệ!")

if __name__ == "__main__":
    main()
