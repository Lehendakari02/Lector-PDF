"""Run the packaged program with a hidden self-check option and report failure.

Usage:
    python packaging/run_check.py PATH_TO_EXE OPTION [ARGUMENTS...]

Fails if the program does not answer 0, or does not finish in two minutes (a
program without a console that hits an error can sit waiting behind a message
box for ever). Prints the error details the program wrote, if any.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 120


def main() -> int:
    command = sys.argv[1:]
    if len(command) < 2:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as folder:
        log = Path(folder) / "check.log"
        environment = {**os.environ, "LECTOR_PDF_CHECK_LOG": str(log)}
        try:
            code = subprocess.run(
                command, timeout=TIMEOUT_SECONDS, check=False, env=environment
            ).returncode
        except subprocess.TimeoutExpired:
            print(f"Did not finish in {TIMEOUT_SECONDS} seconds: {' '.join(command)}")
            code = 1
        if code != 0:
            print(f"Exit code {code}: {' '.join(command)}")
        if log.is_file():
            print(log.read_text(encoding="utf-8"))
    return code


if __name__ == "__main__":
    sys.exit(main())
