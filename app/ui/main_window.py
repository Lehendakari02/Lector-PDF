"""Main window: the work modes, their tools and the function finder."""

from PySide6.QtCore import QSize, Qt, qVersion
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTabBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, BUILD_LABEL, __version__
from app.core.document import engine_version
from app.core.paths import data_dir, is_portable
from app.core.settings import Settings
from app.ui.command_palette import CommandPalette
from app.ui.features import FEATURES, MODES, Feature, Mode, features_of, translate
from app.ui.theme import THEME_SETTING, Theme, apply_theme

# Big enough to press comfortably with a finger on a touch screen.
MIN_BUTTON_HEIGHT = 40
STATUS_MESSAGE_MS = 6000


class MainWindow(QMainWindow):
    """Top-level window of the program."""

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else Settings()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 750)

        self.feature_actions: dict[str, QAction] = {}
        self.mode_toolbars: dict[Mode, QToolBar] = {}
        self.theme_actions: dict[Theme, QAction] = {}

        self._build_feature_actions()
        self._build_mode_bar()
        self._build_tool_bars()
        self._build_menus()
        self.setCentralWidget(self._build_welcome())
        self.statusBar().setSizeGripEnabled(True)

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
        # No function is built yet: every button explains itself for now.
        self.statusBar().showMessage(
            self.tr("«{0}» todavía no está disponible. {1}.").format(
                translate(feature.name), translate(feature.description)
            ),
            STATUS_MESSAGE_MS,
        )
