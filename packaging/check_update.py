"""Check, with the packaged program, that the portable version can update itself.

Usage:
    python packaging/check_update.py PATH_TO_PROGRAM_FOLDER

Makes an "old" portable copy with settings of its own, unpacks a "new" copy
where the program would put a download, and asks the new one to take the place
of the old one, the way "Actualizar ahora" does. Then checks that the new
files are in place, that the user's ``datos`` folder is intact, that the old
files are gone and that the updated program starts.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXE = "Lector-PDF.exe"
TIMEOUT_SECONDS = 180


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    built = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        old = Path(folder) / "Lector-PDF"
        shutil.copytree(built, old, ignore=shutil.ignore_patterns("datos"))
        (old / "portable.txt").touch()
        (old / "solo-en-la-vieja.txt").write_text("old", encoding="utf-8")
        settings = old / "datos" / "ajustes.json"
        settings.parent.mkdir()
        settings.write_text('{"tema": "oscuro"}', encoding="utf-8")

        new = old / "datos" / "actualizacion" / "nueva" / "Lector-PDF"
        shutil.copytree(built, new, ignore=shutil.ignore_patterns("datos"))
        (new / "solo-en-la-nueva.txt").write_text("new", encoding="utf-8")

        # A process that has already ended stands in for the program that closed.
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        code = subprocess.run(
            [str(new / EXE), "--apply-update", str(old), str(ended.pid), "--no-start"],
            timeout=TIMEOUT_SECONDS,
            check=False,
        ).returncode
        problems = []
        if code != 0:
            problems.append(f"the update ended with code {code}")
        if not (old / "solo-en-la-nueva.txt").is_file():
            problems.append("the new files are not in place")
        if (old / "solo-en-la-vieja.txt").exists():
            problems.append("files of the old version were left behind")
        if not settings.is_file() or "oscuro" not in settings.read_text(encoding="utf-8"):
            problems.append("the user's settings were lost")
        if not (old / "portable.txt").is_file():
            problems.append("the program is no longer portable")
        if not problems:
            started = subprocess.run(
                [str(old / EXE), "--autoclose"], timeout=TIMEOUT_SECONDS, check=False
            ).returncode
            if started != 0:
                problems.append(f"the updated program does not start (code {started})")
        for problem in problems:
            print(f"FAILED: {problem}")
        if not problems:
            print("The portable version updated itself and kept the user's data.")
        return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
