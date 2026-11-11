"""Local record of unexpected errors and the report the user can copy.

Nothing here ever leaves the computer: errors are appended to a small file in
the program's data folder, and the report is plain text the user decides to
paste somewhere (or not). The file is only created when a first error happens.

Recording an error must never cause another one, so every disk problem is
swallowed here on purpose.
"""

import contextlib
import datetime
import json
import os
import platform
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from app import APP_NAME, BUILD_LABEL, __version__
from app.core.document import engine_version
from app.core.paths import data_dir, is_portable

ERROR_LOG_FILE_NAME = "errores.jsonl"
MAX_LOG_BYTES = 512 * 1024
ERRORS_IN_REPORT = 5


@dataclass(frozen=True)
class ErrorEntry:
    time: str
    version: str
    where: str
    details: str


def hide_personal_folder(text: str) -> str:
    """Replace the user's home folder (which contains their name) with ``~``."""
    home = str(Path.home())
    if len(home) < 4:  # never replace something as short as "/" or "C:\"
        return text
    for variant in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
        start = 0
        lowered, needle = text.lower(), variant.lower()
        pieces = []
        while (found := lowered.find(needle, start)) != -1:
            pieces.append(text[start:found] + "~")
            start = found + len(variant)
        text = "".join(pieces) + text[start:]
    return text


class ErrorLog:
    """The file with the last unexpected errors."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / ERROR_LOG_FILE_NAME

    def record(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
        where: str = "",
    ) -> ErrorEntry:
        """Write down an error. Never raises."""
        details = "".join(traceback.format_exception(exc_type, exc, tb)).strip()
        entry = ErrorEntry(
            time=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            version=__version__,
            where=where,
            details=hide_personal_folder(details),
        )
        with contextlib.suppress(OSError, ValueError):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
            self._trim()
        return entry

    def entries(self) -> list[ErrorEntry]:
        """All recorded errors, oldest first. Damaged lines are skipped."""
        try:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        result = []
        for line in lines:
            try:
                data = json.loads(line)
                result.append(
                    ErrorEntry(
                        time=str(data["time"]),
                        version=str(data["version"]),
                        where=str(data.get("where", "")),
                        details=str(data["details"]),
                    )
                )
            except (ValueError, KeyError, TypeError):
                continue
        return result

    def _trim(self) -> None:
        """Keep the file small: when it grows too much, drop the oldest half."""
        if self.path.stat().st_size <= MAX_LOG_BYTES:
            return
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        kept = lines[len(lines) // 2 :]
        while kept and sum(len(line.encode("utf-8")) + 1 for line in kept) > MAX_LOG_BYTES:
            kept = kept[1:]
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
        os.replace(temporary, self.path)

    def build_report(self, extra_lines: list[str] | None = None) -> str:
        """Text for the user to copy: what program this is and its last errors."""
        lines = [
            f"Informe de error de {APP_NAME}",
            f"Programa: {__version__}" + (f" · {BUILD_LABEL}" if BUILD_LABEL else ""),
            f"Motor PDF: PyMuPDF {engine_version()}",
            f"Python: {platform.python_version()}",
            f"Sistema: {platform.platform()}",
            "Versión portátil: " + ("sí" if is_portable() else "no"),
            *(extra_lines or []),
            "Fecha del informe: "
            + datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "",
        ]
        entries = self.entries()
        if not entries:
            lines.append("No hay errores registrados.")
        else:
            shown = entries[-ERRORS_IN_REPORT:]
            lines.append(f"Errores registrados: {len(entries)}. Últimos {len(shown)}:")
            for entry in reversed(shown):
                lines.append("")
                header = f"--- {entry.time} · versión {entry.version}"
                lines.append(header + (f" · {entry.where}" if entry.where else "") + " ---")
                lines.append(entry.details)
        return hide_personal_folder("\n".join(lines)) + "\n"


def running_from_source_or_test_build() -> bool:
    """True when developer helpers (like the test error) should be offered."""
    return bool(BUILD_LABEL) or not getattr(sys, "frozen", False)
