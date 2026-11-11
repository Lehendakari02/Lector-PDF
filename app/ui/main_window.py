"""Main window. For now only a placeholder that proves the program starts."""

from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from app import APP_NAME, __version__
from app.core.document import engine_version


class MainWindow(QMainWindow):
    """Top-level window of the program."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 750)

        title = QLabel(f"{APP_NAME} {__version__}")
        title.setObjectName("placeholderTitle")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 10)
        title_font.setBold(True)
        title.setFont(title_font)

        message = QLabel(self.tr("En construcción. Todavía no se pueden abrir documentos."))
        message.setObjectName("placeholderMessage")

        # Shown on purpose: when testing a build it proves the PDF engine and Qt
        # were packaged correctly.
        versions = QLabel(
            self.tr("Motor PDF (PyMuPDF) {0} · Qt {1}").format(engine_version(), qVersion())
        )
        versions.setObjectName("placeholderVersions")

        layout = QVBoxLayout()
        layout.addStretch()
        for label in (title, message, versions):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addStretch()

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
