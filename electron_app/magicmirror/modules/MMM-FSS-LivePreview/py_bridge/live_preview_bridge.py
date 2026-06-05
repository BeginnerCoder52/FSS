#!/usr/bin/env python3
"""
@file live_preview_bridge.py
@brief Poll /opt/fss/latest_preview.jpg and output base64 JSON frames to stdout.

Strategy:
- Poll for file modification time every 100ms
- Output base64-encoded JPEG frames on change
- Handles SIGTERM/SIGINT for graceful shutdown
"""
import json
import sys
import time
import base64
import os
import signal
import logging

PREVIEW_PATH = "/opt/fss/latest_preview.jpg"
POLL_INTERVAL = 0.1

logging.basicConfig(
    level=logging.INFO,
    format="[LivePreview] %(levelname)s: %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)

running = True


def handle_signal(signum, frame):
    global running
    logger.info(f"Received signal {signum} - shutting down")
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

print(json.dumps({"type": "STATUS", "message": "Started"}), flush=True)

last_mtime = 0
error_count = 0
max_errors = 5

while running:
    try:
        if os.path.exists(PREVIEW_PATH):
            mtime = os.path.getmtime(PREVIEW_PATH)
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    with open(PREVIEW_PATH, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                        print(json.dumps({"type": "FRAME", "data": b64}), flush=True)
                        error_count = 0
                except (OSError, IOError) as e:
                    error_count += 1
                    logger.warning(f"File read error ({error_count}/{max_errors}): {e}")
                    if error_count >= max_errors:
                        print(
                            json.dumps({
                                "type": "ERROR",
                                "message": f"Failed to read {PREVIEW_PATH} after {max_errors} attempts",
                            }),
                            flush=True,
                        )
                        error_count = 0
        time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        running = False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        time.sleep(1)

logger.info("LivePreview bridge stopped")

