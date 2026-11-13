"""The settings window: the preferences of the program, in one place.

Every change is applied and saved at once; there is nothing to accept. The
only exception is the size of the interface, which needs a restart: the window
says so and offers to do it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import file_association
from app.core.history import RESTORE_SETTING
from app.core.interface_size import NORMAL_SIZE, SIZE_SETTING, SIZES, wanted_size
from app.core.paths import is_portable
from app.core.updates import CHECK_SETTING
from app.ui.theme import Paper, Theme


class SettingsDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.settings = window.settings
        self.setWindowTitle(self.tr("Ajustes"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        # ---- appearance ----
        layout.addWidget(self._heading(self.tr("Aspecto")))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.theme_box = QComboBox()
        self.theme_box.setAccessibleName(self.tr("Tema"))
        for theme, name in (
            (Theme.SYSTEM, self.tr("Como el sistema")),
            (Theme.LIGHT, self.tr("Claro")),
            (Theme.DARK, self.tr("Oscuro")),
        ):
            self.theme_box.addItem(name, theme)
        self.theme_box.setCurrentIndex(self.theme_box.findData(window.theme))
        self.theme_box.activated.connect(
            lambda _index: window.set_theme(self.theme_box.currentData())
        )
        form.addRow(self.tr("&Tema:"), self.theme_box)

        self.paper_box = QComboBox()
        self.paper_box.setAccessibleName(self.tr("Papel de las páginas"))
        self.paper_box.setToolTip(
            self.tr("Solo cambia cómo se ven las páginas en pantalla, no el PDF ni lo impreso")
        )
        for paper, name in (
            (Paper.WHITE, self.tr("Blanco (como es el documento)")),
            (Paper.SEPIA, self.tr("Sepia (tono cálido para leer muchas horas)")),
            (Paper.NIGHT, self.tr("Noche (papel oscuro y letra clara)")),
        ):
            self.paper_box.addItem(name, paper)
        self.paper_box.setCurrentIndex(self.paper_box.findData(window.paper))
        self.paper_box.activated.connect(
            lambda _index: window.set_paper(self.paper_box.currentData())
        )
        form.addRow(self.tr("&Papel de las páginas:"), self.paper_box)

        self.size_box = QComboBox()
        self.size_box.setAccessibleName(self.tr("Tamaño de la interfaz"))
        self.size_box.setToolTip(self.tr("Tamaño de los botones, los menús y las letras"))
        for size in SIZES:
            name = self.tr("{0} %").format(size)
            if size == NORMAL_SIZE:
                name = self.tr("{0} % (normal)").format(size)
            self.size_box.addItem(name, size)
        self.size_box.setCurrentIndex(self.size_box.findData(wanted_size(self.settings)))
        self.size_box.activated.connect(self._size_chosen)
        self.toolbar_box = QComboBox()
        self.toolbar_box.setAccessibleName(self.tr("Barra de herramientas"))
        self.toolbar_box.setToolTip(
            self.tr(
                "Sin nombres la barra ocupa menos y el documento se ve más grande. "
                "El nombre de cada botón sale al dejar el ratón encima."
            )
        )
        self.toolbar_box.addItem(self.tr("Botones con nombre"), False)
        self.toolbar_box.addItem(self.tr("Solo iconos (más sitio para el documento)"), True)
        self.toolbar_box.setCurrentIndex(self.toolbar_box.findData(window.toolbar_icons_only))
        self.toolbar_box.activated.connect(
            lambda _index: window.set_toolbar_icons_only(self.toolbar_box.currentData())
        )
        form.addRow(self.tr("&Barra de herramientas:"), self.toolbar_box)

        form.addRow(self.tr("Tamaño de la &interfaz:"), self.size_box)
        layout.addLayout(form)

        self.restart_row = QWidget()
        restart_layout = QHBoxLayout(self.restart_row)
        restart_layout.setContentsMargins(0, 0, 0, 0)
        note = QLabel(
            self.tr("El tamaño nuevo se verá al reiniciar el programa. Tus pestañas vuelven solas.")
        )
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        self.restart_button = QPushButton(self.tr("Reiniciar ahora"))
        self.restart_button.clicked.connect(self._restart)
        restart_layout.addWidget(note, 1)
        restart_layout.addWidget(self.restart_button)
        layout.addWidget(self.restart_row)

        # ---- when the program opens ----
        layout.addWidget(self._heading(self.tr("Al abrir el programa")))
        self.restore_box = QCheckBox(self.tr("&Volver a las pestañas de la última vez"))
        self.restore_box.setChecked(window.history.restore_wanted)
        self.restore_box.toggled.connect(lambda on: self.settings.set(RESTORE_SETTING, on))
        layout.addWidget(self.restore_box)

        # ---- new versions ----
        layout.addWidget(self._heading(self.tr("Versiones nuevas")))
        self.updates_box = QCheckBox(self.tr("&Avisarme cuando haya una versión nueva"))
        self.updates_box.setToolTip(
            self.tr(
                "Al abrir el programa pregunta a GitHub si hay versión nueva. "
                "No envía ningún dato tuyo ni de tus documentos."
            )
        )
        self.updates_box.setChecked(window.updater.check_wanted)
        self.updates_box.toggled.connect(lambda on: self.settings.set(CHECK_SETTING, on))
        layout.addWidget(self.updates_box)
        updates_note = QLabel(
            self.tr(
                "Nunca se actualiza solo: siempre te pregunta antes. Versión actual: {0}."
            ).format(window.updater.current_version)
        )
        updates_note.setObjectName("dialogNote")
        updates_note.setWordWrap(True)
        layout.addWidget(updates_note)

        # ---- the program Windows uses for PDFs ----
        self.default_button: QPushButton | None = None
        self.forget_button: QPushButton | None = None
        if file_association.available():
            self._build_default_program(layout)

        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr("Cerrar"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_restart_row()

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("settingsHeading")
        return label

    def _build_default_program(self, layout: QVBoxLayout) -> None:
        layout.addWidget(self._heading(self.tr("Abrir los PDF con Lector-PDF")))
        note = QLabel(
            self.tr(
                "Windows no deja que un programa se elija solo: se abrirá la ventana de "
                "Windows y allí eliges Lector-PDF para los archivos .pdf."
            )
        )
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.default_button = QPushButton(self.tr("Usar Lector-PDF para abrir los PDF…"))
        self.default_button.clicked.connect(self._make_default)
        row.addWidget(self.default_button)
        # The portable version leaves nothing behind unless asked: it can undo it.
        self.forget_button = QPushButton(self.tr("Quitar de «Abrir con»"))
        self.forget_button.setToolTip(
            self.tr("Windows deja de ofrecer este programa para abrir los PDF")
        )
        self.forget_button.clicked.connect(self._forget_default)
        row.addWidget(self.forget_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.default_status = QLabel()
        self.default_status.setObjectName("dialogNote")
        self.default_status.setWordWrap(True)
        layout.addWidget(self.default_status)
        self._refresh_default_program()

    def _refresh_default_program(self) -> None:
        self.forget_button.setVisible(is_portable() and file_association.is_registered())

    def _make_default(self) -> None:
        if not file_association.register():
            self.default_status.setText(
                self.tr("No se ha podido avisar a Windows. Prueba desde «Abrir con» en un PDF.")
            )
            return
        opened = file_association.open_windows_default_programs()
        self.default_status.setText(
            self.tr("Hecho. En la ventana de Windows, busca Lector-PDF y elígelo para .pdf.")
            if opened
            else self.tr(
                "Hecho. Ahora, clic derecho en un PDF → Abrir con → Elegir otra aplicación "
                "→ Lector-PDF → Siempre."
            )
        )
        self._refresh_default_program()

    def _forget_default(self) -> None:
        file_association.unregister()
        self.default_status.setText(self.tr("Windows ya no ofrece Lector-PDF para los PDF."))
        self._refresh_default_program()

    def _size_chosen(self, _index: int) -> None:
        self.settings.set(SIZE_SETTING, self.size_box.currentData())
        self._refresh_restart_row()

    def _refresh_restart_row(self) -> None:
        """The restart is offered only while the size chosen is not the one in use."""
        self.restart_row.setVisible(self.size_box.currentData() != self.window_.interface_size)

    def _restart(self) -> None:
        self.accept()
        self.window_.restart_program()
