"""Saying a moment the way people do: "hoy a las 10:32", "ayer a las 18:05"."""

import time
from datetime import datetime

from PySide6.QtCore import QCoreApplication


def when_text(moment: float, now: float | None = None) -> str:
    """``moment`` (seconds since 1970) in words, seen from ``now``."""
    then = datetime.fromtimestamp(moment)
    today = datetime.fromtimestamp(time.time() if now is None else now).date()
    days = (today - then.date()).days
    hour = then.strftime("%H:%M")
    if days == 0:
        return QCoreApplication.translate("When", "hoy a las {0}").format(hour)
    if days == 1:
        return QCoreApplication.translate("When", "ayer a las {0}").format(hour)
    return QCoreApplication.translate("When", "el {0} a las {1}").format(
        then.strftime("%d/%m/%Y"), hour
    )


def size_text(size: int) -> str:
    """A file size in words: "850 KB", "1,2 MB"."""
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")
