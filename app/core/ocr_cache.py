"""What text recognition has read, kept page by page while a run goes on.

Recognising a whole document can take half an hour, and what is read is
written into the document only at the end, as one change (one Deshacer takes
it all away). If the power goes in the middle, nothing of it reached the
recovery journal. So every page read is also kept here at once, in the
program's data folder, under the fingerprint of the picture that was read:
running "Reconocer texto" again finds those pages already read and only reads
the rest. It never touches the PDF.

When a run ends well its pages leave this folder (they are in the journal and
in the document by then). What is left from a run that never ended is thrown
away after some days.

A picture's fingerprint is that of its pixels: the same page drawn the same
way gives the same fingerprint, whatever its number in the document (sheets
may have been put in) and whatever document it is in.
"""

import contextlib
import hashlib
import json
import os
import time
from pathlib import Path

from app.core.ocr import OcrPage, OcrWord

FOLDER_NAME = "reconocido"
KEEP_DAYS = 7
VERSION = 1


def picture_key(width: int, height: int, dpi: int, samples: bytes) -> str:
    """The fingerprint of a picture of a page."""
    digest = hashlib.sha256(f"{VERSION}:{width}x{height}@{dpi}:".encode())
    digest.update(samples)
    return digest.hexdigest()[:32]


class OcrCache:
    """The folder with the pages read and not yet written into a document."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def _file(self, key: str) -> Path:
        return self.folder / f"{key}.json"

    def get(self, key: str, page: int) -> OcrPage | None:
        """The page read with that picture, as page ``page``; None if not kept."""
        try:
            data = json.loads(self._file(key).read_text(encoding="utf-8"))
            if data.get("v") != VERSION:
                return None
            found = OcrPage(
                page,
                tuple(
                    OcrWord(tuple(float(v) for v in rect), str(text))
                    for rect, text in data["words"]
                ),
                tuple(float(value) for value in data["matrix"]),
                int(data["dpi"]),
                float(data["seconds"]),
                float(data["turned"]),
                str(data.get("text", "")),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if len(found.matrix) != 6 or any(len(word.rect) != 4 for word in found.words):
            return None
        return found

    def put(self, key: str, read: OcrPage) -> bool:
        """Keep what was read on a picture. False if it could not be written."""
        data = {
            "v": VERSION,
            "words": [[list(word.rect), word.text] for word in read.words],
            "matrix": list(read.matrix),
            "dpi": read.dpi,
            "seconds": read.seconds,
            "turned": read.turned,
            "text": read.text,
        }
        file = self._file(key)
        temporary = file.with_name(file.name + ".tmp")
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, separators=(",", ":"))
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, file)
        except OSError:
            with contextlib.suppress(OSError):
                temporary.unlink()
            return False
        return True

    def forget(self, keys) -> None:
        """These pages are in the document (and its journal) now."""
        for key in keys:
            with contextlib.suppress(OSError):
                self._file(key).unlink()

    def forget_old(self, days: float = KEEP_DAYS, now: float | None = None) -> int:
        """Throw away what was kept more than ``days`` ago. Returns how many."""
        limit = (time.time() if now is None else now) - days * 86400
        gone = 0
        try:
            files = list(self.folder.glob("*.json*"))
        except OSError:
            return 0
        for file in files:
            try:
                if file.stat().st_mtime < limit:
                    file.unlink()
                    gone += 1
            except OSError:
                continue
        return gone
