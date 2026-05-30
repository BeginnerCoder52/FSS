#!/usr/bin/env python3
"""Read /opt/fss/latest_preview.jpg and output base64 JSON to stdout."""
import json, sys, time, base64, os

PREVIEW_PATH = "/opt/fss/latest_preview.jpg"
POLL_INTERVAL = 0.1
last_mtime = 0

print(json.dumps({"type": "STATUS", "message": "Started"}), flush=True)

try:
    while True:
        if os.path.exists(PREVIEW_PATH):
            mtime = os.path.getmtime(PREVIEW_PATH)
            if mtime != last_mtime:
                last_mtime = mtime
                with open(PREVIEW_PATH, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    print(json.dumps({"type": "FRAME", "data": b64}), flush=True)
        time.sleep(POLL_INTERVAL)
except KeyboardInterrupt:
    pass
