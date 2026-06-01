#!/usr/bin/env python3
"""
Trace CPU/RAM usage of a program from startup until process exit.

Example:
    python3 tools/resource_trace.py --interval 0.5 -- python3 db_daemon/src/main.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time


try:
    PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
    CLK_TCK = os.sysconf("SC_CLK_TCK")
except OSError as exc:
    raise RuntimeError(
        "Failed to read required sysconf constants (SC_PAGE_SIZE/SC_CLK_TCK). "
        "This platform may not be supported."
    ) from exc
MIN_TIME_DELTA = 1e-9


def _read_proc_stats(pid: int) -> tuple[float, int]:
    """Return (cpu_time_seconds, rss_bytes) for a process."""
    with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
        fields = f.read().split()
    try:
        utime = int(fields[13])
        stime = int(fields[14])
        rss_pages = int(fields[23])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"Failed to parse /proc/{pid}/stat.") from exc
    cpu_seconds = (utime + stime) / CLK_TCK
    rss_bytes = rss_pages * PAGE_SIZE
    return cpu_seconds, rss_bytes


def _format_mb(value_bytes: int) -> str:
    return f"{value_bytes / (1024 * 1024):.2f} MB"


def run_and_trace(command: list[str], interval: float) -> int:
    if not command:
        raise ValueError("Missing command to run.")

    start_wall = time.time()
    try:
        proc = subprocess.Popen(command, shell=False)
    except (FileNotFoundError, OSError) as exc:
        print(f"[ERROR] Failed to launch command: {' '.join(command)}", file=sys.stderr)
        raise exc
    pid = proc.pid

    try:
        start_cpu, start_rss = _read_proc_stats(pid)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Process terminated before initial stats could be read (PID: {pid})."
        ) from exc
    last_valid_cpu = start_cpu
    last_nonzero_rss = start_rss
    prev_cpu = start_cpu
    prev_time = start_wall
    peak_rss = start_rss

    print(f"[TRACE] PID={pid} | command={' '.join(command)}")
    print("[TRACE] t(s)\tcpu(%)\trss")

    while proc.poll() is None:
        now = time.time()
        try:
            cur_cpu, cur_rss = _read_proc_stats(pid)
        except FileNotFoundError:
            break

        # Guard division by zero when samples are too close together.
        dt_wall = max(now - prev_time, MIN_TIME_DELTA)
        # Interval CPU% = added CPU time / added wall time.
        cpu_percent = ((cur_cpu - prev_cpu) / dt_wall) * 100.0
        peak_rss = max(peak_rss, cur_rss)
        last_valid_cpu = cur_cpu
        # Ignore zero RSS artifacts during process teardown.
        if cur_rss > 0:
            last_nonzero_rss = cur_rss

        print(f"[TRACE] {now - start_wall:6.2f}\t{cpu_percent:6.2f}\t{_format_mb(cur_rss)}")

        prev_cpu = cur_cpu
        prev_time = now
        time.sleep(interval)

    return_code = proc.wait()
    end_wall = time.time()
    wall_time = end_wall - start_wall

    # Process may already be gone from /proc; use last successfully read sample.
    end_cpu = last_valid_cpu
    end_rss = last_nonzero_rss
    if end_cpu < start_cpu:
        print("[WARN] End CPU time is smaller than start CPU time; clamping to zero.")
    total_cpu_seconds = max(end_cpu - start_cpu, 0.0)
    avg_cpu_percent = (total_cpu_seconds / max(wall_time, MIN_TIME_DELTA)) * 100.0

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
        description="Trace RAM/CPU consumption from process start to process exit."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Sampling interval in seconds (default: 0.5).",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run (place after '--'), for example: -- python3 app.py",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be > 0.")

    # Be tolerant if users include a literal '--' in the remainder command.
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if not args.command:
        parser.error("Missing target command. Use: resource_trace.py -- <command>")

    return args


def main() -> int:
    args = parse_args()
    return run_and_trace(args.command, args.interval)


if __name__ == "__main__":
    sys.exit(main())
