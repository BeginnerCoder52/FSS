#!/usr/bin/env python3
"""
Write video frames to the FRTApp shared-memory frame buffer.

This is a demo/test substitute for cpp_camera_core. It keeps the same SHM
layout consumed by frt_app/py_ai_core/src/ShmReader.py:

    64-byte header at offset 0, JPEG bytes at offset 64.
"""

import argparse
import mmap
import os
import struct
import time

import cv2


SHM_PATH = "/dev/shm/fss_video_frame"
SHM_SIZE = 2 * 1024 * 1024
HEADER_SIZE = 64
SHM_MAGIC = 0xDEADBEEF
HEADER_FORMAT = "<IIIIQII8I"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream a video file into /dev/shm/fss_video_frame."
    )
    parser.add_argument("video", help="Input video path readable by OpenCV/FFmpeg")
    parser.add_argument("--fps", type=float, default=0.0,
                        help="Playback FPS. Default: use source FPS, fallback 30.")
    parser.add_argument("--jpeg-quality", type=int, default=85,
                        help="JPEG quality 1-100. Default: 85.")
    parser.add_argument("--shm-path", default=SHM_PATH,
                        help=f"Shared memory file path. Default: {SHM_PATH}")
    parser.add_argument("--shm-size", type=int, default=SHM_SIZE,
                        help=f"Shared memory size in bytes. Default: {SHM_SIZE}")
    parser.add_argument("--start-delay", type=float, default=0.0,
                        help="Seconds to wait before writing the first frame.")
    parser.add_argument("--loop", action="store_true",
                        help="Loop the video until interrupted.")
    return parser.parse_args()


def open_shm(path: str, size: int):
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o666)
    os.ftruncate(fd, size)
    try:
        os.chmod(path, 0o666)
    except PermissionError:
        pass
    return fd, mmap.mmap(fd, size, access=mmap.ACCESS_WRITE)


def write_frame(shm, frame, frame_id: int, quality: int, shm_size: int):
    ok, encoded = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    )
    if not ok:
        raise RuntimeError("JPEG encoding failed")

    jpeg = encoded.tobytes()
    if len(jpeg) > shm_size - HEADER_SIZE:
        raise RuntimeError(
            f"JPEG frame is too large for SHM: {len(jpeg)} > {shm_size - HEADER_SIZE}"
        )

    height, width = frame.shape[:2]
    timestamp_us = int(time.time() * 1_000_000)
    header = struct.pack(
        HEADER_FORMAT,
        SHM_MAGIC,
        width,
        height,
        3,  # JPEG
        timestamp_us,
        frame_id,
        len(jpeg),
        *([0] * 8),
    )

    # Data first, header last. The frame_id in the header acts as the commit.
    shm.seek(HEADER_SIZE)
    shm.write(jpeg)
    shm.seek(0)
    shm.write(header)
    shm.flush()


def main() -> int:
    args = parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    playback_fps = args.fps if args.fps > 0 else (source_fps if source_fps > 0 else 30.0)
    frame_delay = 1.0 / playback_fps

    fd, shm = open_shm(args.shm_path, args.shm_size)
    frame_id = 0

    print(
        f"SHM writer ready: path={args.shm_path}, video={args.video}, fps={playback_fps:.2f}",
        flush=True,
    )

    if args.start_delay > 0:
        time.sleep(args.start_delay)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if not args.loop:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            started = time.time()
            write_frame(shm, frame, frame_id, args.jpeg_quality, args.shm_size)
            frame_id += 1

            elapsed = time.time() - started
            time.sleep(max(0.0, frame_delay - elapsed))
    finally:
        shm.close()
        os.close(fd)
        cap.release()

    print(f"SHM writer finished: frames={frame_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
