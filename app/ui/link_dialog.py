"""Asks which document a link goes to and, if the user knows it, where."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

PATH_ROLE = Qt.ItemDataRole.UserRole


class LinkDialog(QDialog):
    """``answer`` is (the other document, where in it) or None if cancelled."""

    def __init__(
        self,
        words: str,
        open_documents: list[tuple[str, Path]],
        topics: list[tuple[str, Path]],
        start_folder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.answer: tuple[Path, str] | None = None
        self.start_folder = start_folder
        self.setWindowTitle(self.tr("Enlazar a otro documento"))
        self.setMinimumSize(480, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        intro = QLabel(self.tr("¿A qué documento lleva «{0}»?").format(words))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.documents = QListWidget()
        self.documents.setAccessibleName(self.tr("Documentos"))
        for title, header in (
            (open_documents, self.tr("Abiertos")),
            (topics, self.tr("De la biblioteca")),
        ):
            if not title:
                continue
            head = QListWidgetItem(header)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            font = head.font()
            font.setBold(True)
            head.setFont(font)
            self.documents.addItem(head)
            for name, path in title:
                item = QListWidgetItem(name)
                item.setData(PATH_ROLE, str(path))
                item.setToolTip(str(path))
                self.documents.addItem(item)
        self.documents.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.documents, 1)
        other = QPushButton(self.tr("Otro archivo…"))
        other.setAutoDefault(False)
        other.clicked.connect(self._choose_file)
        layout.addWidget(other, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(QLabel(self.tr("¿Dónde? (si lo sabes)")))
        self.where = QLineEdit()
        self.where.setPlaceholderText(
            self.tr("art. 14, 3.2, capítulo II, 12 (una página)… o vacío para buscarlo tú")
        )
        layout.addWidget(self.where)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Seguir"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        first = next(
            (
                self.documents.item(i)
                for i in range(self.documents.count())
                if self.documents.item(i).data(PATH_ROLE)
            ),
            None,
        )
        if first is not None:
            self.documents.setCurrentItem(first)

    def _choose_file(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Elegir el documento"),
            self.start_folder,
            self.tr("Documentos PDF (*.pdf)"),
        )
        if chosen:
            self.answer = (Path(chosen), self.where.text().strip())
            super().accept()

    def accept(self) -> None:
        item = self.documents.currentItem()
        path = item.data(PATH_ROLE) if item is not None else None
        if not path:
            return
        self.answer = (Path(path), self.where.text().strip())
        super().accept()
