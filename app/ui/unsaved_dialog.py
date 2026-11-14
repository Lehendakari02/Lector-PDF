"""Asks what to do with changes that are not saved, before closing."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.journal import KEEP_DISCARDED_DAYS

SAVE = "save"
DISCARD = "discard"
CANCEL = "cancel"


class UnsavedDialog(QDialog):
    """Guardar / No guardar / Cancelar, for one document or for several at once.

    ``choice`` holds the answer; closing the dialog any other way is "Cancelar".
    """

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.choice = CANCEL
        self.setWindowTitle(self.tr("Cambios sin guardar"))
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        if len(names) == 1:
            question = self.tr("¿Quieres guardar los cambios de «{0}»?").format(names[0])
        else:
            question = self.tr("Estos {0} documentos tienen cambios sin guardar:").format(
                len(names)
            )
        self.question = QLabel(question)
        self.question.setWordWrap(True)
        layout.addWidget(self.question)

        self.names = QListWidget()
        self.names.setAccessibleName(self.tr("Documentos con cambios sin guardar"))
        self.names.addItems(names)
        self.names.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.names.setMaximumHeight(min(160, 30 * len(names) + 8))
        self.names.setVisible(len(names) > 1)
        layout.addWidget(self.names)

        note = QLabel(
            self.tr(
                "Si no los guardas, el PDF se queda como estaba. Los cambios se conservan "
                "{0} días en Archivo → Recuperar cambios descartados."
            ).format(KEEP_DISCARDED_DAYS)
        )
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox()
        save_text = self.tr("&Guardar") if len(names) == 1 else self.tr("&Guardar todos")
        self.save_button = buttons.addButton(save_text, QDialogButtonBox.ButtonRole.AcceptRole)
        self.discard_button = buttons.addButton(
            self.tr("&No guardar"), QDialogButtonBox.ButtonRole.DestructiveRole
        )
        self.cancel_button = buttons.addButton(
            self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(lambda: self._answer(SAVE))
        self.discard_button.clicked.connect(lambda: self._answer(DISCARD))
        self.cancel_button.clicked.connect(lambda: self._answer(CANCEL))
        layout.addWidget(buttons)

    def _answer(self, choice: str) -> None:
        self.choice = choice
        if choice == CANCEL:
            self.reject()
        else:
            self.accept()
