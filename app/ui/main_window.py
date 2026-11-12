"""Main window: the work modes, their tools and the function finder."""

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, qVersion
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, BUILD_LABEL, __version__
from app.core.document import PdfDocument, PdfOpenError, engine_version
from app.core.error_log import running_from_source_or_test_build
from app.core.history import History, file_key
from app.core.interface_size import NORMAL_SIZE
from app.core.ocr import OcrError, OcrJob, OcrPage
from app.core.paths import data_dir, is_portable
from app.core.settings import Settings
from app.core.signing import PasswordProtected, SigningError, sign_pdf
from app.core.windows_store import SigningCancelled
from app.ui import icons
from app.ui import theme as theme_module
from app.ui.command_palette import CommandPalette
from app.ui.document_page import DocumentPage
from app.ui.error_reporting import ErrorReporter, ProvokedError
from app.ui.features import (
    FEATURES,
    GROUP_STARTS,
    MODES,
    Feature,
    Mode,
    features_of,
    translate,
)
from app.ui.ocr_dialog import OcrResultDialog
from app.ui.page_box import PageBox
from app.ui.pdf_view import PdfView
from app.ui.search_panel import SearchPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.side_panel import SidePanel, Tab
from app.ui.sign_dialog import CertificateDialog
from app.ui.theme import PAPER_SETTING, THEME_SETTING, Paper, Theme, apply_theme
from app.ui.zoom_control import ZoomControl

