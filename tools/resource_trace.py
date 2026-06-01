#!/usr/bin/env python3
"""
Theo dõi mức dùng CPU/RAM của một chương trình từ lúc chạy đến lúc kết thúc.

Ví dụ:
    python3 tools/resource_trace.py --interval 0.5 -- python3 db_daemon/src/main.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from typing import Tuple


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
CLK_TCK = os.sysconf("SC_CLK_TCK")


def _read_proc_stats(pid: int) -> Tuple[float, int]:
    """Trả về (cpu_time_seconds, rss_bytes) của process."""
    with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
        fields = f.read().split()
    utime = int(fields[13])
    stime = int(fields[14])
    rss_pages = int(fields[23])
    cpu_seconds = (utime + stime) / CLK_TCK
    rss_bytes = rss_pages * PAGE_SIZE
    return cpu_seconds, rss_bytes


def _format_mb(value_bytes: int) -> str:
    return f"{value_bytes / (1024 * 1024):.2f} MB"


def run_and_trace(command: list[str], interval: float) -> int:
    if not command:
        raise ValueError("Thiếu command cần chạy.")

    start_wall = time.time()
    proc = subprocess.Popen(command)
    pid = proc.pid

    start_cpu, start_rss = _read_proc_stats(pid)
    prev_cpu = start_cpu
    prev_time = start_wall
    peak_rss = start_rss

    print(f"[TRACE] PID={pid} | command={' '.join(command)}")
    print("[TRACE] t(s)\tcpu(%)\trss")

    while proc.poll() is None:
        time.sleep(interval)
        now = time.time()
        try:
            cur_cpu, cur_rss = _read_proc_stats(pid)
        except FileNotFoundError:
            break

        dt_wall = max(now - prev_time, 1e-9)
        cpu_percent = ((cur_cpu - prev_cpu) / dt_wall) * 100.0
        peak_rss = max(peak_rss, cur_rss)

        print(f"[TRACE] {now - start_wall:6.2f}\t{cpu_percent:6.2f}\t{_format_mb(cur_rss)}")

        prev_cpu = cur_cpu
        prev_time = now

    return_code = proc.wait()
    end_wall = time.time()
    wall_time = end_wall - start_wall

    # Có thể process đã thoát nên không còn /proc/<pid>; dùng giá trị cuối cùng an toàn.
    end_cpu = prev_cpu
    end_rss = max(start_rss, peak_rss)
    total_cpu_seconds = max(end_cpu - start_cpu, 0.0)
    avg_cpu_percent = (total_cpu_seconds / wall_time) * 100.0 if wall_time > 0 else 0.0

    print("\n===== RESOURCE SUMMARY =====")
    print(f"Exit code        : {return_code}")
    print(f"Wall time        : {wall_time:.2f} s")
    print(f"CPU time total   : {total_cpu_seconds:.2f} s")
    print(f"CPU avg          : {avg_cpu_percent:.2f} %")
    print(f"RAM start        : {_format_mb(start_rss)}")
    print(f"RAM peak         : {_format_mb(peak_rss)}")
    print(f"RAM end (approx) : {_format_mb(end_rss)}")
    print("============================")

    return return_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Theo dõi mức tiêu thụ RAM/CPU của chương trình từ khi khởi chạy đến khi kết thúc."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Chu kỳ lấy mẫu (giây), mặc định: 0.5",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Lệnh cần chạy (đặt sau '--'), ví dụ: -- python3 app.py",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval phải > 0.")

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if not args.command:
        parser.error("Thiếu command cần theo dõi. Dùng dạng: resource_trace.py -- <command>")

    return args


def main() -> int:
    args = parse_args()
    return run_and_trace(args.command, args.interval)


if __name__ == "__main__":
    sys.exit(main())
