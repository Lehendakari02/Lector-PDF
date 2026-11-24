"""The help window (F1): every function, what it does and how to use it.

On the left, a search box ("¿Qué quieres hacer?") and the pages grouped by
mode; on the right, the page: where it is, its key, the steps and a button
"Hazlo ahora" that takes you to the function. Everything is in the program:
it works without internet.

The strip with the tip of the day lives here too.
"""

from collections.abc import Callable
from html import escape

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui import help_topics, icons
from app.ui.help_topics import Topic, translate

_TOPIC_ROLE = Qt.ItemDataRole.UserRole


class HelpWindow(QDialog):
    """The pages of the help, searchable. It does not block the main window."""

    def __init__(
        self,
        parent: QWidget | None,
        key_of: Callable[[Topic], str | None],
        can_run: Callable[[Topic], bool],
        run: Callable[[Topic], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Ayuda de Lector-PDF"))
        self.setObjectName("helpWindow")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setModal(False)
        self.resize(920, 640)
        self._key_of = key_of
        self._can_run = can_run
        self._run = run
        self.current: Topic | None = None

        self.query = QLineEdit()
        self.query.setObjectName("helpQuery")
        self.query.setPlaceholderText(
            self.tr("¿Qué quieres hacer? Por ejemplo: firmar, unir, foto")
        )
        self.query.setAccessibleName(self.tr("Buscar en la ayuda"))
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(40)
        self.query.addAction(
            icons.icon("search", icons.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self.pages = QTreeWidget()
        self.pages.setObjectName("helpPages")
        self.pages.setHeaderHidden(True)
        self.pages.setAccessibleName(self.tr("Páginas de la ayuda"))
        self.pages.setUniformRowHeights(True)

        self.empty = QLabel(
            self.tr("No hay nada con esas palabras. Prueba con otras: «juntar», «escanear»…")
        )
        self.empty.setObjectName("dialogNote")
        self.empty.setWordWrap(True)
        self.empty.hide()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.query)
        left_layout.addWidget(self.pages, 1)
        left_layout.addWidget(self.empty)

        self.page = QTextBrowser()
        self.page.setObjectName("helpPage")
        self.page.setAccessibleName(self.tr("Cómo se usa"))
        self.page.setOpenLinks(False)
        self.page.anchorClicked.connect(lambda url: self.show_topic(url.toString()))

        self.run_button = QPushButton(self.tr("Hazlo ahora"))
        self.run_button.setObjectName("bannerMainButton")
        self.run_button.setToolTip(self.tr("Te lleva a esta función"))
        self.run_button.setMinimumHeight(40)
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self._run_current)
        close_button = QPushButton(self.tr("Cerrar"))
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.close)
        for button in (self.run_button, close_button):
            button.setAutoDefault(False)  # Intro in the search box only reads the page
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.run_button)
        buttons.addWidget(close_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.page, 1)
        right_layout.addLayout(buttons)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 620])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._items: dict[str, QTreeWidgetItem] = {}
        self._sections: list[QTreeWidgetItem] = []
        self._fill()
        self.query.textChanged.connect(self.search)
        self.query.installEventFilter(self)
        self.query.returnPressed.connect(self._enter)
        self.pages.currentItemChanged.connect(self._picked)
        self.pages.itemActivated.connect(lambda _item, _column: self._enter())
        self.show_topic("finder")

    # ---- the list ----

    def _fill(self) -> None:
        for section in help_topics.SECTIONS:
            head = QTreeWidgetItem([translate(section)])
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = head.font(0)
            font.setBold(True)
            head.setFont(0, font)
            self.pages.addTopLevelItem(head)
            self._sections.append(head)
            for item in help_topics.topics_of(section):
                row = QTreeWidgetItem([translate(item.title)])
                row.setData(0, _TOPIC_ROLE, item.id)
                row.setToolTip(0, translate(item.summary))
                head.addChild(row)
                self._items[item.id] = row
        self.pages.expandAll()

    def search(self, text: str) -> None:
        """Leave in the list only the pages that have every word, and show the best."""
        found = help_topics.search_topics(text)
        wanted = {item.id for item in found}
        for head in self._sections:
            shown = 0
            for index in range(head.childCount()):
                row = head.child(index)
                visible = row.data(0, _TOPIC_ROLE) in wanted
                row.setHidden(not visible)
                shown += visible
            head.setHidden(shown == 0)
        self.pages.setVisible(bool(found))
        self.empty.setVisible(not found)
        if found and text.strip():
            self.pages.setCurrentItem(self._items[found[0].id])

    def visible_topics(self) -> list[str]:
        return [topic_id for topic_id, row in self._items.items() if not row.isHidden()]

    def _picked(self, row: QTreeWidgetItem | None, _old=None) -> None:
        if row is None:
            return
        topic_id = row.data(0, _TOPIC_ROLE)
        if topic_id:
            self._show(help_topics.topic(topic_id))

    def _move(self, step: int) -> None:
        rows = [self._items[topic_id] for topic_id in self.visible_topics()]
        if not rows:
            return
        current = self.pages.currentItem()
        index = rows.index(current) if current in rows else -1
        self.pages.setCurrentItem(rows[max(0, min(index + step, len(rows) - 1))])

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        """The arrows move through the pages while typing, as in the finder."""
        if watched is self.query and event.type() == QEvent.Type.KeyPress:
            moves = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1}
            if event.key() in moves:
                self._move(moves[event.key()])
                return True
        return super().eventFilter(watched, event)

    def _enter(self) -> None:
        """Intro on a page: read it (the text is next to the list)."""
        if self.current is not None:
            self.page.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---- the page ----

    def show_topic(self, topic_id: str) -> None:
        item = help_topics.topic(topic_id)
        if item is None:
            return
        row = self._items[topic_id]
        if row.isHidden():
            self.query.clear()
        self.pages.setCurrentItem(row)
        self._show(item)

    def _show(self, item: Topic | None) -> None:
        if item is None:
            return
        self.current = item
        self.page.setHtml(self.page_html(item))
        runnable = bool(item.steps) and (item.feature or item.command) and self._can_run(item)
        self.run_button.setVisible(bool(runnable))

    def page_html(self, item: Topic) -> str:
        parts = [f"<h2>{escape(translate(item.title))}</h2>"]
        where = []
        if item.section in help_topics.SECTIONS[:4]:
            where.append(self.tr("Modo {0}").format(translate(item.section)))
        key = self._key_of(item)
        if key:
            where.append(self.tr("Tecla: {0}").format(key))
        if where:
            parts.append(f"<p><i>{escape(' · '.join(where))}</i></p>")
        summary = translate(item.summary)
        if not summary.endswith((".", "?", "!", "…")):
            summary += "."
        parts.append(f"<p>{escape(summary)}</p>")
        if not item.steps:
            parts.append(
                "<p><b>{}</b></p>".format(
                    escape(self.tr("Todavía no está disponible: llegará en una versión próxima."))
                )
            )
            return "".join(parts)
        parts.append("<h3>{}</h3><ol>".format(escape(self.tr("Cómo se hace"))))
        parts.extend(f"<li>{escape(translate(step))}</li>" for step in item.steps)
        parts.append("</ol>")
        if item.tips:
            parts.append("<h3>{}</h3><ul>".format(escape(self.tr("Bueno saber"))))
            parts.extend(f"<li>{escape(translate(tip))}</li>" for tip in item.tips)
            parts.append("</ul>")
        return "".join(parts)

    def _run_current(self) -> None:
        if self.current is not None:
            item = self.current
            self.close()
            self._run(item)


