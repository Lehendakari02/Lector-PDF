"""Main window: the work modes, their tools and the function finder."""

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, qVersion
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
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
from app.core import saving
from app.core.commands import HIGHLIGHT, MARKUP_KINDS, STRIKEOUT, UNDERLINE
from app.core.document import PdfDocument, PdfOpenError, engine_version
from app.core.error_log import running_from_source_or_test_build
from app.core.history import History, file_key
from app.core.interface_size import NORMAL_SIZE
from app.core.ocr import OcrError, OcrJob, OcrPage
from app.core.paths import data_dir, is_portable
from app.core.settings import Settings
from app.core.signing import PasswordProtected, SigningError, sign_pdf
from app.core.updates import Release
from app.core.windows_store import SigningCancelled
from app.ui import icons
from app.ui import theme as theme_module
from app.ui.about_dialog import AboutDialog
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
from app.ui.password_dialog import PasswordDialog
from app.ui.pdf_view import PdfView
from app.ui.print_dialog import PrintChoices, PrintDialog
from app.ui.print_run import PrintRun
from app.ui.search_panel import SearchPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.side_panel import SidePanel, Tab
from app.ui.sign_dialog import CertificateDialog
from app.ui.theme import PAPER_SETTING, THEME_SETTING, Paper, Theme, apply_theme
from app.ui.updater import UpdateBanner, Updater
from app.ui.zoom_control import ZoomControl

