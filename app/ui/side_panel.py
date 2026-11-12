"""The side panel: small pictures of every page and the outline of the document."""

from enum import Enum

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.outline import OutlineEntry
from app.core.render_service import RenderedPage
from app.ui import icons
from app.ui.pdf_view import PdfView

THUMBNAIL_WIDTH = 132  # the box every small picture fits in
THUMBNAIL_HEIGHT = 176
CELL = QSize(THUMBNAIL_WIDTH + 28, THUMBNAIL_HEIGHT + 36)
PICTURES_AHEAD = 12  # drawn before they are scrolled into sight
PICTURES_BEHIND = 6
MAX_PICTURES = 400  # the ones farthest from the page being read are forgotten
REQUEST_PAUSE_MS = 60  # while scrolling fast, do not ask for every row passed


class Tab(Enum):
    THUMBNAILS = "miniaturas"
    OUTLINE = "indice"

    @classmethod
    def from_setting(cls, value: object) -> "Tab | None":
        return next((tab for tab in cls if tab.value == value), None)


class ThumbnailList(QListWidget):
    """Every page in small. Click one to go there."""

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.setObjectName("thumbnailList")
        self.setAccessibleName(self.tr("Miniaturas de las páginas"))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        self.setGridSize(CELL)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._drawn: set[int] = set()
        self._blank: dict[tuple[int, int], QIcon] = {}
        self._pause = QTimer(self)
        self._pause.setSingleShot(True)
        self._pause.setInterval(REQUEST_PAUSE_MS)
        self._pause.timeout.connect(self.request_pictures)

        self.verticalScrollBar().valueChanged.connect(lambda _value: self._pause.start())
        self.itemClicked.connect(self._go)
        self.itemActivated.connect(self._go)
        view.thumbnail_drawn.connect(self._store)
        view.page_changed.connect(lambda page, _count: self.follow(page - 1))
        view.rotation_changed.connect(lambda _degrees: self.rebuild())

    def rebuild(self) -> None:
        """Start again for the document (or the rotation) the view shows now."""
        self.clear()
        self._drawn.clear()
        for page in range(self.view.page_count):
            item = QListWidgetItem(self._blank_icon(page), str(page + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            item.setSizeHint(CELL)
            item.setToolTip(self.tr("Página {0}").format(page + 1))
            self.addItem(item)
        self.follow(self.view.current_page)
        self._pause.start()

    def drawn_pages(self) -> set[int]:
        """Pages whose picture is ready."""
        return set(self._drawn)

    def visible_pages(self) -> range:
        if not self.count():
            return range(0)
        per_row = max(1, self.viewport().width() // CELL.width())
        top = self.verticalScrollBar().value()
        first = (top // CELL.height()) * per_row
        last = ((top + self.viewport().height()) // CELL.height() + 1) * per_row
        return range(min(first, self.count() - 1), min(last, self.count()))

    def request_pictures(self) -> None:
        """Ask for the pictures in sight, and a few around them."""
        if not self.isVisible() or not self.count():
            return
        visible = self.visible_pages()
        order = list(visible)
        order += range(visible.stop, min(self.count(), visible.stop + PICTURES_AHEAD))
        order += range(max(0, visible.start - PICTURES_BEHIND), visible.start)
        ratio = self.devicePixelRatioF()
        self.view.want_thumbnails(
            [page for page in order if page not in self._drawn],
            round(THUMBNAIL_WIDTH * ratio),
            round(THUMBNAIL_HEIGHT * ratio),
        )

    def follow(self, page: int) -> None:
        """Mark the page being read, without moving the document."""
        if not 0 <= page < self.count() or page == self.currentRow():
            return
        self.blockSignals(True)
        self.setCurrentRow(page)
        self.blockSignals(False)
        self.scrollToItem(self.item(page), QListView.ScrollHint.EnsureVisible)

    def _go(self, item: QListWidgetItem) -> None:
        self.view.scroll_to_page(self.row(item))

    def _store(self, result: RenderedPage) -> None:
        if result.page >= self.count() or result.rotation != self.view.rotation:
            return
        image = QImage(
            result.samples,
            result.width,
            result.height,
            result.stride,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(image)  # copies the pixels
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        self.item(result.page).setIcon(_plain_icon(_framed(pixmap)))
        self._drawn.add(result.page)
        if len(self._drawn) > MAX_PICTURES:
            current = self.view.current_page
            farthest = max(self._drawn, key=lambda page: abs(page - current))
            self._drawn.discard(farthest)
            self.item(farthest).setIcon(self._blank_icon(farthest))

    def _blank_icon(self, page: int) -> QIcon:
        """An empty sheet with the shape of the page, shown until its picture is ready."""
        size = self.view.shown_page_size(page)
        scale = min(THUMBNAIL_WIDTH / size.width, THUMBNAIL_HEIGHT / size.height)
        shape = (max(1, round(size.width * scale)), max(1, round(size.height * scale)))
        if shape not in self._blank:
            ratio = self.devicePixelRatioF()
            pixmap = QPixmap(round(shape[0] * ratio), round(shape[1] * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(QColor("white"))
            self._blank[shape] = _plain_icon(_framed(pixmap))
        return self._blank[shape]

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self._pause.start()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._pause.start()


def _framed(pixmap: QPixmap) -> QPixmap:
    """Draw a thin line around a page, so that white pages stand out on white."""
    painter = QPainter(pixmap)
    ratio = pixmap.devicePixelRatio()
    pen = QPen(QColor(0, 0, 0, 70))
    pen.setWidthF(1)
    painter.setPen(pen)
    painter.drawRect(0, 0, round(pixmap.width() / ratio) - 1, round(pixmap.height() / ratio) - 1)
    painter.end()
    return pixmap


def _plain_icon(pixmap: QPixmap) -> QIcon:
    """An icon that looks the same when its row is selected (Qt would tint it)."""
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected, QIcon.Mode.Active):
        icon.addPixmap(pixmap, mode)
    return icon


class OutlineTree(QTreeWidget):
    """The sections of the document. Click one to go there."""

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.setObjectName("outlineTree")
        self.setAccessibleName(self.tr("Índice del documento"))
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setUniformRowHeights(True)
        self.setIndentation(16)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._items: list[tuple[int, QTreeWidgetItem]] = []  # (page, item), in order
        self.itemClicked.connect(self._go)
        self.itemActivated.connect(self._go)
        view.page_changed.connect(lambda page, _count: self.follow(page - 1))

    def rebuild(self, entries: list[OutlineEntry]) -> None:
        self.clear()
        self._items = []
        parents: list[QTreeWidgetItem] = []  # the open section of every level
        for entry in entries:
            del parents[entry.level - 1 :]
            item = QTreeWidgetItem([entry.title])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.page)
            if entry.page >= 0:
                item.setToolTip(0, self.tr("{0} (página {1})").format(entry.title, entry.page + 1))
                self._items.append((entry.page, item))
            else:
                item.setToolTip(0, entry.title)
            if parents:
                parents[-1].addChild(item)
            else:
                self.addTopLevelItem(item)
            parents.append(item)
        # Show the main sections. A single root (the title of the law) is opened too.
        if self.topLevelItemCount() == 1:
            self.topLevelItem(0).setExpanded(True)
        self.follow(self.view.current_page)

    def follow(self, page: int) -> None:
        """Mark the section the page being read belongs to."""
        current = None
        for start, item in self._items:
            if start > page:
                break
            current = item
        if current is None:
            return
        # Never open sections on our own: mark the nearest one that is in sight.
        parent = current.parent()
        while parent is not None:
            if not parent.isExpanded():
                current = parent
            parent = parent.parent()
        if current is not self.currentItem():
            self.blockSignals(True)
            self.setCurrentItem(current)
            self.blockSignals(False)

    def _go(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page is not None and page >= 0:
            self.view.scroll_to_page(page)


class SidePanel(QWidget):
    """Thumbnails and outline, one at a time, with two buttons to switch."""

    closed = Signal()
    tab_changed = Signal(object)  # Tab

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.view = view

        self.thumbnails = ThumbnailList(view)
        self.outline = OutlineTree(view)
        self.no_outline = QLabel(
            self.tr(
                "Este documento no trae índice.\n\n"
                "Puedes moverte con las miniaturas o escribiendo el número de página."
            )
        )
        self.no_outline.setObjectName("panelEmpty")
        self.no_outline.setWordWrap(True)
        self.no_outline.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.tab_buttons: dict[Tab, QToolButton] = {}
        group = QButtonGroup(self)
        header = QHBoxLayout()
        header.setSpacing(4)
        names = {Tab.THUMBNAILS: self.tr("Miniaturas"), Tab.OUTLINE: self.tr("Índice")}
        for tab, name in names.items():
            button = QToolButton()
            button.setObjectName("panelTab")
            button.setText(name)
            button.setCheckable(True)
            button.setMinimumHeight(36)
            button.clicked.connect(lambda _checked=False, t=tab: self.set_tab(t))
            group.addButton(button)
            header.addWidget(button)
            self.tab_buttons[tab] = button
        header.addStretch(1)
        self.close_button = QToolButton()
        self.close_button.setObjectName("iconButton")
        self.close_button.setIcon(icons.icon("close", icons.MUTED))
        self.close_button.setIconSize(QSize(18, 18))
        self.close_button.setAccessibleName(self.tr("Cerrar"))
        self.close_button.setToolTip(self.tr("Cerrar el panel (F4)"))
        self.close_button.clicked.connect(self.closed)
        header.addWidget(self.close_button)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.thumbnails)
        self.stack.addWidget(self.outline)
        self.stack.addWidget(self.no_outline)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 0)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.stack, 1)

        self._tab = Tab.THUMBNAILS
        view.outline_changed.connect(self._outline_changed)
        self.set_tab(Tab.THUMBNAILS)

    @property
    def tab(self) -> Tab:
        return self._tab

    def set_tab(self, tab: Tab) -> None:
        changed = tab is not self._tab
        self._tab = tab
        self.tab_buttons[tab].setChecked(True)
        if tab is Tab.THUMBNAILS:
            self.stack.setCurrentWidget(self.thumbnails)
        else:
            has_outline = self.outline.topLevelItemCount() > 0
            self.stack.setCurrentWidget(self.outline if has_outline else self.no_outline)
        if changed:
            self.tab_changed.emit(tab)

    def document_changed(self) -> None:
        """The view shows another document: start again."""
        self.thumbnails.rebuild()
        self._outline_changed()

    def _outline_changed(self) -> None:
        self.outline.rebuild(self.view.outline)
        self.set_tab(self._tab)
