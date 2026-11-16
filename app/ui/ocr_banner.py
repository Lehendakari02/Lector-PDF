"""The strip over a scanned document that offers to recognise its text.

It never interrupts: it waits above the pages until it is answered or closed.
While the text is being recognised it shows how far it has got, with a
button to stop.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget


class OcrBanner(QFrame):
    """Says that pages are only pictures and offers "Reconocer texto"."""

    recognize_wanted = Signal()
    never_wanted = Signal()  # not again for this document
    cancel_wanted = Signal()  # stop recognising

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
        self.progress = QProgressBar()
        self.progress.setObjectName("bannerProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.setAccessibleName(self.tr("Progreso del reconocimiento del texto"))
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton(self.tr("Cancelar"))
        self.cancel_button.setToolTip(
            self.tr("Para de reconocer. Las páginas ya leídas conservan su texto.")
        )
        self.cancel_button.clicked.connect(self.cancel_wanted)
        self._offer_buttons = (self.recognize_button, self.later_button, self.never_button)
        for button in (*self._offer_buttons, self.cancel_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
        self.working = False
        self._show_working(False)
        self.hide()

    def _show_working(self, working: bool) -> None:
        self.working = working
        for button in self._offer_buttons:
            button.setVisible(not working)
        self.progress.setVisible(working)
        self.cancel_button.setVisible(working)

    def show_progress(self, done: int, total: int) -> None:
        """Recognising: how many of the pages are done."""
        self._show_working(True)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        page = min(done + 1, total)
        self.message.setText(
            self.tr(
                "Reconociendo el texto: página {0} de {1}. Puedes seguir leyendo mientras tanto."
            ).format(page, total)
        )
        self.show()

    def finish(self) -> None:
        """Recognising is over: the strip goes away."""
        self._show_working(False)
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
        self._show_working(False)
        self.show()

    def _never(self) -> None:
        self.hide()
        self.never_wanted.emit()
