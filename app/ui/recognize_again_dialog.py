"""Asks which scanned pages to recognise again: all, the one being read, or
some written by number ("3-5, 8")."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core.printing import PageRangeError, parse_pages


class RecognizeAgainDialog(QDialog):
    """``pages`` holds the answer (counting from 0), or None if cancelled.

    Only scanned pages (``pictures``) can be chosen: the others have the
    document's own text, which is never replaced.
    """

    def __init__(
        self,
        pictures: list[int],
        current: int,
        page_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pages: list[int] | None = None
        self._pictures = sorted(pictures)
        self._current = current
        self._page_count = page_count
        self.setWindowTitle(self.tr("Volver a reconocer el texto"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        intro = QLabel(
            self.tr(
                "El texto que ya tienen estas páginas se sustituye por uno nuevo. La página "
                "se ve igual y, con Deshacer, vuelve el texto de antes."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.all_button = QRadioButton(
            self.tr("Todas las páginas escaneadas ({0})").format(len(self._pictures))
        )
        self.current_button = QRadioButton(
            self.tr("Solo la página que estoy leyendo ({0})").format(current + 1)
        )
        self.current_button.setEnabled(current in self._pictures)
        self.some_button = QRadioButton(self.tr("Estas páginas:"))
        self.some_pages = QLineEdit()
        self.some_pages.setPlaceholderText(self.tr("por ejemplo 3-5, 8"))
        self.some_pages.setAccessibleName(self.tr("Páginas que reconocer de nuevo"))
        self.some_pages.textEdited.connect(lambda _text: self.some_button.setChecked(True))
        group = QButtonGroup(self)
        for button in (self.all_button, self.current_button, self.some_button):
            group.addButton(button)
            layout.addWidget(button)
        layout.addWidget(self.some_pages)
        self.all_button.setChecked(True)

        self.problem = QLabel()
        self.problem.setObjectName("dialogNote")
        self.problem.setWordWrap(True)
        self.problem.hide()
        layout.addWidget(self.problem)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.go_button = buttons.addButton(
            self.tr("Reconocer de nuevo"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> list[int]:
        """The scanned pages chosen. Raises ``ValueError`` with what is wrong."""
        if self.all_button.isChecked():
            return list(self._pictures)
        if self.current_button.isChecked():
            return [self._current]
        try:
            asked = parse_pages(self.some_pages.text(), self._page_count)
        except PageRangeError as error:
            raise ValueError(
                self.tr("No entiendo esas páginas. Escríbelas así: 3-5, 8.")
            ) from error
        pages = sorted(page for page in asked if page in self._pictures)
        if not pages:
            raise ValueError(
                self.tr("Esas páginas no están escaneadas: su texto es el del propio documento.")
            )
        return pages

    def accept(self) -> None:
        try:
            self.pages = self.chosen()
        except ValueError as error:
            self.problem.setText(str(error))
            self.problem.show()
            return
        super().accept()
