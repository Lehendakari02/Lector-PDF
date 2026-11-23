"""«Firmar varios documentos»: which ones, and where the signature goes."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.batch_signing import (
    BOTTOM_LEFT,
    BOTTOM_RIGHT,
    FIRST,
    LAST,
    TOP_LEFT,
    TOP_RIGHT,
    Placement,
)

INVISIBLE = "invisible"


class BatchSignDialog(QDialog):
    """After ``exec()`` returns ``Accepted``: ``paths`` and ``placement``
    (None for an invisible signature)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        open_documents: list[tuple[Path, bool]] | None = None,
        page: str = LAST,
        corner: str = BOTTOM_RIGHT,
        visible: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Firmar varios documentos"))
        self.setMinimumSize(560, 420)
        # The documents open in the window, and whether each has changes not saved.
        self.open_documents = open_documents or []
        self.unsaved = {path for path, modified in self.open_documents if modified}

        explanation = QLabel(
            self.tr(
                "Se firman todos con el mismo certificado. Cada uno se guarda como "
                "«nombre-firmado.pdf» en su misma carpeta; los originales no se tocan."
            )
        )
        explanation.setWordWrap(True)

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Documentos que se van a firmar"))
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._update_buttons)

        add = QPushButton(self.tr("&Añadir documentos…"))
        add.clicked.connect(self.choose_files)
        self.add_open_button = QPushButton(self.tr("Añadir los &abiertos"))
        self.add_open_button.setEnabled(bool(self.open_documents))
        self.add_open_button.clicked.connect(self.add_open)
        self.remove_button = QPushButton(self.tr("&Quitar"))
        self.remove_button.clicked.connect(self.remove_selected)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(self.add_open_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)

        self.where_box = QComboBox()
        self.where_box.setAccessibleName(self.tr("Dónde va la firma"))
        self.where_box.addItem(self.tr("Visible, en la última página"), LAST)
        self.where_box.addItem(self.tr("Visible, en la primera página"), FIRST)
        self.where_box.addItem(self.tr("Invisible"), INVISIBLE)
        self.where_box.setCurrentIndex(self.where_box.findData(page if visible else INVISIBLE))
        if self.where_box.currentIndex() < 0:
            self.where_box.setCurrentIndex(0)
        self.corner_box = QComboBox()
        self.corner_box.setAccessibleName(self.tr("Esquina de la página"))
        for value, name in (
            (BOTTOM_RIGHT, self.tr("Abajo a la derecha")),
            (BOTTOM_LEFT, self.tr("Abajo a la izquierda")),
            (TOP_RIGHT, self.tr("Arriba a la derecha")),
            (TOP_LEFT, self.tr("Arriba a la izquierda")),
        ):
            self.corner_box.addItem(name, value)
        self.corner_box.setCurrentIndex(max(0, self.corner_box.findData(corner)))
        self.where_box.currentIndexChanged.connect(lambda _index: self._update_buttons())
        form = QFormLayout()
        form.addRow(self.tr("La firma:"), self.where_box)
        form.addRow(self.tr("Sitio:"), self.corner_box)

        self.note = QLabel()
        self.note.setObjectName("dialogNote")
        self.note.setWordWrap(True)

        self.buttons = QDialogButtonBox()
        self.sign_button = self.buttons.addButton(
            self.tr("Firmar"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.list, 1)
        layout.addLayout(row)
        layout.addLayout(form)
        layout.addWidget(self.note)
        layout.addWidget(self.buttons)
        self._update_buttons()

    @property
    def paths(self) -> list[Path]:
        return [Path(self.list.item(row).data(256)) for row in range(self.list.count())]

    @property
    def placement(self) -> Placement | None:
        where = self.where_box.currentData()
        if where == INVISIBLE:
            return None
        return Placement(where, self.corner_box.currentData())

    def add(self, paths) -> None:
        """Put documents in the list (each once)."""
        there = set(self.paths)
        for path in map(Path, paths):
            if path in there or path.suffix.lower() != ".pdf":
                continue
            there.add(path)
            text = f"{path.name}  —  {path.parent}"
            if path in self.unsaved:
                text += self.tr("  (tiene cambios sin guardar: se firma lo guardado)")
            item = QListWidgetItem(text)
            item.setData(256, str(path))
            item.setToolTip(str(path))
            self.list.addItem(item)
        self._update_buttons()

    def add_open(self) -> None:
        self.add(path for path, _modified in self.open_documents)

    def choose_files(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Elegir los documentos que se van a firmar"),
            "",
            self.tr("Documentos PDF (*.pdf)"),
        )
        self.add(chosen)

    def remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self._update_buttons()

    def _update_buttons(self) -> None:
        count = self.list.count()
        self.sign_button.setEnabled(count > 0)
        self.sign_button.setText(
            self.tr("Firmar {0} documentos").format(count) if count != 1 else self.tr("Firmar")
        )
        self.remove_button.setEnabled(bool(self.list.selectedItems()))
        self.corner_box.setEnabled(self.where_box.currentData() != INVISIBLE)
        unsaved = [path for path in self.paths if path in self.unsaved]
        self.note.setText(
            self.tr("Hay documentos con cambios sin guardar: guárdalos antes si quieres firmarlos.")
            if unsaved
            else ""
        )
        self.note.setVisible(bool(unsaved))
