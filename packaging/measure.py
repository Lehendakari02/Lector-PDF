"""Report how big a build is and how long the program takes to open.

Usage:
    python packaging/measure.py NAME PATH_TO_EXE [--runs N]

Starts the program several times with ``--autoclose`` (open the window, then
quit) and prints a Markdown table row. On GitHub the row is also added to the
summary page of the run. Fails if the program does not start correctly.
"""

import argparse
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

START_TIMEOUT_SECONDS = 120


def size_mb(path: Path) -> float:
    files = [path] if path.is_file() else [f for f in path.rglob("*") if f.is_file()]
    return sum(f.stat().st_size for f in files) / (1024 * 1024)


def time_start(exe: Path) -> float:
    started = time.perf_counter()
    result = subprocess.run([str(exe), "--autoclose"], timeout=START_TIMEOUT_SECONDS, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise SystemExit(f"{exe} exited with code {result.returncode}")
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("exe", type=Path)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--size-of", type=Path, help="measure this path instead of the exe")
    options = parser.parse_args()

    times = [time_start(options.exe) for _ in range(options.runs)]
    size = size_mb(options.size_of or options.exe)
    row = (
        f"| {options.name} | {size:.0f} MB | {times[0]:.1f} s | "
        f"{statistics.median(times[1:] or times):.1f} s |"
    )
    header = "| Formato | Tamaño | Primer arranque | Arranques siguientes |\n|---|---|---|---|"
    print(header)
    print(row)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        summary_path = Path(summary)
        first = not summary_path.exists() or "Primer arranque" not in summary_path.read_text(
            encoding="utf-8"
        )
        with summary_path.open("a", encoding="utf-8") as out:
            out.write((header + "\n" if first else "") + row + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
