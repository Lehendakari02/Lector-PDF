"""Where one's signature (or initials) is made: drawn, written or from a picture."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QImageReader,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core import my_signature
from app.core.my_signature import INITIALS, SignatureError

INKS = {"black": QColor(26, 26, 26), "blue": QColor(20, 45, 140)}

# Handwriting fonts that come with Windows, best first; the first one this
# computer has is offered first.
HANDWRITING = (
    "Segoe Script",
    "Ink Free",
    "Lucida Handwriting",
    "Segoe Print",
    "Brush Script MT",
    "Gabriola",
)
SCALE = 3  # the picture of a drawing is made this many times larger than the pad
WRITTEN_PIXELS = 140  # the height of the letters of a written signature


def png_of(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data.data())


def handwriting_fonts() -> list[str]:
    have = set(QFontDatabase.families())
    return [family for family in HANDWRITING if family in have]


class DrawPad(QWidget):
    """A white card to sign on with the mouse, a finger or a pen (it feels the
    pressure of a pen)."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(460, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self.setAccessibleName(self.tr("Recuadro para dibujar la firma"))
        self.ink = INKS["black"]
        self.strokes: list[list[tuple[QPointF, float]]] = []
        self._drawing = False
        self.thickness = 2.4

    @property
    def empty(self) -> bool:
        return not any(len(stroke) > 1 for stroke in self.strokes)

    def clear(self) -> None:
        self.strokes = []
        self.update()
        self.changed.emit()

    def undo_stroke(self) -> None:
        if self.strokes:
            self.strokes.pop()
            self.update()
            self.changed.emit()

    def set_ink(self, color: QColor) -> None:
        self.ink = color
        self.update()

    # ---- drawing ---------------------------------------------------------------

    def _start(self, point: QPointF, pressure: float) -> None:
        self._drawing = True
        self.strokes.append([(point, pressure)])

    def _add(self, point: QPointF, pressure: float) -> None:
        if self._drawing and self.strokes:
            self.strokes[-1].append((point, pressure))
            self.update()

    def _end(self) -> None:
        if self._drawing:
            self._drawing = False
            if self.strokes and len(self.strokes[-1]) == 1:
                point, pressure = self.strokes[-1][0]
                self.strokes[-1].append((point + QPointF(0.5, 0.5), pressure))  # a dot
            self.update()
            self.changed.emit()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start(event.position(), 1.0)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._add(event.position(), 1.0)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._end()

    def tabletEvent(self, event) -> None:  # noqa: N802
        pressure = max(0.05, min(1.0, event.pressure()))
        kind = event.type()
        if kind == event.Type.TabletPress:
            self._start(event.position(), pressure)
        elif kind == event.Type.TabletMove:
            self._add(event.position(), pressure)
        elif kind == event.Type.TabletRelease:
            self._end()
        event.accept()

    def _width(self, pressure: float) -> float:
        return self.thickness * (0.45 + 0.85 * pressure)

    def _paint_strokes(self, painter: QPainter, scale: float) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for stroke in self.strokes:
            for (start, before), (end, after) in zip(stroke, stroke[1:], strict=False):
                pen = QPen(self.ink, self._width((before + after) / 2) * scale)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(start * scale, end * scale)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        line = self.height() * 0.72
        painter.drawLine(QPointF(24, line), QPointF(self.width() - 24, line))
        if not self.strokes:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(
                QRectF(0, 0, self.width(), line - 8),
                Qt.AlignmentFlag.AlignCenter,
                self.tr("Firma aquí con el ratón, el dedo o el lápiz"),
            )
        self._paint_strokes(painter, 1.0)
        painter.end()

    def picture(self) -> bytes:
        """What was drawn, as a picture with a see-through background."""
        image = QImage(self.width() * SCALE, self.height() * SCALE, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self._paint_strokes(painter, SCALE)
        painter.end()
        return png_of(image)


def written_picture(text: str, family: str, ink: QColor) -> bytes:
    """A name written with a handwriting font, as a picture."""
    font = QFont(family) if family else QFont()
    if not family:
        font.setItalic(True)
    font.setPixelSize(WRITTEN_PIXELS)
    metrics = QFontMetricsF(font)
    margin = WRITTEN_PIXELS // 2
    width = int(metrics.horizontalAdvance(text) + 2 * margin)
    height = int(metrics.height() + 2 * margin)
    image = QImage(max(width, 4), max(height, 4), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(ink)
    painter.drawText(QPointF(margin, margin + metrics.ascent()), text)
    painter.end()
    return png_of(image)


def upright_picture(path: str) -> bytes:
    """The picture of a file as it is meant to be seen, as PNG (b"" if it
    cannot be read). A phone keeps many photos lying down with a note of how
    to turn them (EXIF): it is turned here, or the signature would come out
    sideways."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        try:  # one Qt cannot read may still be read by the PDF engine
            with open(path, "rb") as file:
                return file.read()
        except OSError:
            return b""
    return png_of(image)


def preview_pixmap(png: bytes, width: int, height: int) -> QPixmap:
    pixmap = QPixmap()
    pixmap.loadFromData(png, "PNG")
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class SignatureDialog(QDialog):
    """``png`` is the picture made, once it is accepted.

    ``image_answer`` (a path) stands for the window that picks a picture, for
    the tests."""

    DRAW, WRITE, PICTURE = range(3)

    def __init__(self, kind: str, suggested: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.png: bytes = b""
        self.image_answer: str | None = None
        self._picture_data: bytes = b""  # the picture chosen, as it was
        self._picture_clean: bytes = b""
        initials = kind == INITIALS
        self.setWindowTitle(self.tr("Mis iniciales") if initials else self.tr("Mi firma"))
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        intro = QLabel(
            self.tr(
                "Hazla una vez y ponla en los documentos con un clic. Se guarda solo en "
                "este ordenador y nunca se envía a ningún sitio."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Draw.
        draw = QWidget()
        draw_layout = QVBoxLayout(draw)
        self.pad = DrawPad()
        self.pad.changed.connect(self._refresh)
        draw_layout.addWidget(self.pad, 1)
        draw_buttons = QHBoxLayout()
        undo = QPushButton(self.tr("Deshacer el último trazo"))
        undo.clicked.connect(self.pad.undo_stroke)
        clear = QPushButton(self.tr("Borrar"))
        clear.clicked.connect(self.pad.clear)
        draw_buttons.addWidget(undo)
        draw_buttons.addWidget(clear)
        draw_buttons.addStretch(1)
        draw_layout.addLayout(draw_buttons)
        self.tabs.addTab(draw, self.tr("Dibujar"))

        # Write.
        write = QWidget()
        write_layout = QVBoxLayout(write)
        self.words = QLineEdit(suggested)
        self.words.setPlaceholderText(
            self.tr("Tus iniciales") if initials else self.tr("Tu nombre")
        )
        self.words.setAccessibleName(self.tr("Lo que se escribe"))
        self.words.textChanged.connect(self._refresh)
        write_layout.addWidget(self.words)
        self.font_box = QComboBox()
        self.font_box.setAccessibleName(self.tr("Letra"))
        for family in handwriting_fonts():
            self.font_box.addItem(family, family)
        self.font_box.addItem(self.tr("Cursiva normal"), "")
        self.font_box.currentIndexChanged.connect(self._refresh)
        write_layout.addWidget(self.font_box)
        self.written_preview = QLabel()
        self.written_preview.setMinimumHeight(120)
        self.written_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.written_preview.setStyleSheet("background: white; border: 1px solid #ccc;")
        write_layout.addWidget(self.written_preview, 1)
        self.tabs.addTab(write, self.tr("Escribir"))

        # From a picture.
        picture = QWidget()
        picture_layout = QVBoxLayout(picture)
        choose = QPushButton(self.tr("Elegir una foto o imagen de tu firma…"))
        choose.clicked.connect(self.choose_picture)
        picture_layout.addWidget(choose)
        self.no_background = QCheckBox(self.tr("Quitar el fondo (el papel)"))
        self.no_background.setChecked(True)
        self.no_background.toggled.connect(self._clean_picture)
        picture_layout.addWidget(self.no_background)
        self.picture_preview = QLabel(
            self.tr("Firma en un papel blanco, hazle una foto y elígela aquí.")
        )
        self.picture_preview.setWordWrap(True)
        self.picture_preview.setMinimumHeight(120)
        self.picture_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture_preview.setStyleSheet("background: #e9e9e9; border: 1px solid #ccc;")
        picture_layout.addWidget(self.picture_preview, 1)
        self.tabs.addTab(picture, self.tr("Desde una imagen"))

        # Ink (for drawing and writing; a picture keeps its own).
        ink_row = QHBoxLayout()
        ink_row.addWidget(QLabel(self.tr("Tinta:")))
        self.ink_group = QButtonGroup(self)
        for name, label in (("black", self.tr("Negra")), ("blue", self.tr("Azul"))):
            button = QRadioButton(label)
            button.setProperty("ink", name)
            button.setChecked(name == "black")
            self.ink_group.addButton(button)
            ink_row.addWidget(button)
        ink_row.addStretch(1)
        self.ink_group.buttonToggled.connect(self._ink_changed)
        layout.addLayout(ink_row)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText(self.tr("Guardar"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.tabs.currentChanged.connect(self._refresh)
        if suggested and not initials:
            self.tabs.setCurrentIndex(self.DRAW)
        self._refresh()

    @property
    def ink(self) -> QColor:
        button = self.ink_group.checkedButton()
        return INKS[button.property("ink") if button else "black"]

    def set_ink(self, name: str) -> None:
        for button in self.ink_group.buttons():
            button.setChecked(button.property("ink") == name)

    def _ink_changed(self, *_args) -> None:
        self.pad.set_ink(self.ink)
        self._refresh()

    def choose_picture(self) -> bool:
        path = self.image_answer
        if path is None:
            path, _filter = QFileDialog.getOpenFileName(
                self,
                self.tr("Elegir la imagen de la firma"),
                "",
                self.tr("Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)"),
            )
        if not path:
            return False
        self._picture_data = upright_picture(path)
        self._clean_picture()
        return bool(self._picture_clean)

    def _clean_picture(self, *_args) -> None:
        self._picture_clean = b""
        if self._picture_data:
            try:
                self._picture_clean = my_signature.clean(
                    self._picture_data, self.no_background.isChecked()
                )
            except SignatureError:
                self.picture_preview.setPixmap(QPixmap())
                self.picture_preview.setText(
                    self.tr(
                        "No se ve ninguna firma en esa imagen. Prueba con una foto de la "
                        "firma en tinta oscura sobre papel blanco."
                    )
                )
        if self._picture_clean:
            self.picture_preview.setPixmap(preview_pixmap(self._picture_clean, 460, 160))
        self._refresh()

    def made(self) -> bytes:
        """The picture of the tab in front, uncut ("" if there is nothing yet)."""
        tab = self.tabs.currentIndex()
        if tab == self.DRAW:
            return b"" if self.pad.empty else self.pad.picture()
        if tab == self.WRITE:
            text = " ".join(self.words.text().split())
            if not text:
                return b""
            return written_picture(text, self.font_box.currentData() or "", self.ink)
        return self._picture_clean

    def _refresh(self, *_args) -> None:
        if self.tabs.currentIndex() == self.WRITE:
            made = self.made()
            if made:
                self.written_preview.setPixmap(preview_pixmap(made, 460, 110))
            else:
                self.written_preview.setPixmap(QPixmap())
        tab = self.tabs.currentIndex()
        ready = (
            not self.pad.empty
            if tab == self.DRAW
            else bool(self.words.text().strip())
            if tab == self.WRITE
            else bool(self._picture_clean)
        )
        self.save_button.setEnabled(ready)

    def accept(self) -> None:
        made = self.made()
        if not made:
            return
        try:
            self.png = (
                made
                if self.tabs.currentIndex() == self.PICTURE
                else my_signature.clean(made, remove_background=False)
            )
        except SignatureError:
            return
        super().accept()
