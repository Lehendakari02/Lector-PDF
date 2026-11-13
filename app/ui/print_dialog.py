"""The window that asks what to print: printer, pages, copies and how."""

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.printing import PageRangeError, Scaling, parse_pages
from app.core.settings import Settings

PRINT_SETTING = "imprimir"  # what was chosen the last time
MAX_COPIES = 99


@dataclass(frozen=True)
class PrintChoices:
    """What the user chose to print."""

    printer: str
    pages: list[int]  # counting from 0, in the order to print
    copies: int = 1
    scaling: Scaling = Scaling.FIT
    both_sides: bool = False
    grey: bool = False


class PrintDialog(QDialog):
    """Asks what to print. After ``exec`` accepted, ``choices`` has the answer.

    The printer and the way of printing are remembered for the next time; the
    pages and the copies are not (they change with every document).
    """

    def __init__(
        self,
        printers: list[str],
        default_printer: str,
        page_count: int,
        current_page: int,
        settings: Settings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._page_count = page_count
        self._current_page = current_page
        self._settings = settings
        self.choices: PrintChoices | None = None
        self.setWindowTitle(self.tr("Imprimir"))
        self.setMinimumWidth(470)
        stored = settings.get(PRINT_SETTING)
        remembered = stored if isinstance(stored, dict) else {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.printer_box = QComboBox()
        self.printer_box.setAccessibleName(self.tr("Impresora"))
        self.printer_box.addItems(printers)
        wanted = remembered.get("impresora")
        chosen = wanted if wanted in printers else default_printer
        if chosen in printers:
            self.printer_box.setCurrentIndex(printers.index(chosen))
        form.addRow(self.tr("&Impresora:"), self.printer_box)
        layout.addLayout(form)

        # ---- pages ----
        layout.addWidget(self._heading(self.tr("Páginas")))
        self.all_button = QRadioButton(self.tr("&Todas ({0})").format(page_count))
        self.current_button = QRadioButton(
            self.tr("La página que estoy &viendo ({0})").format(current_page + 1)
        )
        self.some_button = QRadioButton(self.tr("&Estas páginas:"))
        self.pages_edit = QLineEdit()
        self.pages_edit.setAccessibleName(self.tr("Páginas que se imprimen"))
        self.pages_edit.setPlaceholderText(self.tr("Por ejemplo: 1-5, 8, 12-"))
        self.pages_edit.setToolTip(
            self.tr("Páginas sueltas o tramos, separados por comas. «12-» es de la 12 al final")
        )
        self.pages_edit.textEdited.connect(self._pages_typed)
        self.pages_group = QButtonGroup(self)
        for button in (self.all_button, self.current_button, self.some_button):
            self.pages_group.addButton(button)
        self.all_button.setChecked(True)
        layout.addWidget(self.all_button)
        layout.addWidget(self.current_button)
        some_row = QHBoxLayout()
        some_row.addWidget(self.some_button)
        some_row.addWidget(self.pages_edit, 1)
        layout.addLayout(some_row)
        self.pages_note = QLabel()
        self.pages_note.setWordWrap(True)
        layout.addWidget(self.pages_note)

        # ---- how ----
        layout.addWidget(self._heading(self.tr("Cómo")))
        how = QFormLayout()
        how.setHorizontalSpacing(14)
        how.setVerticalSpacing(10)
        self.copies_box = QSpinBox()
        self.copies_box.setRange(1, MAX_COPIES)
        self.copies_box.setFixedWidth(90)
        self.copies_box.setAccessibleName(self.tr("Copias"))
        how.addRow(self.tr("&Copias:"), self.copies_box)
        self.scaling_box = QComboBox()
        self.scaling_box.setAccessibleName(self.tr("Tamaño"))
        self.scaling_box.addItem(self.tr("Ajustar al papel (se ve la página entera)"), Scaling.FIT)
        self.scaling_box.addItem(self.tr("Tamaño real (sin agrandar ni encoger)"), Scaling.ACTUAL)
        scaling = Scaling.from_setting(remembered.get("escala"))
        self.scaling_box.setCurrentIndex(self.scaling_box.findData(scaling))
        how.addRow(self.tr("Ta&maño:"), self.scaling_box)
        layout.addLayout(how)
        self.both_sides_box = QCheckBox(self.tr("Por las &dos caras (si la impresora puede)"))
        self.both_sides_box.setChecked(remembered.get("dos_caras") is True)
        layout.addWidget(self.both_sides_box)
        self.grey_box = QCheckBox(self.tr("En &blanco y negro"))
        self.grey_box.setChecked(remembered.get("grises") is True)
        layout.addWidget(self.grey_box)

        layout.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.print_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.print_button.setText(self.tr("Imprimir"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for button in self.pages_group.buttons():
            button.toggled.connect(lambda _on: self._refresh())
        self.printer_box.currentIndexChanged.connect(lambda _index: self._refresh())
        self._refresh()

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("settingsHeading")
        return label

    def _pages_typed(self, _text: str) -> None:
        self.some_button.setChecked(True)  # typing pages means wanting those pages
        self._refresh()

    def pages(self) -> list[int]:
        """The pages chosen right now. Raises ``PageRangeError`` if they make no sense."""
        if self.all_button.isChecked():
            return list(range(self._page_count))
        if self.current_button.isChecked():
            return [self._current_page]
        return parse_pages(self.pages_edit.text(), self._page_count)

    def _refresh(self) -> None:
        """Say how many sheets it will be, or what is wrong with the pages typed."""
        problem = ""
        count = 0
        try:
            count = len(self.pages())
        except PageRangeError as error:
            if error.reason == PageRangeError.OUT_OF_RANGE:
                problem = self.tr("«{0}» se sale del documento, que tiene {1} páginas.").format(
                    error.piece, self._page_count
                )
            elif error.reason == PageRangeError.NOT_UNDERSTOOD:
                problem = self.tr("No entiendo «{0}». Escribe, por ejemplo: 1-5, 8, 12-").format(
                    error.piece
                )
            else:
                problem = self.tr("Escribe qué páginas quieres, por ejemplo: 1-5, 8, 12-")
        typing_nothing_yet = self.some_button.isChecked() and not self.pages_edit.text().strip()
        self.pages_note.setObjectName(
            "dialogError" if problem and not typing_nothing_yet else "dialogNote"
        )
        self.pages_note.setStyleSheet("")  # take the look of the new name
        self.pages_note.style().unpolish(self.pages_note)
        self.pages_note.style().polish(self.pages_note)
        if problem:
            self.pages_note.setText(problem)
        elif count == 1:
            self.pages_note.setText(self.tr("Se imprimirá 1 página."))
        else:
            self.pages_note.setText(self.tr("Se imprimirán {0} páginas.").format(count))
        self.print_button.setEnabled(not problem and self.printer_box.count() > 0)

    def accept(self) -> None:
        try:
            pages = self.pages()
        except PageRangeError:
            self._refresh()
            return
        self.choices = PrintChoices(
            printer=self.printer_box.currentText(),
            pages=pages,
            copies=self.copies_box.value(),
            scaling=self.scaling_box.currentData(),
            both_sides=self.both_sides_box.isChecked(),
            grey=self.grey_box.isChecked(),
        )
        self._settings.set(
            PRINT_SETTING,
            {
                "impresora": self.choices.printer,
                "escala": self.choices.scaling.value,
                "dos_caras": self.choices.both_sides,
                "grises": self.choices.grey,
            },
        )
        super().accept()
