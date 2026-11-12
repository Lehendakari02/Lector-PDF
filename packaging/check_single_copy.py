"""Check, with the packaged program, that a second start joins the first window.

Usage:
    python packaging/check_single_copy.py PATH_TO_EXE FIRST_PDF SECOND_PDF

Starts the portable program with a PDF, starts it again with another one and
checks that the second start ends by itself and that the first window has both
documents (it reads the tabs the program remembers in ``datos/ajustes.json``).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

WAIT_SECONDS = 90


def open_documents(settings_file: Path) -> list[str]:
    try:
        stored = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [Path(p).name for p in stored.get("sesion", {}).get("abiertos", [])]


def wait_for(settings_file: Path, wanted: list[str], first: subprocess.Popen) -> bool:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if open_documents(settings_file) == wanted:
            return True
        if first.poll() is not None:
            print(f"The program ended by itself with code {first.returncode}.")
            return False
        time.sleep(0.2)
    print(f"Expected {wanted}, the program remembers {open_documents(settings_file)}.")
    return False


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    program, first_pdf, second_pdf = (Path(arg).resolve() for arg in sys.argv[1:])
    settings_file = program.parent / "datos" / "ajustes.json"
    settings_file.unlink(missing_ok=True)

    first = subprocess.Popen([str(program), str(first_pdf)])
    try:
        if not wait_for(settings_file, [first_pdf.name], first):
            return 1
        try:
            second = subprocess.run(
                [str(program), str(second_pdf)], timeout=WAIT_SECONDS, check=False
            )
        except subprocess.TimeoutExpired:
            print("The second start did not end: it opened its own window.")
            return 1
        if second.returncode != 0:
            print(f"The second start ended with code {second.returncode}.")
            return 1
        if not wait_for(settings_file, [first_pdf.name, second_pdf.name], first):
            return 1
        print("A second start joins the window that is already open.")
        return 0
    finally:
        first.kill()
        first.wait(30)


if __name__ == "__main__":
    sys.exit(main())
