"""The settings window: the preferences of the program, in one place.

Every change is applied and saved at once; there is nothing to accept. The
only exception is the size of the interface, which needs a restart: the window
says so and offers to do it.

Two tabs, so that the window fits in a small screen: "General" and "Guardado".
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core import file_association, pen, save_settings
from app.core.history import RESTORE_SETTING
from app.core.interface_size import NORMAL_SIZE, SIZE_SETTING, SIZES, wanted_size
from app.core.paths import is_portable
from app.core.tool_keys import TOOL_KEYS_SETTING, tool_keys_wanted
from app.core.updates import CHECK_SETTING
from app.ui.theme import Paper, Theme
from app.ui.when import days_text


class SettingsDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.settings = window.settings
        self.setWindowTitle(self.tr("Ajustes"))
        self.setMinimumWidth(460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        general = QWidget()
        self.tabs.addTab(general, self.tr("General"))
        self.tabs.addTab(self._build_saving(), self.tr("Guardado"))
        self.tabs.addTab(self._build_pen(), self.tr("Lápiz y dedo"))

        layout = QVBoxLayout(general)
        layout.setContentsMargins(16, 12, 16, 12)
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

        # ---- keys ----
        layout.addWidget(self._heading(self.tr("Teclado")))
        self.tool_keys_box = QCheckBox(self.tr("Una &tecla para cada herramienta (R, S, T…)"))
        self.tool_keys_box.setToolTip(
            self.tr(
                "Con el documento delante: R resalta, S subraya, T tacha, N nota, X texto, "
                "D dibuja, F formas, B borrador, O oculta las anotaciones y los números "
                "cogen las favoritas. Esc suelta la herramienta."
            )
        )
        self.tool_keys_box.setChecked(tool_keys_wanted(self.settings))
        self.tool_keys_box.toggled.connect(self._tool_keys_chosen)
        layout.addWidget(self.tool_keys_box)

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
        outer.addWidget(buttons)
        self._refresh_restart_row()
        # Notes that take several lines make a page taller than it says: give
        # the tabs the height the tallest one really needs.
        inside = self.minimumWidth() - 40
        self.tabs.setMinimumHeight(
            max(
                self.tabs.widget(index).layout().minimumHeightForWidth(inside)
                for index in range(self.tabs.count())
            )
            + self.tabs.tabBar().sizeHint().height()
            + 8
        )

    def _tool_keys_chosen(self, on: bool) -> None:
        self.settings.set(TOOL_KEYS_SETTING, on)
        self.window_.apply_tool_keys()

    # ---- pen and fingers ---------------------------------------------------

    def _build_pen(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        settings = self.settings

        intro = QLabel(
            self.tr(
                "Para pantallas táctiles y lápices. No hace falta tocar nada: con dos dedos "
                "se mueve y se amplía la página, y el lápiz dibuja con la herramienta elegida."
            )
        )
        intro.setObjectName("dialogNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._heading(self.tr("Lápiz")))
        self.pressure_box = QCheckBox(self.tr("Trazo más &grueso al apretar más el lápiz"))
        self.pressure_box.setToolTip(
            self.tr(
                "Solo con lápices que notan la presión. Sin esto, todo el trazo tiene "
                "el grosor elegido."
            )
        )
        self.pressure_box.setChecked(pen.pressure_wanted(settings))
        self.pressure_box.toggled.connect(lambda on: self._set_pen(pen.PRESSURE_SETTING, on))
        layout.addWidget(self.pressure_box)
        pen_note = QLabel(
            self.tr(
                "La goma del lápiz, o su botón apretado, borran sin tener que cambiar "
                "de herramienta."
            )
        )
        pen_note.setObjectName("dialogNote")
        pen_note.setWordWrap(True)
        layout.addWidget(pen_note)

        layout.addWidget(self._heading(self.tr("El dedo, con una herramienta en la mano")))
        self.finger_box = QComboBox()
        self.finger_box.setAccessibleName(self.tr("El dedo, con una herramienta en la mano"))
        for choice, name in (
            (pen.AUTO, self.tr("Automático: dibuja hasta que se use un lápiz")),
            (pen.DRAWS, self.tr("Dibuja y marca, como el lápiz")),
            (pen.MOVES, self.tr("Solo mueve la página")),
        ):
            self.finger_box.addItem(name, choice)
        self._choose(self.finger_box, pen.finger_mode(settings))
        self.finger_box.activated.connect(
            lambda _index: self._set_pen(pen.FINGER_SETTING, self.finger_box.currentData())
        )
        layout.addWidget(self.finger_box)
        self.finger_note = QLabel()
        self.finger_note.setObjectName("dialogNote")
        self.finger_note.setWordWrap(True)
        layout.addWidget(self.finger_note)

        layout.addStretch(1)
        self._refresh_pen()
        return page

    def _set_pen(self, name: str, value) -> None:
        self.settings.set(name, value)
        self.window_.apply_pen_settings()
        self._refresh_pen()

    def _refresh_pen(self) -> None:
        mode = pen.finger_mode(self.settings)
        if mode == pen.DRAWS:
            text = self.tr(
                "El dedo usa la herramienta elegida. Con dos dedos se mueve y se amplía la página."
            )
        elif mode == pen.MOVES:
            text = self.tr(
                "El dedo nunca pinta: se puede apoyar la mano en la pantalla al escribir "
                "con el lápiz."
            )
        elif pen.pen_seen(self.settings):
            text = self.tr(
                "Ya se ha usado un lápiz en este ordenador: el dedo solo mueve la página, "
                "para poder apoyar la mano al escribir."
            )
        else:
            text = self.tr(
                "Todavía no se ha usado ningún lápiz: el dedo usa la herramienta elegida. "
                "En cuanto se use un lápiz, el dedo solo moverá la página."
            )
        self.finger_note.setText(text)

    # ---- saving ------------------------------------------------------------

    def _build_saving(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        settings = self.settings

        intro = QLabel(
            self.tr(
                "No hace falta tocar nada: tal como viene, el programa nunca cambia un PDF "
                "sin que se lo pidas, y lo que haces no se pierde aunque se vaya la luz."
            )
        )
        intro.setObjectName("dialogNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._heading(self.tr("Al cerrar con cambios sin guardar")))
        self.close_box = QComboBox()
        self.close_box.setAccessibleName(self.tr("Al cerrar con cambios sin guardar"))
        for choice, name in (
            (save_settings.ASK, self.tr("Preguntar qué hacer")),
            (save_settings.SAVE, self.tr("Guardar siempre, sin preguntar")),
            (save_settings.DISCARD, self.tr("No guardar nunca sin que lo pida")),
        ):
            self.close_box.addItem(name, choice)
        self.close_box.setCurrentIndex(
            self.close_box.findData(save_settings.close_choice(settings))
        )
        self.close_box.activated.connect(
            lambda _index: self._set(save_settings.CLOSE_SETTING, self.close_box.currentData())
        )
        layout.addWidget(self.close_box)
        self.close_note = QLabel()
        self.close_note.setObjectName("dialogNote")
        self.close_note.setWordWrap(True)
        layout.addWidget(self.close_note)

        layout.addWidget(self._heading(self.tr("Guardar solo mientras trabajo")))
        self.autosave_box = QCheckBox(self.tr("&Guardar solo en el PDF cuando paro de editar"))
        self.autosave_box.setToolTip(
            self.tr(
                "Guarda tras un rato sin hacer cambios y al cambiar de pestaña; nunca "
                "mientras editas. Un PDF firmado no se guarda solo nunca."
            )
        )
        self.autosave_box.setChecked(save_settings.autosave_wanted(settings))
        self.autosave_box.toggled.connect(lambda on: self._set(save_settings.AUTOSAVE_SETTING, on))
        layout.addWidget(self.autosave_box)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.autosave_seconds_box = QComboBox()
        self.autosave_seconds_box.setAccessibleName(self.tr("Tiempo sin editar antes de guardar"))
        for seconds in save_settings.AUTOSAVE_SECONDS_CHOICES:
            name = (
                self.tr("{0} segundos").format(seconds)
                if seconds < 60
                else self.tr("1 minuto")
                if seconds == 60
                else self.tr("{0} minutos").format(seconds // 60)
            )
            self.autosave_seconds_box.addItem(name, seconds)
        self._choose(self.autosave_seconds_box, save_settings.autosave_seconds(settings))
        self.autosave_seconds_box.activated.connect(
            lambda _index: self._set(
                save_settings.AUTOSAVE_SECONDS_SETTING, self.autosave_seconds_box.currentData()
            )
        )
        form.addRow(self.tr("Guardar tras estar sin &editar:"), self.autosave_seconds_box)
        layout.addLayout(form)

        layout.addWidget(self._heading(self.tr("Versiones anteriores")))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.versions_count_box = QComboBox()
        self.versions_count_box.setAccessibleName(self.tr("Versiones de cada documento"))
        for count in save_settings.VERSIONS_COUNT_CHOICES:
            self.versions_count_box.addItem(self.tr("{0} versiones").format(count), count)
        self._choose(self.versions_count_box, save_settings.versions_count(settings))
        self.versions_count_box.activated.connect(
            lambda _index: self._set(
                save_settings.VERSIONS_COUNT_SETTING, self.versions_count_box.currentData()
            )
        )
        form.addRow(self.tr("De cada &documento se conservan:"), self.versions_count_box)
        self.versions_room_box = QComboBox()
        self.versions_room_box.setAccessibleName(self.tr("Espacio para las versiones"))
        for megabytes in save_settings.VERSIONS_ROOM_CHOICES:
            name = (
                self.tr("{0} MB").format(megabytes)
                if megabytes < 1024
                else self.tr("{0} GB").format(megabytes // 1024)
            )
            self.versions_room_box.addItem(name, megabytes)
        self._choose(self.versions_room_box, save_settings.versions_room_mb(settings))
        self.versions_room_box.activated.connect(
            lambda _index: self._set(
                save_settings.VERSIONS_ROOM_SETTING, self.versions_room_box.currentData()
            )
        )
        form.addRow(self.tr("Entre todas pueden &ocupar:"), self.versions_room_box)
        layout.addLayout(form)
        versions_note = QLabel(
            self.tr("Cuando se pasa de ahí, se borran las más antiguas la próxima vez que guardes.")
        )
        versions_note.setObjectName("dialogNote")
        versions_note.setWordWrap(True)
        layout.addWidget(versions_note)

        layout.addWidget(self._heading(self.tr("Cambios descartados")))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.discarded_days_box = QComboBox()
        self.discarded_days_box.setAccessibleName(
            self.tr("Días que se conservan los cambios descartados")
        )
        self.discarded_days_box.setToolTip(
            self.tr(
                "Lo que dejas sin guardar al cerrar sigue en Archivo → Recuperar cambios "
                "descartados durante este tiempo."
            )
        )
        for days in save_settings.DISCARDED_DAYS_CHOICES:
            self.discarded_days_box.addItem(days_text(days), days)
        self._choose(self.discarded_days_box, save_settings.discarded_days(settings))
        self.discarded_days_box.activated.connect(
            lambda _index: self._set(
                save_settings.DISCARDED_DAYS_SETTING, self.discarded_days_box.currentData()
            )
        )
        form.addRow(self.tr("Se &conservan:"), self.discarded_days_box)
        layout.addLayout(form)

        layout.addStretch(1)
        self._refresh_saving()
        return page

    @staticmethod
    def _choose(box: QComboBox, value) -> None:
        box.setCurrentIndex(box.findData(value))

    def _set(self, name: str, value) -> None:
        """A saving preference has been chosen: keep it and follow it at once."""
        self.settings.set(name, value)
        self.window_.apply_save_settings()
        self._refresh_saving()

    def _refresh_saving(self) -> None:
        autosave = self.autosave_box.isChecked()
        # With saving by itself, closing saves too: there is nothing to choose.
        self.close_box.setEnabled(not autosave)
        self.autosave_seconds_box.setEnabled(autosave)
        days = days_text(save_settings.discarded_days(self.settings))
        if autosave:
            note = self.tr(
                "Con «Guardar solo» activado, al cerrar también se guarda sin preguntar."
            )
        elif self.close_box.currentData() == save_settings.SAVE:
            note = self.tr(
                "Si no querías guardar algo, está en Archivo → Versiones anteriores. "
                "Un PDF firmado sigue preguntando antes."
            )
        elif self.close_box.currentData() == save_settings.DISCARD:
            note = self.tr(
                "Cierra sin preguntar y sin tocar el PDF. Los cambios se conservan {0} en "
                "Archivo → Recuperar cambios descartados."
            ).format(days)
        else:
            note = self.tr("Te pregunta: Guardar / No guardar / Cancelar.")
        self.close_note.setText(note)

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
