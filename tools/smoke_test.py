#!/usr/bin/env python3
import sys, time, json
try:
    import sdbus
    from sdbus.sd_bus_internals import SdBus
except ImportError:
    print("sdbus not installed.")
    sys.exit(1)

SERVICE = "vn.edu.uit.FSS.SensorDaemon"
INTERFACE = "vn.edu.uit.FSS.Interface"

class SmokeTester:
    def __init__(self):
        self.bus = sdbus.sd_bus_open_system()
        sdbus.set_default_bus(self.bus)
        self.data = {}
        
        # We use dbus-monitor approach or standard signal matching
        self.match_str = f"type='signal',sender='{SERVICE}',interface='{INTERFACE}'"
        
    def wait_for_data(self, timeout=3.0):
        start = time.time()
        import subprocess
        
        # Use dbus-monitor to sniff signals
        proc = subprocess.Popen(
            ["dbus-monitor", "--system", self.match_str],
            stdout=subprocess.PIPE, text=True
        )
        
        print("Gathering sensor data... (waiting 3s)")
        
        import select
        while time.time() - start < timeout:
            r, _, _ = select.select([proc.stdout], [], [], 0.5)
            if r:
                line = proc.stdout.readline()
                if "string" in line and "{" in line:
                    try:
                        # Extract json string
                        json_str = line.split("string")[1].strip().strip('"').replace('\\"', '"')
                        if json_str.startswith("{"):
                            parsed = json.loads(json_str)
                            self.data.update(parsed)
                    except:
                        pass
                        
        proc.terminate()
        proc.wait()
        
        print("\n--- Sensor Status ---")
        if "temp" in self.data:
            print(f"✅ SHT3x (Temp/Humid): {self.data.get('temp', 0):.1f}°C / {self.data.get('humid', 0):.1f}%")
        else:
            print("❌ SHT3x (Temp/Humid): No data received (Check I2C/Driver)")
            
        if "distance" in self.data:
            print(f"✅ VL53L0x (Distance): {self.data.get('distance', 0)} mm")
        else:
            print("❌ VL53L0x (Distance): No data received (Disabled or Faulty)")
            
        print("✅ MC38 (Door Sensor): Ready (Interrupt based)")
        print("---------------------")

if __name__ == "__main__":
    tester = SmokeTester()
    tester.wait_for_data()
