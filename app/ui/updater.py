"""New versions in the window: the quiet notice and "Actualizar ahora".

``Updater`` does the slow parts (asking GitHub, downloading) in background
threads and reports with signals. ``UpdateBanner`` is the thin strip that shows
the notice; it never interrupts what the user is doing.
"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from app import __version__
from app.core import updates
from app.core.paths import data_dir, is_packaged, is_portable, program_dir
from app.core.settings import Settings
from app.core.updates import Release, UpdateCancelled, UpdateError


class Updater(QObject):
    """Looks for new versions and prepares their installation."""

    # A newer version is published: Release.
    found = Signal(object)
    # A check asked by hand ended: True if GitHub answered (and there is nothing new).
    nothing_new = Signal(bool)
    # Download progress, 0 to 100.
    progress = Signal(int)
    # The new version is downloaded and checked. The command installs it once
    # this program has closed: list[str].
    ready = Signal(list)
    # The update could not be prepared (True if the user cancelled it).
    failed = Signal(bool)

    def __init__(
        self,
        settings: Settings,
        parent: QObject | None = None,
        opener: updates.Opener | None = None,
        current_version: str = __version__,
        data_folder: Path | None = None,
        portable: bool | None = None,
        packaged: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self._opener = opener if opener is not None else updates._open
        self.current_version = current_version
        self._data_folder = data_folder if data_folder is not None else data_dir()
        self.portable = is_portable() if portable is None else portable
        self.packaged = is_packaged() if packaged is None else packaged
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.release: Release | None = None

    # ---- settings ----

    @property
    def check_wanted(self) -> bool:
        return self.settings.get(updates.CHECK_SETTING, True) is not False

    def skip(self, release: Release) -> None:
        """Do not mention this version again when starting."""
        self.settings.set(updates.SKIPPED_SETTING, release.version)

    @property
    def can_install(self) -> bool:
        """Only the built Windows program can replace itself."""
        return self.packaged

    # ---- looking for a version ----

    def check(self, by_hand: bool = False) -> None:
        """Ask GitHub in the background. When starting, quietly and only if wanted."""
        if not by_hand and not self.check_wanted:
            return
        if self.busy:
            return
        self._thread = threading.Thread(
            target=self._check, args=(by_hand,), name="update-check", daemon=True
        )
        self._thread.start()

    def _check(self, by_hand: bool) -> None:
        try:
            release = updates.newer_release(self.current_version, self._opener, self.portable)
        except UpdateError:
            if by_hand:
                self.nothing_new.emit(False)
            return  # when starting: no network is not worth a word
        if release is None:
            if by_hand:
                self.nothing_new.emit(True)
            return
        skipped = self.settings.get(updates.SKIPPED_SETTING) == release.version
        if skipped and not by_hand:
            return
        self.release = release
        self.found.emit(release)

    # ---- downloading it ----

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_update(self, release: Release) -> bool:
        """Download ``release`` in the background. False if that is not possible here."""
        asset = release.asset(self.portable)
        if not self.can_install or asset is None or self.busy:
            return False
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._prepare, args=(release, asset), name="update-download", daemon=True
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        self._cancel.set()

    def wait(self, seconds: float = 30) -> None:
        """Wait for the background work (used when closing, and by the tests)."""
        if self._thread is not None:
            self._thread.join(seconds)

    def _prepare(self, release: Release, asset: updates.Asset) -> None:
        folder = updates.update_folder(self._data_folder)
        last = -1

        def step(received: int, total: int) -> None:
            nonlocal last
            percent = int(received * 100 / total) if total else 0
            if percent != last:
                last = percent
                self.progress.emit(percent)

        try:
            file = updates.download(release, asset, folder, step, self._cancel.is_set, self._opener)
            if self.portable:
                new = updates.unpack_portable(file, folder / "nueva")
                command = updates.portable_update_command(new, program_dir(), os.getpid())
            else:
                command = updates.installer_command(file)
        except UpdateCancelled:
            self.failed.emit(True)
            return
        except UpdateError:
            self.failed.emit(False)
            return
        self.ready.emit(command)


class UpdateBanner(QFrame):
    """The strip that says a new version exists. Hidden until there is one."""

    update_wanted = Signal()
    cancel_wanted = Signal()
    skip_wanted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.page = updates.RELEASES_PAGE
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(8)
        self.message = QLabel()
        self.message.setObjectName("updateMessage")
        layout.addWidget(self.message)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(160)
        self.bar.setAccessibleName(self.tr("Descarga de la versión nueva"))
        layout.addWidget(self.bar)
        layout.addStretch(1)
        self.update_button = QPushButton(self.tr("Actualizar ahora"))
        self.update_button.setObjectName("bannerMainButton")
        self.update_button.setDefault(False)
        self.update_button.clicked.connect(self.update_wanted)
        self.news_button = QPushButton(self.tr("Ver novedades"))
        self.news_button.setToolTip(self.tr("Abre en el navegador la página de la versión"))
        self.news_button.clicked.connect(self.open_page)
        self.later_button = QPushButton(self.tr("Ahora no"))
        self.later_button.setToolTip(
            self.tr("Te lo recordaré la próxima vez que abras el programa")
        )
        self.later_button.clicked.connect(self.hide)
        self.skip_button = QPushButton(self.tr("Omitir esta versión"))
        self.skip_button.setToolTip(self.tr("No volver a avisar de esta versión"))
        self.skip_button.clicked.connect(self._skip)
        self.cancel_button = QPushButton(self.tr("Cancelar"))
        self.cancel_button.clicked.connect(self.cancel_wanted)
        for button in (
            self.update_button,
            self.news_button,
            self.later_button,
            self.skip_button,
            self.cancel_button,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
        self.hide()

    def _choices(self, shown: bool) -> None:
        for button in (self.update_button, self.news_button, self.later_button, self.skip_button):
            button.setVisible(shown)

    def offer(self, release: Release, can_install: bool) -> None:
        """Say that ``release`` exists and offer to install it."""
        self.page = release.page
        self.message.setText(
            self.tr("Hay una versión nueva de Lector-PDF: la {0}.").format(release.version)
        )
        self.update_button.setText(
            self.tr("Actualizar ahora") if can_install else self.tr("Ir a la descarga")
        )
        self.bar.hide()
        self.cancel_button.hide()
        self._choices(True)
        self.show()

    def downloading(self, percent: int) -> None:
        self.message.setText(self.tr("Descargando la versión nueva… {0} %").format(percent))
        self.bar.setValue(percent)
        self.bar.show()
        self.cancel_button.show()
        self._choices(False)
        self.show()

    def installing(self) -> None:
        self.message.setText(self.tr("Instalando. El programa se abrirá solo en un momento…"))
        self.bar.hide()
        self.cancel_button.hide()
        self._choices(False)
        self.show()

    def problem(self, text: str) -> None:
        self.message.setText(text)
        self.bar.hide()
        self.cancel_button.hide()
        self._choices(True)
        self.skip_button.hide()
        self.show()

    def open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.page))

    def _skip(self) -> None:
        self.skip_wanted.emit()
        self.hide()