# Big enough to press comfortably with a finger on a touch screen.
MIN_BUTTON_HEIGHT = 40
STATUS_MESSAGE_MS = 6000
LAST_FOLDER_SETTING = "ultima_carpeta"
WELCOME_RECENT = 5  # recent documents offered on the welcome page
SIDE_PANEL_SETTING = "panel_lateral"  # "", "miniaturas" or "indice"


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
        self.history = History(self.settings)
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 800)
        self.setAcceptDrops(True)  # a PDF dropped on the window is opened

        self._full_screen = False
        self._was_maximized = False
        self._docks_before: list[QWidget] = []
        self.feature_actions: dict[str, QAction] = {}
        self.mode_toolbars: dict[Mode, QToolBar] = {}
        self.theme_actions: dict[Theme, QAction] = {}
        self.paper_actions: dict[Paper, QAction] = {}
        # The size of the interface this copy of the program started with.
        self.interface_size = NORMAL_SIZE
        # Set when the program must start again after this window closes.
        self.restart_wanted = False

        self._build_feature_actions()
        self._build_mode_bar()
        self._build_tool_bars()
        self._build_menus()
        self.welcome = self._build_welcome()
        # Every open document is a page of this stack, with a tab above it.
        self.documents: list[DocumentPage] = []
        self.document_tabs = DocumentTabBar()
        self.document_tabs.setObjectName("documentTabs")
        self.document_tabs.setAccessibleName(self.tr("Documentos abiertos"))
        self.document_tabs.setMovable(True)
        self.document_tabs.setExpanding(False)
        self.document_tabs.setDrawBase(False)
        self.document_tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.document_tabs.setUsesScrollButtons(True)
        self.document_tabs.hide()
        self.pages = QStackedWidget()
        self.pages.addWidget(self.welcome)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.document_tabs)
        central_layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        # A page kept ready for the next document that is opened. While nothing
        # is open it also stands in as "the current document" (an empty one).
        self._spare = self._new_page()
        self._warm_spares = False
        self.document_tabs.currentChanged.connect(self._tab_changed)
        self.document_tabs.tabCloseRequested.connect(self.close_document)
        self.document_tabs.tabMoved.connect(self._tab_moved)

        self.search_action = QAction(self.tr("Buscar en el documento"), self)
        self.search_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Find))
        self.search_action.triggered.connect(self.show_search)
        self.addAction(self.search_action)

        self.statusBar().setSizeGripEnabled(True)
        self.page_box = PageBox(self.pdf_view)
        self.page_box.go_to.connect(lambda: self.pdf_view.setFocus())
        self.speed_label = QLabel()
        self.speed_label.setObjectName("speedLabel")
        self.speed_label.setVisible(running_from_source_or_test_build())
        self.statusBar().addPermanentWidget(self.speed_label)
        self.statusBar().addPermanentWidget(self.page_box)
        self.zoom_control = ZoomControl(self.pdf_view)
        self.statusBar().addPermanentWidget(self.zoom_control)

        self._ocr_job: OcrJob | None = None
        self.last_ocr: OcrPage | None = None
        self._ocr_timer = QTimer(self)
        self._ocr_timer.setInterval(100)
        self._ocr_timer.timeout.connect(self._check_ocr)

        # Functions that already work. Every other one says it is not built yet.
        self.feature_handlers = {
            "open": self.choose_and_open,
            "search": self.show_search,
            "sign_certificate": self.sign_with_certificate,
            "ocr": self.recognize_current_page,
            "zoom_in": lambda: self.pdf_view.zoom_in(),
            "zoom_out": lambda: self.pdf_view.zoom_out(),
            "fit_width": lambda: self.pdf_view.fit_width(),
            "fit_page": lambda: self.pdf_view.fit_page(),
            "rotate_view": lambda: self.pdf_view.rotate_view(),
            "fullscreen": self.toggle_full_screen,
            "go_to_page": self.go_to_page,
            "copy": lambda: self.pdf_view.copy_selection(),
            "thumbnails": lambda: self.toggle_side_panel(Tab.THUMBNAILS),
            "outline": lambda: self.toggle_side_panel(Tab.OUTLINE),
            "reading_mode": self.toggle_reading_mode,
        }
        self._mark_pending_features()

        self.set_theme(Theme.from_setting(self.settings.get(THEME_SETTING)), remember=False)
        self.set_paper(Paper.from_setting(self.settings.get(PAPER_SETTING)), remember=False)
        # Follow Windows when it switches between light and dark.
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.set_mode(Mode.READ)
        self._refresh_welcome_recent()

    # ---- construction -------------------------------------------------

    def _build_feature_actions(self) -> None:
        for feature in FEATURES:
            action = QAction(translate(feature.name), self)
            action.setObjectName(f"feature_{feature.id}")
            action.setToolTip(translate(feature.description))
            action.setStatusTip(translate(feature.description))
            if icons.has_icon(feature.id):
                action.setIcon(icons.icon(feature.id))
            action.triggered.connect(lambda _checked=False, f=feature: self.run_feature(f))
            self.feature_actions[feature.id] = action
        open_action = self.feature_actions["open"]
        open_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Open))
        open_action.setToolTip(f"{open_action.toolTip()} (Ctrl+O)")

    def _mark_pending_features(self) -> None:
        """Functions that are not built yet look fainter and say so."""
        for feature in FEATURES:
            if feature.id in self.feature_handlers:
                continue
            action = self.feature_actions[feature.id]
            if icons.has_icon(feature.id):
                action.setIcon(icons.icon(feature.id, icons.PENDING))
            action.setToolTip(
                self.tr("{0} (todavía no disponible)").format(translate(feature.description))
            )
            button = self.mode_toolbars[feature.mode].widgetForAction(action)
            if button is not None:
                button.setProperty("pending", True)

    def _build_mode_bar(self) -> None:
        self.mode_tabs = QTabBar()
        self.mode_tabs.setObjectName("modeTabs")
        self.mode_tabs.setAccessibleName(self.tr("Modos de trabajo"))
        self.mode_tabs.setExpanding(False)
        self.mode_tabs.setDrawBase(False)
        self.mode_tabs.setMinimumHeight(MIN_BUTTON_HEIGHT)
        self.mode_tabs.setIconSize(QSize(20, 20))
        self.mode_tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        for number, mode in enumerate(MODES, start=1):
            index = self.mode_tabs.addTab(
                icons.icon(f"mode_{mode.name.lower()}", icons.MUTED), translate(mode.value)
            )
            self.mode_tabs.setTabToolTip(
                index, self.tr("Modo {0} (Ctrl+{1})").format(translate(mode.value), number)
            )
        self.mode_tabs.currentChanged.connect(lambda index: self.set_mode(MODES[index]))

        self.finder_button = QPushButton(self.tr("Buscar una función…   Ctrl+K"))
        self.finder_button.setObjectName("finderButton")
        self.finder_button.setIcon(icons.icon("search", icons.MUTED))
        self.finder_button.setIconSize(QSize(18, 18))
        self.finder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.finder_button.setToolTip(
            self.tr("Escribe lo que quieres hacer y te lleva a la función, esté donde esté")
        )
        self.finder_button.setMinimumHeight(MIN_BUTTON_HEIGHT)
        self.finder_button.clicked.connect(self.open_command_palette)

        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self.mode_tabs)
        layout.addStretch()
        layout.addWidget(self.finder_button)

        holder = self.mode_bar = QToolBar(self.tr("Modos"))
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
            toolbar.setProperty("tools", True)  # the style sheet looks for this
            toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            toolbar.setIconSize(QSize(22, 22))
            for feature in features_of(mode):
                if feature.id in GROUP_STARTS:
                    toolbar.addSeparator()
                action = self.feature_actions[feature.id]
                toolbar.addAction(action)
                toolbar.widgetForAction(action).setMinimumHeight(MIN_BUTTON_HEIGHT)
            # The button that appears when the window is too narrow for every tool.
            more = toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            if more is not None:
                more.setIcon(icons.icon("more"))
                more.setToolTip(self.tr("Más herramientas"))
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
            self.mode_toolbars[mode] = toolbar

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(self.tr("&Archivo"))
        self.open_menu_action = QAction(self.tr("&Abrir…"), self)
        self.open_menu_action.setShortcut(self.feature_actions["open"].shortcut())
        self.open_menu_action.triggered.connect(self.choose_and_open)
        # The shortcut lives here: a tool bar button only answers while its mode is shown.
        self.feature_actions["open"].setShortcut(QKeySequence())
        file_menu.addAction(self.open_menu_action)
        self.recent_menu = file_menu.addMenu(self.tr("Abrir &recientes"))
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self.close_tab_action = QAction(self.tr("&Cerrar pestaña"), self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.triggered.connect(lambda _checked=False: self.close_document())
        self.next_tab_action = QAction(self.tr("Pestaña &siguiente"), self)
        self.next_tab_action.setShortcut(QKeySequence("Ctrl+Tab"))
        self.next_tab_action.triggered.connect(lambda _checked=False: self.step_tab(1))
        self.previous_tab_action = QAction(self.tr("Pestaña a&nterior"), self)
        self.previous_tab_action.setShortcut(QKeySequence("Ctrl+Shift+Tab"))
        self.previous_tab_action.triggered.connect(lambda _checked=False: self.step_tab(-1))
        for action in (self.close_tab_action, self.next_tab_action, self.previous_tab_action):
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.addAction(action)
            file_menu.addAction(action)
        file_menu.addSeparator()
        self.settings_action = QAction(self.tr("A&justes…"), self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.settings_action.setMenuRole(QAction.MenuRole.NoRole)
        self.settings_action.triggered.connect(lambda _checked=False: self.open_settings())
        self.addAction(self.settings_action)
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        self.quit_action = QAction(self.tr("&Salir"), self)
        self.quit_action.triggered.connect(self.close)
        file_menu.addAction(self.quit_action)

        edit_menu = self.menuBar().addMenu(self.tr("&Editar"))
        self.copy_action = QAction(self.tr("&Copiar"), self)
        self.copy_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
        self.copy_action.triggered.connect(lambda _checked=False: self.pdf_view.copy_selection())
        edit_menu.addAction(self.copy_action)
        self.select_all_action = QAction(self.tr("&Seleccionar todo"), self)
        self.select_all_action.setShortcut(QKeySequence(QKeySequence.StandardKey.SelectAll))
        self.select_all_action.triggered.connect(lambda _checked=False: self.pdf_view.select_all())
        edit_menu.addAction(self.select_all_action)

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
        self.full_screen_action = QAction(self.tr("&Pantalla completa"), self)
        self.full_screen_action.setCheckable(True)
        self.full_screen_action.setShortcut(QKeySequence("F11"))
        self.full_screen_action.triggered.connect(lambda _checked=False: self.toggle_full_screen())
        self.go_to_page_action = QAction(self.tr("&Ir a página…"), self)
        self.go_to_page_action.setShortcut(QKeySequence("Ctrl+G"))
        self.go_to_page_action.triggered.connect(lambda _checked=False: self.go_to_page())
        self.rotate_view_action = QAction(self.tr("&Girar vista"), self)
        self.rotate_view_action.setShortcut(QKeySequence("Ctrl+R"))
        self.rotate_view_action.triggered.connect(
            lambda _checked=False: self.pdf_view.rotate_view()
        )
        self.side_panel_action = QAction(self.tr("Panel &lateral (miniaturas e índice)"), self)
        self.side_panel_action.setCheckable(True)
        self.side_panel_action.setShortcut(QKeySequence("F4"))
        self.side_panel_action.triggered.connect(lambda _checked=False: self.toggle_side_panel())
        for action in (
            self.side_panel_action,
            self.full_screen_action,
            self.go_to_page_action,
            self.rotate_view_action,
        ):
            # They must also answer while the menu bar is hidden (full screen).
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.addAction(action)
            view_menu.addAction(action)

        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(self.tr("&Tema"))
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
        paper_menu = view_menu.addMenu(self.tr("Pap&el de las páginas"))
        paper_group = QActionGroup(self)
        papers = {
            Paper.WHITE: self.tr("Blanco"),
            Paper.SEPIA: self.tr("Sepia (modo lectura)"),
            Paper.NIGHT: self.tr("Noche"),
        }
        for paper, name in papers.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, p=paper: self.set_paper(p))
            paper_group.addAction(action)
            paper_menu.addAction(action)
            self.paper_actions[paper] = action

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
        """The page shown while no document is open."""
        self.welcome_logo = QLabel()
        self.welcome_logo.setFixedSize(84, 84)
        self.welcome_logo.setPixmap(icons.logo_pixmap(84, self.devicePixelRatioF()))

        title = QLabel(APP_NAME)
        title.setObjectName("welcomeTitle")
        tagline = QLabel(
            self.tr("Lee, estudia, rellena y firma tus PDF.\nTodo se queda en tu ordenador.")
        )
        tagline.setObjectName("welcomeTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.open_button = QPushButton(self.tr("Abrir un PDF"))
        self.open_button.setObjectName("primaryButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.setMinimumHeight(48)
        self.open_button.setToolTip(self.tr("Abrir un PDF del ordenador (Ctrl+O)"))
        self.open_button.clicked.connect(self.choose_and_open)
        drop = QLabel(self.tr("o arrastra un PDF hasta esta ventana"))
        drop.setObjectName("welcomeDrop")

        hints = QGridLayout()
        hints.setHorizontalSpacing(10)
        hints.setVerticalSpacing(8)
        for row, (keys, what) in enumerate(
            (
                ("Ctrl+K", self.tr("Buscar cualquier función por su nombre")),
                ("Ctrl+F", self.tr("Buscar palabras dentro del documento")),
                ("Ctrl+1 … 4", self.tr("Cambiar de modo: leer, estudiar, firmar, organizar")),
            )
        ):
            key = QLabel(keys)
            key.setObjectName("keyCap")
            key.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text = QLabel(what)
            text.setObjectName("keyHint")
            hints.addWidget(key, row, 0, Qt.AlignmentFlag.AlignRight)
            hints.addWidget(text, row, 1, Qt.AlignmentFlag.AlignLeft)

        self.welcome_card = QFrame()
        self.welcome_card.setObjectName("welcomeCard")
        self.welcome_card.setFixedWidth(560)
        card = QVBoxLayout(self.welcome_card)
        card.setContentsMargins(48, 40, 48, 36)
        card.setSpacing(0)
        centre = Qt.AlignmentFlag.AlignHCenter
        card.addWidget(self.welcome_logo, 0, centre)
        card.addSpacing(14)
        card.addWidget(title, 0, centre)
        card.addSpacing(4)
        card.addWidget(tagline, 0, centre)
        card.addSpacing(26)
        card.addWidget(self.open_button, 0, centre)
        card.addSpacing(8)
        card.addWidget(drop, 0, centre)
        self.welcome_recent = QWidget()
        self.welcome_recent.setObjectName("welcomeRecent")
        recent_layout = QVBoxLayout(self.welcome_recent)
        recent_layout.setContentsMargins(0, 22, 0, 0)
        recent_layout.setSpacing(2)
        card.addWidget(self.welcome_recent)
        card.addSpacing(28)
        card.addLayout(hints)
        card.setAlignment(hints, centre)

        build = QLabel(BUILD_LABEL)
        build.setObjectName("welcomeBuild")
        build.setVisible(bool(BUILD_LABEL))

        # Shown on purpose: when testing a build it proves the PDF engine and Qt
        # were packaged correctly, and where the data is kept.
        if is_portable():
            data_text = self.tr("Versión portátil. Los datos se guardan junto al programa: {0}")
        else:
            data_text = self.tr("Carpeta de datos del programa: {0}")
        details = QLabel(
            self.tr("Versión {0} · Motor PDF (PyMuPDF) {1} · Qt {2}").format(
                __version__, engine_version(), qVersion()
            )
            + "\n"
            + data_text.format(data_dir())
        )
        details.setObjectName("welcomeDetails")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        central = QWidget()
        central.setObjectName("welcome")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(central)
        layout.addStretch(3)
        layout.addWidget(self.welcome_card, 0, centre)
        layout.addSpacing(16)
        layout.addWidget(build, 0, centre)
        layout.addSpacing(6)
        layout.addWidget(details, 0, centre)
        layout.addStretch(4)
        return central

    # ---- behaviour ----------------------------------------------------

    @property
    def mode(self) -> Mode:
        return self._mode

    def _refresh_welcome_recent(self) -> None:
        """The last few documents, one click away on the welcome page."""
        layout = self.welcome_recent.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        recent = self.history.recent()[:WELCOME_RECENT]
        self.welcome_recent.setVisible(bool(recent))
        if not recent:
            return
        heading = QLabel(self.tr("Abiertos hace poco"))
        heading.setObjectName("welcomeRecentTitle")
        layout.addWidget(heading)
        for path in recent:
            button = QPushButton(path.name)
            button.setObjectName("recentButton")
            button.setIcon(icons.icon("go_to_page", icons.MUTED))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(MIN_BUTTON_HEIGHT)
            button.setToolTip(str(path))
            button.clicked.connect(lambda _checked=False, p=path: self.open_document(p))
            layout.addWidget(button)

    def set_mode(self, mode: Mode) -> None:
        """Show the tools of ``mode`` and hide those of the other modes."""
        self._mode = mode
        if self.documents:
            self.current_document.mode = mode
        for other, toolbar in self.mode_toolbars.items():
            toolbar.setVisible(other is mode and not self._full_screen)
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

    @property
    def paper(self) -> Paper:
        return self._paper

    def set_paper(self, paper: Paper, remember: bool = True) -> None:
        """Change the tone of the pages on screen (white, sepia or night)."""
        self._paper = paper
        theme_module.set_paper(paper)
        self.paper_actions[paper].setChecked(True)
        for page in [*self.documents, self._spare]:
            page.view.viewport().update()
        if remember:
            self.settings.set(PAPER_SETTING, paper.value)

    def toggle_reading_mode(self) -> None:
        """Warm paper for long hours of reading; again, back to white."""
        reading = self._paper is not Paper.SEPIA
        self.set_paper(Paper.SEPIA if reading else Paper.WHITE)
        message = (
            self.tr("Modo lectura: papel en tono cálido. Pulsa otra vez para volver al blanco.")
            if reading
            else self.tr("Papel blanco, como es el documento.")
        )
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)

    def open_settings(self) -> SettingsDialog:
        """Show the settings window. Returned so that tests can use it."""
        dialog = SettingsDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()
        return dialog

    def restart_program(self) -> None:
        """Close the program and start it again (``main`` starts the new copy)."""
        self.restart_wanted = True
        self.close()

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

    # The parts of the document in front. With nothing open they are those of
    # an empty page, so the rest of the window never has to ask "is there one?".

    @property
    def current_document(self) -> DocumentPage:
        index = self.document_tabs.currentIndex()
        return self.documents[index] if 0 <= index < len(self.documents) else self._spare

    @property
    def pdf_view(self) -> PdfView:
        return self.current_document.view

    @property
    def search_panel(self) -> SearchPanel:
        return self.current_document.search_panel

    @property
    def side_panel(self) -> SidePanel:
        return self.current_document.side_panel

    # The panels used to be docks of the window; they keep these names.
    search_dock = search_panel
    side_dock = side_panel

    def _new_page(self) -> DocumentPage:
        page = DocumentPage()
        view = page.view
        view.page_changed.connect(self._update_position)
        view.zoom_changed.connect(self._update_position)
        view.page_drawn.connect(lambda number, seconds, p=page: self._page_drawn(p, seconds))
        view.document_failed.connect(self._document_failed)
        view.text_copied.connect(self._text_copied)
        view.no_text_to_select.connect(self._no_text_to_select)
        page.search_panel.closed.connect(self.close_search)
        page.side_panel.closed.connect(self.close_side_panel)
        page.side_panel.tab_changed.connect(self._side_tab_changed)
        # Ctrl+C and Ctrl+A belong to the document only while it has the keyboard:
        # in the search box they must keep copying and selecting what is typed.
        for action in (self.copy_action, self.select_all_action):
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            view.addAction(action)
        self.pages.addWidget(page)
        return page

    def warm_up(self) -> None:
        """Start the helper of the next document now, so opening it is immediate."""
        self._warm_spares = True
        self._spare.view.service.warm_up()

    def index_of_document(self, path: str | Path) -> int:
        """The tab that shows the file at ``path``, or -1."""
        wanted = file_key(path)
        for index, page in enumerate(self.documents):
            if page.path is not None and file_key(page.path) == wanted:
                return index
        return -1

    def open_document(self, path: str | Path) -> bool:
        """Show the PDF at ``path`` in a new tab. Problems give a message, never a crash."""
        already = self.index_of_document(path)
        if already >= 0:
            self.document_tabs.setCurrentIndex(already)  # it is open: go to its tab
            self.pdf_view.setFocus()
            return True
        page = self._spare
        try:
            document = PdfDocument(path)
            if document.needs_password:
                self._show_problem(
                    self.tr("Este PDF tiene contraseña"),
                    self.tr("Todavía no se pueden abrir documentos con contraseña."),
                )
                return False
            page.view.set_document(document)
        except PdfOpenError:
            self._show_problem(
                self.tr("No se puede abrir el documento"),
                self.tr("El archivo «{0}» no existe, está dañado o no es un PDF.").format(
                    Path(path).name
                ),
            )
            return False
        page.path = Path(path).absolute()
        page.slowest_page = 0.0
        # Back to the page and the work mode where this document was left.
        place = self.history.place_of(page.path)
        page.mode = _mode_named(place.mode)
        if 0 < place.page < page.view.page_count:
            page.view.scroll_to_page(place.page)
        self.history.add_recent(page.path)
        page.search_panel.document_changed()
        page.side_panel.document_changed()
        self._spare = self._new_page()
        if self._warm_spares:
            self._spare.view.service.warm_up()
        self.documents.append(page)
        self.document_tabs.blockSignals(True)  # shown below, once everything is in place
        index = self.document_tabs.addTab(page.title)
        self.document_tabs.setTabToolTip(index, str(page.path))
        self.document_tabs.add_close_button(index, self.tr("Cerrar pestaña (Ctrl+W)"))
        self.document_tabs.setCurrentIndex(index)
        self.document_tabs.blockSignals(False)
        self.document_tabs.show()
        self._tab_changed(index)
        # The side panel comes back as it was left the last time.
        remembered = Tab.from_setting(self.settings.get(SIDE_PANEL_SETTING))
        if remembered is not None and not self._full_screen:
            self.show_side_panel(remembered, remember=False)
        self._save_session()
        return True

    def restore_session(self) -> int:
        """Open again the documents of the last time. Returns how many came back."""
        if not self.history.restore_wanted:
            return 0
        paths, current = self.history.session()
        asking = self.show_problem_dialogs
        self.show_problem_dialogs = False  # a file that is gone is not worth a dialog
        try:
            opened = [path for path in paths if path.is_file() and self.open_document(path)]
        finally:
            self.show_problem_dialogs = asking
        if 0 <= current < len(paths) and paths[current] in opened:
            self.document_tabs.setCurrentIndex(self.index_of_document(paths[current]))
        missing = len(paths) - len(opened)
        if missing:
            self.statusBar().showMessage(
                self.tr("No se han encontrado {0} de los documentos de la última vez.").format(
                    missing
                ),
                STATUS_MESSAGE_MS,
            )
        self._save_session()
        return len(opened)

    def _save_session(self) -> None:
        paths = [page.path for page in self.documents if page.path is not None]
        self.history.save_session(paths, self.document_tabs.currentIndex())

    def _remember_place(self, page: DocumentPage) -> None:
        if page.path is not None and page.view.page_count:
            self.history.remember_place(page.path, max(page.view.current_page, 0), page.mode.name)

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self.history.recent()
        for number, path in enumerate(recent, start=1):
            action = self.recent_menu.addAction(f"&{number % 10}  {path.name}")
            action.setToolTip(str(path))
            action.setStatusTip(str(path))
            action.triggered.connect(lambda _checked=False, p=path: self.open_document(p))
        if not recent:
            self.recent_menu.addAction(self.tr("(todavía no hay ninguno)")).setEnabled(False)
            return
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.tr("Vaciar esta lista")).triggered.connect(
            self.forget_recent
        )

    def forget_recent(self) -> None:
        self.history.forget_recent()
        self._refresh_welcome_recent()

    def open_from_another_copy(self, files: list[str]) -> None:
        """The program was started again while open: show its files here, in front."""
        for file in files:
            self.open_document(file)
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def close_document(self, index: int | None = None) -> None:
        """Close a tab (the one in front if none is given)."""
        if index is None:
            index = self.document_tabs.currentIndex()
        if not 0 <= index < len(self.documents):
            return
        page = self.documents.pop(index)
        self._remember_place(page)
        self.document_tabs.blockSignals(True)
        self.document_tabs.removeTab(index)
        self.document_tabs.blockSignals(False)
        page.shutdown()
        self.pages.removeWidget(page)
        page.deleteLater()
        self.document_tabs.setVisible(bool(self.documents) and not self._full_screen)
        self._tab_changed(self.document_tabs.currentIndex())
        self._save_session()

    def step_tab(self, step: int) -> None:
        """Go to the next (1) or the previous (-1) tab, round and round."""
        if len(self.documents) > 1:
            index = (self.document_tabs.currentIndex() + step) % len(self.documents)
            self.document_tabs.setCurrentIndex(index)

    def _tab_moved(self, origin: int, destination: int) -> None:
        self.documents.insert(destination, self.documents.pop(origin))
        self._save_session()

    def _tab_changed(self, _index: int) -> None:
        """Another document is in front (or none): show it and follow it."""
        page = self.current_document
        if self.documents:
            self.pages.setCurrentWidget(page)
            self.setWindowTitle(f"{page.title} – {APP_NAME}")
            page.view.setFocus()
            if page.mode is not self._mode:
                self.set_mode(page.mode)  # every document keeps its work mode
        else:
            self._refresh_welcome_recent()
            self.pages.setCurrentWidget(self.welcome)
            self.setWindowTitle(APP_NAME)
        self.page_box.set_view(page.view)
        self.zoom_control.set_view(page.view)
        self.side_panel_action.setChecked(page.side_panel.isVisible())
        self._show_speed(page)
        if self._full_screen:
            self._hide_panels_for_full_screen()

    def show_search(self) -> None:
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(
                self.tr("Abre un documento para poder buscar en él."), STATUS_MESSAGE_MS
            )
            return
        self.search_dock.show()
        self.search_panel.start()

    # ---- side panel: thumbnails and outline ------------------------------

    def show_side_panel(self, tab: Tab | None = None, remember: bool = True) -> None:
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            self.side_panel_action.setChecked(False)
            return
        if self._full_screen:
            self.set_full_screen(False)
        if tab is not None:
            self.side_panel.set_tab(tab)
        self.current_document.show_side_panel()
        self.side_panel_action.setChecked(True)
        if remember:
            self.settings.set(SIDE_PANEL_SETTING, self.side_panel.tab.value)

    def close_side_panel(self) -> None:
        self.side_dock.hide()
        self.side_panel_action.setChecked(False)
        self.settings.set(SIDE_PANEL_SETTING, "")
        self.pdf_view.setFocus()

    def toggle_side_panel(self, tab: Tab | None = None) -> None:
        """Open the panel, or close it if it already shows what is asked."""
        showing = self.side_dock.isVisible()
        if showing and (tab is None or tab is self.side_panel.tab):
            self.close_side_panel()
        else:
            self.show_side_panel(tab)

    def _side_tab_changed(self, tab: Tab) -> None:
        if self.side_dock.isVisible():
            self.settings.set(SIDE_PANEL_SETTING, tab.value)

    def close_search(self) -> None:
        self.search_dock.hide()
        self.pdf_view.setFocus()

    # ---- text recognition (proof of concept of task 0.9) ---------------

    def recognize_current_page(self) -> None:
        """Read the text of the page on screen, in a separate process."""
        source = self.pdf_view.document_path
        if source is None:
            self.statusBar().showMessage(
                self.tr("Abre un documento escaneado para reconocer su texto."), STATUS_MESSAGE_MS
            )
            return
        if self._ocr_job is not None:
            return  # one at a time
        page = max(self.pdf_view.current_page, 0)
        self._ocr_job = OcrJob(source, page)
        self.statusBar().showMessage(
            self.tr("Reconociendo el texto de la página {0}…").format(page + 1)
        )
        self._ocr_timer.start()

    def _check_ocr(self) -> None:
        if self._ocr_job is None:
            self._ocr_timer.stop()
            return
        try:
            result = self._ocr_job.poll()
        except OcrError as error:
            self._ocr_job = None
            self._ocr_timer.stop()
            self.reporter.log.record(type(error), error, error.__traceback__, "reconocer texto")
            self._show_problem(
                self.tr("No se ha podido reconocer el texto"),
                self.tr("Con Ayuda → «Copiar informe de error» puedes ver el detalle."),
            )
            return
        if result is None:
            return
        self._ocr_job = None
        self._ocr_timer.stop()
        self.last_ocr = result
        self.statusBar().showMessage(
            self.tr("Texto reconocido: {0} palabras.").format(len(result.words)),
            STATUS_MESSAGE_MS,
        )
        if self.show_problem_dialogs:
            OcrResultDialog(result, self).exec()

    # ---- signing (proof of concept of task 0.8) ------------------------

    def sign_with_certificate(self) -> None:
        """Ask for a certificate and a new file name, and sign the open document."""
        source = self.pdf_view.document_path
        if source is None:
            self.statusBar().showMessage(
                self.tr("Abre el documento que quieres firmar."), STATUS_MESSAGE_MS
            )
            return
        dialog = CertificateDialog(self)
        if dialog.exec() != CertificateDialog.DialogCode.Accepted or dialog.signer is None:
            return
        suggested = source.with_name(f"{source.stem}-firmado.pdf")
        target, _filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Guardar el documento firmado como"),
            str(suggested),
            self.tr("Documentos PDF (*.pdf)"),
        )
        if target:
            self.sign_document(source, Path(target), dialog.signer)

    def sign_document(self, source: Path, target: Path, signer) -> bool:
        """Sign ``source`` into ``target`` and tell how it went."""
        if target.resolve() == source.resolve():
            self._show_problem(
                self.tr("Elige otro nombre"),
                self.tr("De momento el documento firmado se guarda como una copia nueva."),
            )
            return False
        try:
            sign_pdf(source, target, signer)
        except SigningCancelled:
            self.statusBar().showMessage(self.tr("Firma cancelada."), STATUS_MESSAGE_MS)
            return False
        except PasswordProtected:
            self._show_problem(
                self.tr("Este PDF tiene contraseña"),
                self.tr("Todavía no se pueden firmar documentos con contraseña."),
            )
            return False
        except SigningError as error:
            self.reporter.log.record(type(error), error, error.__traceback__, "firmar")
            self._show_problem(
                self.tr("No se ha podido firmar"),
                self.tr(
                    "El documento original no se ha tocado. Con Ayuda → «Copiar informe "
                    "de error» puedes ver el detalle."
                ),
            )
            return False
        message = self.tr("Documento firmado y guardado como «{0}».").format(target.name)
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)
        if self.show_problem_dialogs:
            QMessageBox.information(
                self,
                self.tr("Documento firmado"),
                message
                + "\n\n"
                + self.tr(
                    "Para comprobar la firma, ábrelo con Adobe Reader o súbelo a VALIDe "
                    "(valide.redsara.es)."
                ),
            )
        return True

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
        self.page_box.refresh()

    def go_to_page(self) -> None:
        """Put the cursor in the page number of the status bar."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        if self._full_screen:
            self.set_full_screen(False)  # the page number lives in the status bar
        self.page_box.start()

    # ---- full screen ----------------------------------------------------

    @property
    def full_screen(self) -> bool:
        return self._full_screen

    def toggle_full_screen(self) -> None:
        self.set_full_screen(not self._full_screen)

    def set_full_screen(self, on: bool) -> None:
        """Only the document, on the whole screen. Esc or F11 comes back."""
        if on == self._full_screen:
            return
        self._full_screen = on
        self.full_screen_action.setChecked(on)
        if on:
            self._was_maximized = self.isMaximized()
            self._hide_panels_for_full_screen()
        else:
            for panel in self._docks_before:
                if panel.parent() is not None:  # its tab may have been closed meanwhile
                    panel.show()
            self._docks_before = []
        self.document_tabs.setVisible(not on and bool(self.documents))
        self.menuBar().setVisible(not on)
        self.statusBar().setVisible(not on)
        self.mode_bar.setVisible(not on)
        self.set_mode(self._mode)  # shows or hides the tools of the mode
        if on:
            self.showFullScreen()
            self.pdf_view.setFocus()
        elif self._was_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def _hide_panels_for_full_screen(self) -> None:
        for panel in (self.side_panel, self.search_panel):
            if panel.isVisible():
                self._docks_before.append(panel)
                panel.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self._full_screen:
            self.set_full_screen(False)
            return
        super().keyPressEvent(event)

    def _text_copied(self, letters: int) -> None:
        if letters:
            message = self.tr("Texto copiado. Pégalo donde quieras con Ctrl+V.")
        elif self.pdf_view.page_count == 0:
            message = self.tr("Abre primero un documento.")
        elif self.pdf_view.has_selection:
            message = self.tr("En lo seleccionado no hay texto que copiar.")
        else:
            message = self.tr("Selecciona antes el texto arrastrando el ratón sobre él.")
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)

    def _no_text_to_select(self) -> None:
        self.statusBar().showMessage(
            self.tr(
                "Esta página es una imagen (un escaneado): no tiene texto que seleccionar. "
                "Prueba «Reconocer texto» en el modo Estudiar."
            ),
            STATUS_MESSAGE_MS,
        )

    def _page_drawn(self, page: DocumentPage, seconds: float) -> None:
        page.slowest_page = max(page.slowest_page, seconds)
        if page is self.current_document:
            self._show_speed(page, seconds)

    def _show_speed(self, page: DocumentPage, seconds: float | None = None) -> None:
        if seconds is None:
            self.speed_label.setText("")
            return
        self.speed_label.setText(
            self.tr("Dibujo de página: {0} ms (la más lenta: {1} ms)").format(
                round(seconds * 1000), round(page.slowest_page * 1000)
            )
        )

    # ---- dropping a file on the window ----------------------------------

    @staticmethod
    def _dropped_pdfs(event) -> list[str]:
        return [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
        ]

    def _show_dropping(self, dropping: bool) -> None:
        self.welcome_card.setProperty("dropping", dropping)
        self.welcome_card.style().unpolish(self.welcome_card)
        self.welcome_card.style().polish(self.welcome_card)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._dropped_pdfs(event):
            self._show_dropping(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._show_dropping(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._show_dropping(False)
        paths = self._dropped_pdfs(event)
        if paths:
            event.acceptProposedAction()
            for path in paths:  # each one in its own tab
                self.open_document(path)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, "welcome_logo"):
            # Moved to a screen with another scale: draw the logo sharp again.
            self.welcome_logo.setPixmap(icons.logo_pixmap(84, self.devicePixelRatioF()))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._ocr_job is not None:
            self._ocr_job.cancel()
            self._ocr_job = None
        for page in self.documents:
            self._remember_place(page)
        self._save_session()
        self.shutdown_documents()
        super().closeEvent(event)

    def shutdown_documents(self) -> None:
        """Stop the helper processes of every tab. Safe to call more than once."""
        for page in [*self.documents, self._spare]:
            page.shutdown()


def _mode_named(name: str) -> Mode:
    """The work mode with that name; reading if it is unknown."""
    return next((mode for mode in MODES if mode.name == name), Mode.READ)


class DocumentTabBar(QTabBar):
    """The tabs of the open documents, each with its button to close it.

    A click with the wheel on a tab closes it too.
    """

    def add_close_button(self, index: int, tip: str) -> None:
        button = QToolButton()
        button.setObjectName("tabCloseButton")
        button.setIcon(icons.icon("close", icons.MUTED))
        button.setIconSize(QSize(14, 14))
        button.setAccessibleName(tip)
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(lambda: self._close_tab_of(button))
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)

    def _close_tab_of(self, button: QToolButton) -> None:
        for index in range(self.count()):
            if self.tabButton(index, QTabBar.ButtonPosition.RightSide) is button:
                self.tabCloseRequested.emit(index)
                return

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.tabCloseRequested.emit(index)
                return
        super().mouseReleaseEvent(event)
