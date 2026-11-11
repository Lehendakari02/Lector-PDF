"""Main window. For now only a placeholder that proves the program starts."""

from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from app import APP_NAME, BUILD_LABEL, __version__
from app.core.document import engine_version
from app.core.paths import data_dir, is_portable


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

        build = QLabel(BUILD_LABEL)
        build.setObjectName("placeholderBuild")
        build.setVisible(bool(BUILD_LABEL))

        if is_portable():
            data_text = self.tr("Versión portátil. Los datos se guardan junto al programa: {0}")
        else:
            data_text = self.tr("Carpeta de datos del programa: {0}")
        data = QLabel(data_text.format(data_dir()))
        data.setObjectName("placeholderData")

        layout = QVBoxLayout()
        layout.addStretch()
        for label in (title, build, message, versions, data):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addStretch()

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
