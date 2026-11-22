"""Main window: the work modes, their tools and the function finder."""

import contextlib
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, QUrl, Signal, qVersion
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPixmap,
)
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, BUILD_LABEL, __version__
from app.core import (
    certificate_settings,
    my_data,
    my_signature,
    ocr,
    pen,
    pictures,
    save_checks,
    save_settings,
    saving,
    sheets,
    stamps,
    symbols,
)
from app.core.commands import HIGHLIGHT, MARKUP_KINDS, STRIKEOUT, UNDERLINE
from app.core.doc_links import DocLink, relative_file, resolve
from app.core.document import PdfDocument, PdfOpenError, engine_version
from app.core.drawing import (
    ARROW,
    BOX,
    BRACE,
    DOUBLE_ARROW,
    DRAW,
    ELBOW,
    ERASER,
    LINE,
    OVAL,
    RHOMBUS,
    SHAPE_TOOL,
    TRIANGLE,
    WIDTHS,
)
from app.core.error_log import running_from_source_or_test_build
from app.core.favourites import MAX_FAVOURITES, Favourites, apply_to, favourite_of
from app.core.forms import COMBO
from app.core.forms import TEXT as FORM_TEXT
from app.core.history import History, file_key
from app.core.interface_size import NORMAL_SIZE
from app.core.journal import FOLDER_NAME as JOURNAL_FOLDER
from app.core.journal import Journal, Pending
from app.core.library import FOLDER_SETTING as LIBRARY_FOLDER_SETTING
from app.core.library import topics_in
from app.core.marker_styles import (
    LINE_KINDS,
    SEE_THROUGH_KINDS,
    STYLED_KINDS,
    TEXT_SIZES,
    MarkerStyles,
)
from app.core.my_data import MyData, choice_for, datum_for
from app.core.notes import MONO, NOTE, SANS, SERIF, TEXT_BOX
from app.core.ocr import OcrError
from app.core.ocr_cache import FOLDER_NAME as OCR_CACHE_FOLDER
from app.core.ocr_cache import OcrCache
from app.core.paths import data_dir, is_portable
from app.core.settings import Settings
from app.core.signing import (
    PasswordProtected,
    SigningError,
    TimestampFailed,
    Visible,
    sign_pdf,
)
from app.core.stamps import Stamp
from app.core.summary import summary_of, write_docx, write_pdf
from app.core.tool_keys import FAVOURITE_KEYS, TOOL_KEYS, tool_keys_wanted
from app.core.updates import Release
from app.core.versions import FOLDER_NAME as VERSIONS_FOLDER
from app.core.versions import Version, VersionError, Versions
from app.core.windows_store import SigningCancelled
from app.ui import color_naming, icons
from app.ui import theme as theme_module
from app.ui.about_dialog import AboutDialog
from app.ui.color_menu import ColorMenu
from app.ui.command_palette import CommandPalette
from app.ui.document_page import DocumentPage
from app.ui.error_reporting import ErrorReporter, ProvokedError
from app.ui.favourites_bar import FavouritesBar
from app.ui.features import (
    FEATURES,
    GROUP_STARTS,
    MODES,
    Feature,
    Mode,
    features_of,
    translate,
)
from app.ui.library_window import LibraryWindow
from app.ui.link_dialog import LinkDialog
from app.ui.margin_dialog import MarginChoice, MarginDialog
from app.ui.margin_dialog import remember as remember_margin
from app.ui.margin_dialog import remembered as remembered_margin
from app.ui.my_data_dialog import MyDataDialog, datum_names
from app.ui.page_box import PageBox
from app.ui.password_dialog import PasswordDialog
from app.ui.pdf_view import SIGN_TOOL, PdfView
from app.ui.print_dialog import PrintChoices, PrintDialog
from app.ui.print_run import PrintRun
from app.ui.recognize_again_dialog import RecognizeAgainDialog
from app.ui.recovery_dialog import RecoveryDialog
from app.ui.search_panel import SearchPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.shape_icons import shape_icon
from app.ui.side_by_side import BesideArea
from app.ui.side_panel import SidePanel, Tab
from app.ui.sign_dialog import CertificateDialog
from app.ui.signature_dialog import SignatureDialog
from app.ui.text_recognition import TextRecognition
from app.ui.theme import PAPER_SETTING, THEME_SETTING, Paper, Theme, apply_theme
from app.ui.unsaved_dialog import CANCEL, DISCARD, SAVE, UnsavedDialog
from app.ui.updater import UpdateBanner, Updater
from app.ui.versions_dialog import RESTORE, VIEW, VersionsDialog
from app.ui.when import when_text
from app.ui.zoom_control import ZoomControl


def signed_name(path: Path) -> Path:
    """The name proposed for a document just signed: "contrato-firmado.pdf"."""
    return path.with_name(f"{path.stem}-firmado.pdf")


CERTIFICATE_SETTING = "firma/certificado"  # the certificate of Windows used last
CERTIFICATE_FILE_SETTING = "firma/archivo"  # the certificate file used last
DATE_SETTING = "firma/fecha"  # whether the date is written under the signature
# Big enough to press comfortably with a finger on a touch screen.
MIN_BUTTON_HEIGHT = 40
# The row with the menu, the modes and the search box is a little lower.
BAR_BUTTON_HEIGHT = 34
STATUS_MESSAGE_MS = 6000
STATUS_MESSAGE_LONG_MS = 12000  # a message with more to read
LAST_FOLDER_SETTING = "ultima_carpeta"
WELCOME_RECENT = 5  # recent documents offered on the welcome page
# The tools of each mode with their names under the drawing, or only the drawings.
TOOLBAR_SETTING = "barra_herramientas"
SAVE_AS, SAVE_HERE = "save_as", "save_here"  # answers to a warning before saving
# Something of another program taken away, too big to copy: saving makes it
# impossible to undo. Asked every time, whatever the settings say.
FOREIGN_LOST = "foreign_lost"
RESTORE_TRIES = 6
RESTORE_PAUSE = 0.25  # seconds
PLACE_DELAY_MS = 2000  # how long after turning the page it is remembered
MARKERS_SETTING = "rotuladores"  # colour and opacity of each marking tool
FAVOURITES_SETTING = "favoritas"  # the favourite tools, in the order of their bar
TOOLBAR_NAMES, TOOLBAR_ICONS = "nombres", "iconos"
TOP_SEARCH_WIDTH = 280
SIDE_PANEL_SETTING = "panel_lateral"  # "", "miniaturas", "indice" or "anotaciones"
SUMMARY_FORMAT_SETTING = "resumen/formato"  # "pdf" or "docx": the last one chosen
SHEET_SETTING = "hoja_nueva"  # the kind of sheet Insertar hoja puts: the last one chosen


