"""«De foto a PDF»: photos of paper made into a PDF that looks scanned.

The dialog shows each photo with the four corners of the sheet found in it,
which can be dragged (with the mouse, a finger or a pen) or moved with the
keyboard, and beside it how the page will look. The work itself is done by
``app.core.photo_scan``; here the photos are only shown in a small copy.
"""

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core import photo_scan
from app.core.photo_scan import Photo, PhotoError

SHOWN_SIDE = 1400  # the photo is shown from a copy this long
RESULT_SIDE = 700  # and how the page will look, from a copy this long
HANDLE = 11  # radius of a corner handle, in pixels on screen
REACH = 28  # a press this close to a corner takes it (big enough for a finger)
STEP = 0.004  # an arrow key moves the corner this share of the photo (Mayús: 5 times)

LOOK_NAMES = {
    photo_scan.DOCUMENT: "Documento (recomendado)",
    photo_scan.GRAY: "Gris",
    photo_scan.BLACK_WHITE: "Blanco y negro",
    photo_scan.PHOTO: "Foto sin retocar",
}
LOOK_SETTING = "photo_scan/look"
CORNER_NAMES = (
    "arriba a la izquierda",
    "arriba a la derecha",
    "abajo a la derecha",
    "abajo a la izquierda",
)


def to_image(pix) -> QImage:
    """A PyMuPDF pixmap (grey or RGB, no see-through) as a QImage."""
    kind = QImage.Format.Format_Grayscale8 if pix.n == 1 else QImage.Format.Format_RGB888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, kind).copy()


def photo_types() -> str:
    return " ".join(f"*.{kind}" for kind in photo_scan.IMAGE_TYPES)


