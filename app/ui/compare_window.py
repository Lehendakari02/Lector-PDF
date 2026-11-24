"""The «Comparar» window: the list of what changed between two versions.

It stays open beside the two documents (seen side by side): choosing a
change in the list marks it on both and brings it into view.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.compare import ADDED, CHANGED, REMOVED, Change, Comparison


def change_text(change: Change, tr) -> str:
    """The row of a change: what happened, where, and the words around."""
    if change.kind == ADDED:
        what = tr("Añadido: «{0}»").format(change.new_text)
    elif change.kind == REMOVED:
        what = tr("Quitado: «{0}»").format(change.old_text)
    else:
        what = tr("Cambiado: «{0}» por «{1}»").format(change.old_text, change.new_text)
    if change.kind == REMOVED:
        where = tr("Página {0} de la anterior").format(change.old_page + 1)
    else:
        where = tr("Página {0}").format(change.new_page + 1)
    middle = change.old_text if change.kind == REMOVED else change.new_text
    around = f"…{change.before} «{middle}» {change.after}…"
    return f"{where} · {what}\n{around}"


def summary_text(result: Comparison, tr) -> str:
    count = len(result.changes)
    if count == 0:
        return tr("No hay ninguna diferencia en el texto.")
    kinds = (
        (result.changed, tr("1 cambiada"), tr("{0} cambiadas")),
        (result.added, tr("1 añadida"), tr("{0} añadidas")),
        (result.removed, tr("1 quitada"), tr("{0} quitadas")),
    )
    parts = [(one if n == 1 else many.format(n)) for n, one, many in kinds if n]
    if count == 1:
        return tr("1 diferencia.")
    return tr("{0} diferencias: {1}.").format(count, ", ".join(parts))


class CompareWindow(QDialog):
    """The changes, one per row. ``picked(index)`` when one is chosen,
    ``swap_asked`` for «Intercambiar» (the other one was the earlier)."""

    picked = Signal(int)
    swap_asked = Signal()

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Comparar versiones"))
        self.setModal(False)
        self.resize(460, 520)
        self.result: Comparison | None = None
        self.versions = QLabel()
        self.versions.setWordWrap(True)
        self.versions.setTextFormat(Qt.TextFormat.PlainText)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Diferencias"))
        self.list.setWordWrap(True)
        self.list.setAlternatingRowColors(True)
        self.list.currentRowChanged.connect(self._row_changed)
        self.list.itemActivated.connect(lambda item: self.picked.emit(self.list.row(item)))

        self.previous_button = QPushButton(self.tr("&Anterior"))
        self.previous_button.setToolTip(self.tr("La diferencia anterior"))
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button = QPushButton(self.tr("&Siguiente"))
        self.next_button.setToolTip(self.tr("La diferencia siguiente"))
        self.next_button.clicked.connect(lambda: self.step(1))
        self.swap_button = QPushButton(self.tr("&Intercambiar"))
        self.swap_button.setToolTip(self.tr("La versión anterior es la otra: compararlas al revés"))
        self.swap_button.clicked.connect(self.swap_asked)
        steps = QHBoxLayout()
        steps.addWidget(self.previous_button)
        steps.addWidget(self.next_button)
        steps.addStretch(1)
        steps.addWidget(self.swap_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr("Cerrar"))
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.versions)
        layout.addWidget(self.summary)
        layout.addWidget(self.list, 1)
        layout.addLayout(steps)
        layout.addWidget(buttons)

    def show_result(self, result: Comparison, old_name: str, new_name: str) -> None:
        self.result = result
        self.versions.setText(self.tr("Anterior: «{0}»\nNueva: «{1}»").format(old_name, new_name))
        self.summary.setText(summary_text(result, self.tr))
        self.list.blockSignals(True)
        self.list.clear()
        for change in result.changes:
            item = QListWidgetItem(change_text(change, self.tr))
            item.setData(Qt.ItemDataRole.UserRole, change.kind)
            item.setToolTip(
                {
                    ADDED: self.tr("Está en la nueva y no en la anterior"),
                    REMOVED: self.tr("Estaba en la anterior y ya no está"),
                    CHANGED: self.tr("Ha cambiado de la anterior a la nueva"),
                }[change.kind]
            )
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._refresh_buttons()
        if result.changes:
            self.list.setCurrentRow(0)
        self.list.setFocus()

    def step(self, by: int) -> None:
        row = self.list.currentRow() + by
        if 0 <= row < self.list.count():
            self.list.setCurrentRow(row)

    def _row_changed(self, row: int) -> None:
        self._refresh_buttons()
        if row >= 0:
            self.picked.emit(row)

    def _refresh_buttons(self) -> None:
        row, count = self.list.currentRow(), self.list.count()
        self.previous_button.setEnabled(row > 0)
        self.next_button.setEnabled(0 <= row < count - 1)