class MainWindow(QMainWindow):
    """Top-level window of the program."""

    # Off in the automatic tests, whose documents all live in temporary folders.
    warn_about_temporary_folders = True

    def __init__(
        self, settings: Settings | None = None, reporter: ErrorReporter | None = None
    ) -> None:
        super().__init__()
        self.settings = settings if settings is not None else Settings()
        color_naming.install(self.settings)  # the user's own names for colours
        self.reporter = reporter if reporter is not None else ErrorReporter(parent=self)
        # Tests turn this off so that message boxes do not block them.
        self.show_problem_dialogs = True
        self.history = History(self.settings)
        self._told_settings_failed = False
        self._restoring = False  # True while the tabs of the last time are coming back
        self._absent_tabs: list[Path] = self.history.absent_tabs()
        # Every change is written down here at once, apart from the PDF, next to
        # the settings (so the portable version keeps it in its own folder).
        self.journal = Journal(self.settings.path.parent / JOURNAL_FOLDER)
        # Pages recognised in a run that has not ended yet (a power cut).
        self.ocr_cache = OcrCache(self.settings.path.parent / OCR_CACHE_FOLDER)
        # The safety net under "Guardar": how each PDF was before it was saved.
        self.versions = Versions(self.settings.path.parent / VERSIONS_FOLDER)
        # Saving by itself, only for whoever turns it on: after a while without
        # changes, never while editing.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave)
        self._front_page: DocumentPage | None = None  # the one a tab change leaves
        self.apply_save_settings()
        self._version_not_kept = False
        self._versioned: set[str] = set()  # files whose version was kept in this session
        # For the tests: the answer to a warning before saving, without the question
        # (SAVE_AS, SAVE_HERE or CANCEL).
        self.save_warning_answer: str | None = None
        # For the tests: the answer to "restore this version?" without the question.
        self.restore_answer: bool | None = None
        # For the tests: the answer to "recover the changes?" without the question.
        self.recovery_answer: bool | None = None
        # The page being read is remembered a moment after it changes, not only
        # when closing: after a power cut the document comes back where it was.
        self._place_timer = QTimer(self)
        self._place_timer.setSingleShot(True)
        self._place_timer.setInterval(PLACE_DELAY_MS)
        self._place_timer.timeout.connect(self._remember_current_place)
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
        self._build_tool_keys()
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
        # Two documents at once: the one in front on the left, another beside it.
        self.beside = BesideArea()
        self.beside.close_asked.connect(self.stop_beside)
        self.beside.link_here.connect(self.finish_link)
        self.beside.link_cancelled.connect(self.cancel_link)
        self._pending_link: tuple | None = None  # (source, words area, target)
        self.halves = QSplitter(Qt.Orientation.Horizontal)
        self.halves.setObjectName("documentHalves")
        self.halves.setChildrenCollapsible(False)
        self.halves.setHandleWidth(4)
        self.halves.addWidget(self.pages)
        self.halves.addWidget(self.beside)
        self.beside.hide()
        central_layout.addWidget(self.halves, 1)
        self.setCentralWidget(central)
        # A click in one half makes the tools act on its document.
        QApplication.instance().focusChanged.connect(self._focus_moved)
        # A page kept ready for the next document that is opened. While nothing
        # is open it also stands in as "the current document" (an empty one).
        self._spare = self._new_page()
        self._warm_spares = False
        self.update_banner.update_wanted.connect(self.update_now)
        self.update_banner.cancel_wanted.connect(self.updater.cancel)
        self.update_banner.skip_wanted.connect(self._skip_new_version)
        self.document_tabs.currentChanged.connect(self._tab_changed)
        self.document_tabs.tabCloseRequested.connect(self.close_document)
        self.document_tabs.beside_asked.connect(self._beside_from_tab)
        self.document_tabs.tabMoved.connect(self._tab_moved)

        self.search_action = QAction(self.tr("Buscar en el documento"), self)
        self.search_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Find))
        self.search_action.triggered.connect(self.show_search)
        self.addAction(self.search_action)

        self.statusBar().setSizeGripEnabled(True)
        self.page_box = PageBox(self.pdf_view)
        self.page_box.go_to.connect(lambda: self.pdf_view.setFocus())
        self.page_box.told.connect(
            lambda text: self.statusBar().showMessage(text, STATUS_MESSAGE_MS)
        )
        self.speed_label = QLabel()
        self.speed_label.setObjectName("speedLabel")
        self.speed_label.setVisible(running_from_source_or_test_build())
        # Always in sight: whether the document in front is saved.
        self.save_state_label = QLabel()
        self.save_state_label.setObjectName("saveStateLabel")
        self.save_state_label.setAccessibleName(self.tr("Estado de guardado"))
        self.statusBar().addPermanentWidget(self.save_state_label)
        # For the tests: the answer to "save the changes?" without showing the question.
        self.unsaved_answer: str | None = None
        # For the tests: the pages to recognise again, without asking.
        self.recognize_again_answer: list[int] | None = None
        self.margin_answer: MarginChoice | None = None  # the tests answer without asking
        self.summary_target: Path | None = None  # the tests choose the file without asking
        self.library: LibraryWindow | None = None
        self.library_asks_folder = True  # the first time, it asks for the folder at once
        self.open_exported = True  # a summary made is opened (not in the tests)
        # For the tests: the other document of a link and where, without the dialog;
        # and where a document that is not found is now ("" = not known).
        self.link_answer: tuple[Path, str] | None = None
        self.where_is_answer: Path | str | None = None
        # For the tests: «Mis datos» as written in the dialog, without showing it.
        self.my_data_answer: MyData | None = None
        self.my_data_menu: QMenu | None = None
        self.stamps_menu: QMenu | None = None
        # For the tests: the picture made (b"" to cancel), and the answer to
        # "¿Quitar tu firma?".
        self.signature_answer: bytes | None = None
        self.forget_signature_answer: bool | None = None
        self.signature_menu: QMenu | None = None
        # For the tests: "copy", "same" or "" (cancel) when saving what was just
        # signed, and what the "Guardar como" window answers, given its suggestion.
        self.signed_save_answer: str | None = None
        # For the tests, signing with a certificate: whether to save first, the
        # signer chosen, and where the signed document goes (given the proposal).
        self.sign_save_answer: bool | None = None
        self.signer_answer = None
        self.sign_target_answer = None
        # For the tests: whether to sign without a timestamp when the server fails.
        self.timestamp_failed_answer: bool | None = None
        self._sign_when_saved: DocumentPage | None = None
        self.save_as_answer = None
        self.new_stamp_answer: str | None = None  # the tests answer without asking
        self._saving_to_close: list[DocumentPage] = []  # being saved before closing
        self._after_saving = None  # what to do once they are all saved
        self.statusBar().addPermanentWidget(self.speed_label)
        self.statusBar().addPermanentWidget(self.page_box)
        self.zoom_control = ZoomControl(self.pdf_view)
        self.statusBar().addPermanentWidget(self.zoom_control)

        # Functions that already work. Every other one says it is not built yet.
        self.feature_handlers = {
            "open": self.choose_and_open,
            "search": self.show_search,
            "sign_certificate": self.sign_with_certificate,
            "ocr": self.recognize_text,
            "ocr_again": self.recognize_again,
            "zoom_in": lambda: self.pdf_view.zoom_in(),
            "zoom_out": lambda: self.pdf_view.zoom_out(),
            "fit_comfortable": lambda: self.pdf_view.fit_comfortable(),
            "fit_width": lambda: self.pdf_view.fit_width(),
            "fit_page": lambda: self.pdf_view.fit_page(),
            "rotate_view": lambda: self.pdf_view.rotate_view(),
            "fullscreen": self.toggle_full_screen,
            "go_to_page": self.go_to_page,
            "go_to_article": lambda: self.go_to_page(place=True),
            "bookmark": self.add_bookmark,
            "copy": self.copy,
            "thumbnails": lambda: self.toggle_side_panel(Tab.THUMBNAILS),
            "outline": lambda: self.toggle_side_panel(Tab.OUTLINE),
            "annotations": lambda: self.toggle_side_panel(Tab.ANNOTATIONS),
            "reading_mode": self.toggle_reading_mode,
            "print": self.print_document,
            "highlight": lambda: self.use_marker(HIGHLIGHT),
            "underline": lambda: self.use_marker(UNDERLINE),
            "strikeout": lambda: self.use_marker(STRIKEOUT),
            "note": lambda: self.use_writing_tool(NOTE),
            "text_box": lambda: self.use_writing_tool(TEXT_BOX),
            # On a document without fields (a scan, a letter) one writes anywhere:
            # it is the same text, in the mode of filling.
            "type_text": lambda: self.use_writing_tool(TEXT_BOX),
            "draw": lambda: self.use_writing_tool(DRAW),
            "shapes": lambda: self.use_writing_tool(SHAPE_TOOL),
            "eraser": lambda: self.use_writing_tool(ERASER),
            "hide_annotations": self.toggle_annotations,
            "review": self.toggle_review,
            "summary": self.export_summary,
            "beside": self.toggle_beside,
            "library": self.show_library,
            "link": self.link_selection,
            "fill_form": self.fill_form,
            "my_data": self.show_my_data,
            "my_data_edit": self.edit_my_data,
            "stamps": self.show_stamps,
            "sign_drawn": self.show_signature,
            "my_signature": lambda: self.make_signature(my_signature.SIGNATURE),
            "initials_everywhere": self.initials_everywhere,
            "margins": self.add_margin,
            "undo": self.undo,
            "redo": self.redo,
            "save": self.save_document,
            "save_as": self.save_document_as,
            "insert_sheet": self.insert_sheet,
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

    def _build_tool_keys(self) -> None:
        """A key for each tool and a digit for each favourite, while the page
        has the keyboard (every page gets them in ``_new_page``)."""
        self.tool_key_actions: dict[str, QAction] = {}
        for feature_id in TOOL_KEYS:
            action = QAction(translate(self._feature_named(feature_id).name), self)
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            action.triggered.connect(lambda _checked=False, f=feature_id: self.use_tool_key(f))
            self.tool_key_actions[feature_id] = action
        self.favourite_key_actions: list[QAction] = []
        for index, _key in enumerate(FAVOURITE_KEYS):
            action = QAction(self.tr("Herramienta favorita {0}").format(index + 1), self)
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            action.triggered.connect(lambda _checked=False, i=index: self.use_favourite_key(i))
            self.favourite_key_actions.append(action)
        self.apply_tool_keys()

    def apply_tool_keys(self) -> None:
        """Follow what the settings say now about the keys of the tools."""
        wanted = tool_keys_wanted(self.settings)
        for feature_id, key in TOOL_KEYS.items():
            self.tool_key_actions[feature_id].setShortcut(QKeySequence(key if wanted else ""))
            tip = translate(self._feature_named(feature_id).description)
            # The key is said where the tool is, so nobody has to learn a list.
            tip = self.tr("{0} (tecla {1})").format(tip, key) if wanted else tip
            self.feature_actions[feature_id].setToolTip(tip)
        for action, key in zip(self.favourite_key_actions, FAVOURITE_KEYS, strict=True):
            action.setShortcut(QKeySequence(key if wanted else ""))

    def use_tool_key(self, feature_id: str) -> None:
        """The key of a tool was pressed on the page: the same as its button,
        which is shown (the tools of Estudiar come to sight)."""
        if self.documents and self._mode is not Mode.STUDY:
            self.set_mode(Mode.STUDY)
        self.feature_handlers[feature_id]()

    def use_favourite_key(self, index: int) -> None:
        if index >= len(self.favourites):
            return
        if self.documents and self._mode is not Mode.STUDY:
            self.set_mode(Mode.STUDY)
        self.use_favourite(index)

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
        self._build_color_menus()
        self._build_sheet_menu()
        self._build_recognition_menu()
        self._build_favourites_bar()
        self.set_toolbar_icons_only(
            self.settings.get(TOOLBAR_SETTING) == TOOLBAR_ICONS, remember=False
        )

    def _build_color_menus(self) -> None:
        """Each marker carries, in the arrow next to it, its colour and opacity;
        the notes their colour; the text its colour, font and size; the pen
        and the shapes their colour, thickness and opacity."""
        self.marker_styles = MarkerStyles.from_setting(self.settings.get(MARKERS_SETTING))
        self.color_menus: dict[str, ColorMenu] = {}
        self.favourite_actions: dict[str, QAction] = {}
        toolbar = self.mode_toolbars[Mode.STUDY]
        for kind in STYLED_KINDS:
            action = self.feature_actions[kind]
            name = translate(self._feature_named(kind).name)
            menu = ColorMenu(name, self, with_opacity=kind in SEE_THROUGH_KINDS)
            if kind == TEXT_BOX:
                self._add_text_choices(menu)
            if kind == SHAPE_TOOL:
                self._add_shape_choices(menu)
            if kind in LINE_KINDS:
                self._add_width_choices(menu, kind)
            menu.addSeparator()
            keep = menu.addAction(self.tr("Guardar en favoritas"))
            keep.setToolTip(
                self.tr("Deja esta herramienta, tal como está ahora, en la barra de favoritas")
            )
            keep.triggered.connect(lambda _checked=False, k=kind: self.add_favourite(k))
            self.favourite_actions[kind] = keep
            menu.color_chosen.connect(lambda color, k=kind: self.set_marker_color(k, color))
            menu.opacity_chosen.connect(lambda value, k=kind: self.set_marker_opacity(k, value))
            self.color_menus[kind] = menu
            button = toolbar.widgetForAction(action)
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            button.setProperty("withMenu", True)  # the style sheet makes room for the arrow
        self._show_marker_styles()

    def _build_sheet_menu(self) -> None:
        """Insertar hoja puts the kind of sheet chosen last; the arrow next to
        it offers the three."""
        menu = QMenu(self)
        menu.setObjectName("sheetMenu")
        self.sheet_actions: dict[str, QAction] = {}
        group = QActionGroup(menu)
        for kind, name, tip in (
            (sheets.PLAIN, self.tr("En blanco"), self.tr("Una hoja lisa")),
            (sheets.RULED, self.tr("De rayas"), self.tr("Con renglones, como un cuaderno")),
            (sheets.SQUARED, self.tr("Cuadriculada"), self.tr("Cuadrícula de 5 mm, para esquemas")),
        ):
            action = menu.addAction(name)
            action.setToolTip(tip)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, k=kind: self.insert_sheet(k))
            group.addAction(action)
            self.sheet_actions[kind] = action
        menu.setToolTipsVisible(True)
        self.sheet_actions[self.sheet_kind].setChecked(True)
        button = self.mode_toolbars[Mode.STUDY].widgetForAction(
            self.feature_actions["insert_sheet"]
        )
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.setProperty("withMenu", True)

    def _build_recognition_menu(self) -> None:
        """Reconocer texto reads the pages without text; the arrow next to it
        also offers to recognise again pages that already have it."""
        menu = QMenu(self)
        menu.setObjectName("recognitionMenu")
        new = menu.addAction(self.tr("Reconocer las páginas escaneadas sin texto"))
        new.triggered.connect(lambda _checked=False: self.recognize_text())
        menu.addAction(self.feature_actions["ocr_again"])
        menu.setToolTipsVisible(True)
        button = self.mode_toolbars[Mode.STUDY].widgetForAction(self.feature_actions["ocr"])
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.setProperty("withMenu", True)

    @property
    def sheet_kind(self) -> str:
        """The kind of sheet Insertar hoja puts (the last one chosen)."""
        kind = self.settings.get(SHEET_SETTING)
        return kind if kind in sheets.SHEETS else sheets.DEFAULT_SHEET

    def insert_sheet(self, kind: str | None = None) -> bool:
        """Put a sheet to write on after the page being read."""
        if kind is not None and kind in sheets.SHEETS:
            self.settings.set(SHEET_SETTING, kind)
            self.sheet_actions[kind].setChecked(True)
        if not self.pdf_view.page_count:
            self.statusBar().showMessage(
                self.tr("Abre un documento para añadirle hojas."), STATUS_MESSAGE_MS
            )
            return False
        page = self.pdf_view.current_page
        if not self.pdf_view.insert_sheet(self.sheet_kind):
            return False
        self.statusBar().showMessage(
            self.tr("Hoja añadida después de la página {0}. Deshacer (Ctrl+Z) la quita.").format(
                max(page, 0) + 1
            ),
            STATUS_MESSAGE_MS,
        )
        return True

    # ---- favourite tools ---------------------------------------------------

    def _build_favourites_bar(self) -> None:
        """A second, thinner bar in the mode Estudiar, with the favourite tools.
        It only takes room once there is one."""
        self.favourites = Favourites.from_setting(self.settings.get(FAVOURITES_SETTING))
        # For the tests: what the question for a name answers (None: cancelled).
        self.ask_favourite_name = self._ask_favourite_name
        bar = self.favourites_bar = FavouritesBar(self)
        bar.used.connect(self.use_favourite)
        bar.removed.connect(self.remove_favourite)
        bar.rename_asked.connect(self.rename_favourite)
        bar.moved.connect(self.move_favourite)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self._show_favourites()

    def favourite_name(self, favourite) -> str:
        """The name of a favourite: the one it was given or what it is."""
        if favourite.name:
            return favourite.name
        kind = favourite.kind
        tool = translate(self._feature_named(kind).name)
        if kind == SHAPE_TOOL:
            tool = self.shape_actions[favourite.shape].text()
        parts = [tool, self.color_menus[kind].swatch_name(favourite.color).lower()]
        if kind == SHAPE_TOOL and favourite.fill:
            parts.append(self.tr("relleno"))
        if kind == SHAPE_TOOL and favourite.dashed:
            parts.append(self.tr("discontinua"))
        named = self.width_actions.get(kind, {})
        if favourite.width in named and favourite.width != WIDTHS[1]:
            parts.append(named[favourite.width].text().lower())
        if kind in SEE_THROUGH_KINDS and favourite.opacity < 0.995:
            parts.append(f"{round(favourite.opacity * 100)} %")
        if kind == TEXT_BOX:
            parts.append(f"{favourite.size:g}")
        return " · ".join(parts)

    def _current_favourite(self) -> int:
        """The favourite that is the tool in hand as it is set now, or -1."""
        if not hasattr(self, "documents"):
            return -1  # the window is still being built
        tool = self.pdf_view.markup_tool
        if tool not in STYLED_KINDS:
            return -1
        return self.favourites.find(favourite_of(self.marker_styles, tool))

    def _show_favourites(self) -> None:
        names = [self.favourite_name(favourite) for favourite in self.favourites]
        self.favourites_bar.show_favourites(self.favourites, names, self._current_favourite())
        self._place_favourites_bar()

    def _place_favourites_bar(self) -> None:
        if hasattr(self, "favourites_bar"):
            in_study = getattr(self, "_mode", None) is Mode.STUDY
            self.favourites_bar.setVisible(
                in_study and not self._full_screen and len(self.favourites) > 0
            )

    def _favourites_changed(self) -> None:
        self.settings.set(FAVOURITES_SETTING, self.favourites.to_setting())
        self._show_favourites()

    def add_favourite(self, kind: str) -> int:
        """Keep a tool, as it is set now, in the bar of favourites.

        Returns where it is in the bar, or -1 if the bar is full.
        """
        favourite = favourite_of(self.marker_styles, kind)
        already = self.favourites.find(favourite)
        index = self.favourites.add(favourite)
        if index < 0:
            message = self.tr(
                "La barra de favoritas está llena ({0}). Quita alguna con el botón derecho."
            ).format(MAX_FAVOURITES)
        elif already >= 0:
            message = self.tr("Ya estaba en favoritas: {0}.").format(self.favourite_name(favourite))
        else:
            message = self.tr("Guardada en favoritas: {0}.").format(self.favourite_name(favourite))
            self._favourites_changed()
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)
        return index

    def use_favourite(self, index: int) -> None:
        """Set a tool the way a favourite has it and take it in hand."""
        if not 0 <= index < len(self.favourites):
            return
        favourite = self.favourites[index]
        apply_to(self.marker_styles, favourite)
        # Choosing its colour is what takes the tool (or marks the selected text).
        self.set_marker_color(favourite.kind, favourite.color)
        self.favourites_bar.set_current(self._current_favourite())

    def remove_favourite(self, index: int) -> None:
        if self.favourites.remove(index):
            self._favourites_changed()

    def move_favourite(self, index: int, by: int) -> None:
        if self.favourites.move(index, by) != index:
            self._favourites_changed()

    def rename_favourite(self, index: int) -> None:
        """Ask for a name for a favourite. An empty one gives back its description."""
        if not 0 <= index < len(self.favourites):
            return
        name = self.ask_favourite_name(self.favourite_name(self.favourites[index]))
        if name is not None and self.favourites.rename(index, name):
            self._favourites_changed()

    def _ask_favourite_name(self, current: str) -> str | None:
        name, accepted = QInputDialog.getText(
            self,
            self.tr("Nombre de la favorita"),
            self.tr("Nombre (vacío: el que pone el programa):"),
            text=current,
        )
        return name if accepted else None

    def _add_text_choices(self, menu: ColorMenu) -> None:
        """Font and size of the text written on the page, under its colours."""
        menu.addSeparator()
        fonts = menu.addMenu(self.tr("Tipo de letra"))
        self.text_font_actions: dict[str, QAction] = {}
        group = QActionGroup(fonts)
        for font, name in (
            (SANS, self.tr("Sin remates (como Arial)")),
            (SERIF, self.tr("Con remates (como Times)")),
            (MONO, self.tr("Máquina de escribir (como Courier)")),
        ):
            action = fonts.addAction(name)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, f=font: self.set_text_font(f))
            group.addAction(action)
            self.text_font_actions[font] = action
        sizes = menu.addMenu(self.tr("Tamaño de letra"))
        self.text_size_actions: dict[int, QAction] = {}
        group = QActionGroup(sizes)
        for size in TEXT_SIZES:
            action = sizes.addAction(str(size))
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, n=size: self.set_text_size(n))
            group.addAction(action)
            self.text_size_actions[size] = action

    def _add_shape_choices(self, menu: ColorMenu) -> None:
        """Which shape is drawn: at the top of the menu of the shapes."""
        self.shape_actions: dict[str, QAction] = {}
        group = QActionGroup(menu)
        first = menu.actions()[0]
        for shape, name in (
            (ARROW, self.tr("Flecha")),
            (DOUBLE_ARROW, self.tr("Flecha doble")),
            (ELBOW, self.tr("Flecha en codo")),
            (LINE, self.tr("Línea")),
            (BOX, self.tr("Recuadro")),
            (OVAL, self.tr("Óvalo")),
            (TRIANGLE, self.tr("Triángulo")),
            (RHOMBUS, self.tr("Rombo")),
            (BRACE, self.tr("Llave { }")),
        ):
            action = QAction(shape_icon(shape), name, menu)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, k=shape: self.set_shape(k))
            group.addAction(action)
            menu.insertAction(first, action)
            self.shape_actions[shape] = action
        self.shape_actions[BRACE].setToolTip(
            self.tr("Arrastrando hacia la derecha sale {, hacia la izquierda }")
        )
        menu.insertSeparator(first)
        self.shape_fill_action = QAction(self.tr("Relleno claro"), menu)
        self.shape_fill_action.setCheckable(True)
        self.shape_fill_action.setToolTip(
            self.tr(
                "Recuadros, óvalos, triángulos y rombos, rellenos de un tono claro que deja leer"
            )
        )
        self.shape_fill_action.toggled.connect(self.set_shape_fill)
        menu.insertAction(first, self.shape_fill_action)
        self.shape_dashed_action = QAction(self.tr("Línea discontinua"), menu)
        self.shape_dashed_action.setCheckable(True)
        self.shape_dashed_action.toggled.connect(self.set_shape_dashed)
        menu.insertAction(first, self.shape_dashed_action)
        note = QAction(self.tr("Con Mayús: líneas rectas, cuadrados y círculos"), menu)
        note.setEnabled(False)
        menu.insertAction(first, note)
        menu.insertSeparator(first)

    def _add_width_choices(self, menu: ColorMenu, kind: str) -> None:
        """How thick the line is, under the colours."""
        if not hasattr(self, "width_actions"):
            self.width_actions: dict[str, dict[float, QAction]] = {}
        menu.addSeparator()
        widths = menu.addMenu(self.tr("Grosor"))
        group = QActionGroup(widths)
        names = (self.tr("Fino"), self.tr("Normal"), self.tr("Grueso"), self.tr("Muy grueso"))
        self.width_actions[kind] = {}
        for width, name in zip(WIDTHS, names, strict=True):
            action = widths.addAction(name)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, k=kind, w=width: self.set_line_width(k, w)
            )
            group.addAction(action)
            self.width_actions[kind][width] = action

    def set_shape(self, shape: str) -> None:
        """Choose the shape that is drawn (arrow, line, box or oval) and take it."""
        self.marker_styles.set_shape(shape)
        self._line_style_chosen(SHAPE_TOOL)

    def set_shape_fill(self, fill: bool) -> None:
        """Fill the closed shapes with a light tone, or not."""
        if fill != self.marker_styles.shape_fill:
            self.marker_styles.set_shape_fill(fill)
            self._line_style_chosen(SHAPE_TOOL)

    def set_shape_dashed(self, dashed: bool) -> None:
        """Draw the shapes with a dashed line, or not."""
        if dashed != self.marker_styles.shape_dashed:
            self.marker_styles.set_shape_dashed(dashed)
            self._line_style_chosen(SHAPE_TOOL)

    def set_line_width(self, kind: str, width: float) -> None:
        """Choose how thick the pen or the shapes draw, and take that tool."""
        self.marker_styles.set_width(kind, width)
        self._line_style_chosen(kind)

    def _line_style_chosen(self, kind: str) -> None:
        self.settings.set(MARKERS_SETTING, self.marker_styles.to_setting())
        self._show_marker_styles()
        if self.pdf_view.page_count and self.pdf_view.markup_tool != kind:
            self.use_writing_tool(kind)

    def set_text_font(self, font: str) -> None:
        self.marker_styles.set_text_font(font)
        self._text_style_chosen()

    def set_text_size(self, size: float) -> None:
        self.marker_styles.set_text_size(size)
        self._text_style_chosen()

    def set_text_bold(self, bold: bool) -> None:
        self.marker_styles.set_text_bold(bold)
        self._text_style_chosen()

    def text_style_used(self, look: dict) -> None:
        """The look given to a text while writing it is the one of the next texts."""
        if "color" in look:
            self.marker_styles.set_color(TEXT_BOX, look["color"])
        if "size" in look:
            self.marker_styles.set_text_size(look["size"])
        if "bold" in look:
            self.marker_styles.set_text_bold(look["bold"])
        self.settings.set(MARKERS_SETTING, self.marker_styles.to_setting())
        self._show_marker_styles()

    def _text_style_chosen(self) -> None:
        self.settings.set(MARKERS_SETTING, self.marker_styles.to_setting())
        self._show_marker_styles()
        if self.pdf_view.page_count and self.pdf_view.markup_tool != TEXT_BOX:
            self.use_writing_tool(TEXT_BOX)

    def _show_marker_styles(self) -> None:
        """Put the styles in the buttons, the menus and every open document."""
        for font, action in self.text_font_actions.items():
            action.setChecked(font == self.marker_styles.text_font)
        for size, action in self.text_size_actions.items():
            action.setChecked(size == self.marker_styles.text_size)
        for shape, action in self.shape_actions.items():
            action.setChecked(shape == self.marker_styles.shape)
        for action, on in (
            (self.shape_fill_action, self.marker_styles.shape_fill),
            (self.shape_dashed_action, self.marker_styles.shape_dashed),
        ):
            action.blockSignals(True)
            action.setChecked(on)
            action.blockSignals(False)
        for kind, actions in self.width_actions.items():
            for width, action in actions.items():
                action.setChecked(width == self.marker_styles.width_of(kind))
        for kind in STYLED_KINDS:
            style = self.marker_styles.of(kind)
            name = translate(self._feature_named(kind).name)
            self.feature_actions[kind].setIcon(icons.marker_icon(kind, style.color))
            menu = self.color_menus[kind]
            menu.set_recent(self.marker_styles.recent)
            menu.set_style(style.color, style.opacity)
            button = self.mode_toolbars[Mode.STUDY].widgetForAction(self.feature_actions[kind])
            button.setAccessibleDescription(
                self.tr("Color de {0}: {1}. La flecha de al lado lo cambia.").format(
                    name, menu.swatch_name(style.color)
                )
            )
        if hasattr(self, "favourites_bar"):
            self.favourites_bar.set_current(self._current_favourite())
        # While the window is being built there are no documents yet.
        pages = [*getattr(self, "documents", []), getattr(self, "_spare", None)]
        for page in pages:
            if page is not None:
                self._give_marker_styles(page.view)

    def _give_marker_styles(self, view: PdfView) -> None:
        for kind in MARKUP_KINDS:
            style = self.marker_styles.of(kind)
            view.markup_colors[kind] = style.color
            view.markup_opacity[kind] = style.opacity
        view.note_color = self.marker_styles.of(NOTE).color
        look = {
            "color": self.marker_styles.of(TEXT_BOX).color,
            "font": self.marker_styles.text_font,
            "size": self.marker_styles.text_size,
            "bold": self.marker_styles.text_bold,
        }
        before = {
            "color": view.text_color,
            "font": view.text_font,
            "size": view.text_size,
            "bold": view.text_bold,
        }
        view.text_color, view.text_font = look["color"], look["font"]
        view.text_size, view.text_bold = look["size"], look["bold"]
        changed = {name: value for name, value in look.items() if value != before[name]}
        if changed:
            view.text_style_given(**changed)  # a text being written takes it at once
        pen, shapes = self.marker_styles.of(DRAW), self.marker_styles.of(SHAPE_TOOL)
        view.draw_color, view.draw_opacity = pen.color, pen.opacity
        view.draw_width = self.marker_styles.width_of(DRAW)
        view.shape_color, view.shape_opacity = shapes.color, shapes.opacity
        view.shape_width = self.marker_styles.width_of(SHAPE_TOOL)
        view.shape_kind = self.marker_styles.shape
        view.shape_fill = self.marker_styles.shape_fill
        view.shape_dashed = self.marker_styles.shape_dashed

    def set_marker_color(self, kind: str, color: tuple[float, float, float]) -> None:
        """Choose the colour of a marking tool and use it at once.

        Like choosing a marker from the case: the selected text gets marked
        with it or, with nothing selected, the marker stays in hand.
        """
        self.marker_styles.set_color(kind, color)
        self.settings.set(MARKERS_SETTING, self.marker_styles.to_setting())
        self._show_marker_styles()
        view = self.pdf_view
        if view.page_count == 0:
            return
        if kind not in MARKUP_KINDS:
            if view.markup_tool != kind:
                self.use_writing_tool(kind)
        elif view.has_selection:
            view.mark_selection(kind)
        elif view.markup_tool != kind:
            self.use_marker(kind)
        self._refresh_edit_actions()

    def set_marker_opacity(self, kind: str, opacity: float) -> None:
        self.marker_styles.set_opacity(kind, opacity)
        self.settings.set(MARKERS_SETTING, self.marker_styles.to_setting())
        self._show_marker_styles()

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
        self.favourites_bar.set_icons_only(icons_only)
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
        self.revert_action = QAction(self.tr("&Volver a como estaba al abrirlo"), self)
        self.revert_action.setStatusTip(
            self.tr("Quitar de una vez todos los cambios hechos desde que se abrió el documento")
        )
        self.revert_action.setEnabled(False)
        self.revert_action.triggered.connect(lambda _checked=False: self.revert_document())
        file_menu.addAction(self.revert_action)
        self.print_action = QAction(self.tr("&Imprimir…"), self)
        self.print_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Print))
        self.print_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.print_action.triggered.connect(lambda _checked=False: self.print_document())
        self.addAction(self.print_action)
        file_menu.addAction(self.print_action)
        file_menu.addSeparator()
        self.versions_action = QAction(self.tr("Versiones &anteriores…"), self)
        self.versions_action.setStatusTip(
            self.tr("Ver o restaurar cómo estaba el documento antes de guardarlo")
        )
        self.versions_action.setEnabled(False)
        self.versions_action.triggered.connect(lambda _checked=False: self.choose_version())
        file_menu.addAction(self.versions_action)
        self.recover_discarded_action = QAction(self.tr("Recuperar cambios &descartados…"), self)
        self.recover_discarded_action.setStatusTip(
            self.tr("Volver a poner cambios que no se guardaron al cerrar")
        )
        self.recover_discarded_action.triggered.connect(
            lambda _checked=False: self.choose_discarded_changes()
        )
        file_menu.addAction(self.recover_discarded_action)
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
        self.copy_action.triggered.connect(lambda _checked=False: self.copy())
        edit_menu.addAction(self.copy_action)
        self.paste_action = QAction(self.tr("&Pegar anotación"), self)
        self.paste_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Paste))
        self.paste_action.triggered.connect(lambda _checked=False: self.paste())
        edit_menu.addAction(self.paste_action)
        self.duplicate_action = QAction(self.tr("D&uplicar anotación"), self)
        self.duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        self.duplicate_action.triggered.connect(lambda _checked=False: self.duplicate_picked())
        edit_menu.addAction(self.duplicate_action)
        self.delete_action = QAction(self.tr("&Borrar anotación"), self)
        self.delete_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self.delete_action.triggered.connect(lambda _checked=False: self.delete_picked())
        edit_menu.addAction(self.delete_action)
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
        self.bookmark_action = QAction(self.tr("Poner un &marcador aquí"), self)
        self.bookmark_action.setShortcut(QKeySequence("Ctrl+M"))
        self.bookmark_action.triggered.connect(lambda _checked=False: self.add_bookmark())
        self.rotate_view_action = QAction(self.tr("&Girar vista"), self)
        self.rotate_view_action.setShortcut(QKeySequence("Ctrl+R"))
        self.rotate_view_action.triggered.connect(
            lambda _checked=False: self.pdf_view.rotate_view()
        )
        self.side_panel_action = QAction(
            self.tr("Panel &lateral (miniaturas, índice y anotaciones)"), self
        )
        self.side_panel_action.setCheckable(True)
        self.side_panel_action.setShortcut(QKeySequence("F4"))
        self.side_panel_action.triggered.connect(lambda _checked=False: self.toggle_side_panel())
        for action in (
            self.side_panel_action,
            self.full_screen_action,
            self.go_to_page_action,
            self.bookmark_action,
            self.rotate_view_action,
        ):
            # They must also answer while the menu bar is hidden (full screen).
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.addAction(action)
            view_menu.addAction(action)

        view_menu.addSeparator()
        view_menu.addAction(self.feature_actions["hide_annotations"])
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
        self._place_favourites_bar()
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
        if self._saving_to_close:
            return  # saving first; the program closes and installs when that is done
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

    def use_writing_tool(self, kind: str) -> None:
        """Notes, text, pen, shapes or eraser: taken in hand, to use on the page.

        With the notes or the text, a click starts one there; the pen and the
        shapes draw while the button is held; the eraser takes away what it is
        passed over. It stays in hand until the button is pressed again (or Esc).
        """
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
        elif view.markup_tool == kind:
            view.set_markup_tool("")
        else:
            view.clear_selection()
            view.set_markup_tool(kind)
            hints = {
                NOTE: self.tr("Haz clic donde quieras la nota (Esc: dejarlo)."),
                TEXT_BOX: self.tr("Haz clic donde quieras escribir (Esc: dejarlo)."),
                DRAW: self.tr("Dibuja sobre la página con el botón pulsado (Esc: dejarlo)."),
                SHAPE_TOOL: self.tr("Arrastra sobre la página para poner la forma (Esc: dejarlo)."),
                ERASER: self.tr(
                    "Pasa por encima de un dibujo, una marca o una nota para borrarlo "
                    "(Esc: dejarlo)."
                ),
            }
            self.statusBar().showMessage(hints[kind], STATUS_MESSAGE_MS)
        self._refresh_edit_actions()

    def copy(self) -> None:
        """Copy the annotation that is picked or, without one, the selected text."""
        view = self.pdf_view
        if view.picked_item() is None:
            view.copy_selection()
        elif not view.copy_picked():
            self.statusBar().showMessage(
                self.tr("Una marca sobre el texto no se puede copiar: va con sus palabras."),
                STATUS_MESSAGE_MS,
            )
        self._refresh_edit_actions()

    def paste(self) -> None:
        """Put the annotation copied last where the pointer is, or on the page in sight."""
        view = self.pdf_view
        pointer = view.viewport().mapFromGlobal(QCursor.pos())
        at = pointer if view.viewport().underMouse() else None
        if not view.paste(at):
            self.statusBar().showMessage(
                self.tr("No hay ninguna anotación copiada."), STATUS_MESSAGE_MS
            )

    def duplicate_picked(self) -> None:
        if not self.pdf_view.duplicate_picked():
            self.statusBar().showMessage(
                self.tr("Elige antes una nota, un texto o un dibujo haciendo clic en él."),
                STATUS_MESSAGE_MS,
            )

    def delete_picked(self) -> None:
        if not self.pdf_view.remove_picked():
            self.statusBar().showMessage(
                self.tr("Elige antes una anotación haciendo clic en ella."), STATUS_MESSAGE_MS
            )

    @staticmethod
    def _feature_named(feature_id: str) -> Feature:
        return next(feature for feature in FEATURES if feature.id == feature_id)

    def undo(self) -> None:
        if not self.pdf_view.undo():
            self.statusBar().showMessage(self.tr("No hay nada que deshacer."), STATUS_MESSAGE_MS)

    def redo(self) -> None:
        if not self.pdf_view.redo():
            self.statusBar().showMessage(self.tr("No hay nada que rehacer."), STATUS_MESSAGE_MS)

    def revert_document(self) -> int:
        """ "Volver a como estaba al abrirlo": take back every change of this session.

        Nothing is lost for good: Rehacer brings them back one by one, and the
        PDF itself does not change until it is saved. Returns how many changes.
        """
        count = self.pdf_view.undo_all()
        if count == 0:
            self.statusBar().showMessage(
                self.tr("El documento ya está como al abrirlo."), STATUS_MESSAGE_MS
            )
        else:
            self.statusBar().showMessage(
                self.tr("Documento como estaba al abrirlo. Rehacer (Ctrl+Y) devuelve los cambios."),
                STATUS_MESSAGE_MS,
            )
        return count

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
        self.revert_action.setEnabled(view.can_undo)
        picked = view.picked_item()
        self.delete_action.setEnabled(picked is not None)
        self.duplicate_action.setEnabled(picked is not None and picked.kind not in MARKUP_KINDS)
        self.paste_action.setEnabled(PdfView.copied is not None and view.page_count > 0)
        if hasattr(self, "favourites_bar"):
            self.favourites_bar.set_current(self._current_favourite())
        for kind in (*STYLED_KINDS, ERASER):
            action = self.feature_actions[kind]
            action.setCheckable(True)
            action.setChecked(view.markup_tool == kind)
        stamping = self.feature_actions["stamps"]
        stamping.setCheckable(True)
        stamping.setChecked(view.markup_tool == "stamp")
        signing = self.feature_actions["sign_drawn"]
        signing.setCheckable(True)
        signing.setChecked(view.markup_tool == SIGN_TOOL)
        typing = self.feature_actions["type_text"]
        typing.setCheckable(True)
        typing.setChecked(view.markup_tool == TEXT_BOX)
        hide = self.feature_actions["hide_annotations"]
        hide.setCheckable(True)
        hide.setChecked(not view.annotations_shown)
        review = self.feature_actions["review"]
        review.setCheckable(True)
        review.setChecked(view.review)

    def add_margin(self) -> bool:
        """Ask where and how much blank room to add for notes, and add it."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        choice = self.margin_answer
        if choice is None:
            dialog = MarginDialog(remembered_margin(self.settings), max(view.current_page, 0), self)
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.choice is None:
                return False
            choice = dialog.choice
        remember_margin(self.settings, choice)
        if not view.add_margin(*choice.room(), every_page=choice.every_page):
            self.statusBar().showMessage(
                self.tr("No cabe más margen: la página sería demasiado grande."), STATUS_MESSAGE_MS
            )
            return False
        return True

    def export_summary(self) -> bool:
        """Ask where to save the summary of the document (PDF or Word) and make it."""
        view = self.pdf_view
        source = view.document_path
        if view.page_count == 0 or source is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        view.finish_writing()  # what is being written goes in too
        target = self.summary_target
        if target is None:
            word = self.settings.get(SUMMARY_FORMAT_SETTING) == "docx"
            pdf_filter = self.tr("Documento PDF (*.pdf)")
            word_filter = self.tr("Documento de Word (*.docx)")
            suggested = source.with_name(
                self.tr("{0} - resumen").format(source.stem) + (".docx" if word else ".pdf")
            )
            chosen, picked = QFileDialog.getSaveFileName(
                self,
                self.tr("Guardar el resumen como"),
                str(suggested),
                f"{pdf_filter};;{word_filter}",
                word_filter if word else pdf_filter,
            )
            if not chosen:
                return False
            target = Path(chosen)
            if target.suffix.lower() not in (".pdf", ".docx"):
                target = target.with_name(
                    target.name + (".docx" if picked == word_filter else ".pdf")
                )
        target = Path(target)
        if target.suffix.lower() not in (".pdf", ".docx"):
            target = target.with_name(target.name + ".pdf")
        if target.resolve() == source.resolve():
            self._show_problem(
                self.tr("Elige otro nombre"),
                self.tr("El resumen no puede ocupar el lugar del documento."),
            )
            return False
        index = self.index_of_document(target)
        if index >= 0 and self.documents[index].view.modified:
            # A summary made before, still open, is replaced only when nothing is lost.
            self._show_problem(
                self.tr("Elige otro nombre"),
                self.tr(
                    "«{0}» está abierto y tiene cambios sin guardar: el resumen no puede "
                    "ocupar su lugar."
                ).format(target.name),
            )
            return False
        self.settings.set(
            SUMMARY_FORMAT_SETTING, "docx" if target.suffix.lower() == ".docx" else "pdf"
        )
        view.summary_listed.connect(
            lambda entries, v=view, t=target: self._summary_came(v, t, entries),
            Qt.ConnectionType.SingleShotConnection,
        )
        self.statusBar().showMessage(self.tr("Preparando el resumen…"), STATUS_MESSAGE_MS)
        view.want_summary()
        return True

    def _summary_came(self, view: PdfView, target: Path, entries: object) -> None:
        """The annotations came back: write the summary where it was asked."""
        if view.document_path is None:
            return
        made = summary_of(
            view.document_path.stem,
            entries,
            color_naming.name_of,
            {
                "title": self.tr("Resumen de {0}"),
                "made": self.tr("Lo subrayado y anotado, página a página."),
                "page": self.tr("Página {0}"),
                HIGHLIGHT: self.tr("Resaltado"),
                UNDERLINE: self.tr("Subrayado"),
                STRIKEOUT: self.tr("Tachado"),
                NOTE: self.tr("Nota"),
                TEXT_BOX: self.tr("Texto"),
                "empty": self.tr("Este documento no tiene nada subrayado ni anotado."),
            },
        )
        index = self.index_of_document(target)
        if index >= 0:
            if self.documents[index].view.modified:
                return  # changed since it was asked: it is not replaced
            self._close_page(self.documents[index])  # the old summary, opened again below
        try:
            if target.suffix.lower() == ".docx":
                write_docx(made, target)
            else:
                write_pdf(made, target)
        except Exception as error:  # a locked file, no room, no permission…
            self._show_problem(
                self.tr("No se ha podido guardar el resumen"),
                self.tr("Prueba con otro nombre o en otra carpeta. ({0})").format(error),
            )
            return
        self.statusBar().showMessage(
            self.tr("Resumen guardado: {0}").format(target.name), STATUS_MESSAGE_MS
        )
        if self.open_exported:
            if target.suffix.lower() == ".pdf":
                self.open_document(target)  # in a tab of its own
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def show_library(self) -> LibraryWindow:
        """The syllabus library: every topic of a folder, searched all at once."""
        if self.library is None:
            self.library = LibraryWindow(self)
        self.library.show()
        self.library.raise_()
        self.library.activateWindow()
        if not self.library.folder and self.library_asks_folder:
            self.library.choose_folder()
        return self.library

    def open_from_library(self, path: str | Path, page: int, query: str = "") -> bool:
        """Open a topic found in the library at the page of the result."""
        if not self.open_document(path):
            return False
        view = self.pdf_view
        if query:
            self.search_box.setText(query)
            self.search_dock.show()
            self.search_panel.box.setText(query)  # its results are marked on the pages
        view.scroll_to_page(page)
        view.setFocus()
        return True

    def toggle_review(self) -> None:
        """Cover what is highlighted and underlined, to try to remember it, or stop."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            self._refresh_edit_actions()
            return
        view.set_review(not view.review)
        if view.review and view.document_path is not None:
            self.history.mark_reviewed(view.document_path)  # the library shows it
        self.statusBar().showMessage(
            self.tr(
                "Modo repaso: lo resaltado y subrayado está tapado. Haz clic en un trozo "
                "para verlo y otra vez para taparlo. Esc para salir."
            )
            if view.review
            else self.tr("Modo repaso terminado."),
            STATUS_MESSAGE_MS,
        )

    def toggle_annotations(self) -> None:
        """See the document clean, or with what was put on it again."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            self._refresh_edit_actions()
            return
        view.set_annotations_shown(not view.annotations_shown)
        self.statusBar().showMessage(
            self.tr("Anotaciones a la vista.")
            if view.annotations_shown
            else self.tr("Anotaciones ocultas: no se ha borrado nada."),
            STATUS_MESSAGE_MS,
        )

    def _edit_failed(self, details: str) -> None:
        if "no text" in details:
            message = self.tr("No se ha podido hacer el cambio: ahí no hay texto que marcar.")
        elif "not in this document" in details:
            # Something of another program taken away and then saved: it is no
            # longer in the file. The copy kept before saving still has it.
            message = self.tr(
                "No se puede deshacer: ya se guardó sin eso. "
                "Está en Archivo → Versiones anteriores."
            )
        else:
            message = self.tr("No se ha podido hacer el cambio.")
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)

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
        self.versions_action.setEnabled(is_open)
        if not is_open:
            state = ""
        elif view.saving:
            state = self.tr("Guardando…")
        elif view.modified:
            state = self.tr("Cambios sin guardar")
        else:
            state = self.tr("Guardado")
        self.save_state_label.setText(state)
        self.save_state_label.setProperty("pending", is_open and view.modified)
        self.save_state_label.style().unpolish(self.save_state_label)
        self.save_state_label.style().polish(self.save_state_label)

    def _modified_changed(self, page: DocumentPage) -> None:
        if page in self.documents:
            # A dot on the tab says "this one has changes not saved yet".
            index = self.documents.index(page)
            self.document_tabs.setTabText(index, self._tab_title(page))
        if page is self.current_document:
            self._refresh_save_actions()

    @staticmethod
    def _tab_title(page: DocumentPage) -> str:
        return f"{page.title} ●" if page.view.modified else page.title

    # ---- closing with changes not saved ------------------------------------

    def _ask_unsaved(self, pages: list[DocumentPage]) -> str:
        """Guardar / No guardar / Cancelar for these documents: what the user answers.

        Whoever chose in the settings to save always, or never to be asked, is
        not asked. The warnings before saving (a signed PDF…) come up all the same.
        """
        if self.unsaved_answer is not None:
            return self.unsaved_answer
        wanted = save_settings.when_closing(self.settings)
        if wanted == save_settings.SAVE:
            return SAVE
        if wanted == save_settings.DISCARD:
            return DISCARD  # kept some days in "Recuperar cambios descartados"
        if not self.show_problem_dialogs:
            return DISCARD  # nobody to ask (automatic checks)
        dialog = UnsavedDialog(
            [page.title for page in pages], self, save_settings.discarded_days(self.settings)
        )
        try:
            dialog.exec()
            return dialog.choice
        finally:
            dialog.deleteLater()

    def _save_then(self, pages: list[DocumentPage], then) -> None:
        """Save these documents and, once every one is saved, do ``then``.

        If one cannot be saved nothing else happens: its message is shown and
        the documents stay open with their changes.
        """
        self._saving_to_close = list(pages)
        self._after_saving = then
        for page in pages:
            if not page.view.saving and not self._save_checked(page):
                # Something had to be asked and the answer was not to save.
                self._saved_before_closing(page, False)
                return

    def _saved_before_closing(self, page: DocumentPage, worked: bool) -> None:
        if page not in self._saving_to_close:
            return
        if not worked:
            self._saving_to_close, self._after_saving = [], None
            self.restart_wanted = False
            self.after_exit_command = None
            return
        self._saving_to_close.remove(page)
        if not self._saving_to_close and self._after_saving is not None:
            then, self._after_saving = self._after_saving, None
            then()

    def save_document(self, page: DocumentPage | None = None) -> bool:
        """Save the changes of a document (the one in front) in its own file.

        Returns True if the saving has started; the result comes a moment later.
        """
        page = page if page is not None else self.current_document
        if page.view.page_count == 0 or page.path is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        page.view.finish_writing()  # what is being typed goes in too
        if page.view.saving:
            return False
        if not page.view.modified:
            self.statusBar().showMessage(self.tr("No hay cambios que guardar."), STATUS_MESSAGE_MS)
            return False
        return self._save_checked(page)

    def _signed_save_choice(self, page: DocumentPage) -> str | None:
        """ "copy" (a new file "-firmado"), "same" (this file) or None (cancel)."""
        if self.signed_save_answer is not None:
            return self.signed_save_answer or None
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.tr("Guardar el documento firmado"))
        box.setText(
            self.tr(
                "Acabas de firmar «{0}». ¿Lo guardas como un archivo nuevo, «{1}», para "
                "que el original quede como estaba?"
            ).format(page.path.name, signed_name(page.path).name)
        )
        copy = box.addButton(self.tr("Guardar como «-firmado»"), QMessageBox.ButtonRole.AcceptRole)
        same = box.addButton(self.tr("Guardar en el mismo"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(self.tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(copy)
        box.exec()
        clicked = box.clickedButton()
        return "copy" if clicked is copy else "same" if clicked is same else None

    def _save_checked(self, page: DocumentPage) -> bool:
        """Save a document in its own file, unless something deserves asking first.

        These warnings come up always, whatever the settings say: the PDF is
        signed, another program has changed the file, or it is in a temporary
        folder. Returns True if a saving has started.
        """
        if page.view.signed_by_hand and not page.path.stem.lower().endswith("-firmado"):
            # Just signed: a copy "-firmado" keeps the original as it was. Asked
            # however the saving is wanted (Ctrl+S, or "Guardar" when closing);
            # the saving by itself never asks (the original stays in "Versiones
            # anteriores").
            page.view.signed_by_hand = False  # asked once
            choice = self._signed_save_choice(page)
            if choice is None:
                page.view.signed_by_hand = True
                return False
            if choice == "copy":
                if page in self.documents:
                    self.document_tabs.setCurrentIndex(self.documents.index(page))
                if self.save_document_as(suggested=signed_name(page.path)):
                    return True
                page.view.signed_by_hand = True  # not saved: asked again next time
                return False
        reasons = [r for r in self._save_warnings(page) if r not in page.accepted_warnings]
        if reasons:
            answer = self._ask_save_warning(page, reasons[0])  # the gravest one
            if answer == SAVE_AS:
                if page in self.documents:
                    self.document_tabs.setCurrentIndex(self.documents.index(page))
                return self.save_document_as()
            if answer != SAVE_HERE:
                return False
            page.accepted_warnings.update(reasons)  # asked once, not at every save
        self._start_saving(page, None)
        return True

    def _save_warnings(self, page: DocumentPage) -> list[str]:
        if page.path is None:
            return []
        document = page.view._document
        password = document.password if document is not None else None
        found = save_checks.warnings_for(page.path, page.stamp, password)
        if not self.warn_about_temporary_folders and save_checks.TEMPORARY in found:
            found.remove(save_checks.TEMPORARY)
        if page.view.loses_undo_on_save:
            found.append(FOREIGN_LOST)
        return found

    def _ask_save_warning(self, page: DocumentPage, reason: str) -> str:
        """Explain why saving here deserves a thought, and what the user decides."""
        name = page.title
        texts = {
            save_checks.SIGNED: (
                self.tr("El documento está firmado"),
                self.tr(
                    "«{0}» está firmado con certificado. Si lo guardas con cambios, la firma "
                    "deja de ser válida.\n\nLo normal es guardar una copia y dejar el "
                    "original firmado como está."
                ),
            ),
            save_checks.CHANGED_OUTSIDE: (
                self.tr("Otro programa ha cambiado el archivo"),
                self.tr(
                    "«{0}» ha cambiado en el disco desde que lo abriste. Si guardas aquí, se "
                    "pierde lo que haya hecho ese otro programa (quedaría en Archivo → "
                    "Versiones anteriores).\n\nLo más seguro es guardar una copia."
                ),
            ),
            FOREIGN_LOST: (
                self.tr("No se podrá deshacer"),
                self.tr(
                    "En «{0}» has quitado algo hecho con otro programa que es demasiado "
                    "grande para guardar una copia. Si guardas, Deshacer ya no podrá "
                    "devolverlo (seguirá en Archivo → Versiones anteriores).\n\nSi no "
                    "estás seguro, guarda una copia."
                ),
            ),
            save_checks.TEMPORARY: (
                self.tr("El documento está en una carpeta temporal"),
                self.tr(
                    "«{0}» está en una carpeta temporal (por ejemplo, un adjunto abierto "
                    "desde el correo). Lo que guardes ahí puede borrarse solo.\n\nGuárdalo "
                    "en una carpeta tuya."
                ),
            ),
        }
        title, text = texts[reason]
        text = text.format(name)
        if self.save_warning_answer is not None:
            return self.save_warning_answer
        if not self.show_problem_dialogs:
            # Nobody to ask: never saved by itself.
            self.statusBar().showMessage(f"{title}. " + self.tr("No se ha guardado."), 0)
            return CANCEL
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=self)
        save_as = box.addButton(self.tr("Guardar como…"), QMessageBox.ButtonRole.AcceptRole)
        here = box.addButton(
            self.tr("Guardar aquí de todos modos"), QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton(self.tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_as)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is save_as:
            return SAVE_AS
        return SAVE_HERE if clicked is here else CANCEL

    def save_document_as(
        self, target: str | Path | None = None, suggested: Path | None = None
    ) -> bool:
        """Save the document in front as another file and go on working in that one.

        Without ``target`` the user is asked where. Returns True if the saving
        has started.
        """
        page = self.current_document
        if page.view.page_count == 0 or page.path is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        page.view.finish_writing()
        if page.view.saving:
            return False
        if target is None:
            if suggested is None:
                suggested = page.path.with_name(self.tr("{0} - copia.pdf").format(page.path.stem))
            if self.save_as_answer is not None:
                chosen = self.save_as_answer(suggested)
            else:
                chosen, _filter = QFileDialog.getSaveFileName(
                    self,
                    self.tr("Guardar como"),
                    str(suggested),
                    self.tr("Documentos PDF (*.pdf)"),
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
        page.view.signed_by_hand = False  # a name of one's own was chosen: not asked again
        self._start_saving(page, target)
        return True

    # ---- the saving settings ---------------------------------------------------

    def apply_pen_settings(self) -> None:
        """Follow what the settings say now about the pen and the fingers."""
        pages = [*getattr(self, "documents", []), getattr(self, "_spare", None)]
        for page in pages:
            if page is not None:
                self._give_pen_settings(page.view)

    def _give_pen_settings(self, view: PdfView) -> None:
        view.pen_pressure = pen.pressure_wanted(self.settings)
        view.finger_mode = pen.finger_mode(self.settings)
        view.pen_seen = pen.pen_seen(self.settings)
        view.typed_arrows = symbols.typed_wanted(self.settings)  # the keyboard, while at it

    def _pen_was_seen(self) -> None:
        """A pen has been used: from now on the fingers leave the drawing to it
        (unless the settings say otherwise)."""
        if not pen.pen_seen(self.settings):
            self.settings.set(pen.PEN_SEEN_SETTING, True)
        self.apply_pen_settings()

    def apply_save_settings(self) -> None:
        """Follow what the settings say now about versions and saving by itself."""
        self.versions.max_per_document = save_settings.versions_count(self.settings)
        self.versions.max_total_bytes = save_settings.versions_room_bytes(self.settings)
        self._autosave_timer.setInterval(save_settings.autosave_seconds(self.settings) * 1000)
        if not save_settings.autosave_wanted(self.settings):
            self._autosave_timer.stop()
        elif any(page.view.modified for page in getattr(self, "documents", [])):
            self._autosave_timer.start()

    def _schedule_autosave(self) -> None:
        """A change has just been made: count the quiet time again from now."""
        if save_settings.autosave_wanted(self.settings):
            self._autosave_timer.start()

    def _autosave(self) -> None:
        """The quiet time has passed: save what is pending, without asking anything."""
        if QApplication.activeModalWidget() is not None or self._saving_to_close:
            self._autosave_timer.start()  # a question is open: later
            return
        for page in list(self.documents):
            self._autosave_page(page)

    def _autosave_page(self, page: DocumentPage) -> bool:
        """Save this document by itself if it is wanted and nothing advises against it.

        A signed PDF, a file changed by another program or one in a temporary
        folder is never saved by itself: that is asked when the user saves.
        """
        if not save_settings.autosave_wanted(self.settings):
            return False
        if page not in self.documents or page.path is None:
            return False
        if not page.view.modified or page.view.saving:
            return False
        reasons = [r for r in self._save_warnings(page) if r not in page.accepted_warnings]
        if reasons:
            if not page.autosave_told:
                page.autosave_told = True
                why = {
                    save_checks.SIGNED: self.tr("está firmado"),
                    save_checks.CHANGED_OUTSIDE: self.tr("otro programa ha cambiado el archivo"),
                    save_checks.TEMPORARY: self.tr("está en una carpeta temporal"),
                    FOREIGN_LOST: self.tr("Deshacer ya no podría devolver lo que has quitado"),
                }[reasons[0]]
                self.statusBar().showMessage(
                    self.tr("«{0}» no se guarda solo: {1}. Guárdalo tú con Guardar.").format(
                        page.title, why
                    ),
                    0,
                )
            return False
        self._start_saving(page, None, by_itself=True)
        return True

    def _start_saving(
        self, page: DocumentPage, target: Path | None, by_itself: bool = False
    ) -> None:
        page.saving_by_itself = by_itself
        keep = self._version_wanted(target if target is not None else page.path)
        self.statusBar().showMessage(self.tr("Guardando…"))
        page.view.save(target, keep)
        self._refresh_save_actions()

    def _version_wanted(self, file: Path | None) -> tuple | None:
        """Before a file is saved over for the first time in this session, a copy
        of how it was is kept: what the helper needs to make it, or None.

        The helper copies it, so that a big file never holds the window up.
        Not being able to must not stop the saving (``_version_failed``).
        """
        if file is None or file_key(file) in self._versioned:
            return None
        self._versioned.add(file_key(file))
        return (
            str(self.versions.folder),
            self.versions.max_per_document,
            self.versions.max_total_bytes,
        )

    def _version_failed(self, page: DocumentPage) -> None:
        self._version_not_kept = True  # said with the result of the saving
        if page.path is not None:
            self._versioned.discard(file_key(page.path))  # tried again next time

    # ---- earlier versions --------------------------------------------------

    def choose_version(self) -> None:
        """ "Archivo → Versiones anteriores": look at one or put it back."""
        page = self.current_document
        if not self.documents or page.path is None:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        dialog = VersionsDialog(page.title, self.versions.of(page.path), self)
        try:
            dialog.exec()
            action, chosen = dialog.action, dialog.chosen
        finally:
            dialog.deleteLater()
        if chosen is None:
            return
        if action == VIEW:
            self.view_version(chosen)
        elif action == RESTORE:
            self.restore_version(chosen)

    def view_version(self, version: Version) -> bool:
        """Open an earlier version in its own tab, to look at it. Nothing changes."""
        moment = datetime.fromtimestamp(version.when).strftime("%d-%m-%Y %H.%M")
        name = self.tr("{0} (versión del {1}).pdf").format(version.document.stem, moment)
        copy = Path(tempfile.gettempdir()) / "Lector-PDF versiones" / name
        try:
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(version.file, copy)
        except OSError:
            self._show_problem(
                self.tr("No se puede abrir esa versión"),
                self.tr("No se ha podido preparar la copia para verla."),
            )
            return False
        return self.open_document(copy, remember=False)

    def restore_version(self, version: Version) -> bool:
        """Leave the document as it was in ``version``.

        How it is now is kept as one more version, and changes not saved are
        set aside in the journal: nothing is lost by restoring.
        """
        document = version.document
        if self.restore_answer is not None:
            wanted = self.restore_answer
        elif not self.show_problem_dialogs:
            wanted = False
        else:
            wanted = (
                QMessageBox.question(
                    self,
                    self.tr("Restaurar versión"),
                    self.tr(
                        "«{0}» quedará como estaba {1}.\n\nLo de ahora se guarda como una "
                        "versión más, por si quieres volver."
                    ).format(document.name, when_text(version.when)),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                == QMessageBox.StandardButton.Yes
            )
        if not wanted:
            return False
        index = self.index_of_document(document)
        place = -1
        if index >= 0:
            place = self.documents[index].view.current_page
            # Its helper lets go of the file; changes not saved go to the journal.
            self.close_document(index, ask=False)
        error = ""
        for _attempt in range(RESTORE_TRIES):
            try:
                self.versions.restore(version)
                error = ""
                break
            except VersionError as failed:
                error = str(failed)
                time.sleep(RESTORE_PAUSE)  # the helper may need a moment to let go
        self._versioned.add(file_key(document))
        reopened = index < 0 or self.open_document(document)
        if error:
            self._show_problem(
                self.tr("No se ha podido restaurar"),
                self.tr(
                    "«{0}» sigue como estaba. Puede que otro programa lo tenga abierto."
                ).format(document.name),
            )
            return False
        if reopened and index >= 0:
            # Back to its place among the tabs, not at the end.
            now = self.index_of_document(document)
            if 0 <= now != index and index < len(self.documents):
                self.document_tabs.moveTab(now, index)
                self.document_tabs.setCurrentIndex(index)
        if reopened and index >= 0 and 0 < place < self.pdf_view.page_count:
            self.pdf_view.scroll_to_page(place)
        self.statusBar().showMessage(
            self.tr("«{0}» ha vuelto a como estaba {1}.").format(
                document.name, when_text(version.when)
            ),
            STATUS_MESSAGE_MS,
        )
        return True

    def _document_saved(self, page: DocumentPage, _number: int, path: object) -> None:
        path = Path(path)
        if page.path is not None and file_key(path) != file_key(page.path):
            # "Guardar como": from now on this tab is the new file.
            page.path = path
            # The copy is the user's own working file: its signature, if it had
            # one, went with the changes, and the signed original is untouched.
            page.accepted_warnings = {save_checks.SIGNED}
            self.history.add_recent(path)
            if page in self.documents:
                index = self.documents.index(page)
                self.document_tabs.setTabText(index, self._tab_title(page))
                self.document_tabs.setTabToolTip(index, str(path))
                self._save_session()
            if page is self.current_document:
                self.setWindowTitle(f"{page.title} – {APP_NAME}")
        page.saving_by_itself = page.autosave_failed = page.autosave_told = False
        page.stamp = save_checks.stamp_of(path)  # as we left it: ours, not another program's
        # If another program changes it again, that deserves asking again.
        page.accepted_warnings.discard(save_checks.CHANGED_OUTSIDE)
        page.accepted_warnings.discard(FOREIGN_LOST)  # asked again for the next one
        message = self.tr("Guardado en «{0}».").format(path.name)
        if self._version_not_kept:
            self._version_not_kept = False
            message += " " + self.tr("No se ha podido conservar la versión anterior.")
        self.statusBar().showMessage(message, STATUS_MESSAGE_MS)
        self._refresh_save_actions()
        self._saved_before_closing(page, True)
        self._sign_after_saving(page, True)

    def _save_failed(self, page: DocumentPage, _number: int, kind: str) -> None:
        self._refresh_save_actions()
        self._saved_before_closing(page, False)
        self._sign_after_saving(page, False)
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
        if page.saving_by_itself:
            # Saving by itself tries again after the next change; the window
            # explaining it comes up the first time only.
            page.saving_by_itself = False
            again, page.autosave_failed = page.autosave_failed, True
            if again:
                return
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
        self.pdf_view.finish_writing()  # printed as it is seen
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
            annotations=self.pdf_view.annotations_shown,
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
        run = PrintRun(
            page.view, printer, choices.pages, choices.scaling, self, choices.annotations
        )
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
        self._give_marker_styles(view)
        self._give_pen_settings(view)
        view.pen_seen_changed.connect(self._pen_was_seen)
        view.text_style_chosen.connect(self.text_style_used)
        view.page_changed.connect(self._update_position)
        view.page_changed.connect(lambda *_args: self._place_timer.start())
        view.zoom_changed.connect(self._update_position)
        view.page_drawn.connect(lambda number, seconds, p=page: self._page_drawn(p, seconds))
        view.document_failed.connect(self._document_failed)
        view.text_copied.connect(self._text_copied)
        view.no_text_to_select.connect(self._no_text_to_select)
        view.scanned_found.connect(
            lambda pages, count, p=page: self._scanned_found(p, pages, count)
        )
        page.ocr_banner.recognize_wanted.connect(lambda p=page: self._recognize_offered(p))
        page.ocr_banner.never_wanted.connect(lambda p=page: self._ocr_declined(p))
        page.ocr_banner.cancel_wanted.connect(lambda p=page: self.cancel_text_recognition(p))
        view.modified_changed.connect(lambda _modified, p=page: self._modified_changed(p))
        view.saved.connect(lambda number, path, p=page: self._document_saved(p, number, path))
        view.save_failed.connect(
            lambda number, kind, details, p=page: self._save_failed(p, number, kind)
        )
        view.version_not_kept.connect(lambda _number, p=page: self._version_failed(p))
        page.search_panel.closed.connect(self.close_search)
        page.search_panel.box.textChanged.connect(self._panel_search_typed)
        page.side_panel.closed.connect(self.close_side_panel)
        page.side_panel.tab_changed.connect(self._side_tab_changed)
        # Ctrl+C and Ctrl+A belong to the document only while it has the keyboard:
        # in the search box they must keep copying and selecting what is typed.
        # The same goes for Ctrl+Z: in a text box it undoes what was typed there.
        for action in (
            self.copy_action,
            self.paste_action,
            self.duplicate_action,
            self.delete_action,
            self.select_all_action,
            self.undo_action,
            self.redo_action,
        ):
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            view.addAction(action)
        view.addActions([*self.tool_key_actions.values(), *self.favourite_key_actions])
        view.history_changed.connect(lambda p=page: self._edit_state_changed(p))
        view.history_changed.connect(self._schedule_autosave)
        view.modified_changed.connect(lambda _modified: self._schedule_autosave())
        view.markup_tool_changed.connect(lambda _kind, p=page: self._edit_state_changed(p))
        view.certificate_place.connect(
            lambda number, rect, p=page: self._certificate_placed(p, number, rect)
        )
        view.selection_changed.connect(lambda _has, p=page: self._edit_state_changed(p))
        view.picked_changed.connect(lambda p=page: self._edit_state_changed(p))
        view.annotations_shown_changed.connect(lambda _on, p=page: self._edit_state_changed(p))
        view.review_changed.connect(lambda _on, p=page: self._edit_state_changed(p))
        view.item_copied.connect(self._refresh_edit_actions)
        view.item_copied.connect(
            lambda: self.statusBar().showMessage(
                self.tr("Anotación copiada. Pégala con Ctrl+V, aquí o en otro documento."),
                STATUS_MESSAGE_MS,
            )
        )
        view.edit_failed.connect(self._edit_failed)
        view.form_found.connect(lambda p=page: self._form_found(p))
        view.my_data_items = self._my_data_items
        view.field_refused.connect(lambda why: self.statusBar().showMessage(why, STATUS_MESSAGE_MS))
        view.link_wanted.connect(lambda area, words, p=page: self._link_asked(p, area, words))
        view.doc_link_clicked.connect(lambda link, p=page: self.follow_doc_link(p, link))
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

    def open_document(self, path: str | Path, remember: bool = True) -> bool:
        """Show the PDF at ``path`` in a new tab. Problems give a message, never a crash.

        With ``remember`` False the document is only being looked at (an
        earlier version): it is left out of the recent files and of the tabs
        that come back the next time.
        """
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
        page.remembered = remember
        page.stamp = save_checks.stamp_of(page.path)
        page.accepted_warnings = set()
        page.view.journal = self.journal.of(page.path)
        page.slowest_page = 0.0
        # Back to the page and the work mode where this document was left.
        place = self.history.place_of(page.path)
        page.mode = _mode_named(place.mode)
        if 0 < place.page < page.view.page_count:
            page.view.scroll_to_page(place.page)
        if remember:
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
        # The ones that were not there the last times are tried again too.
        waited = [path for path in self.history.absent_tabs() if path not in paths]
        asking = self.show_problem_dialogs
        self.show_problem_dialogs = False  # a file that is gone is not worth a dialog
        self._password_dialogs = asking  # but a protected one still asks for its password
        # Nothing is written down until all are back: closing by force half way
        # (say, with a password being asked) must not forget the rest.
        self._restoring = True
        try:
            opened = [
                path for path in [*paths, *waited] if path.is_file() and self.open_document(path)
            ]
        finally:
            self.show_problem_dialogs = asking
            self._password_dialogs = None
            self._restoring = False
        # A file that is not there now (a USB stick not plugged in, a network
        # folder not ready) keeps its place: its tab comes back when it does.
        self._absent_tabs = [path for path in [*paths, *waited] if not path.is_file()]
        if 0 <= current < len(paths) and paths[current] in opened:
            self.document_tabs.setCurrentIndex(self.index_of_document(paths[current]))
        missing = len(paths) - len([path for path in paths if path in opened])
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
        if self._restoring:
            return
        kept = [page for page in self.documents if page.path is not None and page.remembered]
        front = self.current_document if self.documents else None
        current = kept.index(front) if front in kept else -1
        self.history.save_session([page.path for page in kept], current, self._absent_tabs)
        if self.settings.save_failed and not self._told_settings_failed:
            self._told_settings_failed = True  # said once, not at every change
            self.statusBar().showMessage(
                self.tr(
                    "No se pueden guardar los ajustes (disco lleno o protegido): "
                    "las pestañas y preferencias no se recordarán."
                ),
                STATUS_MESSAGE_MS,
            )

    def _remember_place(self, page: DocumentPage) -> None:
        if page.path is not None and page.view.page_count and page.remembered:
            self.history.remember_place(page.path, max(page.view.current_page, 0), page.mode.name)

    def _remember_current_place(self) -> None:
        if self.documents:
            self._remember_place(self.current_document)

    # ---- recovering changes that were never saved --------------------------

    def offer_recovery(self) -> int:
        """After a power cut, a hang or a forced close: offer the changes back.

        Called when the program starts. Returns how many documents got their
        changes back. Saying no does not lose them: they are set aside some days.
        """
        self.journal.forget_old(save_settings.discarded_days(self.settings))
        pending = self.journal.pending()
        if not pending:
            return 0
        if self.recovery_answer is not None:
            wanted = self.recovery_answer
        elif not self.show_problem_dialogs:
            return 0  # nobody to ask (automatic checks): they stay where they are
        else:
            dialog = RecoveryDialog(
                pending,
                crashed=True,
                parent=self,
                days=save_settings.discarded_days(self.settings),
            )
            try:
                dialog.exec()
                wanted = bool(dialog.chosen)
            finally:
                dialog.deleteLater()
        if not wanted:
            for found in pending:
                self._set_aside(found)
            self.statusBar().showMessage(
                self.tr(
                    "Cambios no recuperados. Siguen en Archivo → Recuperar cambios descartados."
                ),
                STATUS_MESSAGE_MS,
            )
            return 0
        return sum(1 for found in pending if self.recover_changes(found))

    def choose_discarded_changes(self) -> None:
        """ "Archivo → Recuperar cambios descartados": choose one and bring it back."""
        self.journal.forget_old(save_settings.discarded_days(self.settings))
        dialog = RecoveryDialog(
            self.journal.discarded(),
            crashed=False,
            parent=self,
            days=save_settings.discarded_days(self.settings),
        )
        try:
            dialog.exec()
            chosen = list(dialog.chosen)
        finally:
            dialog.deleteLater()
        for found in chosen:
            self.recover_changes(found)

    def recover_changes(self, found: Pending) -> bool:
        """Put the changes of ``found`` back in its document, as changes not saved.

        The document is opened if it is not. False if it cannot be opened; the
        changes are then kept for later.
        """
        name = found.path.name
        if not found.path.is_file() or not self.open_document(found.path):
            self._set_aside(found)  # not asked again at every start, but kept
            self.statusBar().showMessage(
                self.tr("No se encuentra «{0}»: sus cambios se conservan unos días.").format(name),
                STATUS_MESSAGE_MS,
            )
            return False
        view = self.documents[self.index_of_document(found.path)].view
        entries = list(found.entries)
        if view.journal is None:
            view.journal = self.journal.of(found.path)
        if found.file == view.journal.file and not view.modified:
            view.journal.restart(entries)  # the same journal goes on, tidied up
        else:
            # First written down in the journal of the open document, then the
            # old note is thrown away: at no moment are they in neither.
            for order, undone in entries:
                view.journal.record(order, undone)
            if found.file != view.journal.file:
                self.journal.forget(found)
        view.recover(entries)
        self.statusBar().showMessage(
            self.tr("Cambios de «{0}» recuperados. Están sin guardar: pulsa Guardar.").format(name),
            STATUS_MESSAGE_MS,
        )
        return True

    def _set_aside(self, found: Pending) -> None:
        """Keep these changes for some days without offering them at every start."""
        if found.discarded:
            return
        index = self.index_of_document(found.path)
        journal = self.documents[index].view.journal if index >= 0 else None
        if journal is not None and journal.file == found.file:
            journal.discard()  # the open document starts a clean journal
        else:
            self.journal.set_aside(found)

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

    def close_document(self, index: int | None = None, ask: bool = True) -> None:
        """Close a tab (the one in front if none is given).

        With changes not saved it asks first: Guardar / No guardar / Cancelar.
        """
        if index is None:
            index = self.document_tabs.currentIndex()
        if not 0 <= index < len(self.documents):
            return
        page = self.documents[index]
        page.view.finish_writing()  # what is being typed is not lost unasked
        if ask and page.view.modified:
            self.document_tabs.setCurrentIndex(index)  # the one being asked about, in front
            answer = self._ask_unsaved([page])
            if answer == CANCEL:
                return
            if answer == SAVE:
                self._save_then([page], lambda p=page: self._close_page(p))
                return
        self._close_page(page)

    def _close_page(self, page: DocumentPage) -> None:
        if page not in self.documents:
            return
        index = self.documents.index(page)
        if page is self.beside.page:
            self.beside.take()
            self.beside.hide()
        self.documents.pop(index)
        self._remember_place(page)
        self._set_changes_aside(page)
        self.document_tabs.blockSignals(True)
        self.document_tabs.removeTab(index)
        self.document_tabs.blockSignals(False)
        page.shutdown()
        self.pages.removeWidget(page)
        page.deleteLater()
        self.document_tabs.setVisible(bool(self.documents) and not self._full_screen)
        self._tab_changed(self.document_tabs.currentIndex())
        self._save_session()

    @staticmethod
    def _set_changes_aside(page: DocumentPage) -> None:
        """A document is closed without saving: its changes are kept some days."""
        if page.view.modified and page.view.journal is not None:
            page.view.journal.discard()

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
        left, self._front_page = self._front_page, page if self.documents else None
        if left is not None and left is not page:
            self._autosave_page(left)  # "guardar solo" also saves when leaving a tab
        if self.documents:
            if page is self.beside.page:
                self._keep_one_in_front()
            else:
                self.pages.setCurrentWidget(page)
            self.beside.set_active(page is self.beside.page)
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

    # ---- two documents side by side ------------------------------------------

    @property
    def beside_page(self) -> DocumentPage | None:
        return self.beside.page

    def _front_half(self) -> DocumentPage | None:
        """The document shown on the left half."""
        widget = self.pages.currentWidget()
        return widget if widget in self.documents else None

    def _keep_one_in_front(self) -> None:
        """The left half always shows a document that is not the one beside."""
        if self._front_half() is not None:
            return
        others = [page for page in self.documents if page is not self.beside.page]
        if others:
            self.pages.setCurrentWidget(others[0])
        else:
            self.stop_beside()

    def toggle_beside(self) -> None:
        """See two documents at once, or stop: the button of the tool bar."""
        if self.beside.page is not None:
            self.stop_beside()
            return
        if not self.documents:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        front = self.current_document
        others = [page for page in self.documents if page is not front]
        if len(others) == 1:
            self.show_beside(others[0])
        elif others:
            menu = QMenu(self)
            menu.setTitle(self.tr("¿Qué documento quieres ver al lado?"))
            for page in others:
                menu.addAction(page.title, lambda p=page: self.show_beside(p))
            self.beside_menu = menu  # the tests pick from it
            menu.popup(QCursor.pos())
        else:
            self.statusBar().showMessage(
                self.tr("Elige el otro documento: se abrirá al lado."), STATUS_MESSAGE_MS
            )
            before = set(self.documents)
            self.choose_and_open()
            opened = [page for page in self.documents if page not in before]
            if opened:
                self.document_tabs.setCurrentIndex(self.documents.index(front))
                self.show_beside(opened[-1])

    def show_beside(self, page: DocumentPage) -> bool:
        """Put an open document on the right half, beside the one in front."""
        if page not in self.documents:
            return False
        if self.beside.page is page:
            return True
        if self.beside.page is not None:
            self.stop_beside()
        front = self._front_half()
        if front is page or front is None:  # another one goes to the left half
            others = [other for other in self.documents if other is not page]
            if not others:
                return False
            self.document_tabs.setCurrentIndex(self.documents.index(others[0]))
        self.pages.removeWidget(page)
        self.beside.put(page)
        self.beside.show()
        width = max(2, self.halves.width())
        self.halves.setSizes([width // 2, width - width // 2])
        # Each half is narrower now: both are shown at a comfortable size again.
        QTimer.singleShot(0, self, self._fit_halves)
        self.document_tabs.setTabToolTip(
            self.documents.index(page), self.tr("{0} (al lado)").format(page.path or page.title)
        )
        self._tab_changed(self.document_tabs.currentIndex())
        return True

    def _fit_halves(self) -> None:
        for page in (self._front_half(), self.beside.page):
            if page is not None and page.view.page_count:
                page.view.fit_comfortable()

    def stop_beside(self) -> None:
        """Back to one document at a time; the one beside keeps its tab."""
        self.cancel_link()
        page = self.beside.take()
        self.beside.hide()
        if page is None:
            return
        self.pages.addWidget(page)
        if page in self.documents:
            index = self.documents.index(page)
            self.document_tabs.setTabToolTip(index, str(page.path or page.title))
        self._tab_changed(self.document_tabs.currentIndex())
        QTimer.singleShot(0, self, self._fit_halves)

    def _beside_from_tab(self, index: int) -> None:
        """Right click on a tab: see it beside the one in front, or stop."""
        if not 0 <= index < len(self.documents):
            return
        page = self.documents[index]
        if page is self.beside.page:
            self.stop_beside()
        else:
            self.show_beside(page)

    def _focus_moved(self, _old, new) -> None:
        """A click or Tab into one half: the tools act on its document."""
        if new is None or self.beside.page is None:
            return
        if self.beside.isAncestorOf(new):
            wanted = self.beside.page
        elif self.pages.isAncestorOf(new):
            wanted = self._front_half()
        else:
            return
        if wanted is not None and wanted is not self.current_document:
            self.document_tabs.setCurrentIndex(self.documents.index(wanted))

    # ---- forms ------------------------------------------------------------------

    def fill_form(self) -> bool:
        """ "Rellenar campos": the keyboard goes to the first field of the form."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        if view.focus_field(+1) is None:
            self.statusBar().showMessage(
                self.tr("Este documento no tiene campos de formulario."),
                STATUS_MESSAGE_MS,
            )
            return False
        self.statusBar().showMessage(
            self.tr("Escribe y pulsa Tab para pasar al siguiente campo; Esc para terminar."),
            STATUS_MESSAGE_MS,
        )
        return True

    @property
    def my_data(self) -> MyData:
        return MyData.from_setting(self.settings.get(my_data.SETTING))

    def _my_data_items(self) -> list[tuple[str, str]]:
        names = datum_names(self)
        return [(names[key], value) for key, value in self.my_data.filled()]

    def edit_my_data(self) -> bool:
        """Write or change «Mis datos» (kept only on this computer)."""
        answer = self.my_data_answer
        if answer is None:
            dialog = MyDataDialog(self.my_data, self)
            if not dialog.exec():
                return False
            answer = dialog.data
        self.settings.set(my_data.SETTING, answer.to_setting())
        return True

    def _my_data_fills(self, data: MyData) -> list:
        """The empty fields of the form that ask for one of the data, with it."""
        view = self.pdf_view
        wanted = []
        for page in range(view.page_count):
            for field in view.fields_of(page) if page in view._fields else ():
                if field.read_only or field.value or field.kind not in (FORM_TEXT, COMBO):
                    continue
                key = datum_for(field.label, field.name)
                value = data.value(key) if key else ""
                if value and field.kind == COMBO and not field.editable:
                    value = choice_for(value, field.choices) or ""
                if value:
                    wanted.append((field, value))
        return wanted

    def show_my_data(self) -> QMenu | None:
        """«Mis datos»: put them all in the form at once, or one where it is clicked."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return None
        data = self.my_data
        if data.empty and not self.edit_my_data():
            return None
        data = self.my_data
        if data.empty:
            return None
        menu = QMenu(self)
        fills = self._my_data_fills(data)
        if fills:
            every = menu.addAction(
                self.tr("Rellenar el formulario con mis datos ({0} campos)").format(len(fills))
            )
            every.triggered.connect(lambda _checked=False: self.fill_with_my_data())
            menu.addSeparator()
        names = datum_names(self)
        for key, value in data.filled():
            menu.addAction(f"{names[key]}: {value}").triggered.connect(
                lambda _checked=False, v=value: self.put_datum(v)
            )
        menu.addSeparator()
        menu.addAction(self.tr("Editar mis datos…")).triggered.connect(
            lambda _checked=False: self.edit_my_data()
        )
        self.my_data_menu = menu  # the tests pick from it
        menu.popup(QCursor.pos())
        return menu

    def fill_with_my_data(self) -> int:
        """Every empty field that asks for one of «Mis datos» gets it (one change)."""
        filled = self.pdf_view.fill_many(self._my_data_fills(self.my_data))
        if filled:
            self.statusBar().showMessage(
                self.tr("Tus datos se han puesto en {0} campos. Ctrl+Z lo deshace.").format(filled),
                STATUS_MESSAGE_MS,
            )
        else:
            self.statusBar().showMessage(
                self.tr("No hay campos vacíos que pidan tus datos."), STATUS_MESSAGE_MS
            )
        return filled

    def put_datum(self, value: str) -> None:
        """One datum, to put with a click where it goes (in a field: at once)."""
        view = self.pdf_view
        editor = view.field_editor
        if editor is not None:  # a field being written: the datum goes in it
            editor.box.setFocus()
            if hasattr(editor.box, "insert"):
                editor.box.insert(value)
            else:
                editor.box.insertPlainText(value)
            return
        view.clear_selection()
        view.set_markup_tool(TEXT_BOX)
        view.text_to_put = value
        self.statusBar().showMessage(
            self.tr("Haz clic donde quieras poner «{0}» (Esc: dejarlo).").format(value),
            STATUS_MESSAGE_MS,
        )
        self._refresh_edit_actions()

    # ---- stamps ------------------------------------------------------------------

    @property
    def stamp_size(self) -> float:
        size = self.settings.get(stamps.SIZE_SETTING)
        return float(size) if size in stamps.SIZES else stamps.DEFAULT_SIZE

    def show_stamps(self) -> QMenu | None:
        """«Sellos»: a mark or a stamp to put with a click wherever it goes."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            self._refresh_edit_actions()
            return None
        if view.markup_tool == "stamp":
            view.use_stamp(None)  # pressed again: leave it
            self._refresh_edit_actions()
            return None
        menu = QMenu(self)
        today = Stamp(stamps.TODAY).text()
        for stamp, name in (
            (Stamp(stamps.CHECK), self.tr("✓  Marca")),
            (Stamp(stamps.CROSS), self.tr("✗  Cruz")),
            (Stamp(stamps.DOT), self.tr("●  Punto")),
            (Stamp(stamps.TODAY), self.tr("Fecha de hoy ({0})").format(today)),
            (Stamp(stamps.RECEIVED, self.tr("Recibido")), self.tr("Recibido")),
        ):
            menu.addAction(name).triggered.connect(
                lambda _checked=False, s=stamp: self.use_stamp(s)
            )
        own = stamps.own_stamps(self.settings.get(stamps.OWN_SETTING))
        if own:
            menu.addSeparator()
            for words in own:
                menu.addAction(words).triggered.connect(
                    lambda _checked=False, w=words: self.use_stamp(Stamp(stamps.OWN, w))
                )
        menu.addSeparator()
        menu.addAction(self.tr("Nuevo sello…")).triggered.connect(
            lambda _checked=False: self.new_stamp()
        )
        if own:
            forget = menu.addMenu(self.tr("Quitar un sello"))
            for words in own:
                forget.addAction(words).triggered.connect(
                    lambda _checked=False, w=words: self.forget_stamp(w)
                )
        sizes = menu.addMenu(self.tr("Tamaño"))
        for size, name in zip(
            stamps.SIZES,
            (self.tr("Pequeño"), self.tr("Normal"), self.tr("Grande"), self.tr("Muy grande")),
            strict=True,
        ):
            action = sizes.addAction(name)
            action.setCheckable(True)
            action.setChecked(size == self.stamp_size)
            action.triggered.connect(
                lambda _checked=False, s=size: self.settings.set(stamps.SIZE_SETTING, s)
            )
        self.stamps_menu = menu  # the tests pick from it
        menu.popup(QCursor.pos())
        return menu

    def use_stamp(self, stamp: Stamp) -> None:
        view = self.pdf_view
        view.stamp_size = self.stamp_size
        view.use_stamp(stamp)
        self.statusBar().showMessage(
            self.tr("Haz clic donde quieras ponerlo; cada clic pone otro (Esc: dejarlo)."),
            STATUS_MESSAGE_MS,
        )
        self._refresh_edit_actions()

    def new_stamp(self) -> bool:
        """A stamp with words of one's own («Pagado», «Copia»…), kept for next time."""
        words = self.new_stamp_answer
        if words is None:
            words, ok = QInputDialog.getText(
                self,
                self.tr("Nuevo sello"),
                self.tr("Lo que dirá el sello (por ejemplo, «Pagado» o «Copia»):"),
            )
            if not ok:
                return False
        words = " ".join(words.split())[:60]
        if not words:
            return False
        own = stamps.own_stamps(self.settings.get(stamps.OWN_SETTING))
        if words not in own:
            self.settings.set(stamps.OWN_SETTING, [*own, words][-stamps.MOST_OWN :])
        if self.pdf_view.page_count:
            self.use_stamp(Stamp(stamps.OWN, words))
        return True

    def forget_stamp(self, words: str) -> None:
        own = stamps.own_stamps(self.settings.get(stamps.OWN_SETTING))
        self.settings.set(stamps.OWN_SETTING, [kept for kept in own if kept != words])

    # ---- the saved signature and initials ---------------------------------------

    @property
    def signature_folder(self) -> Path:
        return self.settings.path.parent / my_signature.FOLDER

    def saved_signature(self, kind: str) -> bytes | None:
        return my_signature.load(self.signature_folder, kind)

    def _suggested_words(self, kind: str) -> str:
        """What a written signature says at first: one's name, or its initials."""
        name = self.my_data.value(my_data.FULL_NAME)
        if kind == my_signature.SIGNATURE:
            return name
        return " ".join(f"{word[0].upper()}." for word in name.split() if word[0].isalpha())

    def make_signature(self, kind: str) -> bool:
        """Make (or make again) one's signature or initials and keep it."""
        png = self.signature_answer
        if png is None:
            dialog = SignatureDialog(kind, self._suggested_words(kind), self)
            if not dialog.exec():
                return False
            png = dialog.png
        if not png:
            return False
        try:
            my_signature.save(self.signature_folder, kind, png)
        except OSError:
            QMessageBox.warning(
                self,
                self.tr("Mi firma"),
                self.tr("No se ha podido guardar. Comprueba que queda sitio en el disco."),
            )
            return False
        self.statusBar().showMessage(
            self.tr("Iniciales guardadas.")
            if kind == my_signature.INITIALS
            else self.tr("Firma guardada."),
            STATUS_MESSAGE_MS,
        )
        return True

    def forget_signature(self, kind: str) -> bool:
        initials = kind == my_signature.INITIALS
        sure = self.forget_signature_answer
        if sure is None:
            sure = (
                QMessageBox.question(
                    self,
                    self.tr("Quitar mis iniciales") if initials else self.tr("Quitar mi firma"),
                    self.tr(
                        "¿Quitar tus iniciales guardadas? Los documentos ya firmados no cambian."
                    )
                    if initials
                    else self.tr(
                        "¿Quitar tu firma guardada? Los documentos ya firmados no cambian."
                    ),
                )
                == QMessageBox.StandardButton.Yes
            )
        if sure:
            my_signature.forget(self.signature_folder, kind)
        return bool(sure)

    @property
    def date_with_signature(self) -> bool:
        """Whether today's date is written under the signature (yes, unless said)."""
        return self.settings.get(DATE_SETTING) is not False

    def put_signature(self, kind: str = my_signature.SIGNATURE, every_page: bool = False) -> bool:
        """Take the signature (or the initials) in hand: a click puts it (with
        ``every_page``, on every page in the same place)."""
        view = self.pdf_view
        png = self.saved_signature(kind)
        if view.page_count == 0 or png is None:
            return False
        initials = kind == my_signature.INITIALS
        date = "" if initials or not self.date_with_signature else stamps.Stamp(stamps.TODAY).text()
        view.use_picture(
            png,
            self.tr("Iniciales") if initials else self.tr("Firma"),
            pictures.INITIALS_WIDTH if initials else pictures.SIGNATURE_WIDTH,
            date,
            every_page,
        )
        self.statusBar().showMessage(
            self.tr(
                "Haz clic donde van en esta página: se ponen en el mismo sitio de todas "
                "(Ctrl+Z las quita todas; Esc: dejarlo)."
            )
            if every_page
            else self.tr(
                "Haz clic donde va. Después puedes moverla y cambiar su tamaño (Esc: dejarlo)."
            ),
            STATUS_MESSAGE_MS,
        )
        self._refresh_edit_actions()
        return True

    def initials_everywhere(self) -> bool:
        """«Iniciales en todas las páginas»: made first if there are none yet."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        if self.saved_signature(my_signature.INITIALS) is None and not self.make_signature(
            my_signature.INITIALS
        ):
            return False
        return self.put_signature(my_signature.INITIALS, every_page=True)

    def show_signature(self) -> QMenu | None:
        """«Firmar»: the first time, make the signature; then put it with a click."""
        view = self.pdf_view
        if view.markup_tool == SIGN_TOOL:
            view.use_picture(None)  # pressed again: leave it
            self._refresh_edit_actions()
            return None
        if self.saved_signature(my_signature.SIGNATURE) is None:
            if self.make_signature(my_signature.SIGNATURE) and view.page_count:
                self.put_signature()
            return None
        menu = QMenu(self)
        opened = view.page_count > 0
        for kind, put in (
            (my_signature.SIGNATURE, self.tr("Poner mi firma")),
            (my_signature.INITIALS, self.tr("Poner mis iniciales")),
        ):
            saved = self.saved_signature(kind)
            if saved is None:
                continue
            action = menu.addAction(put)
            picture = QPixmap()
            picture.loadFromData(saved, "PNG")
            action.setIcon(QIcon(picture))
            action.setEnabled(opened)
            action.triggered.connect(lambda _checked=False, k=kind: self.put_signature(k))
            if kind == my_signature.INITIALS:
                everywhere = menu.addAction(self.tr("Poner mis iniciales en todas las páginas"))
                everywhere.setEnabled(opened)
                everywhere.triggered.connect(lambda _checked=False: self.initials_everywhere())
        dated = menu.addAction(self.tr("Poner la fecha de hoy debajo de la firma"))
        dated.setCheckable(True)
        dated.setChecked(self.date_with_signature)
        dated.toggled.connect(lambda on: self.settings.set(DATE_SETTING, bool(on)))
        menu.addSeparator()
        for kind, change, make, forget in (
            (
                my_signature.SIGNATURE,
                self.tr("Cambiar mi firma…"),
                self.tr("Crear mi firma…"),
                self.tr("Quitar mi firma"),
            ),
            (
                my_signature.INITIALS,
                self.tr("Cambiar mis iniciales…"),
                self.tr("Crear mis iniciales…"),
                self.tr("Quitar mis iniciales"),
            ),
        ):
            saved = self.saved_signature(kind)
            menu.addAction(change if saved else make).triggered.connect(
                lambda _checked=False, k=kind: self.make_signature(k)
            )
            if saved:
                menu.addAction(forget).triggered.connect(
                    lambda _checked=False, k=kind: self.forget_signature(k)
                )
        self.signature_menu = menu  # the tests pick from it
        menu.popup(QCursor.pos())
        return menu

    def _form_found(self, page: DocumentPage) -> None:
        if page is self.current_document:
            self.statusBar().showMessage(
                self.tr(
                    "Este documento es un formulario: haz clic en un campo para rellenarlo "
                    "(Tab pasa al siguiente)."
                ),
                STATUS_MESSAGE_MS,
            )

    # ---- links between documents ---------------------------------------------

    def link_selection(self) -> bool:
        """ "Enlazar a…": the words selected lead to a place of another document."""
        view = self.pdf_view
        if view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return False
        if not view.ask_link():
            self.statusBar().showMessage(
                self.tr(
                    "Selecciona primero las palabras que quieres enlazar "
                    "(o haz clic derecho en una nota)."
                ),
                STATUS_MESSAGE_MS,
            )
            return False
        return True

    def _link_asked(self, source: DocumentPage, area: tuple, words: str) -> bool:
        """Which document and where: then the other one is shown beside, at
        that place, until "Enlazar aquí"."""
        if source.path is None:
            return False
        answer = self.link_answer
        if answer is None:
            folder = str(self.settings.get(LIBRARY_FOLDER_SETTING) or "")
            opened = [
                (page.title, page.path)
                for page in self.documents
                if page is not source and page.path is not None
            ]
            mine = file_key(source.path)
            topics = []
            for path in topics_in(folder):
                if file_key(path) == mine:
                    continue
                try:
                    name = str(path.relative_to(folder))
                except ValueError:
                    name = path.name
                topics.append((name, path))
            dialog = LinkDialog(words, opened, topics, folder or str(source.path.parent), self)
            if not dialog.exec() or dialog.answer is None:
                return False
            answer = dialog.answer
        target_path, where = Path(answer[0]), answer[1].strip()
        if file_key(target_path) == file_key(source.path):
            self.statusBar().showMessage(
                self.tr("Un enlace lleva a otro documento: elige uno distinto de este."),
                STATUS_MESSAGE_MS,
            )
            return False
        target = self._open_beside(source, target_path)
        if target is None:
            return False
        if where.isdigit():
            target.view.scroll_to_page(int(where) - 1)
        elif where:
            lost = self.tr("No se ha encontrado «{0}»: ve tú al sitio.").format(where)
            if target.view.go_to_place(where):
                target.view.place_answered.connect(
                    lambda found: found or self.statusBar().showMessage(lost, STATUS_MESSAGE_MS),
                    Qt.ConnectionType.SingleShotConnection,
                )
            else:
                self.statusBar().showMessage(lost, STATUS_MESSAGE_MS)
        self._pending_link = (source, area, target)
        self.beside.ask_link_place(words)
        return True

    def _open_beside(self, source: DocumentPage, path: Path) -> DocumentPage | None:
        """Open ``path`` (if it is not open yet) beside ``source``, which stays in front."""
        if self.index_of_document(path) < 0 and not self.open_document(path):
            return None
        target = self.documents[self.index_of_document(path)]
        if target is source or source not in self.documents:
            return None
        if self.beside.page is source:
            self.stop_beside()  # the one with the link goes to the left half
        self.document_tabs.setCurrentIndex(self.documents.index(source))
        self.show_beside(target)
        return target

    def finish_link(self) -> bool:
        """ "Enlazar aquí": the link leads to the place shown beside."""
        pending, self._pending_link = self._pending_link, None
        self.beside.end_link()
        if pending is None:
            return False
        source, area, target = pending
        if (
            source not in self.documents
            or target not in self.documents
            or source.path is None
            or target.path is None
        ):
            return False
        page, top = target.view.place_for_link()
        file = relative_file(source.path, target.path)
        if not source.view.add_doc_link(file, page, top, area):
            return False
        self.document_tabs.setCurrentIndex(self.documents.index(source))
        self.statusBar().showMessage(
            self.tr("Enlace hecho: lleva a {0}, página {1}.").format(target.title, page + 1),
            STATUS_MESSAGE_MS,
        )
        return True

    def cancel_link(self) -> None:
        self._pending_link = None
        self.beside.end_link()

    def follow_doc_link(self, source: DocumentPage, link: DocLink) -> bool:
        """A click on a link: the other document opens beside, at its place.
        If it is not where the link says, it is looked for (and the links mended)."""
        if source.path is None:
            return False
        path = resolve(source.path, link.file)
        if not path.is_file():
            found = self._find_moved(source, link.file)
            if found is None:
                found = self._ask_where_is(link.file)
            if found is None:
                return False
            source.view.change_link_file(link.file, relative_file(source.path, found))
            path = found
        target = self._open_beside(source, path)
        if target is None:
            return False
        # After both halves have taken their new size.
        QTimer.singleShot(0, target.view, lambda: target.view.go_to_link_place(link.page, link.top))
        return True

    def _find_moved(self, source: DocumentPage, file: str) -> Path | None:
        """The document of a link that is not there: an open one or a topic of
        the library with the same name, if there is only one."""
        name = PurePosixPath(file.replace("\\", "/")).name.lower()
        if not name:
            return None
        folder = str(self.settings.get(LIBRARY_FOLDER_SETTING) or "")
        found: dict[str, Path] = {}
        candidates = [page.path for page in self.documents if page.path is not None]
        for path in [*candidates, *topics_in(folder)]:
            if path.name.lower() == name and file_key(path) != file_key(source.path):
                found.setdefault(file_key(path), Path(path))
        if len(found) != 1:
            return None
        path = next(iter(found.values()))
        self.statusBar().showMessage(
            self.tr(
                "«{0}» se había movido: está en {1}. Los enlaces a él se han corregido."
            ).format(path.name, path.parent),
            STATUS_MESSAGE_MS,
        )
        return path

    def _ask_where_is(self, file: str) -> Path | None:
        """ "Documento no encontrado": the user may say where it is now."""
        name = PurePosixPath(file.replace("\\", "/")).name
        answer = self.where_is_answer
        if answer is None:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle(self.tr("Documento no encontrado"))
            box.setText(self.tr("No se encuentra «{0}».").format(name))
            box.setInformativeText(
                self.tr(
                    "Puede que se haya movido o cambiado de nombre, o que este documento se "
                    "haya compartido sin él. Lo subrayado y las notas se siguen viendo."
                )
            )
            where = box.addButton(self.tr("¿Dónde está ahora?…"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(self.tr("Cerrar"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not where:
                return None
            answer, _filter = QFileDialog.getOpenFileName(
                self,
                self.tr("¿Dónde está ahora «{0}»?").format(name),
                "",
                self.tr("Documentos PDF (*.pdf)"),
            )
        if not answer:
            self.statusBar().showMessage(
                self.tr("Documento no encontrado: «{0}».").format(name), STATUS_MESSAGE_MS
            )
            return None
        path = Path(answer)
        return path if path.is_file() else None

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

    def add_bookmark(self) -> None:
        """Bookmark the place being read; it is listed first in the Índice."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        title = self.pdf_view.add_bookmark()
        if title:
            self.statusBar().showMessage(
                self.tr("Marcador «{0}» puesto. Lo tienes en el Índice (F4).").format(title),
                STATUS_MESSAGE_MS,
            )

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

    # ---- text recognition (OCR) -----------------------------------------

    def recognize_text(self, page: DocumentPage | None = None) -> bool:
        """Read the text of the scanned pages of a document, in the background.

        Its pages go on being read meanwhile; the strip above them shows how far
        it has got, with Cancelar. A document whose scans already have their
        text asks which pages to recognise again. False if nothing starts.
        """
        page = self._page_for_recognition(page)
        if page is None:
            return False
        view = page.view
        if not view.scanned_known:
            # Still looking at the pages: it starts as soon as they are known.
            page.recognize_when_known = True
            self.statusBar().showMessage(
                self.tr("Buscando las páginas escaneadas…"), STATUS_MESSAGE_MS
            )
            return True
        if not view.scanned_pages:
            if view.recognised_pages:
                return self.recognize_again(page)
            page.ocr_banner.finish()
            self.statusBar().showMessage(
                self.tr("Este documento ya tiene texto: no hay páginas escaneadas que reconocer."),
                STATUS_MESSAGE_MS,
            )
            return False
        return self._start_recognition(page, view.scanned_pages)

    def recognize_again(self, page: DocumentPage | None = None) -> bool:
        """Recognise again scanned pages that already have text (a poor one,
        made by another program or here): all of them or the ones chosen."""
        page = self._page_for_recognition(page)
        if page is None:
            return False
        view = page.view
        if not view.scanned_known:
            self.statusBar().showMessage(
                self.tr("Todavía estoy mirando las páginas. Prueba otra vez en un momento."),
                STATUS_MESSAGE_MS,
            )
            return False
        pictures = sorted({*view.scanned_pages, *view.recognised_pages})
        if not pictures:
            self.statusBar().showMessage(
                self.tr("Este documento no tiene páginas escaneadas: su texto es el suyo propio."),
                STATUS_MESSAGE_MS,
            )
            return False
        if self.recognize_again_answer is not None:  # the tests answer without asking
            pages = [number for number in self.recognize_again_answer if number in pictures]
        else:
            dialog = RecognizeAgainDialog(
                pictures, max(view.current_page, 0), view.page_count, self
            )
            if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.pages:
                return False
            pages = dialog.pages
        if not pages:
            return False
        return self._start_recognition(page, pages, replace=True)

    def _page_for_recognition(self, page: DocumentPage | None) -> DocumentPage | None:
        page = page or self.current_document
        if page is None or page.view.page_count == 0:
            self.statusBar().showMessage(
                self.tr("Abre un documento escaneado para reconocer su texto."), STATUS_MESSAGE_MS
            )
            return None
        if page.text_recognition is not None:
            return None  # already at it
        if not ocr.is_available():
            self._show_problem(
                self.tr("No se puede reconocer el texto"),
                self.tr("Falta el archivo del idioma español. Vuelve a instalar el programa."),
            )
            return None
        return page

    def _start_recognition(self, page: DocumentPage, pages: list[int], replace=False) -> bool:
        self.ocr_cache.forget_old()
        run = TextRecognition(page.view, pages, page, replace, self.ocr_cache)
        page.text_recognition = run
        run.progressed.connect(page.ocr_banner.show_progress)
        run.finished.connect(
            lambda written, total, failed, cancelled, p=page: self._text_recognised(
                p, written, total, failed, cancelled, replace
            )
        )
        run.failed.connect(self._text_recognition_failed)
        run.start()
        return True

    def _text_recognised(
        self,
        page: DocumentPage,
        written: int,
        total: int,
        failed: int,
        cancelled: bool,
        again: bool = False,
    ) -> None:
        page.text_recognition = None
        page.ocr_banner.finish()
        if cancelled:
            message = (
                self.tr(
                    "Reconocimiento cancelado. Las {0} páginas ya leídas tienen su texto."
                ).format(written)
                if written
                else self.tr("Reconocimiento cancelado.")
            )
        elif written == 0:
            message = self.tr("No se ha podido reconocer el texto de ninguna página.")
        elif again:
            message = self.tr(
                "Texto reconocido de nuevo en {0} páginas. Con Deshacer vuelve el de antes. "
                "Se guarda en el PDF al guardar."
            ).format(written)
        else:
            message = self.tr(
                "Texto reconocido en {0} páginas: ya puedes buscar, subrayar y copiar. "
                "Se guarda en el PDF al guardar."
            ).format(written)
            if written == 1:
                message = self.tr(
                    "Texto reconocido en 1 página: ya puedes buscar, subrayar y copiar. "
                    "Se guarda en el PDF al guardar."
                )
            if failed:
                message += " " + self.tr("{0} no se han podido leer.").format(failed)
        self.statusBar().showMessage(message, STATUS_MESSAGE_LONG_MS)
        if written and page.search_panel.box.text():
            page.search_panel.search_now()  # what is found may be more now

    def cancel_text_recognition(self, page: DocumentPage | None = None) -> None:
        page = page or self.current_document
        if page is not None and page.text_recognition is not None:
            page.text_recognition.cancel()

    def _text_recognition_failed(self, details: str) -> None:
        error = OcrError(details)
        self.reporter.log.record(type(error), error, None, "reconocer texto")

    # ---- signing with a digital certificate -------------------------------

    def sign_with_certificate(self) -> bool:
        """«Firmar con certificado»: the document in front, as it is saved.

        Changes not saved are saved first (asked), so that what is signed is
        what is seen. A visible signature (the default) needs a place: a click
        on the page says it. Then the certificate (the one used last time comes
        first) and where the signed document goes: a copy «-firmado» unless the
        document already is one. Returns True if it was signed (or the saving
        before signing, or choosing the place, has started).
        """
        page = self.current_document
        view = page.view
        if view.page_count == 0 or page.path is None:
            self.statusBar().showMessage(
                self.tr("Abre el documento que quieres firmar."), STATUS_MESSAGE_MS
            )
            return False
        view.finish_writing()
        if view.saving:
            return False
        if view.modified:
            if not self._save_before_signing(page):
                return False
            self._sign_when_saved = page
            if not self.save_document(page):
                self._sign_when_saved = None
                return False
            return True
        if certificate_settings.visible_wanted(self.settings):
            view.choose_certificate_place()
            self.statusBar().showMessage(
                self.tr(
                    "Haz clic en la página donde quieres la firma. Esc para cancelar. "
                    "(Firma invisible: en Ajustes → Firma.)"
                ),
                STATUS_MESSAGE_MS * 3,
            )
            return True
        return self._sign_at(page, None)

    def _certificate_placed(self, page: DocumentPage, number: int, rect) -> bool:
        """The place of a visible signature was chosen on ``page``."""
        if page.path is None or page.view.modified:
            # Changed after «Firmar con certificado» was pressed: start again.
            self.sign_with_certificate()
            return False
        png = None
        if certificate_settings.handwritten_wanted(self.settings):
            png = self.saved_signature(my_signature.SIGNATURE)
        return self._sign_at(page, Visible(number, tuple(rect), png))

    def _sign_at(self, page: DocumentPage, visible: Visible | None) -> bool:
        signer = self._choose_signer()
        if signer is None:
            return False
        target = self._signed_target(page.path)
        if target is None:
            return False
        return self.sign_document(page.path, target, signer, visible)

    def _save_before_signing(self, page: DocumentPage) -> bool:
        if self.sign_save_answer is not None:
            return self.sign_save_answer
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.tr("Firmar con certificado"))
        box.setText(
            self.tr(
                "«{0}» tiene cambios sin guardar. Para que entren en la firma, primero se guardan."
            ).format(page.path.name)
        )
        go = box.addButton(self.tr("Guardar y firmar"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(self.tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        box.exec()
        return box.clickedButton() is go

    def _sign_after_saving(self, page: DocumentPage, worked: bool) -> None:
        if self._sign_when_saved is not page:
            return
        self._sign_when_saved = None
        if worked and page is self.current_document:
            QTimer.singleShot(0, self.sign_with_certificate)

    def _sign_without_timestamp(self) -> bool:
        if self.timestamp_failed_answer is not None:
            return self.timestamp_failed_answer
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(self.tr("Sin sello de tiempo"))
        box.setText(
            self.tr(
                "No se ha podido conseguir el sello de tiempo (puede que no haya conexión "
                "a internet). La firma es válida igualmente sin él."
            )
        )
        go = box.addButton(self.tr("Firmar sin sello de tiempo"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(self.tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        box.exec()
        return box.clickedButton() is go

    def _choose_signer(self):
        """The certificate to sign with, ready (None: cancelled)."""
        if self.signer_answer is not None:
            return self.signer_answer
        dialog = CertificateDialog(
            self,
            preferred=str(self.settings.get(CERTIFICATE_SETTING) or ""),
            last_file=str(self.settings.get(CERTIFICATE_FILE_SETTING) or ""),
        )
        if dialog.exec() != CertificateDialog.DialogCode.Accepted or dialog.signer is None:
            return None
        if dialog.chosen:
            self.settings.set(CERTIFICATE_SETTING, dialog.chosen)
        if dialog.chosen_file:  # where it is, never its password
            self.settings.set(CERTIFICATE_FILE_SETTING, dialog.chosen_file)
        return dialog.signer

    def _signed_target(self, source: Path) -> Path | None:
        """Where the signed document goes: asked, «-firmado» proposed."""
        suggested = source if source.stem.lower().endswith("-firmado") else signed_name(source)
        if self.sign_target_answer is not None:
            chosen = self.sign_target_answer(suggested)
        else:
            chosen, _filter = QFileDialog.getSaveFileName(
                self,
                self.tr("Guardar el documento firmado como"),
                str(suggested),
                self.tr("Documentos PDF (*.pdf)"),
            )
        if not chosen:
            return None
        target = Path(chosen).absolute()
        if target.suffix.lower() != ".pdf":
            target = target.with_name(target.name + ".pdf")
        return target

    def sign_document(
        self, source: Path, target: Path, signer, visible: Visible | None = None
    ) -> bool:
        """Sign ``source`` into ``target`` and tell how it went. The signed
        document is shown: in its own tab if it was open (``source`` itself,
        signed in its place), or in a new one. With a timestamp if the
        settings ask for one; if its server fails, signing without it is offered."""
        source, target = Path(source), Path(target)
        open_tab = self.index_of_document(target)
        in_place = open_tab >= 0 or (target.exists() and file_key(target) == file_key(source))
        written = target
        if in_place:
            # The open file cannot be replaced while it is shown: sign beside it.
            handle, name = tempfile.mkstemp(dir=target.parent, prefix=".firmado-", suffix=".pdf")
            os.close(handle)
            written = Path(name)
        server = ""
        if certificate_settings.timestamp_wanted(self.settings):
            server = certificate_settings.timestamp_server(self.settings)
        try:
            try:
                sign_pdf(source, written, signer, visible, server)
            except TimestampFailed as error:
                self.reporter.log.record(type(error), error, error.__traceback__, "sello de tiempo")
                if not self._sign_without_timestamp():
                    raise SigningCancelled() from error
                sign_pdf(source, written, signer, visible)
        except SigningCancelled:
            self.statusBar().showMessage(self.tr("Firma cancelada."), STATUS_MESSAGE_MS)
            self._forget_file(written if in_place else None)
            return False
        except PasswordProtected:
            self._forget_file(written if in_place else None)
            self._show_problem(
                self.tr("Este PDF tiene contraseña"),
                self.tr("Todavía no se pueden firmar documentos con contraseña."),
            )
            return False
        except SigningError as error:
            self._forget_file(written if in_place else None)
            self.reporter.log.record(type(error), error, error.__traceback__, "firmar")
            self._show_problem(
                self.tr("No se ha podido firmar"),
                self.tr(
                    "El documento original no se ha tocado. Con Ayuda → «Copiar informe "
                    "de error» puedes ver el detalle."
                ),
            )
            return False
        if in_place and not self._put_signed_in_place(written, target):
            return False
        if self.index_of_document(target) < 0:
            self.open_document(target)
        who = getattr(getattr(signer, "signing_cert", None), "subject", None)
        name = ""
        if who is not None:
            name = who.native.get("common_name", "") if hasattr(who, "native") else ""
        message = (
            self.tr("Documento firmado por {0} y guardado como «{1}».").format(name, target.name)
            if name
            else self.tr("Documento firmado y guardado como «{0}».").format(target.name)
        )
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

    @staticmethod
    def _forget_file(path: Path | None) -> None:
        if path is not None:
            with contextlib.suppress(OSError):
                path.unlink()

    def _put_signed_in_place(self, signed: Path, target: Path) -> bool:
        """The signed copy takes the place of the open file ``target``: its tab
        lets go of it, how it was is kept among the earlier versions, and it
        opens again at the same page."""
        index = self.index_of_document(target)
        place = -1
        if index >= 0:
            place = self.documents[index].view.current_page
            self.close_document(index, ask=False)
        with contextlib.suppress(Exception):
            self.versions.keep(target)
        error = ""
        for _attempt in range(RESTORE_TRIES):
            try:
                os.replace(signed, target)
                error = ""
                break
            except OSError as failed:
                error = str(failed)
                time.sleep(RESTORE_PAUSE)  # the helper may need a moment to let go
        if error:
            self._forget_file(signed)
            if index >= 0:
                self.open_document(target)
            self._show_problem(
                self.tr("No se ha podido firmar"),
                self.tr(
                    "«{0}» sigue como estaba: otro programa lo tiene abierto. Ciérralo y "
                    "vuelve a firmar, o firma una copia con otro nombre."
                ).format(target.name),
            )
            return False
        if index >= 0 and self.open_document(target):
            now = self.index_of_document(target)
            if 0 <= now != index and index < len(self.documents):
                self.document_tabs.moveTab(now, index)
                self.document_tabs.setCurrentIndex(index)
            if 0 < place < self.pdf_view.page_count:
                self.pdf_view.scroll_to_page(place)
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

    def go_to_page(self, place: bool = False) -> None:
        """Put the cursor in the page number of the status bar (where an
        article or a section can be written too, ``place``)."""
        if self.pdf_view.page_count == 0:
            self.statusBar().showMessage(self.tr("Abre primero un documento."), STATUS_MESSAGE_MS)
            return
        if self._full_screen:
            self.set_full_screen(False)  # the page number lives in the status bar
        self.page_box.start(place)

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

    def _scanned_found(self, page: DocumentPage, scanned: list[int], count: int) -> None:
        """The document has been looked at: offer to recognise the text of
        its scanned pages, unless the user said not to."""
        if page.text_recognition is not None:
            return  # being recognised: the strip shows how far it has got
        if page.recognize_when_known:
            page.recognize_when_known = False
            self.recognize_text(page)
            return
        wanted = bool(scanned) and ocr.offer_wanted(self.settings)
        if wanted and page.path is not None and ocr.declined(self.settings, page.path):
            wanted = False
        if wanted:
            page.ocr_banner.offer(len(scanned), count)
        else:
            page.ocr_banner.hide()

    def _recognize_offered(self, page: DocumentPage) -> None:
        page.ocr_banner.hide()
        if page in self.documents:
            self.document_tabs.setCurrentIndex(self.documents.index(page))
        self.recognize_text(page)

    def _ocr_declined(self, page: DocumentPage) -> None:
        if page.path is not None:
            ocr.decline(self.settings, page.path)
        self.statusBar().showMessage(
            self.tr(
                "No te lo volveré a ofrecer en este documento. «Reconocer texto» sigue "
                "en el modo Estudiar."
            ),
            STATUS_MESSAGE_MS,
        )

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
        for page in self.documents:
            page.view.finish_writing()  # what is being typed is not lost unasked
        pending = [page for page in self.documents if page.view.modified]
        if pending:
            answer = self._ask_unsaved(pending)
            if answer != DISCARD:
                event.ignore()
                if answer == SAVE:
                    # Closing goes on by itself when every one is saved.
                    self._save_then(pending, self.close)
                else:
                    self.restart_wanted = False
                    self.after_exit_command = None
                return
        if self._print_run is not None:
            self._print_run.cancel()
        self.updater.cancel()
        self._place_timer.stop()
        self._autosave_timer.stop()
        for page in self.documents:
            self._remember_place(page)
            self._set_changes_aside(page)  # "No guardar": recoverable for some days
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

    beside_asked = Signal(int)  # right click → "Ver al lado" on that tab

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        index = self.tabAt(event.pos())
        if index < 0 or self.count() < 2:
            return
        window = self.window()
        beside = getattr(window, "beside_page", None)
        documents = getattr(window, "documents", [])
        shown = 0 <= index < len(documents) and documents[index] is beside
        menu = QMenu(self)
        menu.addAction(
            self.tr("Dejar de verlo al lado") if shown else self.tr("Ver al lado"),
            lambda: self.beside_asked.emit(index),
        )
        menu.addAction(self.tr("Cerrar"), lambda: self.tabCloseRequested.emit(index))
        menu.exec(event.globalPos())

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
