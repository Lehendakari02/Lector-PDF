"""«Unir» and «Dividir»: which documents go together, and how one is cut."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
