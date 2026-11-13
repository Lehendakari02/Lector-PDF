"""Asks for the password of a protected PDF, until it is right or the user gives up."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class PasswordDialog(QDialog):
    """``try_password`` receives what was typed and says if it opened the document.

    The password is never stored: it lives only while the document is open.
    """

    def __init__(
        self, file_name: str, try_password: Callable[[str], bool], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._try_password = try_password
        self.setWindowTitle(self.tr("Documento con contraseña"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        message = QLabel(self.tr("«{0}» está protegido. Escribe su contraseña:").format(file_name))
        message.setWordWrap(True)
        layout.addWidget(message)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setAccessibleName(self.tr("Contraseña del documento"))
        self.password_edit.textEdited.connect(lambda _text: self.error_label.hide())
        layout.addWidget(self.password_edit)

        self.show_box = QCheckBox(self.tr("&Mostrar la contraseña"))
        self.show_box.toggled.connect(self._show_password)
        layout.addWidget(self.show_box)

        self.error_label = QLabel(self.tr("Esa contraseña no es correcta. Prueba otra vez."))
        self.error_label.setObjectName("dialogError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        note = QLabel(self.tr("La contraseña no se guarda: se pedirá cada vez que lo abras."))
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.open_button.setText(self.tr("Abrir"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self._try)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password_edit.setFocus()

    def _show_password(self, shown: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)

    def _try(self) -> None:
        if self._try_password(self.password_edit.text()):
            self.accept()
            return
        self.error_label.show()
        self.password_edit.selectAll()
        self.password_edit.setFocus()
