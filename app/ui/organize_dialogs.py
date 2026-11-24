"""«Unir», «Dividir», «Insertar páginas», «Exportar», «Comprimir» and
«Contraseña»: which documents go together, how one is cut, where pages go,
what is taken out, how much it is packed and with which password."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.combine import EVERY, OUTLINE, RANGES, every, parse_ranges
from app.core.compress import NORMAL, STRONG
from app.core.export import IMAGE_KINDS, JPEG, PNG, RESOLUTIONS
from app.core.protection import MIN_LENGTH

PATH_ROLE = Qt.ItemDataRole.UserRole


class MergeDialog(QDialog):
    """After ``exec()`` returns ``Accepted``: ``paths``, in the order chosen."""

    def __init__(
        self,
        parent: QWidget | None = None,
        open_documents: list[tuple[Path, bool]] | None = None,
        first: list[Path] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Unir documentos"))
        self.setMinimumSize(560, 420)
        self.open_documents = open_documents or []
        self.unsaved = {path for path, modified in self.open_documents if modified}

        explanation = QLabel(
            self.tr(
                "Se juntan en un documento nuevo, en el orden de la lista (arrastra para "
                "cambiarlo). Cada uno queda como un apartado del índice. Los originales "
                "no se tocan."
            )
        )
        explanation.setWordWrap(True)

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Documentos que se van a unir, en orden"))
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.model().rowsMoved.connect(lambda *_args: self._update_buttons())

        add = QPushButton(self.tr("&Añadir documentos…"))
        add.clicked.connect(self.choose_files)
        self.add_open_button = QPushButton(self.tr("Añadir los &abiertos"))
        self.add_open_button.setEnabled(bool(self.open_documents))
        self.add_open_button.clicked.connect(self.add_open)
        self.up_button = QPushButton(self.tr("&Subir"))
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button = QPushButton(self.tr("&Bajar"))
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.remove_button = QPushButton(self.tr("&Quitar"))
        self.remove_button.clicked.connect(self.remove_selected)
        row = QHBoxLayout()
        for button in (
            add,
            self.add_open_button,
            self.up_button,
            self.down_button,
            self.remove_button,
        ):
            row.addWidget(button)
        row.addStretch(1)

        self.note = QLabel()
        self.note.setObjectName("dialogNote")
        self.note.setWordWrap(True)

        self.buttons = QDialogButtonBox()
        self.merge_button = self.buttons.addButton(
            self.tr("Unir"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.list, 1)
        layout.addLayout(row)
        layout.addWidget(self.note)
        layout.addWidget(self.buttons)
        self.add(first or [])
        self._update_buttons()

    @property
    def paths(self) -> list[Path]:
        return [Path(self.list.item(row).data(PATH_ROLE)) for row in range(self.list.count())]

    def add(self, paths) -> None:
        """Put documents at the end of the list. The same one may go twice."""
        for path in map(Path, paths):
            if path.suffix.lower() != ".pdf":
                continue
            text = f"{path.name}  —  {path.parent}"
            if path in self.unsaved:
                text += self.tr("  (tiene cambios sin guardar: se une lo guardado)")
            item = QListWidgetItem(text)
            item.setData(PATH_ROLE, str(path))
            item.setToolTip(str(path))
            self.list.addItem(item)
        self._update_buttons()

    def add_open(self) -> None:
        there = set(self.paths)
        self.add(path for path, _modified in self.open_documents if path not in there)

    def choose_files(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileNames(
            self, self.tr("Elegir los documentos que se van a unir"), "", "PDF (*.pdf)"
        )
        self.add(chosen)

    def move_selected(self, step: int) -> None:
        rows = sorted(self.list.row(item) for item in self.list.selectedItems())
        if not rows or (step < 0 and rows[0] == 0):
            return
        if step > 0 and rows[-1] == self.list.count() - 1:
            return
        for row in rows if step < 0 else reversed(rows):
            item = self.list.takeItem(row)
            self.list.insertItem(row + step, item)
            item.setSelected(True)
        self._update_buttons()

    def remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self._update_buttons()

    def _update_buttons(self) -> None:
        count = self.list.count()
        self.merge_button.setEnabled(count >= 2)
        self.merge_button.setText(
            self.tr("Unir {0} documentos").format(count) if count >= 2 else self.tr("Unir")
        )
        picked = bool(self.list.selectedItems())
        for button in (self.up_button, self.down_button, self.remove_button):
            button.setEnabled(picked)
        if count < 2:
            text = self.tr("Añade al menos dos documentos.")
        elif any(path in self.unsaved for path in self.paths):
            text = self.tr(
                "Hay documentos con cambios sin guardar: guárdalos antes si los quieres."
            )
        else:
            text = ""
        self.note.setText(text)
        self.note.setVisible(bool(text))


class SplitDialog(QDialog):
    """After ``exec()`` returns ``Accepted``: ``parts`` (lists of pages,
    counting from 0), ``titles`` (section titles, or None) and ``folder``."""

    def __init__(
        self,
        parent: QWidget | None,
        name: str,
        count: int,
        folder: Path,
        sections: list[tuple[str, list[int]]] | None = None,
        size: int = 1,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Dividir «{0}»").format(name))
        self.setMinimumWidth(520)
        self.count = count
        self.sections = sections or []
        self.folder = Path(folder)

        explanation = QLabel(
            self.tr(
                "Se crea un documento nuevo por cada parte, con sus notas y su trozo del "
                "índice. El original no se toca. Tiene {0} páginas."
            ).format(count)
        )
        explanation.setWordWrap(True)

        self.way = QButtonGroup(self)
        self.every_button = QRadioButton(self.tr("Cada"))
        self.size_box = QSpinBox()
        self.size_box.setRange(1, max(1, count))
        self.size_box.setValue(max(1, min(size, count)))
        self.size_box.setSuffix(self.tr(" páginas"))
        self.size_box.setAccessibleName(self.tr("Páginas de cada parte"))
        self.ranges_button = QRadioButton(self.tr("Por páginas:"))
        self.ranges_edit = QLineEdit()
        self.ranges_edit.setPlaceholderText(self.tr("Por ejemplo: 1-3, 4-10, 11-"))
        self.ranges_edit.setAccessibleName(self.tr("Páginas de cada parte, separadas por comas"))
        self.outline_button = QRadioButton(
            self.tr("Por los apartados principales del índice ({0})").format(len(self.sections))
            if self.sections
            else self.tr("Por los apartados del índice (este documento no tiene)")
        )
        self.outline_button.setEnabled(bool(self.sections))
        for button, value in (
            (self.every_button, EVERY),
            (self.ranges_button, RANGES),
            (self.outline_button, OUTLINE),
        ):
            button.setProperty("way", value)
            self.way.addButton(button)
        (self.outline_button if self.sections else self.every_button).setChecked(True)

        grid = QGridLayout()
        grid.addWidget(self.every_button, 0, 0)
        grid.addWidget(self.size_box, 0, 1)
        grid.addWidget(self.ranges_button, 1, 0)
        grid.addWidget(self.ranges_edit, 1, 1)
        grid.addWidget(self.outline_button, 2, 0, 1, 2)
        grid.setColumnStretch(1, 1)

        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        change = QPushButton(self.tr("&Cambiar carpeta…"))
        change.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_label, 1)
        folder_row.addWidget(change)

        self.note = QLabel()
        self.note.setObjectName("dialogNote")
        self.note.setWordWrap(True)

        self.buttons = QDialogButtonBox()
        self.split_button = self.buttons.addButton(
            self.tr("Dividir"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(grid)
        layout.addLayout(folder_row)
        layout.addWidget(self.note)
        layout.addWidget(self.buttons)

        self.way.buttonClicked.connect(lambda _button: self._update())
        self.size_box.valueChanged.connect(lambda _value: self._choose(self.every_button))
        self.ranges_edit.textEdited.connect(lambda _text: self._choose(self.ranges_button))
        self._show_folder()
        self._update()

    @property
    def chosen_way(self) -> str:
        return self.way.checkedButton().property("way")

    def _choose(self, button: QRadioButton) -> None:
        button.setChecked(True)
        self._update()

    @property
    def parts(self) -> list[list[int]]:
        way = self.chosen_way
        if way == OUTLINE:
            return [pages for _title, pages in self.sections]
        if way == RANGES:
            try:
                return parse_ranges(self.ranges_edit.text(), self.count)
            except ValueError:
                return []
        return every(self.count, self.size_box.value())

    @property
    def titles(self) -> list[str] | None:
        return [title for title, _pages in self.sections] if self.chosen_way == OUTLINE else None

    def choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, self.tr("Carpeta para las partes"), str(self.folder)
        )
        if chosen:
            self.folder = Path(chosen)
            self._show_folder()

    def _show_folder(self) -> None:
        self.folder_label.setText(self.tr("Se guardan en: {0}").format(self.folder))

    def _update(self) -> None:
        parts = self.parts
        if self.chosen_way == RANGES and self.ranges_edit.text().strip() and not parts:
            text = self.tr(
                "No entiendo esas páginas. Escribe trozos separados por comas, por "
                "ejemplo «1-3, 4-10, 11-» (del 1 al {0})."
            ).format(self.count)
        elif len(parts) == 1 and len(parts[0]) == self.count:
            text = self.tr("Así sale una sola parte igual que el original.")
            parts = []
        elif parts:
            text = self.tr("Saldrán {0} documentos.").format(len(parts))
        else:
            text = ""
        self.note.setText(text)
        self.note.setVisible(bool(text))
        self.split_button.setEnabled(bool(parts))


class InsertWhereDialog(QDialog):
    """Where the pages go. After ``exec()`` returns ``Accepted``: ``at``,
    the place the first of them takes (counting from 0)."""

    def __init__(self, parent: QWidget | None, what: str, count: int, current: int) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Insertar páginas"))
        self.count = count
        explanation = QLabel(self.tr("¿Dónde van {0}?").format(what))
        explanation.setWordWrap(True)
        self.after_current = QRadioButton(
            self.tr("Después de la página que estás leyendo ({0})").format(current + 1)
        )
        self.after_current.setProperty("at", current + 1)
        self.first = QRadioButton(self.tr("Al principio"))
        self.first.setProperty("at", 0)
        self.last = QRadioButton(self.tr("Al final"))
        self.last.setProperty("at", count)
        self.after_page = QRadioButton(self.tr("Después de la página:"))
        self.page_box = QSpinBox()
        self.page_box.setRange(1, max(1, count))
        self.page_box.setValue(max(1, current + 1))
        self.page_box.setAccessibleName(self.tr("Número de página"))
        self.page_box.valueChanged.connect(lambda _value: self.after_page.setChecked(True))
        self.after_current.setChecked(True)
        grid = QGridLayout()
        grid.addWidget(self.after_current, 0, 0, 1, 2)
        grid.addWidget(self.first, 1, 0, 1, 2)
        grid.addWidget(self.last, 2, 0, 1, 2)
        grid.addWidget(self.after_page, 3, 0)
        grid.addWidget(self.page_box, 3, 1)
        grid.setColumnStretch(1, 1)
        buttons = QDialogButtonBox()
        buttons.addButton(self.tr("Insertar"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(grid)
        layout.addWidget(buttons)

    @property
    def at(self) -> int:
        if self.after_page.isChecked():
            return self.page_box.value()
        for button in (self.after_current, self.first, self.last):
            if button.isChecked():
                return int(button.property("at"))
        return self.count


IMAGES = "imagenes"
TEXT = "texto"


class ExportDialog(QDialog):
    """What to take out of the document and which pages. After ``exec()``
    returns ``Accepted``: ``what`` (IMAGES or TEXT), ``pages`` (counting
    from 0), ``kind``, ``resolution`` and ``annotations``."""

    def __init__(
        self,
        parent: QWidget | None,
        count: int,
        current: int,
        picked: list[int],
        remembered: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Exportar"))
        self.count = count
        self.picked = sorted(picked)
        remembered = remembered or {}

        self.as_images = QRadioButton(self.tr("Las páginas como &imagen"))
        self.as_text = QRadioButton(self.tr("El &texto, en un archivo de texto"))
        (self.as_text if remembered.get("what") == TEXT else self.as_images).setChecked(True)

        self.kind_box = QComboBox()
        self.kind_box.setAccessibleName(self.tr("Formato de la imagen"))
        self.kind_box.addItem(self.tr("PNG (nítida, para documentos)"), PNG)
        self.kind_box.addItem(self.tr("JPG (ocupa menos, para fotos)"), JPEG)
        self.kind_box.setCurrentIndex(max(0, self.kind_box.findData(remembered.get("kind", PNG))))
        self.resolution_box = QComboBox()
        self.resolution_box.setAccessibleName(self.tr("Resolución"))
        names = {
            96: self.tr("Pantalla (96 ppp)"),
            150: self.tr("Normal (150 ppp)"),
            300: self.tr("Alta, para imprimir (300 ppp)"),
        }
        for resolution in RESOLUTIONS:
            self.resolution_box.addItem(names[resolution], resolution)
        self.resolution_box.setCurrentIndex(
            max(0, self.resolution_box.findData(remembered.get("resolution", 150)))
        )
        self.annotations_box = QCheckBox(
            self.tr("Con mis &anotaciones (subrayados, notas, dibujos)")
        )
        self.annotations_box.setChecked(bool(remembered.get("annotations", True)))
        image_options = QGridLayout()
        kind_label = QLabel(self.tr("&Formato:"))
        kind_label.setBuddy(self.kind_box)
        resolution_label = QLabel(self.tr("&Resolución:"))
        resolution_label.setBuddy(self.resolution_box)
        image_options.addWidget(kind_label, 0, 0)
        image_options.addWidget(self.kind_box, 0, 1)
        image_options.addWidget(resolution_label, 1, 0)
        image_options.addWidget(self.resolution_box, 1, 1)
        image_options.addWidget(self.annotations_box, 2, 0, 1, 2)
        image_options.setContentsMargins(24, 0, 0, 0)
        self.image_options = QWidget()
        self.image_options.setLayout(image_options)
        self.as_images.toggled.connect(self.image_options.setEnabled)
        self.image_options.setEnabled(self.as_images.isChecked())

        self.current_page = QRadioButton(
            self.tr("La página que estás leyendo ({0})").format(current + 1)
        )
        self.current_page.setProperty("pages", [current])
        self.picked_pages = QRadioButton(
            self.tr("Las {0} páginas elegidas en las miniaturas").format(len(self.picked))
        )
        self.picked_pages.setProperty("pages", self.picked)
        self.picked_pages.setVisible(len(self.picked) > 1)
        self.all_pages = QRadioButton(self.tr("Todas ({0})").format(count))
        self.all_pages.setProperty("pages", list(range(count)))
        self.these_pages = QRadioButton(self.tr("Estas:"))
        self.ranges_edit = QLineEdit()
        self.ranges_edit.setPlaceholderText(self.tr("por ejemplo 1-3, 7"))
        self.ranges_edit.setAccessibleName(self.tr("Páginas que se exportan"))
        self.ranges_edit.textEdited.connect(lambda _text: self.these_pages.setChecked(True))
        (self.picked_pages if len(self.picked) > 1 else self.current_page).setChecked(True)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet("color: palette(link);")
        pages_grid = QGridLayout()
        pages_grid.addWidget(self.current_page, 0, 0, 1, 2)
        pages_grid.addWidget(self.picked_pages, 1, 0, 1, 2)
        pages_grid.addWidget(self.all_pages, 2, 0, 1, 2)
        pages_grid.addWidget(self.these_pages, 3, 0)
        pages_grid.addWidget(self.ranges_edit, 3, 1)
        pages_grid.setColumnStretch(1, 1)
        what_group = QButtonGroup(self)
        what_group.addButton(self.as_images)
        what_group.addButton(self.as_text)
        pages_group = QButtonGroup(self)
        for button in (self.current_page, self.picked_pages, self.all_pages, self.these_pages):
            pages_group.addButton(button)

        buttons = QDialogButtonBox()
        buttons.addButton(self.tr("Exportar"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("¿Qué quieres sacar?")))
        layout.addWidget(self.as_images)
        layout.addWidget(self.image_options)
        layout.addWidget(self.as_text)
        layout.addSpacing(8)
        layout.addWidget(QLabel(self.tr("¿De qué páginas?")))
        layout.addLayout(pages_grid)
        layout.addWidget(self.problem)
        layout.addWidget(buttons)

    @property
    def what(self) -> str:
        return TEXT if self.as_text.isChecked() else IMAGES

    @property
    def kind(self) -> str:
        kind = self.kind_box.currentData()
        return kind if kind in IMAGE_KINDS else PNG

    @property
    def resolution(self) -> int:
        return int(self.resolution_box.currentData())

    @property
    def annotations(self) -> bool:
        return self.annotations_box.isChecked()

    @property
    def pages(self) -> list[int]:
        """The pages chosen, counting from 0 (empty if what is written is wrong)."""
        if self.these_pages.isChecked():
            try:
                parts = parse_ranges(self.ranges_edit.text(), self.count)
            except ValueError:
                return []
            return sorted({page for part in parts for page in part})
        for button in (self.current_page, self.picked_pages, self.all_pages):
            if button.isChecked():
                return list(button.property("pages"))
        return []

    def remembered(self) -> dict:
        """The choices to offer again next time."""
        return {
            "what": self.what,
            "kind": self.kind,
            "resolution": self.resolution,
            "annotations": self.annotations,
        }

    def accept(self) -> None:
        if not self.pages:
            self.problem.setText(
                self.tr("Escribe las páginas así: 1-3, 7 (del 1 al {0}).").format(self.count)
            )
            self.ranges_edit.setFocus()
            return
        super().accept()


class CompressDialog(QDialog):
    """How much to compress. After ``exec()`` returns ``Accepted``: ``level``
    (NORMAL or STRONG)."""

    def __init__(
        self, parent: QWidget | None, size: str, signed: bool, level: str = NORMAL
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Comprimir"))
        explanation = QLabel(
            self.tr(
                "Ahora ocupa {0}. Se crea una copia que ocupa menos; el documento no cambia."
            ).format(size)
        )
        explanation.setWordWrap(True)
        self.normal = QRadioButton(self.tr("&Normal: todo se ve exactamente igual"))
        self.strong = QRadioButton(
            self.tr("&Fuerte: las fotos y las páginas escaneadas pierden algo de nitidez")
        )
        strong_note = QLabel(
            self.tr(
                "Se quedan a 150 ppp: se leen e imprimen bien, pero al ampliar mucho se "
                "nota. Es la que más reduce en documentos escaneados."
            )
        )
        strong_note.setWordWrap(True)
        strong_note.setContentsMargins(24, 0, 0, 0)
        (self.strong if level == STRONG else self.normal).setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.normal)
        group.addButton(self.strong)
        self.signed_note = QLabel(
            self.tr(
                "Este documento está firmado con certificado: en la copia las firmas ya "
                "no serán válidas. Si hay que enviarlo firmado, comprímelo antes de firmar."
            )
        )
        self.signed_note.setWordWrap(True)
        self.signed_note.setStyleSheet("color: palette(link);")
        self.signed_note.setVisible(signed)
        buttons = QDialogButtonBox()
        buttons.addButton(self.tr("Comprimir"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.normal)
        layout.addWidget(self.strong)
        layout.addWidget(strong_note)
        layout.addWidget(self.signed_note)
        layout.addWidget(buttons)

    @property
    def level(self) -> str:
        return STRONG if self.strong.isChecked() else NORMAL


class ProtectDialog(QDialog):
    """Put a password on the document, or take it off or change it if it has
    one. After ``exec()`` returns ``Accepted``: ``password`` (the new one, or
    "" to take it off)."""

    def __init__(self, parent: QWidget | None, has_password: bool, signed: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Contraseña"))
        self.has_password = has_password
        self.take_off = QRadioButton(self.tr("&Quitar la contraseña"))
        self.change = QRadioButton(self.tr("&Cambiarla por otra"))
        group = QButtonGroup(self)
        group.addButton(self.take_off)
        group.addButton(self.change)
        self.take_off.setChecked(True)
        self.take_off.setVisible(has_password)
        self.change.setVisible(has_password)
        if has_password:
            intro = self.tr(
                "Este documento pide contraseña al abrirlo. Se crea una copia con lo que "
                "elijas; el documento no cambia."
            )
        else:
            intro = self.tr(
                "Se crea una copia que pide esta contraseña al abrirla (en cualquier "
                "programa); el documento no cambia. Quien la sepa puede hacer de todo con "
                "la copia: leerla, imprimirla, rellenarla y firmarla."
            )
        explanation = QLabel(intro)
        explanation.setWordWrap(True)
        self.first = QLineEdit()
        self.first.setEchoMode(QLineEdit.EchoMode.Password)
        self.first.setAccessibleName(self.tr("Contraseña nueva"))
        self.second = QLineEdit()
        self.second.setEchoMode(QLineEdit.EchoMode.Password)
        self.second.setAccessibleName(self.tr("Repite la contraseña"))
        self.show_box = QCheckBox(self.tr("&Mostrar lo que escribo"))
        self.show_box.toggled.connect(self._show)
        fields = QGridLayout()
        first_label = QLabel(self.tr("Contraseña &nueva:"))
        first_label.setBuddy(self.first)
        second_label = QLabel(self.tr("&Repítela:"))
        second_label.setBuddy(self.second)
        fields.addWidget(first_label, 0, 0)
        fields.addWidget(self.first, 0, 1)
        fields.addWidget(second_label, 1, 0)
        fields.addWidget(self.second, 1, 1)
        fields.addWidget(self.show_box, 2, 1)
        if has_password:
            fields.setContentsMargins(24, 0, 0, 0)
        self.fields = QWidget()
        self.fields.setLayout(fields)
        self.fields.setEnabled(not has_password)
        self.change.toggled.connect(self.fields.setEnabled)
        self.change.toggled.connect(lambda on: on and self.first.setFocus())
        for edit in (self.first, self.second):
            edit.textEdited.connect(lambda _text: self.change.setChecked(True))
        warning = QLabel(
            self.tr(
                "Apúntala en un sitio seguro: si se olvida, nadie puede abrir la copia, "
                "tampoco este programa."
            )
        )
        warning.setWordWrap(True)
        self.signed_note = QLabel(
            self.tr(
                "Este documento está firmado con certificado: en la copia las firmas ya "
                "no serán válidas. Puedes firmar la copia después."
            )
        )
        self.signed_note.setWordWrap(True)
        self.signed_note.setStyleSheet("color: palette(link);")
        self.signed_note.setVisible(signed)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet("color: palette(link);")
        buttons = QDialogButtonBox()
        buttons.addButton(self.tr("Crear la copia"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.take_off)
        layout.addWidget(self.change)
        layout.addWidget(self.fields)
        layout.addWidget(warning)
        layout.addWidget(self.signed_note)
        layout.addWidget(self.problem)
        layout.addWidget(buttons)
        if not has_password:
            self.first.setFocus()

    def _show(self, shown: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        self.first.setEchoMode(mode)
        self.second.setEchoMode(mode)

    @property
    def removing(self) -> bool:
        return self.has_password and self.take_off.isChecked()

    @property
    def password(self) -> str:
        return "" if self.removing else self.first.text()

    def accept(self) -> None:
        if not self.removing:
            if len(self.first.text()) < MIN_LENGTH:
                self.problem.setText(
                    self.tr("La contraseña tiene que tener al menos {0} caracteres.").format(
                        MIN_LENGTH
                    )
                )
                self.first.setFocus()
                return
            if self.first.text() != self.second.text():
                self.problem.setText(self.tr("Las dos contraseñas no son iguales."))
                self.second.setFocus()
                return
        super().accept()
