"""The function finder (Ctrl+K): type a few letters and pick a function."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.features import Feature, search_features, translate


class CommandPalette(QDialog):
    """A small window with a text box and the list of matching functions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Buscar una función"))
        self.setModal(True)
        self.resize(560, 420)
        self.chosen: Feature | None = None

        self.query = QLineEdit()
        self.query.setObjectName("paletteQuery")
        self.query.setPlaceholderText(self.tr("Escribe lo que quieres hacer: firmar, unir, rotar…"))
        self.query.setAccessibleName(self.tr("Qué quieres hacer"))
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(40)

        self.results = QListWidget()
        self.results.setObjectName("paletteResults")
        self.results.setAccessibleName(self.tr("Funciones encontradas"))
        self.results.setSpacing(3)
        self.results.setAlternatingRowColors(True)

        self.empty = QLabel(self.tr("No hay ninguna función con esas palabras."))
        self.empty.setObjectName("paletteEmpty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(self.tr("↑ ↓ para moverte · Intro para elegir · Esc para cerrar"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.query)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.empty)
        layout.addWidget(hint)

        self.query.textChanged.connect(self._refresh)
        self.query.returnPressed.connect(self._accept_current)
        self.results.itemActivated.connect(lambda _item: self._accept_current())
        self.results.itemClicked.connect(lambda _item: self._accept_current())
        self.query.installEventFilter(self)
        self._refresh("")

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
        if found:
            self.results.setCurrentRow(0)

    def _accept_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        """Let the arrow keys move through the list while typing."""
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
