"""The "Acerca de" window: version, licence and the software the program uses."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, BUILD_LABEL, __version__
from app.core import about
from app.ui.icons import logo_icon

LOGO_SIZE = 56


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Acerca de {0}").format(APP_NAME))
        self.setMinimumSize(660, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(logo_icon().pixmap(LOGO_SIZE, LOGO_SIZE))
        top.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        version = self.tr("Versión {0}").format(__version__)
        if BUILD_LABEL:
            version += f" · {BUILD_LABEL}"
        self.title = QLabel(f"<b>{APP_NAME}</b><br>{version}")
        self.title.setObjectName("aboutTitle")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top.addWidget(self.title, 1)
        layout.addLayout(top)

        self.summary = QLabel(
            self.tr(
                "Lector de PDF gratuito y libre. Tus documentos no salen de tu ordenador: "
                "sin cuentas, sin anuncios y sin enviar datos."
            )
        )
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.notices = QPlainTextEdit()
        self.notices.setReadOnly(True)
        self.notices.setAccessibleName(self.tr("Licencia y software que usa el programa"))
        self.notices.setPlainText(
            about.notices_text()
            or self.tr("Software libre bajo licencia AGPL-3.0. Código fuente: {0}").format(
                about.SOURCE_URL
            )
        )
        layout.addWidget(self.notices, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr("Cerrar"))
        self.source_button = QPushButton(self.tr("Ver el &código fuente"))
        self.source_button.setToolTip(self.tr("Abre en el navegador la página del proyecto"))
        self.source_button.clicked.connect(self.open_source_page)
        self.licences_button = QPushButton(self.tr("Abrir la carpeta de &licencias"))
        self.licences_button.setToolTip(self.tr("El texto completo de cada licencia"))
        self.licences_button.clicked.connect(self.open_licence_folder)
        buttons.addButton(self.source_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self.licences_button, QDialogButtonBox.ButtonRole.ActionRole)
        for button in (self.source_button, self.licences_button):
            button.setAutoDefault(False)
        buttons.button(QDialogButtonBox.StandardButton.Close).setDefault(True)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_source_page(self) -> None:
        QDesktopServices.openUrl(QUrl(about.SOURCE_URL))

    def open_licence_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(about.licence_folder())))
