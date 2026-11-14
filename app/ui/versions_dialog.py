"""Shows the earlier versions of a document, to look at one or put it back."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.versions import Version
from app.ui.when import size_text, when_text

VIEW = "view"
RESTORE = "restore"


class VersionsDialog(QDialog):
    """ "Archivo → Versiones anteriores".

    After it closes, ``action`` is ``VIEW``, ``RESTORE`` or "" (nothing), and
    ``chosen`` the version it is about.
    """

    def __init__(self, name: str, versions: list[Version], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.versions = list(versions)
        self.action = ""
        self.chosen: Version | None = None
        self.setWindowTitle(self.tr("Versiones anteriores"))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        if self.versions:
            text = self.tr("Así estaba «{0}» antes de guardarlo. Elige una versión:").format(name)
        else:
            text = self.tr("Todavía no hay versiones anteriores de «{0}».").format(name)
        self.message = QLabel(text)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Versiones anteriores del documento"))
        for version in self.versions:
            line = self.tr("Como estaba {0}  ·  {1}").format(
                when_text(version.when), size_text(version.size)
            )
            self.list.addItem(QListWidgetItem(line))
        if self.versions:
            self.list.setCurrentRow(0)
        self.list.setMaximumHeight(min(260, 36 * max(1, len(self.versions)) + 14))
        self.list.setVisible(bool(self.versions))
        self.list.itemDoubleClicked.connect(lambda _item: self._finish(VIEW))
        layout.addWidget(self.list)

        note = QLabel(
            self.tr(
                "El programa guarda una copia de cómo estaba el PDF la primera vez que "
                "pulsas Guardar cada vez que lo abres. Restaurar una versión también se "
                "puede deshacer: lo de ahora queda guardado como una versión más."
            )
        )
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox()
        self.view_button = buttons.addButton(
            self.tr("&Ver"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.view_button.setToolTip(self.tr("Abrir esa versión en otra pestaña, sin cambiar nada"))
        self.restore_button = buttons.addButton(
            self.tr("&Restaurar"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.restore_button.setToolTip(self.tr("Dejar el documento como estaba en esa versión"))
        self.close_button = buttons.addButton(
            self.tr("Cerrar"), QDialogButtonBox.ButtonRole.RejectRole
        )
        for button in (self.view_button, self.restore_button):
            button.setEnabled(bool(self.versions))
        self.view_button.setDefault(bool(self.versions))
        self.view_button.clicked.connect(lambda: self._finish(VIEW))
        self.restore_button.clicked.connect(lambda: self._finish(RESTORE))
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _finish(self, action: str) -> None:
        row = self.list.currentRow()
        if not 0 <= row < len(self.versions):
            return
        self.action = action
        self.chosen = self.versions[row]
        self.accept()
