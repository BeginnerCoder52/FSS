import RPi.GPIO as GPIO
import time
import sys
import signal

# --- Use BCM pin numbering (GPIO numbers, not physical) ---
GPIO.setmode(GPIO.BCM)

# --- MC-38 on GPIO26 (Physical Pin 37) -------------------
DOOR_SENSOR_PIN = 26   # other wire ? GND (Physical Pin 39)

# --- State tracking ---------------------------------------
isOpen    = None
oldIsOpen = None

# --- Cleanup on Ctrl+C ------------------------------------
def cleanup(signal, frame):
    print("\n[MC-38] Cleaning up GPIO...")
    GPIO.cleanup()
    sys.exit(0)

# --- Setup pin as input with pull-up resistor -------------
# pull-up: pin reads HIGH when open, LOW when magnet closes switch
GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- Register Ctrl+C handler ------------------------------
signal.signal(signal.SIGINT, cleanup)

print("[MC-38] Door sensor started on GPIO26 (Pin 37)")
print("        GND on Pin 39")
print("        Press Ctrl+C to exit")
print("----------------------------------------")

# --- Main loop --------------------------------------------
while True:
    oldIsOpen = isOpen
    isOpen    = GPIO.input(DOOR_SENSOR_PIN)

    if isOpen and (isOpen != oldIsOpen):
        print("[DOOR] OPEN  (magnet away)")

    elif not isOpen and (isOpen != oldIsOpen):
        print("[DOOR] CLOSED (magnet near)")

    time.sleep(0.1)  # poll every 100ms