# Big enough to press comfortably with a finger on a touch screen.
MIN_BUTTON_HEIGHT = 40
# The row with the menu, the modes and the search box is a little lower.
BAR_BUTTON_HEIGHT = 34
STATUS_MESSAGE_MS = 6000
LAST_FOLDER_SETTING = "ultima_carpeta"
WELCOME_RECENT = 5  # recent documents offered on the welcome page
# The tools of each mode with their names under the drawing, or only the drawings.
TOOLBAR_SETTING = "barra_herramientas"
TOOLBAR_NAMES, TOOLBAR_ICONS = "nombres", "iconos"
TOP_SEARCH_WIDTH = 280
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
        # How a protected PDF gets its password. Tests put their own answer here.
        self.ask_password = self._ask_password
        self._password_dialogs: bool | None = None  # None: as show_problem_dialogs
        self._password_questions: dict[str, PasswordDialog] = {}  # open ones, by file
        self._print_run: PrintRun | None = None
        # Set when a new version is ready: run after this program has closed.
        self.after_exit_command: list[str] | None = None
        self.updater = Updater(self.settings, self)
        self.updater.found.connect(self._new_version_found)
        self.updater.nothing_new.connect(self._no_new_version)
        self.updater.progress.connect(self._update_progress)
        self.updater.ready.connect(self._update_ready)
        self.updater.failed.connect(self._update_failed)
        self._printer: QPrinter | None = None  # kept alive while it prints
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 800)
        self.setAcceptDrops(True)  # a PDF dropped on the window is opened

        self._full_screen = False
        self._was_maximized = False
        self._docks_before: list[QWidget] = []
        self.feature_actions: dict[str, QAction] = {}
        self.mode_toolbars: dict[Mode, QToolBar] = {}
        self._toolbar_icons_only = False
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
        self.update_banner = UpdateBanner()
        central_layout.addWidget(self.update_banner)
        central_layout.addWidget(self.document_tabs)
        central_layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        # A page kept ready for the next document that is opened. While nothing
        # is open it also stands in as "the current document" (an empty one).
        self._spare = self._new_page()
        self._warm_spares = False
        self.update_banner.update_wanted.connect(self.update_now)
        self.update_banner.cancel_wanted.connect(self.updater.cancel)
        self.update_banner.skip_wanted.connect(self._skip_new_version)
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
            "fit_comfortable": lambda: self.pdf_view.fit_comfortable(),
            "fit_width": lambda: self.pdf_view.fit_width(),
            "fit_page": lambda: self.pdf_view.fit_page(),
            "rotate_view": lambda: self.pdf_view.rotate_view(),
            "fullscreen": self.toggle_full_screen,
            "go_to_page": self.go_to_page,
            "copy": lambda: self.pdf_view.copy_selection(),
            "thumbnails": lambda: self.toggle_side_panel(Tab.THUMBNAILS),
            "outline": lambda: self.toggle_side_panel(Tab.OUTLINE),
            "reading_mode": self.toggle_reading_mode,
            "print": self.print_document,
            "highlight": lambda: self.use_marker(HIGHLIGHT),
            "underline": lambda: self.use_marker(UNDERLINE),
            "strikeout": lambda: self.use_marker(STRIKEOUT),
            "undo": self.undo,
            "redo": self.redo,
            "save": self.save_document,
            "save_as": self.save_document_as,
        }
        self._mark_pending_features()
        self._refresh_save_actions()
        self._refresh_edit_actions()

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
        self.mode_tabs.setMinimumHeight(BAR_BUTTON_HEIGHT)
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

        # The menus (Archivo, Editar, Ver, Ayuda) live behind one button: a whole
        # row less above the document. Filled in _build_menus.
        self.menu_button = QToolButton()
        self.menu_button.setObjectName("menuButton")
        self.menu_button.setText(self.tr("&Menú"))
        self.menu_button.setIcon(icons.icon("menu"))
        self.menu_button.setIconSize(QSize(20, 20))
        self.menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setToolTip(self.tr("Archivo, Editar, Ver y Ayuda (Alt+M)"))
        self.menu_button.setAccessibleName(self.tr("Menú del programa"))
        self.menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_button.setMinimumHeight(BAR_BUTTON_HEIGHT)

        # Always in view: typing here searches the document in front.
        self.search_box = QLineEdit()
        self.search_box.setObjectName("topSearch")
        self.search_box.setPlaceholderText(self.tr("Buscar en el documento…   Ctrl+F"))
        self.search_box.setAccessibleName(self.tr("Buscar en el documento"))
        self.search_box.setToolTip(
            self.tr(
                "Escribe una palabra o una frase. No hacen falta tildes ni mayúsculas. "
                "Intro: siguiente resultado."
            )
        )
        self.search_box.setClearButtonEnabled(True)
        self.search_box.addAction(
            icons.icon("search", icons.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_box.setFixedWidth(TOP_SEARCH_WIDTH)
        self.search_box.setMinimumHeight(BAR_BUTTON_HEIGHT)
        self.search_box.textEdited.connect(self._top_search_typed)
        self.search_box.returnPressed.connect(self._top_search_enter)
        self.search_box.installEventFilter(self)

        self.finder_button = QPushButton(self.tr("Funciones   Ctrl+K"))
        self.finder_button.setAccessibleName(self.tr("Buscar una función"))
        self.finder_button.setObjectName("finderButton")
        self.finder_button.setIcon(icons.icon("search", icons.MUTED))
        self.finder_button.setIconSize(QSize(18, 18))
        self.finder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.finder_button.setToolTip(
            self.tr("Escribe lo que quieres hacer y te lleva a la función, esté donde esté")
        )
        self.finder_button.setMinimumHeight(BAR_BUTTON_HEIGHT)
        self.finder_button.clicked.connect(self.open_command_palette)

        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        layout.addWidget(self.menu_button)
        layout.addWidget(self.mode_tabs)
        layout.addStretch()
        layout.addWidget(self.search_box)
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
            toolbar.setIconSize(QSize(20, 20))
            if mode is not Mode.READ:
                # Saving is at hand wherever the document can be changed.
                toolbar.addAction(self.feature_actions["save"])
                save_button = toolbar.widgetForAction(self.feature_actions["save"])
                save_button.setMinimumHeight(MIN_BUTTON_HEIGHT)
                toolbar.addSeparator()
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
        self.set_toolbar_icons_only(
            self.settings.get(TOOLBAR_SETTING) == TOOLBAR_ICONS, remember=False
        )

    @property
    def toolbar_icons_only(self) -> bool:
        return self._toolbar_icons_only

    def set_toolbar_icons_only(self, icons_only: bool, remember: bool = True) -> None:
        """Show the tools with their names (the default) or only their drawings.

        Without names the bar is lower and the document gets more room; the
        name of every tool is still in its tooltip and for screen readers.
        """
        self._toolbar_icons_only = icons_only
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if icons_only
            else Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        for toolbar in self.mode_toolbars.values():
            toolbar.setToolButtonStyle(style)
            toolbar.setIconSize(QSize(22, 22) if icons_only else QSize(20, 20))
            for action in toolbar.actions():
                button = toolbar.widgetForAction(action)
                if isinstance(button, QToolButton) and not action.isSeparator():
                    button.setMinimumWidth(MIN_BUTTON_HEIGHT if icons_only else 0)
        if remember:
            self.settings.set(TOOLBAR_SETTING, TOOLBAR_ICONS if icons_only else TOOLBAR_NAMES)

    def _build_menus(self) -> None:
        # Works in every mode, like the other shortcuts of the window.
        self.initial_size_action = QAction(self.tr("Tamaño inicial"), self)
        self.initial_size_action.setShortcut(QKeySequence("Ctrl+0"))
        self.initial_size_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.initial_size_action.triggered.connect(lambda _c=False: self.pdf_view.fit_comfortable())
        self.addAction(self.initial_size_action)
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
        self.save_action = QAction(self.tr("&Guardar"), self)
        self.save_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Save))
        self.save_action.triggered.connect(lambda _checked=False: self.save_document())
        self.save_as_action = QAction(self.tr("Guardar c&omo…"), self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_as_action.triggered.connect(lambda _checked=False: self.save_document_as())
        for action in (self.save_action, self.save_as_action):
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.addAction(action)
            file_menu.addAction(action)
        self.print_action = QAction(self.tr("&Imprimir…"), self)
        self.print_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Print))
        self.print_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.print_action.triggered.connect(lambda _checked=False: self.print_document())
        self.addAction(self.print_action)
        file_menu.addAction(self.print_action)
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
        self.undo_action = QAction(self.tr("&Deshacer"), self)
        self.undo_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Undo))
        self.undo_action.triggered.connect(lambda _checked=False: self.undo())
        self.redo_action = QAction(self.tr("&Rehacer"), self)
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.redo_action.triggered.connect(lambda _checked=False: self.redo())
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
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

        self.check_updates_action = QAction(self.tr("Buscar &versiones nuevas…"), self)
        self.check_updates_action.triggered.connect(lambda _checked=False: self.check_for_updates())
        help_menu.addAction(self.check_updates_action)

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

        help_menu.addSeparator()
        self.about_action = QAction(self.tr("&Acerca de {0}").format(APP_NAME), self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(lambda _checked=False: self.show_about())
        help_menu.addAction(self.about_action)

        # The same menus, behind the "Menú" button. The classic bar stays hidden:
        # its row is given to the document.
        self.main_menu = QMenu(self.menu_button)
        for top_action in self.menuBar().actions():
            self.main_menu.addAction(top_action)
        self.menu_button.setMenu(self.main_menu)
        self.menuBar().hide()
        # A shortcut only works while its action belongs to something in view.
        waiting = list(self.menuBar().actions())
        while waiting:
            action = waiting.pop()
            if action.menu() is not None:
                waiting.extend(action.menu().actions())
            elif not action.shortcut().isEmpty() and action not in self.actions():
                self.addAction(action)

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

    def show_about(self) -> AboutDialog:
        """The window with the version, the licence and the software used."""
        dialog = AboutDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()
        return dialog

    # ---- new versions --------------------------------------------------

    def check_for_updates(self) -> None:
        """Asked by hand: look for a new version now and say what was found."""
        self.statusBar().showMessage(self.tr("Buscando versiones nuevas…"), STATUS_MESSAGE_MS)
        self.updater.check(by_hand=True)

    def _new_version_found(self, release: Release) -> None:
        self.update_banner.offer(release, self.updater.can_install)

    def _no_new_version(self, answered: bool) -> None:
        if answered:
            text = self.tr("Tienes la última versión ({0}).").format(self.updater.current_version)
        else:
            text = self.tr("No se ha podido consultar. Comprueba tu conexión a internet.")
        self.statusBar().showMessage(text, STATUS_MESSAGE_MS)

    def _skip_new_version(self) -> None:
        if self.updater.release is not None:
            self.updater.skip(self.updater.release)

    def update_now(self) -> None:
        """Download the new version; when it is ready the program restarts with it."""
        release = self.updater.release
        if release is None:
            return
        if not self.updater.start_update(release):
            self.update_banner.open_page()  # from the source code: nothing to replace
            return
        self.update_banner.downloading(0)

    def _update_progress(self, percent: int) -> None:
        self.update_banner.downloading(percent)

    def _update_failed(self, cancelled: bool) -> None:
        if cancelled:
            if self.updater.release is not None:
                self.update_banner.offer(self.updater.release, self.updater.can_install)
            return
        self.update_banner.problem(
            self.tr("No se ha podido descargar la versión nueva. Sigues con la de siempre.")
        )

    def _update_ready(self, command: list) -> None:
        """Everything is downloaded and checked: close, and let the new version in."""
        self.update_banner.installing()
        self.after_exit_command = [str(part) for part in command]
        self.close()
        if self.isVisible():  # closing was refused (something pending): do not install
            self.after_exit_command = None
            if self.updater.release is not None:
                self.update_banner.offer(self.updater.release, self.updater.can_install)

    # ---- printing -------------------------------------------------------

    # ---- marking text, undo and redo -------------------------------------

    def use_marker(self, kind: str) -> None:
        """Highlight, underline or strike out.

        With text selected, it is marked at once. With nothing selected, the
        marker stays in hand: every text selected from then on gets marked,
        until the button is pressed again (or Esc).
        """
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            self._refresh_edit_actions()
            return
        if view.has_selection:
            view.mark_selection(kind)
        elif view.markup_tool == kind:
            view.set_markup_tool("")
            self.statusBar().showMessage(self.tr("Rotulador guardado."), STATUS_MESSAGE_MS)
        else:
            view.set_markup_tool(kind)
            self.statusBar().showMessage(
                self.tr("{0}: selecciona texto y queda marcado. Esc para dejarlo.").format(
                    translate(self._feature_named(kind).name)
                ),
                STATUS_MESSAGE_MS,
            )
        self._refresh_edit_actions()

    @staticmethod
    def _feature_named(feature_id: str) -> Feature:
        return next(feature for feature in FEATURES if feature.id == feature_id)

    def undo(self) -> None:
        if not self.pdf_view.undo():
            self.statusBar().showMessage(self.tr("No hay nada que deshacer."), STATUS_MESSAGE_MS)

    def redo(self) -> None:
        if not self.pdf_view.redo():
            self.statusBar().showMessage(self.tr("No hay nada que rehacer."), STATUS_MESSAGE_MS)

    def _edit_state_changed(self, page: DocumentPage) -> None:
        if page is self.current_document:
            self._refresh_edit_actions()

    def _refresh_edit_actions(self) -> None:
        """Undo and redo light up when there is something; the marker in hand stays pressed."""
        view = self.pdf_view
        for action in (self.undo_action, self.feature_actions["undo"]):
            action.setEnabled(view.can_undo)
        for action in (self.redo_action, self.feature_actions["redo"]):
            action.setEnabled(view.can_redo)
        for kind in MARKUP_KINDS:
            action = self.feature_actions[kind]
            action.setCheckable(True)
            action.setChecked(view.markup_tool == kind)

    def _edit_failed(self, _details: str) -> None:
        self.statusBar().showMessage(
            self.tr("No se ha podido hacer el cambio: ahí no hay texto que marcar."),
            STATUS_MESSAGE_MS,
        )

    # ---- saving ---------------------------------------------------------

    def _refresh_save_actions(self) -> None:
        """ "Guardar" only lights up when the document in front has something to save."""
        view = self.pdf_view
        is_open = view.page_count > 0
        can_save = is_open and view.modified and not view.saving
        for action in (self.save_action, self.feature_actions["save"]):
            action.setEnabled(can_save)
        for action in (self.save_as_action, self.feature_actions["save_as"]):
            action.setEnabled(is_open and not view.saving)

    def _modified_changed(self, page: DocumentPage) -> None:
        if page is self.current_document:
            self._refresh_save_actions()

    def save_document(self, page: DocumentPage | None = None) -> bool:
        """Save the changes of a document (the one in front) in its own file.

        Returns True if the saving has started; the result comes a moment later.
        """
        page = page if page is not None else self.current_document
        if page.view.page_count == 0 or page.path is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        if page.view.saving:
            return False
        if not page.view.modified:
            self.statusBar().showMessage(self.tr("No hay cambios que guardar."), STATUS_MESSAGE_MS)
            return False
        self._start_saving(page, None)
        return True

    def save_document_as(self, target: str | Path | None = None) -> bool:
        """Save the document in front as another file and go on working in that one.

        Without ``target`` the user is asked where. Returns True if the saving
        has started.
        """
        page = self.current_document
        if page.view.page_count == 0 or page.path is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        if page.view.saving:
            return False
        if target is None:
            suggested = page.path.with_name(self.tr("{0} - copia.pdf").format(page.path.stem))
            chosen, _filter = QFileDialog.getSaveFileName(
                self, self.tr("Guardar como"), str(suggested), self.tr("Documentos PDF (*.pdf)")
            )
            if not chosen:
                return False
            target = chosen
        target = Path(target).absolute()
        if target.suffix.lower() != ".pdf":
            target = target.with_name(target.name + ".pdf")
        if file_key(target) != file_key(page.path) and self.index_of_document(target) >= 0:
            self._show_problem(
                self.tr("Ese archivo está abierto"),
                self.tr(
                    "«{0}» está abierto en otra pestaña. Elige otro nombre o cierra antes "
                    "esa pestaña."
                ).format(target.name),
            )
            return False
        self._start_saving(page, target)
        return True

    def _start_saving(self, page: DocumentPage, target: Path | None) -> None:
        self.statusBar().showMessage(self.tr("Guardando…"))
        page.view.save(target)
        self._refresh_save_actions()

    def _document_saved(self, page: DocumentPage, _number: int, path: object) -> None:
        path = Path(path)
        if page.path is not None and file_key(path) != file_key(page.path):
            # "Guardar como": from now on this tab is the new file.
            page.path = path
            self.history.add_recent(path)
            if page in self.documents:
                index = self.documents.index(page)
                self.document_tabs.setTabText(index, page.title)
                self.document_tabs.setTabToolTip(index, str(path))
                self._save_session()
            if page is self.current_document:
                self.setWindowTitle(f"{page.title} – {APP_NAME}")
        self.statusBar().showMessage(
            self.tr("Guardado en «{0}».").format(path.name), STATUS_MESSAGE_MS
        )
        self._refresh_save_actions()

    def _save_failed(self, page: DocumentPage, _number: int, kind: str) -> None:
        self._refresh_save_actions()
        name = page.title
        reasons = {
            saving.LOCKED: self.tr(
                "Otro programa tiene abierto «{0}» (o se está sincronizando con la nube). "
                "Ciérralo en el otro programa y vuelve a guardar."
            ),
            saving.READ_ONLY: self.tr(
                "«{0}» o su carpeta no se pueden cambiar (es de solo lectura). "
                "Guárdalo en otro sitio con «Guardar como»."
            ),
            saving.NO_SPACE: self.tr(
                "No queda sitio en el disco para guardar «{0}». Libera espacio o guárdalo "
                "en otro sitio con «Guardar como»."
            ),
        }
        reason = reasons.get(
            kind,
            self.tr("No se ha podido guardar «{0}». Prueba a guardarlo en otro sitio."),
        ).format(name)
        text = self.tr("{0}\n\nNo se ha perdido nada: tus cambios siguen aquí.").format(reason)
        title = self.tr("No se ha podido guardar")
        self.statusBar().showMessage(f"{title}. {reason}", STATUS_MESSAGE_MS)
        if not self.show_problem_dialogs:
            return
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=self)
        save_as = box.addButton(self.tr("Guardar como…"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(self.tr("Cerrar"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is save_as and page in self.documents:
            self.document_tabs.setCurrentIndex(self.documents.index(page))
            self.save_document_as()

    def print_document(self) -> None:
        """Ask what to print of the document in front, and print it."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        if self._print_run is not None:
            self.statusBar().showMessage(
                self.tr("Espera a que termine lo que se está imprimiendo."), STATUS_MESSAGE_MS
            )
            return
        printers = QPrinterInfo.availablePrinterNames()
        if not printers:
            self._show_problem(
                self.tr("No hay ninguna impresora"),
                self.tr("Windows no tiene ninguna impresora instalada. Añade una y vuelve aquí."),
            )
            return
        dialog = PrintDialog(
            printers,
            QPrinterInfo.defaultPrinterName(),
            self.pdf_view.page_count,
            max(0, self.pdf_view.current_page),
            self.settings,
            self,
        )
        try:
            if dialog.exec() != PrintDialog.DialogCode.Accepted or dialog.choices is None:
                return
            choices = dialog.choices
        finally:
            dialog.deleteLater()
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(choices.printer)
        self.start_printing(printer, choices)

    def start_printing(self, printer: QPrinter, choices: PrintChoices) -> bool:
        """Send the chosen pages of the document in front to ``printer``."""
        page = self.current_document
        printer.setDocName(page.title)
        printer.setCopyCount(choices.copies)
        printer.setDuplex(
            QPrinter.DuplexMode.DuplexAuto if choices.both_sides else QPrinter.DuplexMode.DuplexNone
        )
        printer.setColorMode(
            QPrinter.ColorMode.GrayScale if choices.grey else QPrinter.ColorMode.Color
        )
        run = PrintRun(page.view, printer, choices.pages, choices.scaling, self)
        progress = QProgressDialog(self)
        progress.setWindowTitle(self.tr("Imprimiendo"))
        progress.setLabelText(self.tr("Preparando «{0}»…").format(page.title))
        progress.setCancelButtonText(self.tr("Cancelar"))
        progress.setRange(0, run.total)
        progress.setMinimumDuration(400)  # a short job does not flash a window
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.canceled.connect(run.cancel)

        def step(done: int, total: int) -> None:
            progress.setLabelText(self.tr("Imprimiendo página {0} de {1}…").format(done, total))
            progress.setValue(done)

        run.progress.connect(step)
        run.finished.connect(
            lambda failed, cancelled: self._printing_finished(run, progress, failed, cancelled)
        )
        self._print_run, self._printer = run, printer
        if not run.start():
            self._print_run = self._printer = None
            progress.deleteLater()
            run.deleteLater()
            self._show_problem(
                self.tr("No se puede imprimir"),
                self.tr("La impresora «{0}» no responde. Comprueba que está encendida.").format(
                    printer.printerName()
                ),
            )
            return False
        return True

    def _printing_finished(
        self, run: PrintRun, progress: QProgressDialog, failed: list, cancelled: bool
    ) -> None:
        self._print_run = self._printer = None
        progress.canceled.disconnect(run.cancel)
        progress.close()
        progress.deleteLater()
        run.deleteLater()
        sent = run.total - len(failed)
        if cancelled:
            self.statusBar().showMessage(self.tr("Impresión cancelada."), STATUS_MESSAGE_MS)
        elif failed:
            numbers = ", ".join(str(page + 1) for page in failed)
            self._show_problem(
                self.tr("Algunas páginas no se han impreso"),
                self.tr(
                    "Están dañadas y no se han podido imprimir: {0}. "
                    "Las demás ({1}) se han enviado a la impresora."
                ).format(numbers, sent),
            )
        elif sent == 1:
            self.statusBar().showMessage(
                self.tr("1 página enviada a la impresora."), STATUS_MESSAGE_MS
            )
        else:
            self.statusBar().showMessage(
                self.tr("{0} páginas enviadas a la impresora.").format(sent), STATUS_MESSAGE_MS
            )

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
        view.modified_changed.connect(lambda _modified, p=page: self._modified_changed(p))
        view.saved.connect(lambda number, path, p=page: self._document_saved(p, number, path))
        view.save_failed.connect(
            lambda number, kind, details, p=page: self._save_failed(p, number, kind)
        )
        page.search_panel.closed.connect(self.close_search)
        page.search_panel.box.textChanged.connect(self._panel_search_typed)
        page.side_panel.closed.connect(self.close_side_panel)
        page.side_panel.tab_changed.connect(self._side_tab_changed)
        # Ctrl+C and Ctrl+A belong to the document only while it has the keyboard:
        # in the search box they must keep copying and selecting what is typed.
        # The same goes for Ctrl+Z: in a text box it undoes what was typed there.
        for action in (
            self.copy_action,
            self.select_all_action,
            self.undo_action,
            self.redo_action,
        ):
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            view.addAction(action)
        view.history_changed.connect(lambda p=page: self._edit_state_changed(p))
        view.markup_tool_changed.connect(lambda _kind, p=page: self._edit_state_changed(p))
        view.selection_changed.connect(lambda _has, p=page: self._edit_state_changed(p))
        view.edit_failed.connect(self._edit_failed)
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
                document = self.ask_password(Path(path))
                if document is None:
                    return False  # the user gave up
            page.view.set_document(document)
        except PdfOpenError:
            self._show_problem(
                self.tr("No se puede abrir el documento"),
                self.tr(
                    "El archivo «{0}» no existe, está dañado o incompleto, o no es un PDF."
                ).format(Path(path).name),
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
        self._password_dialogs = asking  # but a protected one still asks for its password
        try:
            opened = [path for path in paths if path.is_file() and self.open_document(path)]
        finally:
            self.show_problem_dialogs = asking
            self._password_dialogs = None
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

    def _ask_password(self, path: Path) -> PdfDocument | None:
        """Ask for the password of a protected PDF. None if the user gives up."""
        asking = self._password_dialogs
        if not (self.show_problem_dialogs if asking is None else asking):
            self.statusBar().showMessage(
                self.tr("«{0}» tiene contraseña y no se ha abierto.").format(path.name),
                STATUS_MESSAGE_MS,
            )
            return None
        unlocked: list[PdfDocument] = []

        def try_password(password: str) -> bool:
            document = PdfDocument(path, password)
            if document.needs_password:
                return False
            unlocked.append(document)
            return True

        # Asked to open the same file again while its password is being asked
        # (several double clicks): one question is enough, bring it to the front.
        key = str(path.absolute())
        waiting = self._password_questions.get(key)
        if waiting is not None:
            waiting.raise_()
            waiting.activateWindow()
            return None
        dialog = PasswordDialog(path.name, try_password, self)
        self._password_questions[key] = dialog
        try:
            accepted = dialog.exec() == PasswordDialog.DialogCode.Accepted
        finally:
            self._password_questions.pop(key, None)
            dialog.deleteLater()
        return unlocked[-1] if accepted and unlocked else None

    def open_from_another_copy(self, files: list[str]) -> None:
        """The program was started again while open: show its files here, in front."""
        # First the window, then the files: a file may ask something (a password)
        # and the question must come up in front, over a window that is in view.
        self.bring_to_front()
        for file in files:
            self.open_document(file)

    def bring_to_front(self) -> None:
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
        # The box at the top shows what is being searched in this document.
        searching = page.search_panel.isVisible()
        self.search_box.setText(page.search_panel.box.text() if searching else "")
        self.side_panel_action.setChecked(page.side_panel.isVisible())
        self._refresh_save_actions()
        self._refresh_edit_actions()
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
        self.search_box.clear()
        self.pdf_view.setFocus()

    # ---- the search box at the top ---------------------------------------

    def _top_search_typed(self, text: str) -> None:
        """Typed in the box at the top: the panel of the document searches it."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(
                self.tr("Abre un documento para poder buscar en él."), STATUS_MESSAGE_MS
            )
            return
        self.search_dock.show()  # the list of results; the cursor stays up here
        self.search_panel.box.setText(text)

    def _top_search_enter(self) -> None:
        if self.pdf_view.page_count and self.search_box.text():
            self.search_dock.show()
            self.search_panel.box.setText(self.search_box.text())
            self.search_panel.enter_pressed()

    def _panel_search_typed(self, text: str) -> None:
        """Typed in the panel of a document: the box at the top says the same."""
        if self.sender() is self.search_panel.box and self.search_box.text() != text:
            self.search_box.setText(text)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        """In the search box at the top: arrows walk the results, Esc ends the search."""
        if watched is self.search_box and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) or (
                shift and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            ):
                if self.pdf_view.page_count:
                    if key == Qt.Key.Key_Down:
                        self.search_panel.go_next()
                    else:
                        self.search_panel.go_previous()
                return True
            if key == Qt.Key.Key_Escape:
                if self.pdf_view.page_count:
                    self.search_panel.close_search()
                else:
                    self.search_box.clear()
                return True
        return super().eventFilter(watched, event)

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
        """A document that was open cannot be shown after all: close its tab and say so."""
        view = self.sender()
        index = next((i for i, page in enumerate(self.documents) if page.view is view), -1)
        name = self.documents[index].title if index >= 0 else ""
        if index >= 0:
            self.close_document(index)  # back to the other tabs, or to the welcome page
        self._show_problem(
            self.tr("No se puede mostrar el documento"),
            self.tr("El archivo «{0}» está dañado o no es un PDF.").format(name)
            if name
            else self.tr("El archivo está dañado o no es un PDF."),
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
        if self._print_run is not None:
            self._print_run.cancel()
        self.updater.cancel()
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
