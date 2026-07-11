#!/usr/bin/env python3
"""
@file live_preview_bridge.py
@brief Poll /opt/fss/latest_preview.jpg with heartbeat and detailed timing.

Strategy:
- Poll for file modification time every 100ms
- Output base64-encoded JPEG frames on change
- Re-send last frame every HEARTBEAT_INTERVAL to keep display alive
- Forward all pipeline timing fields from metadata JSON
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
META_PATH = "/opt/fss/latest_preview_meta.json"
POLL_INTERVAL = 0.1
HEARTBEAT_INTERVAL = 2.0

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
last_meta_mtime = 0
error_count = 0
max_errors = 5
last_frame_b64 = None
last_frame_msg = None
last_heartbeat_time = 0

TIMING_FIELDS = [
    "pipeline_time_ms",
    "capture_time_ms",
    "motion_time_ms",
    "preprocess_time_ms",
    "inference_time_ms",
    "tracking_time_ms",
]


def read_frame():
    global last_mtime, last_meta_mtime, error_count, last_frame_b64, last_frame_msg
    if not os.path.exists(PREVIEW_PATH):
        return False
    mtime = os.path.getmtime(PREVIEW_PATH)
    if mtime == last_mtime:
        return False
    last_mtime = mtime
    try:
        with open(PREVIEW_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            error_count = 0
        msg = {"type": "FRAME", "data": b64}
        if os.path.exists(META_PATH):
            meta_mtime = os.path.getmtime(META_PATH)
            if meta_mtime != last_meta_mtime:
                last_meta_mtime = meta_mtime
            try:
                with open(META_PATH, "r") as f:
                    meta = json.load(f)
                    for field in TIMING_FIELDS:
                        msg[field] = meta.get(field, 0)
                    msg["foods"] = meta.get("foods", "")
                    msg["events"] = meta.get("events", [])
            except Exception:
                pass
        last_frame_b64 = b64
        last_frame_msg = msg
        print(json.dumps(msg), flush=True)
        return True
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
        return False


while running:
    try:
        read_frame()
        now = time.time()
        if last_frame_msg and (now - last_heartbeat_time) >= HEARTBEAT_INTERVAL:
            last_heartbeat_time = now
            msg = dict(last_frame_msg)
            msg["type"] = "FRAME"
            print(json.dumps(msg), flush=True)
        time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        running = False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        time.sleep(1)

logger.info("LivePreview bridge stopped")
