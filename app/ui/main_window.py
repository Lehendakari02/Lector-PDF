"""Main window: the work modes, their tools and the function finder."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, qVersion
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, BUILD_LABEL, __version__
from app.core.document import PdfDocument, PdfOpenError, engine_version
from app.core.error_log import running_from_source_or_test_build
from app.core.paths import data_dir, is_portable
from app.core.settings import Settings
from app.ui.command_palette import CommandPalette
from app.ui.error_reporting import ErrorReporter, ProvokedError
from app.ui.features import FEATURES, MODES, Feature, Mode, features_of, translate
from app.ui.pdf_view import PdfView
from app.ui.search_panel import SearchPanel
from app.ui.theme import THEME_SETTING, Theme, apply_theme

# Big enough to press comfortably with a finger on a touch screen.
MIN_BUTTON_HEIGHT = 40
STATUS_MESSAGE_MS = 6000
LAST_FOLDER_SETTING = "ultima_carpeta"


class MainWindow(QMainWindow):
    """Top-level window of the program."""

    def __init__(
        self, settings: Settings | None = None, reporter: ErrorReporter | None = None
    ) -> None:
        super().__init__()
        self.settings = settings if settings is not None else Settings()
        self.reporter = reporter if reporter is not None else ErrorReporter(parent=self)
        # Tests turn this off so that message boxes do not block them.
        self.show_problem_dialogs = True
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 750)

        self.feature_actions: dict[str, QAction] = {}
        self.mode_toolbars: dict[Mode, QToolBar] = {}
        self.theme_actions: dict[Theme, QAction] = {}

        self._build_feature_actions()
        self._build_mode_bar()
        self._build_tool_bars()
        self._build_menus()
        self.welcome = self._build_welcome()
        self.pdf_view = PdfView()
        self.pages = QStackedWidget()
        self.pages.addWidget(self.welcome)
        self.pages.addWidget(self.pdf_view)
        self.setCentralWidget(self.pages)

        self.search_panel = SearchPanel(self.pdf_view)
        self.search_dock = QDockWidget(self.tr("Buscar"), self)
        self.search_dock.setObjectName("searchDock")
        self.search_dock.setWidget(self.search_panel)
        self.search_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.search_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.search_dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.search_dock)
        self.search_dock.hide()
        self.search_panel.closed.connect(self.close_search)
        self.search_action = QAction(self.tr("Buscar en el documento"), self)
        self.search_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Find))
        self.search_action.triggered.connect(self.show_search)
        self.addAction(self.search_action)

        self.statusBar().setSizeGripEnabled(True)
        self.position_label = QLabel()
        self.position_label.setObjectName("positionLabel")
        self.speed_label = QLabel()
        self.speed_label.setObjectName("speedLabel")
        self.speed_label.setVisible(running_from_source_or_test_build())
        self.statusBar().addPermanentWidget(self.speed_label)
        self.statusBar().addPermanentWidget(self.position_label)
        self._slowest_page = 0.0

        self.pdf_view.page_changed.connect(self._update_position)
        self.pdf_view.zoom_changed.connect(lambda _zoom: self._update_position())
        self.pdf_view.page_drawn.connect(self._update_speed)
        self.pdf_view.document_failed.connect(self._document_failed)

        # Functions that already work. Every other one says it is not built yet.
        self.feature_handlers = {
            "open": self.choose_and_open,
            "search": self.show_search,
            "zoom_in": self.pdf_view.zoom_in,
            "zoom_out": self.pdf_view.zoom_out,
            "fit_width": self.pdf_view.fit_width,
        }

        self.set_theme(Theme.from_setting(self.settings.get(THEME_SETTING)), remember=False)
        # Follow Windows when it switches between light and dark.
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.set_mode(Mode.READ)

    # ---- construction -------------------------------------------------

    def _build_feature_actions(self) -> None:
        for feature in FEATURES:
            action = QAction(translate(feature.name), self)
            action.setObjectName(f"feature_{feature.id}")
            action.setToolTip(translate(feature.description))
            action.setStatusTip(translate(feature.description))
            action.triggered.connect(lambda _checked=False, f=feature: self.run_feature(f))
            self.feature_actions[feature.id] = action

    def _build_mode_bar(self) -> None:
        self.mode_tabs = QTabBar()
        self.mode_tabs.setObjectName("modeTabs")
        self.mode_tabs.setAccessibleName(self.tr("Modos de trabajo"))
        self.mode_tabs.setExpanding(False)
        self.mode_tabs.setDrawBase(False)
        self.mode_tabs.setMinimumHeight(MIN_BUTTON_HEIGHT)
        tab_font = self.mode_tabs.font()
        tab_font.setPointSize(tab_font.pointSize() + 2)
        self.mode_tabs.setFont(tab_font)
        for number, mode in enumerate(MODES, start=1):
            index = self.mode_tabs.addTab(translate(mode.value))
            self.mode_tabs.setTabToolTip(
                index, self.tr("Modo {0} (Ctrl+{1})").format(translate(mode.value), number)
            )
        self.mode_tabs.currentChanged.connect(lambda index: self.set_mode(MODES[index]))

        self.finder_button = QPushButton(self.tr("Buscar función  (Ctrl+K)"))
        self.finder_button.setObjectName("finderButton")
        self.finder_button.setToolTip(
            self.tr("Escribe lo que quieres hacer y te lleva a la función, esté donde esté")
        )
        self.finder_button.setMinimumHeight(MIN_BUTTON_HEIGHT)
        self.finder_button.clicked.connect(self.open_command_palette)

        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 0)
        layout.addWidget(self.mode_tabs)
        layout.addStretch()
        layout.addWidget(self.finder_button)

        holder = QToolBar(self.tr("Modos"))
        holder.setObjectName("modeBar")
        holder.setMovable(False)
        holder.setFloatable(False)
        holder.toggleViewAction().setEnabled(False)
        holder.addWidget(bar)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, holder)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

    def _build_tool_bars(self) -> None:
        for mode in MODES:
            toolbar = QToolBar(self.tr("Herramientas de {0}").format(translate(mode.value)))
            toolbar.setObjectName(f"tools_{mode.name.lower()}")
            toolbar.setMovable(False)
            toolbar.setFloatable(False)
            toolbar.toggleViewAction().setEnabled(False)
            toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            toolbar.setIconSize(QSize(24, 24))
            for feature in features_of(mode):
                action = self.feature_actions[feature.id]
                toolbar.addAction(action)
                toolbar.widgetForAction(action).setMinimumHeight(MIN_BUTTON_HEIGHT)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
            self.mode_toolbars[mode] = toolbar

    def _build_menus(self) -> None:
        view_menu = self.menuBar().addMenu(self.tr("&Ver"))
        self.mode_actions: dict[Mode, QAction] = {}
        mode_group = QActionGroup(self)
        for number, mode in enumerate(MODES, start=1):
            action = QAction(self.tr("Modo {0}").format(translate(mode.value)), self)
            action.setCheckable(True)
            action.setShortcut(QKeySequence(f"Ctrl+{number}"))
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_mode(m))
            mode_group.addAction(action)
            view_menu.addAction(action)
            self.mode_actions[mode] = action

        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(self.tr("&Aspecto"))
        theme_group = QActionGroup(self)
        names = {
            Theme.SYSTEM: self.tr("Como el sistema"),
            Theme.LIGHT: self.tr("Claro"),
            Theme.DARK: self.tr("Oscuro"),
        }
        for theme, name in names.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, t=theme: self.set_theme(t))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[theme] = action

        help_menu = self.menuBar().addMenu(self.tr("A&yuda"))
        self.finder_action = QAction(self.tr("Buscar una función…"), self)
        self.finder_action.setShortcut(QKeySequence("Ctrl+K"))
        self.finder_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.finder_action.triggered.connect(self.open_command_palette)
        help_menu.addAction(self.finder_action)

        help_menu.addSeparator()
        self.copy_report_action = QAction(self.tr("Copiar informe de error"), self)
        self.copy_report_action.setStatusTip(
            self.tr("Copia los últimos errores para que puedas pegarlos donde quieras")
        )
        self.copy_report_action.triggered.connect(self.copy_error_report)
        help_menu.addAction(self.copy_report_action)

        self.test_error_action = QAction(self.tr("Provocar un error de prueba"), self)
        self.test_error_action.setStatusTip(
            self.tr("Solo en versiones de prueba: comprueba que los errores se registran")
        )
        self.test_error_action.triggered.connect(self.raise_test_error)
        self.test_error_action.setVisible(running_from_source_or_test_build())
        help_menu.addAction(self.test_error_action)

    def _build_welcome(self) -> QWidget:
        title = QLabel(f"{APP_NAME} {__version__}")
        title.setObjectName("placeholderTitle")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 10)
        title_font.setBold(True)
        title.setFont(title_font)

        message = QLabel(self.tr("En construcción. Todavía no se pueden abrir documentos."))
        message.setObjectName("placeholderMessage")

        # Shown on purpose: when testing a build it proves the PDF engine and Qt
        # were packaged correctly.
        versions = QLabel(
            self.tr("Motor PDF (PyMuPDF) {0} · Qt {1}").format(engine_version(), qVersion())
        )
        versions.setObjectName("placeholderVersions")

        build = QLabel(BUILD_LABEL)
        build.setObjectName("placeholderBuild")
        build.setVisible(bool(BUILD_LABEL))

        if is_portable():
            data_text = self.tr("Versión portátil. Los datos se guardan junto al programa: {0}")
        else:
            data_text = self.tr("Carpeta de datos del programa: {0}")
        data = QLabel(data_text.format(data_dir()))
        data.setObjectName("placeholderData")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addStretch()
        for label in (title, build, message, versions, data):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addStretch()
        return central

    # ---- behaviour ----------------------------------------------------

    @property
    def mode(self) -> Mode:
        return self._mode

    def set_mode(self, mode: Mode) -> None:
        """Show the tools of ``mode`` and hide those of the other modes."""
        self._mode = mode
        for other, toolbar in self.mode_toolbars.items():
            toolbar.setVisible(other is mode)
        self.mode_actions[mode].setChecked(True)
        index = MODES.index(mode)
        if self.mode_tabs.currentIndex() != index:
            self.mode_tabs.blockSignals(True)
            self.mode_tabs.setCurrentIndex(index)
            self.mode_tabs.blockSignals(False)

    @property
    def theme(self) -> Theme:
        return self._theme

    def set_theme(self, theme: Theme, remember: bool = True) -> None:
        """Change the colours. ``remember`` saves the choice for next time."""
        self._theme = theme
        apply_theme(theme)
        self.theme_actions[theme].setChecked(True)
        if remember:
            self.settings.set(THEME_SETTING, theme.value)

    def _system_theme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._theme is Theme.SYSTEM:
            apply_theme(Theme.SYSTEM)

    def open_command_palette(self) -> None:
        palette = CommandPalette(self)
        if palette.exec() and palette.chosen is not None:
            self.go_to_feature(palette.chosen)

    def go_to_feature(self, feature: Feature) -> None:
        """Switch to the mode of ``feature``, point at its button and run it."""
        self.set_mode(feature.mode)
        button = self.mode_toolbars[feature.mode].widgetForAction(self.feature_actions[feature.id])
        if button is not None:
            button.setFocus(Qt.FocusReason.OtherFocusReason)
        self.run_feature(feature)

    def run_feature(self, feature: Feature) -> None:
        handler = self.feature_handlers.get(feature.id)
        if handler is not None:
            handler()
            return
        self.statusBar().showMessage(
            self.tr("«{0}» todavía no está disponible. {1}.").format(
                translate(feature.name), translate(feature.description)
            ),
            STATUS_MESSAGE_MS,
        )

    def copy_error_report(self) -> None:
        self.reporter.copy_report()
        self.statusBar().showMessage(
            self.tr("Informe de error copiado. Pégalo donde quieras con Ctrl+V."),
            STATUS_MESSAGE_MS,
        )

    def raise_test_error(self) -> None:
        raise ProvokedError("Error de prueba provocado desde el menú Ayuda")

    # ---- documents ----------------------------------------------------

    def choose_and_open(self) -> None:
        start = str(self.settings.get(LAST_FOLDER_SETTING, ""))
        path, _filter = QFileDialog.getOpenFileName(
            self, self.tr("Abrir un PDF"), start, self.tr("Documentos PDF (*.pdf)")
        )
        if path:
            self.settings.set(LAST_FOLDER_SETTING, str(Path(path).parent))
            self.open_document(path)

    def open_document(self, path: str | Path) -> bool:
        """Show the PDF at ``path``. Problems give a message, never a crash."""
        try:
            document = PdfDocument(path)
            if document.needs_password:
                document.close()
                self._show_problem(
                    self.tr("Este PDF tiene contraseña"),
                    self.tr("Todavía no se pueden abrir documentos con contraseña."),
                )
                return False
            self._slowest_page = 0.0
            self.pdf_view.set_document(document)
        except PdfOpenError:
            self._show_problem(
                self.tr("No se puede abrir el documento"),
                self.tr("El archivo «{0}» no existe, está dañado o no es un PDF.").format(
                    Path(path).name
                ),
            )
            return False
        self.pages.setCurrentWidget(self.pdf_view)
        self.pdf_view.setFocus()
        self.search_panel.document_changed()
        self.setWindowTitle(f"{Path(path).name} – {APP_NAME}")
        self._update_position()
        return True

    def show_search(self) -> None:
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(
                self.tr("Abre un documento para poder buscar en él."), STATUS_MESSAGE_MS
            )
            return
        self.search_dock.show()
        self.search_panel.start()

    def close_search(self) -> None:
        self.search_dock.hide()
        self.pdf_view.setFocus()

    def _document_failed(self, _message: str) -> None:
        self._show_problem(
            self.tr("No se puede mostrar el documento"),
            self.tr("El archivo está dañado o no es un PDF."),
        )

    def _show_problem(self, title: str, text: str) -> None:
        self.statusBar().showMessage(f"{title}. {text}", STATUS_MESSAGE_MS)
        if self.show_problem_dialogs:
            QMessageBox.warning(self, title, text)

    def _update_position(self, *_args: object) -> None:
        if self.pdf_view.page_count == 0:
            self.position_label.setText("")
            return
        self.position_label.setText(
            self.tr("Página {0} de {1} · {2} %").format(
                self.pdf_view.current_page + 1,
                self.pdf_view.page_count,
                round(self.pdf_view.zoom * 100),
            )
        )

    def _update_speed(self, _page: int, seconds: float) -> None:
        self._slowest_page = max(self._slowest_page, seconds)
        self.speed_label.setText(
            self.tr("Dibujo de página: {0} ms (la más lenta: {1} ms)").format(
                round(seconds * 1000), round(self._slowest_page * 1000)
            )
        )

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.pdf_view.shutdown()
        super().closeEvent(event)
