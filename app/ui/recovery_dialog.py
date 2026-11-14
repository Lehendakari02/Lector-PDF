"""Offers to bring back changes that were never saved."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.journal import KEEP_DISCARDED_DAYS, Pending
from app.ui.when import when_text


class RecoveryDialog(QDialog):
    """Two uses, the same list.

    - After the program was closed by force (``crashed``): every document with
      changes not saved; "Recuperar" brings them all back, "Ahora no" sets them
      aside for some days.
    - "Archivo → Recuperar cambios descartados": what was set aside with
      "No guardar"; one is chosen and brought back.

    ``chosen`` holds what has to be recovered (empty if nothing).
    """

    def __init__(self, items: list[Pending], crashed: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.items = list(items)
        self.crashed = crashed
        self.chosen: list[Pending] = []
        self.setWindowTitle(
            self.tr("Recuperar cambios") if crashed else self.tr("Cambios descartados")
        )
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        if crashed:
            text = self.tr(
                "El programa se cerró sin que diera tiempo a guardar. "
                "Estos documentos tenían cambios sin guardar:"
            )
        elif self.items:
            text = self.tr("Cambios que no se guardaron al cerrar. Elige cuáles recuperar:")
        else:
            text = self.tr("No hay cambios descartados que recuperar.")
        self.message = QLabel(text)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Documentos con cambios que se pueden recuperar"))
        for pending in self.items:
            item = QListWidgetItem(self._describe(pending))
            item.setToolTip(str(pending.path))
            self.list.addItem(item)
        if crashed:
            self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        elif self.items:
            self.list.setCurrentRow(0)
        self.list.setMaximumHeight(min(240, 36 * max(1, len(self.items)) + 14))
        self.list.setVisible(bool(self.items))
        self.list.itemDoubleClicked.connect(lambda _item: self._recover())
        layout.addWidget(self.list)

        note = QLabel(
            self.tr(
                "Al recuperarlos vuelven al documento como cambios sin guardar: "
                "el PDF no cambia hasta que pulses Guardar."
            )
            if self.items
            else ""
        )
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        note.setVisible(bool(self.items))
        layout.addWidget(note)
        self.keep_note = QLabel(
            self.tr(
                "Si eliges «Ahora no», se conservan {0} días en "
                "Archivo → Recuperar cambios descartados."
            ).format(KEEP_DISCARDED_DAYS)
            if crashed
            else self.tr("Los cambios descartados se conservan {0} días.").format(
                KEEP_DISCARDED_DAYS
            )
        )
        self.keep_note.setObjectName("dialogNote")
        self.keep_note.setWordWrap(True)
        layout.addWidget(self.keep_note)

        buttons = QDialogButtonBox()
        self.recover_button = buttons.addButton(
            self.tr("&Recuperar"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.recover_button.setDefault(True)
        self.recover_button.setEnabled(bool(self.items))
        self.recover_button.clicked.connect(self._recover)
        self.later_button = buttons.addButton(
            self.tr("&Ahora no") if crashed else self.tr("Cerrar"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.later_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _recover(self) -> None:
        if self.crashed:
            self.chosen = list(self.items)
        else:
            row = self.list.currentRow()
            self.chosen = [self.items[row]] if 0 <= row < len(self.items) else []
        if self.chosen:
            self.accept()

    def _describe(self, pending: Pending) -> str:
        if pending.count == 1:
            changes = self.tr("1 cambio")
        else:
            changes = self.tr("{0} cambios").format(pending.count)
        return f"{pending.path.name}  ·  {changes}  ·  {when_text(pending.when)}"

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.recover_button.isEnabled():
            self._recover()
            return
        super().keyPressEvent(event)