class CornerEditor(QWidget):
    """A photo with the four corners of the sheet on it, to move them.

    The corners are shares of the photo's width and height (0 to 1). The
    chosen corner (Tab and Mayús+Tab go round them) moves with the arrows.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image = QImage()
        self.corners: list[tuple[float, float]] = []
        self.current = 0
        self._held: int | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(self.tr("Esquinas de la hoja en la foto"))
        self.setToolTip(
            self.tr(
                "Arrastra las esquinas hasta las de la hoja. Con el teclado: Tab elige la "
                "esquina y las flechas la mueven (con Mayús, más deprisa)."
            )
        )

    def show_photo(self, image: QImage, corners: list[tuple[float, float]]) -> None:
        self.image = image
        self.corners = list(corners)
        self.current = 0
        self._describe()
        self.update()

    # ---- where things are on screen ----

    def _frame(self) -> QRectF:
        """Where the photo is drawn: as large as fits, in the middle."""
        if self.image.isNull():
            return QRectF()
        margin = HANDLE + 2
        room = QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)
        size = QSize(self.image.width(), self.image.height()).scaled(
            room.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio
        )
        frame = QRectF(0, 0, size.width(), size.height())
        frame.moveCenter(room.center())
        return frame

    def _on_screen(self, corner: tuple[float, float]) -> QPointF:
        frame = self._frame()
        return QPointF(
            frame.left() + corner[0] * frame.width(), frame.top() + corner[1] * frame.height()
        )

    def _share(self, point: QPointF) -> tuple[float, float]:
        frame = self._frame()
        x = (point.x() - frame.left()) / max(1.0, frame.width())
        y = (point.y() - frame.top()) / max(1.0, frame.height())
        return min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)

    def corner_on_screen(self, index: int) -> QPointF:
        return self._on_screen(self.corners[index])

    # ---- moving ----

    def move_corner(self, index: int, share: tuple[float, float]) -> bool:
        """Put a corner there, unless the sheet would fold over itself."""
        share = (min(max(share[0], 0.0), 1.0), min(max(share[1], 0.0), 1.0))
        moved = list(self.corners)
        moved[index] = share
        if not photo_scan.is_convex(moved):
            return False
        self.corners = moved
        self.update()
        self.changed.emit()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.corners:
            return super().mousePressEvent(event)
        position = event.position()
        distances = [
            (QPointF(self._on_screen(corner) - position).manhattanLength(), index)
            for index, corner in enumerate(self.corners)
        ]
        distance, index = min(distances)
        if distance <= REACH * 1.4:
            self._held = self.current = index
            self._describe()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._held is not None:
            self.move_corner(self._held, self._share(event.position()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._held = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if not self.corners:
            return super().keyPressEvent(event)
        step = STEP * (5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
        moves = {
            Qt.Key.Key_Left: (-step, 0),
            Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, -step),
            Qt.Key.Key_Down: (0, step),
        }
        if key in moves:
            x, y = self.corners[self.current]
            dx, dy = moves[key]
            self.move_corner(self.current, (x + dx, y + dy))
            return
        if key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4):
            self.current = key - Qt.Key.Key_1
            self._describe()
            self.update()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, forward: bool) -> bool:
        # Tab goes round the corners first, then on to the next control.
        if self.hasFocus() and self.corners:
            following = self.current + (1 if forward else -1)
            if 0 <= following < 4:
                self.current = following
                self._describe()
                self.update()
                return True
            self.current = 0 if forward else 3
        return super().focusNextPrevChild(forward)

    def _describe(self) -> None:
        if self.corners:
            self.setAccessibleDescription(
                self.tr("Esquina elegida: {0}").format(self.tr(CORNER_NAMES[self.current]))
            )

    # ---- drawing ----

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        frame = self._frame()
        if self.image.isNull():
            return
        painter.drawImage(frame, self.image)
        if not self.corners:
            return
        sheet = QPolygonF([self._on_screen(corner) for corner in self.corners])
        outside = QPainterPath()
        outside.addRect(frame)
        inside = QPainterPath()
        inside.addPolygon(sheet)
        inside.closeSubpath()
        painter.fillPath(outside.subtracted(inside), QColor(0, 0, 0, 120))
        accent = self.palette().highlight().color()
        painter.setPen(QPen(accent, 2))
        painter.drawPolygon(sheet)
        for index, corner in enumerate(sheet):
            chosen = index == self.current and self.hasFocus()
            painter.setPen(QPen(QColor("white"), 2))
            painter.setBrush(accent.darker(130) if chosen else accent)
            radius = HANDLE + (3 if chosen else 0)
            painter.drawEllipse(corner, radius, radius)


class PhotoScanDialog(QDialog):
    """After ``exec()`` returns ``Accepted``: ``photos`` (what to do with each
    photo, in order) and ``look``."""

    def __init__(self, parent: QWidget | None, paths: list[Path], look: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("De foto a PDF"))
        self.setMinimumSize(900, 600)
        self._shown: dict[int, object] = {}  # small copies of the photos, by id of their item
        self._next_id = 0
        self.problems: list[str] = []

        explanation = QLabel(
            self.tr(
                "Cada foto será una página. Si las esquinas no están sobre las de la hoja, "
                "arrástralas. A la derecha ves cómo quedará."
            )
        )
        explanation.setWordWrap(True)

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Fotos, en el orden de las páginas"))
        self.list.setIconSize(QSize(64, 64))
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.setMaximumWidth(220)
        self.list.currentItemChanged.connect(lambda *_args: self._show_current())
        self.list.model().rowsMoved.connect(lambda *_args: self._update_buttons())
        add = QPushButton(self.tr("&Añadir fotos…"))
        add.clicked.connect(self.choose_photos)
        self.remove_button = QPushButton(self.tr("&Quitar"))
        self.remove_button.clicked.connect(self.remove_current)
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addWidget(add)
        left.addWidget(self.remove_button)

        self.editor = CornerEditor()
        self.editor.changed.connect(self._corners_moved)
        self.turn_left = QPushButton(self.tr("Girar a la &izquierda"))
        self.turn_left.clicked.connect(lambda: self.turn(-1))
        self.turn_right = QPushButton(self.tr("Girar a la &derecha"))
        self.turn_right.clicked.connect(lambda: self.turn(1))
        self.whole_button = QPushButton(self.tr("&Toda la foto"))
        self.whole_button.setToolTip(self.tr("Usar la foto entera, sin recortar"))
        self.whole_button.clicked.connect(self.use_whole)
        self.find_button = QPushButton(self.tr("&Buscar la hoja"))
        self.find_button.setToolTip(self.tr("Volver a buscar las esquinas de la hoja"))
        self.find_button.clicked.connect(self.find_again)
        tools = QHBoxLayout()
        for button in (self.turn_left, self.turn_right, self.whole_button, self.find_button):
            tools.addWidget(button)
        middle = QVBoxLayout()
        middle.addWidget(self.editor, 1)
        middle.addLayout(tools)

        self.result = QLabel()
        self.result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result.setMinimumSize(240, 320)
        self.result.setAccessibleName(self.tr("Así quedará la página"))
        self.look_box = QComboBox()
        self.look_box.setAccessibleName(self.tr("Aspecto"))
        for key, name in LOOK_NAMES.items():
            self.look_box.addItem(self.tr(name), key)
        self.look_box.setCurrentIndex(max(0, self.look_box.findData(look)))
        self.look_box.currentIndexChanged.connect(lambda *_args: self._redraw_soon())
        look_label = QLabel(self.tr("&Aspecto:"))
        look_label.setBuddy(self.look_box)
        right = QVBoxLayout()
        right.addWidget(QLabel(self.tr("Así quedará:")))
        right.addWidget(self.result, 1)
        right.addWidget(look_label)
        right.addWidget(self.look_box)

        columns = QHBoxLayout()
        columns.addLayout(left)
        columns.addLayout(middle, 3)
        columns.addLayout(right, 2)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.create_button = self.buttons.addButton(
            self.tr("&Crear PDF"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.create_button.setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(columns, 1)
        layout.addWidget(self.buttons)

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(150)
        self._redraw_timer.timeout.connect(self.redraw_result)

        self.add_photos(paths)
        self._update_buttons()

    # ---- the list ----

    def add_photos(self, paths) -> None:
        for path in paths:
            try:
                small = photo_scan.open_photo(path, SHOWN_SIDE)
            except PhotoError:
                self.problems.append(Path(path).name)
                continue
            corners = photo_scan.as_shares(small, photo_scan.find_paper(small))
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, Photo(Path(path), corners))
            item.setData(Qt.ItemDataRole.UserRole + 1, self._next_id)
            item.setToolTip(str(path))
            image = to_image(small)
            item.setIcon(
                QIcon(QPixmap.fromImage(image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)))
            )
            self._shown[self._next_id] = (small, image)
            self._next_id += 1
            self.list.addItem(item)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self._update_buttons()

    def choose_photos(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Elegir las fotos"),
            "",
            self.tr("Imágenes ({0})").format(photo_types()),
        )
        self.add_photos([Path(name) for name in chosen])

    def remove_current(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            item = self.list.takeItem(row)
            self._shown.pop(item.data(Qt.ItemDataRole.UserRole + 1), None)
        self._show_current()
        self._update_buttons()

    def _update_buttons(self) -> None:
        has = self.list.count() > 0
        current = self.list.currentItem() is not None
        self.create_button.setEnabled(has)
        for button in (
            self.remove_button,
            self.turn_left,
            self.turn_right,
            self.whole_button,
            self.find_button,
        ):
            button.setEnabled(current)

    @property
    def photos(self) -> list[Photo]:
        return [
            self.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.list.count())
        ]

    @property
    def look(self) -> str:
        return self.look_box.currentData()

    # ---- the photo shown ----

    def _current(self):
        item = self.list.currentItem()
        if item is None:
            return None, None, None
        small, image = self._shown[item.data(Qt.ItemDataRole.UserRole + 1)]
        return item, item.data(Qt.ItemDataRole.UserRole), (small, image)

    def _show_current(self) -> None:
        item, photo, shown = self._current()
        if item is None:
            self.editor.show_photo(QImage(), [])
            self.result.clear()
        else:
            self.editor.show_photo(shown[1], photo.corners)
            self.redraw_result()
        self._update_buttons()

    def _keep(self, photo: Photo) -> None:
        self.list.currentItem().setData(Qt.ItemDataRole.UserRole, photo)

    def _corners_moved(self) -> None:
        item, photo, _shown = self._current()
        if item is not None:
            self._keep(Photo(photo.path, list(self.editor.corners), photo.turns))
            self._redraw_soon()

    def turn(self, quarters: int) -> None:
        item, photo, _shown = self._current()
        if item is not None:
            self._keep(Photo(photo.path, photo.corners, (photo.turns + quarters) % 4))
            self.redraw_result()

    def use_whole(self) -> None:
        item, photo, shown = self._current()
        if item is not None:
            corners = photo_scan.as_shares(shown[0], photo_scan.whole(shown[0]))
            self._keep(Photo(photo.path, corners, photo.turns))
            self._show_current()

    def find_again(self) -> None:
        item, photo, shown = self._current()
        if item is not None:
            corners = photo_scan.as_shares(shown[0], photo_scan.find_paper(shown[0]))
            self._keep(Photo(photo.path, corners, photo.turns))
            self._show_current()

    def _redraw_soon(self) -> None:
        self._redraw_timer.start()

    def redraw_result(self) -> None:
        """Show how the page of the photo in front will look."""
        item, photo, shown = self._current()
        if item is None:
            return
        small = shown[0]
        try:
            corners = photo_scan.in_pixels(small, photo.corners)
            page = photo_scan.straighten(small, corners, photo.turns, RESULT_SIDE)
            page = photo_scan.clean(page, self.look)
        except PhotoError:
            self.result.setText(self.tr("Esas esquinas no forman una hoja."))
            return
        picture = QPixmap.fromImage(to_image(page))
        self.result.setPixmap(
            picture.scaled(
                self.result.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.last_result = page

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._redraw_soon()
