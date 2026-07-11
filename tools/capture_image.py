#!/usr/bin/env python3
"""
capture_image.py — Capture a single 640x480 frame from USB camera

Usage:
    python3 capture_image.py
    python3 capture_image.py --camera /dev/video1 --output ~/test.jpg --width 1280 --height 720
"""

import cv2
import argparse
import os
import sys
from datetime import datetime


def capture_image(device: str, width: int, height: int, output: str) -> int:
    cap = cv2.VideoCapture(device)

    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {device}", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("ERROR: Failed to capture frame", file=sys.stderr)
        return 1

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if output:
        outpath = output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outpath = f"capture_{ts}_{actual_w}x{actual_h}.jpg"

    cv2.imwrite(outpath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"Captured {actual_w}x{actual_h} -> {os.path.abspath(outpath)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Capture 640x480 image from USB camera")
    parser.add_argument("--camera", default="/dev/video0", help="Camera device (default: /dev/video0)")
    parser.add_argument("--width", type=int, default=640, help="Frame width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height (default: 480)")
    parser.add_argument("--output", "-o", default="", help="Output file path")
    args = parser.parse_args()

    return capture_image(args.camera, args.width, args.height, args.output)


if __name__ == "__main__":
    sys.exit(main())
