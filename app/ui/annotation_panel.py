"""The list of everything put on the document, in the side panel.

Marks, notes, texts and drawings in reading order, each with its colour, its
page and the words it is about. Above, a button per colour used (and one for
all of them) and a choice of what to see; a click on one goes there and picks
it.
"""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.annotation_list import (
    DRAWINGS,
    MARKS,
    NOTES,
    Entry,
    colors_of,
    same_color,
)
from app.core.commands import HIGHLIGHT, STRIKEOUT, UNDERLINE
from app.core.drawing import INK, SHAPES
from app.core.notes import NOTE, TEXT_BOX
from app.ui.color_menu import ColorMenu, Swatch

REFRESH_MS = 400  # after a change, the list is read again once things are quiet
CHIP = 30
DOT = 14
SHOWN_TEXT = 140  # letters of what an entry says shown in its row


def _dot(color) -> QIcon:
    picture = QPixmap(DOT, DOT)
    picture.fill(Qt.GlobalColor.transparent)
    painter = QPainter(picture)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(0, 0, 0, 60))
    painter.setBrush(QColor.fromRgbF(*color))
    painter.drawEllipse(1, 1, DOT - 2, DOT - 2)
    painter.end()
    return QIcon(picture)


class AnnotationPanel(QWidget):
    """Every annotation of the document in the view, to filter and go to."""

    def __init__(self, view, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.entries: list[Entry] = []
        self._color = None  # the colour kept, or None for all
        self._wanted = False  # the list is old and is read again when seen

        self.colors_row = QHBoxLayout()
        self.colors_row.setSpacing(2)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.all_button = QToolButton()
        self.all_button.setObjectName("panelTab")
        self.all_button.setText(self.tr("Todos"))
        self.all_button.setCheckable(True)
        self.all_button.setChecked(True)
        self.all_button.setToolTip(self.tr("Ver todos los colores"))
        self.all_button.clicked.connect(lambda: self.keep_color(None))
        self.color_group.addButton(self.all_button)
        self.color_buttons: list[Swatch] = []

        self.kind_box = QComboBox()
        self.kind_box.setAccessibleName(self.tr("Qué anotaciones ver"))
        for name, group in (
            (self.tr("Todo"), None),
            (self.tr("Subrayados y resaltados"), MARKS),
            (self.tr("Notas y textos"), NOTES),
            (self.tr("Dibujos y formas"), DRAWINGS),
        ):
            self.kind_box.addItem(name, group)
        self.kind_box.currentIndexChanged.connect(lambda _index: self._fill())

        self.list = QListWidget()
        self.list.setObjectName("annotationList")
        self.list.setAccessibleName(self.tr("Anotaciones del documento"))
        self.list.setWordWrap(True)
        self.list.setIconSize(QSize(DOT, DOT))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._go)
        self.list.itemActivated.connect(self._go)
        self.empty = QLabel()
        self.empty.setObjectName("panelEmpty")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.empty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(self.colors_row)
        layout.addWidget(self.kind_box)
        layout.addWidget(self.stack, 1)

        self._pause = QTimer(self)
        self._pause.setSingleShot(True)
        self._pause.setInterval(REFRESH_MS)
        self._pause.timeout.connect(self.refresh)
        view.annotations_listed.connect(self._listed)
        view.pages_changed.connect(lambda _pages: self.changed())
        view.pages_reshaped.connect(self.changed)
        self._show_colors()
        self._fill()

    # ---- reading the list ---------------------------------------------------

    def changed(self) -> None:
        """The document changed: read the list again (soon, if it is seen)."""
        self._wanted = True
        if self.isVisible():
            self._pause.start()

    def refresh(self) -> None:
        self._wanted = False
        self.view.want_annotations()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._wanted or not self.entries:
            self.refresh()

    def document_changed(self) -> None:
        self.entries = []
        self._color = None
        self._show_colors()
        self._fill()
        self.changed()

    def _listed(self, entries: object) -> None:
        self.entries = list(entries)
        if self._color is not None and not any(
            same_color(entry.color, self._color) for entry in self.entries
        ):
            self._color = None  # that colour is no longer used
        self._show_colors()
        self._fill()

    # ---- the filters --------------------------------------------------------

    def _show_colors(self) -> None:
        for button in self.color_buttons:
            self.color_group.removeButton(button)
            button.deleteLater()
        self.color_buttons = []
        while self.colors_row.count():
            self.colors_row.takeAt(0)
        self.colors_row.addWidget(self.all_button)
        for color in colors_of(self.entries):
            button = Swatch(color, ColorMenu.swatch_name(self, color) or self.tr("Otro color"))
            button.setFixedSize(QSize(CHIP, CHIP))
            button.setToolTip(self.tr("Ver solo este color"))
            button.clicked.connect(lambda _checked=False, c=color: self.keep_color(c))
            self.color_group.addButton(button)
            self.colors_row.addWidget(button)
            self.color_buttons.append(button)
            button.setChecked(self._color is not None and same_color(color, self._color))
        self.all_button.setChecked(self._color is None)
        self.colors_row.addStretch(1)

    def keep_color(self, color) -> None:
        """Show only the annotations of one colour, or all with None."""
        self._color = tuple(color) if color is not None else None
        for button in self.color_buttons:
            button.setChecked(self._color is not None and same_color(button.color, self._color))
        self.all_button.setChecked(self._color is None)
        self._fill()

    def keep_group(self, group: str | None) -> None:
        self.kind_box.setCurrentIndex(max(0, self.kind_box.findData(group)))

    def shown(self) -> list[Entry]:
        """The annotations that pass the filters, in reading order."""
        group = self.kind_box.currentData()
        return [
            entry
            for entry in self.entries
            if (group is None or entry.group == group)
            and (self._color is None or same_color(entry.color, self._color))
        ]

    # ---- the list ---------------------------------------------------------------

    def kind_name(self, kind: str) -> str:
        names = {
            HIGHLIGHT: self.tr("Resaltado"),
            UNDERLINE: self.tr("Subrayado"),
            STRIKEOUT: self.tr("Tachado"),
            NOTE: self.tr("Nota"),
            TEXT_BOX: self.tr("Texto"),
            INK: self.tr("Dibujo"),
        }
        if kind in names:
            return names[kind]
        return self.tr("Forma") if kind in SHAPES else self.tr("Anotación")

    def _fill(self) -> None:
        self.list.clear()
        shown = self.shown()
        for entry in shown:
            title = self.tr("Pág. {0} · {1}").format(entry.page + 1, self.kind_name(entry.kind))
            text = entry.text
            if len(text) > SHOWN_TEXT:
                text = text[: SHOWN_TEXT - 1].rstrip() + "…"
            item = QListWidgetItem(_dot(entry.color), f"{title}\n{text}" if text else title)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(entry.text or title)
            self.list.addItem(item)
        if shown:
            self.stack.setCurrentWidget(self.list)
            return
        if not self.entries:
            self.empty.setText(
                self.tr(
                    "Aún no hay nada subrayado ni anotado en este documento.\n\n"
                    "Lo que subrayes, escribas o dibujes aparecerá aquí, en orden."
                )
            )
        else:
            self.empty.setText(self.tr("No hay anotaciones con este filtro."))
        self.stack.setCurrentWidget(self.empty)

    def _go(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self.view.show_annotation(entry.page, entry.rect, entry.name)
