"""The search panel: type a word and see every place where it appears."""

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.search import SearchHit, SearchOptions, prepare_query
from app.ui import icons
from app.ui.item_delegates import SearchHitDelegate
from app.ui.pdf_view import PdfView

CONTEXT_BEFORE = 30  # letters shown before the result in the list
TYPING_PAUSE_MS = 250  # wait until the person stops typing before searching


class SearchPanel(QWidget):
    """Search box, options and the list of results of one document view."""

    closed = Signal()

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.view = view
        self.hits: list[SearchHit] = []
        self.current = -1
        self._search_id = 0
        self._searching = False
        self._too_many = False
        self._start_page = 0

        title = QLabel(self.tr("Buscar"))
        title.setObjectName("panelTitle")

        self.box = QLineEdit()
        self.box.setPlaceholderText(self.tr("Buscar en el documento"))
        self.box.setAccessibleName(self.tr("Texto que buscar"))
        self.box.setClearButtonEnabled(True)
        self.box.setMinimumHeight(40)
        self.box.addAction(
            icons.icon("search", icons.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )
        self.box.setToolTip(
            self.tr("No hace falta poner tildes ni mayúsculas. Intro: siguiente resultado.")
        )

        self.whole_word = QCheckBox(self.tr("Palabra completa"))
        self.whole_word.setToolTip(self.tr("«ley» no encuentra «leyes»"))
        self.exact = QCheckBox(self.tr("Coincidencia exacta"))
        self.exact.setToolTip(self.tr("Tiene en cuenta las tildes y las mayúsculas"))

        self.previous_button = self._icon_button(
            "previous", self.tr("Anterior"), self.tr("Resultado anterior (Mayús+Intro)")
        )
        self.next_button = self._icon_button(
            "next", self.tr("Siguiente"), self.tr("Resultado siguiente (Intro)")
        )
        self.close_button = self._icon_button(
            "close", self.tr("Cerrar"), self.tr("Cerrar la búsqueda (Esc)")
        )

        self.status = QLabel()
        self.status.setObjectName("searchStatus")
        self.status.setWordWrap(True)
        self.results = QListWidget()
        self.results.setAccessibleName(self.tr("Resultados de la búsqueda"))
        self.results.setUniformItemSizes(True)
        self.results.setMouseTracking(True)
        self.results.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        delegate = SearchHitDelegate(self._hit_of_row, CONTEXT_BEFORE, self.results)
        delegate.page_label = self.tr("Pág. {0}")
        self.results.setItemDelegate(delegate)

        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.close_button)
        navigation = QHBoxLayout()
        navigation.addWidget(self.status, 1)
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.next_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 8)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.box)
        layout.addWidget(self.whole_word)
        layout.addWidget(self.exact)
        layout.addLayout(navigation)
        layout.addWidget(self.results, 1)

        self._pause = QTimer(self)
        self._pause.setSingleShot(True)
        self._pause.setInterval(TYPING_PAUSE_MS)
        self._pause.timeout.connect(self.search_now)

        self.box.textChanged.connect(lambda _text: self._pause.start())
        self.box.returnPressed.connect(self._enter_pressed)
        self.whole_word.toggled.connect(lambda _on: self.search_now())
        self.exact.toggled.connect(lambda _on: self.search_now())
        self.next_button.clicked.connect(self.go_next)
        self.previous_button.clicked.connect(self.go_previous)
        self.close_button.clicked.connect(self.close_search)
        self.results.currentRowChanged.connect(self._row_chosen)
        for keys, action in (
            (Qt.Key.Key_Escape, self.close_search),
            (Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_Return, self.go_previous),
            (Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_Enter, self.go_previous),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)

        view.search_hits.connect(self._hits_arrived)
        view.search_finished.connect(self._finished)
        self._update_status()

    def _icon_button(self, icon_name: str, name: str, tip: str) -> QToolButton:
        """A small button with only a drawing; its name is kept for screen readers."""
        button = QToolButton()
        button.setObjectName("iconButton")
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(20, 20))
        button.setMinimumSize(36, 36)
        button.setAccessibleName(name)
        button.setToolTip(tip)
        return button

    def _hit_of_row(self, row: int) -> SearchHit | None:
        return self.hits[row] if 0 <= row < len(self.hits) else None

    # ---- actions --------------------------------------------------------

    def start(self) -> None:
        """Called when the panel is opened: ready to type."""
        self.box.setFocus()
        self.box.selectAll()

    def options(self) -> SearchOptions:
        return SearchOptions(whole_word=self.whole_word.isChecked(), exact=self.exact.isChecked())

    def search_now(self) -> None:
        """Search what is in the box, without waiting for the typing pause."""
        self._pause.stop()
        self.hits = []
        self.current = -1
        self._too_many = False
        self.results.clear()
        self.view.set_search_marks([])
        self._start_page = max(self.view.current_page, 0)
        if prepare_query(self.box.text(), self.options()) and self.view.page_count:
            self._searching = True
            self._search_id = self.view.service.search(self.box.text(), self.options())
        else:
            self._searching = False
            self.view.service.cancel_search()
        self._update_status()

    def close_search(self) -> None:
        self._pause.stop()
        self.view.service.cancel_search()
        self._searching = False
        self.view.set_search_marks([])
        self.closed.emit()

    def document_changed(self) -> None:
        """Another document was opened: the old results mean nothing now."""
        if self.box.text():
            self.search_now()

    def go_next(self) -> None:
        self._go(1)

    def go_previous(self) -> None:
        self._go(-1)

    def _go(self, step: int) -> None:
        if self.hits:
            self._select((self.current + step) % len(self.hits))

    def _enter_pressed(self) -> None:
        if self._pause.isActive():
            self.search_now()  # Enter right after typing: search at once
        else:
            self.go_next()

    # ---- results --------------------------------------------------------

    def _hits_arrived(self, search_id: int, hits: list[SearchHit]) -> None:
        if search_id != self._search_id or not self._searching:
            return
        first_new = len(self.hits)
        self.hits.extend(hits)
        self.results.addItems([self._describe(hit) for hit in hits])
        self.view.add_search_marks(hits)
        if self.current == -1 and hits[0].page >= self._start_page:
            # Begin with the first result from the page being read onwards.
            self._select(first_new)
        self._update_status()

    def _finished(self, search_id: int, too_many: bool) -> None:
        if search_id != self._search_id:
            return
        self._searching = False
        self._too_many = too_many
        if self.current == -1 and self.hits:
            self._select(0)
        self._update_status()

    def _describe(self, hit: SearchHit) -> str:
        before = hit.before
        if len(before) > CONTEXT_BEFORE:
            # Shorten at a space, so the line does not begin in the middle of a word.
            before = before[-CONTEXT_BEFORE:].partition(" ")[2]
        return self.tr("Pág. {0}:  {1}[{2}]{3}").format(hit.page + 1, before, hit.match, hit.after)

    def _row_chosen(self, row: int) -> None:
        if 0 <= row < len(self.hits) and row != self.current:
            self._select(row)

    def _select(self, index: int) -> None:
        self.current = index
        self.results.setCurrentRow(index)
        self.view.show_search_hit(self.hits[index])
        self._update_status()

    def _update_status(self) -> None:
        has_hits = bool(self.hits)
        self.next_button.setEnabled(has_hits)
        self.previous_button.setEnabled(has_hits)
        if not prepare_query(self.box.text(), self.options()):
            text = ""
        elif not has_hits:
            text = self.tr("Buscando…") if self._searching else self.tr("Sin resultados")
        else:
            text = self.tr("Resultado {0} de {1}").format(max(self.current, 0) + 1, len(self.hits))
            if self._searching:
                text += self.tr(" (buscando…)")
            elif self._too_many:
                text += self.tr(". Hay más: se muestran solo los primeros.")
        self.status.setText(text)
