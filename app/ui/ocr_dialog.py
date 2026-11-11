"""Shows the text recognised in a scanned page."""

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.ocr import OcrPage


class OcrResultDialog(QDialog):
    def __init__(self, result: OcrPage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Texto reconocido"))
        self.resize(640, 520)
        self.summary = QLabel(
            self.tr("Página {0} · {1} palabras · {2} segundos").format(
                result.page + 1, len(result.words), f"{result.seconds:.1f}".replace(".", ",")
            )
        )
        self.text = QPlainTextEdit(result.text)
        self.text.setReadOnly(True)
        self.text.setAccessibleName(self.tr("Texto reconocido en la página"))
        self.note = QLabel(
            self.tr(
                "Esto es una prueba: el texto todavía no se guarda en el PDF. "
                "Eso llegará con la fase de documentos escaneados."
            )
        )
        self.note.setWordWrap(True)
        buttons = QDialogButtonBox()
        self.copy_button = buttons.addButton(
            self.tr("Copiar texto"), QDialogButtonBox.ButtonRole.ActionRole
        )
        buttons.addButton(self.tr("Cerrar"), QDialogButtonBox.ButtonRole.RejectRole)
        self.copy_button.clicked.connect(self.copy_text)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.note)
        layout.addWidget(buttons)

    def copy_text(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())