class TipBanner(QFrame):
    """A strip over the document with one tip ("¿Sabías que…?"). Never in the way:
    it stays until it is closed, and only once a day."""

    show_wanted = Signal(str)  # the page that explains the tip
    never_wanted = Signal()
    another_wanted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tipBanner")
        self.topic_id = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(8)
        self.message = QLabel()
        self.message.setObjectName("bannerMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message, 1)
        self.how_button = QPushButton(self.tr("Ver cómo se hace"))
        self.how_button.setObjectName("bannerMainButton")
        self.how_button.clicked.connect(self._how)
        self.another_button = QPushButton(self.tr("Otro truco"))
        self.another_button.clicked.connect(self.another_wanted)
        self.never_button = QPushButton(self.tr("No enseñar más trucos"))
        self.never_button.setToolTip(
            self.tr("Se vuelven a activar en Ajustes → General → Al abrir el programa")
        )
        self.never_button.clicked.connect(self._never)
        self.close_button = QPushButton(self.tr("Cerrar"))
        self.close_button.clicked.connect(self.hide)
        for button in (self.how_button, self.another_button, self.never_button, self.close_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
        self.hide()

    def offer(self, tip: tuple[str, str]) -> None:
        text, self.topic_id = tip
        self.message.setText(self.tr("¿Sabías que…? {0}").format(translate(text)))
        self.message.setAccessibleName(self.message.text())
        self.show()

    def _how(self) -> None:
        self.hide()
        self.show_wanted.emit(self.topic_id)

    def _never(self) -> None:
        self.hide()
        self.never_wanted.emit()
