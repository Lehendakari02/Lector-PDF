"""The function finder (Ctrl+K): type a few letters and pick a function."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui import icons
from app.ui.features import Feature, search_features, translate
from app.ui.item_delegates import FeatureDelegate


class CommandPalette(QDialog):
    """A small window with a text box and the list of matching functions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Buscar una función"))
        self.setObjectName("commandPalette")
        self.setModal(True)
        # A pop-up, like the finders of other programs: no title bar, and it
        # closes with Esc or with a click anywhere outside it.
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.resize(620, 470)
        self.chosen: Feature | None = None
        self.help_wanted: Feature | None = None  # F1: how is this one used?
        self.help_query: str | None = None  # nothing found: look in the help

        self.query = QLineEdit()
        self.query.setObjectName("paletteQuery")
        self.query.setPlaceholderText(self.tr("Escribe lo que quieres hacer: firmar, unir, rotar…"))
        self.query.setAccessibleName(self.tr("Qué quieres hacer"))
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(48)
        self.query.addAction(
            icons.icon("search", icons.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self.results = QListWidget()
        self.results.setObjectName("paletteResults")
        self.results.setAccessibleName(self.tr("Funciones encontradas"))
        self.results.setMouseTracking(True)
        self.results.setItemDelegate(FeatureDelegate(self.results))

        self.empty = QLabel(self.tr("No hay ninguna función con esas palabras."))
        self.empty.setObjectName("paletteEmpty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ask_help = QPushButton(self.tr("Buscarlo en la ayuda"))
        self.ask_help.setToolTip(self.tr("La ayuda explica también lo que no tiene botón"))
        self.ask_help.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_help.setAutoDefault(False)  # Intro with nothing found does nothing
        self.ask_help.clicked.connect(self._look_in_help)

        hint = QLabel(
            self.tr("↑ ↓ para moverte · Intro para elegir · F1 cómo se usa · Esc para cerrar")
        )
        hint.setObjectName("paletteHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self.query)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.empty)
        layout.addWidget(self.ask_help, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)

        self.query.textChanged.connect(self._refresh)
        self.query.returnPressed.connect(self._accept_current)
        self.results.itemActivated.connect(lambda _item: self._accept_current())
        self.results.itemClicked.connect(lambda _item: self._accept_current())
        self.query.installEventFilter(self)
        self._refresh("")

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Appear in the upper part of the window, centred."""
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            area = parent.frameGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.top() + max(60, (area.height() - self.height()) // 4),
            )
        self.query.setFocus()

    def _refresh(self, text: str) -> None:
        self.results.clear()
        for feature in search_features(text):
            name = translate(feature.name)
            where = translate(feature.mode.value)
            label = f"{name}\n{where} · {translate(feature.description)}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, feature)
            self.results.addItem(item)
        found = self.results.count() > 0
        self.results.setVisible(found)
        self.empty.setVisible(not found)
        self.ask_help.setVisible(not found)
        if found:
            self.results.setCurrentRow(0)

    def _accept_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _look_in_help(self) -> None:
        self.help_query = self.query.text()
        self.accept()

    def _help_for_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            self._look_in_help()
            return
        self.help_wanted = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _is_help_key(self, event) -> bool:
        """F1, or the key the user gave to the help instead."""
        pressed = QKeySequence(event.keyCombination())
        action = getattr(self.parentWidget(), "help_action", None)
        keys = action.shortcuts() if action is not None else []
        return event.key() == Qt.Key.Key_F1 or any(key == pressed for key in keys)

    def event(self, event) -> bool:  # noqa: D102
        # The key of the help belongs to this window while it is open: it
        # explains the function chosen in the list.
        if event.type() == QEvent.Type.ShortcutOverride and self._is_help_key(event):
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress and self._is_help_key(event):
            self._help_for_current()
            return True
        return super().event(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        """Let the arrow keys move through the list while typing; F1 tells how
        the chosen function is used."""
        help_key = event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
        if watched is self.query and help_key and self._is_help_key(event):
            if event.type() == QEvent.Type.ShortcutOverride:
                event.accept()  # not a shortcut of the window: it is ours
            else:
                self._help_for_current()
            return True
        if watched is self.query and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            moves = {
                Qt.Key.Key_Down: 1,
                Qt.Key.Key_Up: -1,
                Qt.Key.Key_PageDown: 8,
                Qt.Key.Key_PageUp: -8,
            }
            if key in moves and self.results.count():
                row = self.results.currentRow() + moves[key]
                self.results.setCurrentRow(max(0, min(row, self.results.count() - 1)))
                return True
        return super().eventFilter(watched, event)
