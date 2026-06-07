#!/usr/bin/env python3
"""
mock_ai_dbus.py - Mock AI (FRTApp) D-Bus Emitter
Giả lập luồng AI FRTApp: Mỗi 10 giây phát tín hiệu D-Bus (FoodDetected) chứa thông tin thay đổi số lượng thực phẩm.
Cần chạy bằng quyền sudo (hoặc user có quyền truy cập System D-Bus) và venv của Python.
"""

import time
import json
import asyncio
try:
    import sdbus
    from sdbus import (
        DbusInterfaceCommonAsync,
        dbus_signal_async,
        sd_bus_open_system,
        set_default_bus,
        request_default_bus_name_async,
        sd_bus_internals
    )
except ImportError:
    print("Vui lòng cài đặt module sdbus-python hoặc kích hoạt venv của FSS trước khi chạy.")
    print("Ví dụ: source frt_app/py_ai_core/venv/bin/activate")
    exit(1)

SERVICE_NAME = "vn.edu.uit.FSS.FRTApp"
OBJECT_PATH = "/vn/edu/uit/FSS/FRTApp"

class FrtMockDbusObject(DbusInterfaceCommonAsync, interface_name=SERVICE_NAME):
    @dbus_signal_async('s')
    def FoodDetected(self, json_data: str) -> None:
        pass

async def main():
    print(f"Khởi tạo Mock AI D-Bus Service ({SERVICE_NAME})...")
    
    # Kết nối vào System Bus
    set_default_bus(sd_bus_open_system())
    
    # Đăng ký tên dịch vụ D-Bus
    await request_default_bus_name_async(
        SERVICE_NAME,
        replace_existing=True
    )

    # Xuất object ra D-Bus
    mock_obj = FrtMockDbusObject()
    mock_obj.export_to_dbus(OBJECT_PATH)
    print("✅ Mock AI đã kết nối thành công vào D-Bus.")
    print("⏳ Bắt đầu phát tín hiệu mỗi 10 giây. Nhấn Ctrl+C để dừng.\n")

    while True:
        # Lưu ý: DBDaemon mong đợi format {"id": <tên>, "score": <độ tin cậy>, "qty": <số lượng thay đổi>}
        
        # 1. Phát tín hiệu thêm 1 apple
        apple_payload = {"id": "apple", "score": 0.95, "qty": 1}
        print(f"[{time.strftime('%X')}] Gửi D-Bus (FoodDetected): {apple_payload}")
        mock_obj.FoodDetected.emit(json.dumps(apple_payload))
        
        # Đợi một chút để tránh spam liên tục
        await asyncio.sleep(1)
        
        # 2. Phát tín hiệu bớt 1 egg
        egg_payload = {"id": "egg", "score": 0.98, "qty": -1}
        print(f"[{time.strftime('%X')}] Gửi D-Bus (FoodDetected): {egg_payload}")
        mock_obj.FoodDetected.emit(json.dumps(egg_payload))
        
        print("-" * 50)
        # Đợi 10 giây cho lần lặp tiếp theo
        await asyncio.sleep(9)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nMock AI đã dừng.")
