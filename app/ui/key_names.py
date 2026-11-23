"""How the keys of the functions are shown, and what each function is."""

from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction, QKeySequence

from app.core import shortcuts


@dataclass
class KeyCommand:
    """A function that can have keys, and the actions that answer them."""

    id: str
    name: str
    group: str
    action: QAction  # answers its keys (all of them, or those with Ctrl or Alt)
    twin: QAction | None = None  # answers the plain keys, only on the document


def shown(key: str) -> str:
    """A key as the interface shows it ("Ctrl+Mayús+S" in Spanish Windows)."""
    return QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText)


def key_hint(key: str) -> str:
    """How a key is mentioned in a tip: "tecla R", or "Ctrl+S"."""
    if shortcuts.is_plain(key):
        return QCoreApplication.translate("Keys", "tecla {0}").format(shown(key))
    return shown(key)
