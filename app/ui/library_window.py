"""The window of the syllabus library: every topic of a folder, how far each
one is studied, and a search in all of them at once."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.library import FOLDER_SETTING, LibraryHit, LibraryWork, TopicInfo, topics_in
from app.core.search import SearchOptions
from app.ui.when import when_text

POLL_MS = 60
PATH_ROLE = Qt.ItemDataRole.UserRole
HIT_ROLE = Qt.ItemDataRole.UserRole + 1


def _ask_folder(parent, start: str) -> str:
    return QFileDialog.getExistingDirectory(
        parent, parent.tr("Elige la carpeta de tu temario"), start
    )


class LibraryWindow(QDialog):
    """Opened from "Biblioteca del temario"; it stays open beside the documents."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.settings = window.settings
        self.history = window.history
        self.ask_folder = _ask_folder  # the tests answer without the dialog
        self.setWindowTitle(self.tr("Biblioteca del temario"))
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(760, 560)
        self.topics: list[Path] = []
        self.infos: dict[Path, TopicInfo] = {}
        self.hits: list[LibraryHit] = []
        self._work: LibraryWork | None = None
        self._searching = False
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        top = QHBoxLayout()
        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        top.addWidget(self.folder_label, 1)
        self.folder_button = QPushButton(self.tr("Elegir carpeta…"))
        self.folder_button.clicked.connect(self.choose_folder)
        top.addWidget(self.folder_button)
        layout.addLayout(top)

        row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("Buscar en todos los temas…"))
        self.search_box.setAccessibleName(self.tr("Buscar en todos los temas"))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.returnPressed.connect(self.search)
        row.addWidget(self.search_box, 1)
        self.search_button = QPushButton(self.tr("Buscar"))
        self.search_button.clicked.connect(self.search)
        row.addWidget(self.search_button)
        self.stop_button = QPushButton(self.tr("Parar"))
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.hide()
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        self.whole_word = QCheckBox(self.tr("Palabra completa"))
        self.whole_word.setToolTip(self.tr("«artículo 14» no encuentra «artículo 140»"))
        layout.addWidget(self.whole_word)

        self.stack = QStackedWidget()
        self.topic_list = QTreeWidget()
        self.topic_list.setRootIsDecorated(False)
        self.topic_list.setAlternatingRowColors(True)
        self.topic_list.setHeaderLabels(
            [self.tr("Tema"), self.tr("Leído"), self.tr("Subrayados"), self.tr("Repasado")]
        )
        self.topic_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.topic_list.header().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.topic_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.topic_list.itemActivated.connect(self._topic_chosen)
        self.topic_list.setAccessibleName(self.tr("Temas"))
        self.stack.addWidget(self.topic_list)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = QPushButton(self.tr("← Volver a los temas"))
        self.back_button.clicked.connect(self.show_topics)
        results_layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.hit_list = QListWidget()
        self.hit_list.setWordWrap(True)
        self.hit_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hit_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.hit_list.setAccessibleName(self.tr("Resultados en todos los temas"))
        self.hit_list.itemActivated.connect(self._hit_chosen)
        results_layout.addWidget(self.hit_list, 1)
        self.stack.addWidget(results)
        layout.addWidget(self.stack, 1)

        self.status = QLabel()
        self.status.setObjectName("libraryStatus")
        layout.addWidget(self.status)
        # Intro in the search box searches: no button of the window is pressed by it.
        for button in (self.folder_button, self.search_button, self.stop_button, self.back_button):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.load(self.settings.get(FOLDER_SETTING) or "")

    # ---- the topics ----------------------------------------------------------

    @property
    def folder(self) -> str:
        return str(self.settings.get(FOLDER_SETTING) or "")

    def choose_folder(self) -> bool:
        chosen = self.ask_folder(self, self.folder)
        if not chosen:
            return False
        self.settings.set(FOLDER_SETTING, str(chosen))
        self.load(chosen)
        return True

    def load(self, folder: str | Path) -> None:
        """Show the topics of the folder and start looking at each one."""
        self.stop()
        self.topics = topics_in(folder) if folder else []
        self.infos = {}
        if not folder:
            self.folder_label.setText(
                self.tr("Elige la carpeta donde tienes los temas (en PDF) para verlos aquí.")
            )
        else:
            self.folder_label.setText(self.tr("Carpeta: {0}").format(folder))
        self.show_topics()
        self._fill_topics()
        if self.topics:
            self._start(LibraryWork(self.topics), searching=False)
            self.status.setText(self.tr("Mirando los temas…"))
        elif folder:
            self.status.setText(self.tr("No hay ningún PDF en esta carpeta."))
        else:
            self.status.setText("")

    def _name(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.folder))
        except ValueError:
            return path.name

    def _fill_topics(self) -> None:
        self.topic_list.clear()
        for path in self.topics:
            item = QTreeWidgetItem([self._name(path), "", "", ""])
            item.setData(0, PATH_ROLE, str(path))
            item.setToolTip(0, str(path))
            self.topic_list.addTopLevelItem(item)
            self._show_progress(item, path)

    def _show_progress(self, item: QTreeWidgetItem, path: Path) -> None:
        info = self.infos.get(path)
        place = self.history.place_of(path)
        if info is not None and info.problem == "password":
            item.setText(1, self.tr("Con contraseña"))
        elif info is not None and info.problem:
            item.setText(1, self.tr("No se puede abrir"))
        elif info is not None and info.pages:
            read = min(info.pages, place.farthest + 1) if (place.farthest or place.page) else 0
            item.setText(1, self.tr("{0} %").format(round(100 * read / info.pages)))
            item.setToolTip(
                1, self.tr("Has llegado a la página {0} de {1}").format(read, info.pages)
            )
        else:
            item.setText(1, "…")
        item.setText(2, str(info.marks) if info is not None and not info.problem else "")
        item.setText(3, when_text(place.reviewed) if place.reviewed else self.tr("Todavía no"))

    def refresh_progress(self) -> None:
        """Show again how far each topic is studied (after reading or reviewing)."""
        for index in range(self.topic_list.topLevelItemCount()):
            item = self.topic_list.topLevelItem(index)
            self._show_progress(item, Path(item.data(0, PATH_ROLE)))

    def show_topics(self) -> None:
        self.stack.setCurrentIndex(0)

    def _topic_chosen(self, item: QTreeWidgetItem) -> None:
        self.window_.open_document(item.data(0, PATH_ROLE))

    # ---- searching in every topic ---------------------------------------------

    def search(self) -> bool:
        query = self.search_box.text().strip()
        if not query or not self.topics:
            return False
        self.stop()
        self.hits = []
        self.hit_list.clear()
        self.stack.setCurrentIndex(1)
        self._query = query
        options = SearchOptions(whole_word=self.whole_word.isChecked())
        self._start(LibraryWork(self.topics, query, options), searching=True)
        self.status.setText(self.tr("Buscando en {0} temas…").format(len(self.topics)))
        return True

    def _hit_chosen(self, item: QListWidgetItem) -> None:
        hit: LibraryHit = item.data(HIT_ROLE)
        self.window_.open_from_library(hit.path, hit.page, self._query)

    def _add_hit(self, hit: LibraryHit) -> None:
        self.hits.append(hit)
        text = self.tr("{0} · pág. {1}").format(self._name(hit.path), hit.page + 1)
        item = QListWidgetItem(f"{text}\n…{hit.before}{hit.match}{hit.after}…")
        item.setData(HIT_ROLE, hit)
        self.hit_list.addItem(item)

    # ---- the work in the background -------------------------------------------

    def _start(self, work: LibraryWork, searching: bool) -> None:
        self._work = work
        self._searching = searching
        self._done = 0
        self.stop_button.setVisible(searching)
        self._timer.start()

    def _poll(self) -> None:
        work = self._work
        if work is None:
            self._timer.stop()
            return
        for message in work.messages():
            kind = message[0]
            if kind == "info":
                info: TopicInfo = message[1]
                self.infos[info.path] = info
                self._refresh_topic(info.path)
            elif kind == "hit":
                self._add_hit(message[1])
            elif kind == "done_one":
                self._done = message[1] + 1
                if self._searching:
                    self.status.setText(
                        self.tr("Buscando… {0} de {1} temas, {2} resultados").format(
                            self._done, len(self.topics), len(self.hits)
                        )
                    )
        if work.finished:
            self._finish()

    def _refresh_topic(self, path: Path) -> None:
        for index in range(self.topic_list.topLevelItemCount()):
            item = self.topic_list.topLevelItem(index)
            if Path(item.data(0, PATH_ROLE)) == path:
                self._show_progress(item, path)
                return

    def _finish(self) -> None:
        self._timer.stop()
        if self._work is not None:
            self._work.stop()
        self._work = None
        self.stop_button.hide()
        if self._searching:
            topics = len({hit.path for hit in self.hits})
            if self.hits:
                self.status.setText(
                    self.tr("{0} resultados en {1} temas.").format(len(self.hits), topics)
                )
            else:
                self.status.setText(self.tr("No se ha encontrado en ningún tema."))
        else:
            self.status.setText(self.tr("{0} temas.").format(len(self.topics)))

    @property
    def busy(self) -> bool:
        return self._work is not None

    def stop(self) -> None:
        if self._work is not None:
            self._work.stop()
            self._work = None
            self._timer.stop()
            self.stop_button.hide()
            self.status.setText(self.tr("Parado."))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_progress()

    def done(self, result: int) -> None:
        self.stop()
        super().done(result)
