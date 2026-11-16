"""The strip over a scanned document that offers to recognise its text.

It never interrupts: it waits above the pages until it is answered or closed.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class OcrBanner(QFrame):
    """Says that pages are only pictures and offers "Reconocer texto"."""

    recognize_wanted = Signal()
    never_wanted = Signal()  # not again for this document

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ocrBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(8)
        self.message = QLabel()
        self.message.setObjectName("bannerMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message, 1)
        self.recognize_button = QPushButton(self.tr("Reconocer texto"))
        self.recognize_button.setObjectName("bannerMainButton")
        self.recognize_button.setToolTip(
            self.tr(
                "Lee las letras de las páginas escaneadas para poder buscar, subrayar y "
                "copiar. Se hace en tu ordenador; la página se sigue viendo igual."
            )
        )
        self.recognize_button.clicked.connect(self.recognize_wanted)
        self.later_button = QPushButton(self.tr("Ahora no"))
        self.later_button.setToolTip(self.tr("Te lo vuelvo a ofrecer al abrirlo otra vez"))
        self.later_button.clicked.connect(self.hide)
        self.never_button = QPushButton(self.tr("No preguntar más en este documento"))
        self.never_button.clicked.connect(self._never)
        for button in (self.recognize_button, self.later_button, self.never_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
        self.hide()

    def offer(self, scanned: int, count: int) -> None:
        """Offer it for a document with ``scanned`` of its ``count`` pages scanned."""
        if scanned >= count:
            text = self.tr(
                "Este documento está escaneado: sus páginas son imágenes, sin texto. "
                "Para buscar, subrayar o copiar, reconoce su texto."
            )
        elif scanned == 1:
            text = self.tr(
                "Una página de este documento está escaneada (es una imagen, sin texto)."
            )
        else:
            text = self.tr(
                "{0} de las {1} páginas de este documento están escaneadas "
                "(son imágenes, sin texto)."
            ).format(scanned, count)
        self.message.setText(text)
        self.show()

    def _never(self) -> None:
        self.hide()
        self.never_wanted.emit()
