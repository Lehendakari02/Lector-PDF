"""Asks where to add blank room to write notes in, how wide, and on which pages."""

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core.margins import cm

RIGHT, LEFT, BOTH, BELOW = "right", "left", "both", "below"
SIDES = (RIGHT, LEFT, BOTH, BELOW)
WIDTHS_CM = (3.0, 5.0, 8.0)  # narrow, normal, wide
DEFAULT_SIDE, DEFAULT_WIDTH = RIGHT, 5.0
SIDE_SETTING = "margins/side"
WIDTH_SETTING = "margins/width_cm"
ALL_SETTING = "margins/all_pages"


@dataclass(frozen=True)
class MarginChoice:
    side: str
    width_cm: float
    every_page: bool

    def room(self) -> tuple[float, float, float]:
        """Points to add on the left, on the right and below."""
        width = cm(self.width_cm)
        return {
            RIGHT: (0.0, width, 0.0),
            LEFT: (width, 0.0, 0.0),
            BOTH: (width, width, 0.0),
            BELOW: (0.0, 0.0, width),
        }[self.side]


def remembered(settings) -> MarginChoice:
    """The last choice (or a coherent one the first time: 5 cm on the right)."""
    side = settings.get(SIDE_SETTING, DEFAULT_SIDE)
    width = settings.get(WIDTH_SETTING, DEFAULT_WIDTH)
    try:
        width = float(width)
    except (TypeError, ValueError):
        width = DEFAULT_WIDTH
    return MarginChoice(
        side if side in SIDES else DEFAULT_SIDE,
        width if width in WIDTHS_CM else DEFAULT_WIDTH,
        bool(settings.get(ALL_SETTING, False)),
    )


def remember(settings, choice: MarginChoice) -> None:
    settings.set(SIDE_SETTING, choice.side)
    settings.set(WIDTH_SETTING, choice.width_cm)
    settings.set(ALL_SETTING, choice.every_page)


class MarginDialog(QDialog):
    """``choice`` holds the answer, or None if cancelled."""

    def __init__(self, start: MarginChoice, page: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.choice: MarginChoice | None = None
        self.setWindowTitle(self.tr("Añadir margen para apuntes"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        intro = QLabel(
            self.tr(
                "La página se hace más grande con espacio en blanco para escribir. "
                "Lo que hay en ella no se mueve de su sitio. Deshacer lo quita."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel(self.tr("<b>Dónde</b>")), 0, 0)
        grid.addWidget(QLabel(self.tr("<b>Cuánto</b>")), 0, 1)
        self.side_group = QButtonGroup(self)
        self.side_buttons: dict[str, QRadioButton] = {}
        for row, (side, name) in enumerate(
            (
                (RIGHT, self.tr("A la derecha")),
                (LEFT, self.tr("A la izquierda")),
                (BOTH, self.tr("A los dos lados")),
                (BELOW, self.tr("Abajo")),
            ),
            start=1,
        ):
            button = QRadioButton(name)
            button.setChecked(side == start.side)
            self.side_group.addButton(button)
            self.side_buttons[side] = button
            grid.addWidget(button, row, 0)
        self.width_group = QButtonGroup(self)
        self.width_buttons: dict[float, QRadioButton] = {}
        for row, (width, name) in enumerate(
            zip(
                WIDTHS_CM,
                (self.tr("Estrecho (3 cm)"), self.tr("Normal (5 cm)"), self.tr("Ancho (8 cm)")),
                strict=True,
            ),
            start=1,
        ):
            button = QRadioButton(name)
            button.setChecked(width == start.width_cm)
            self.width_group.addButton(button)
            self.width_buttons[width] = button
            grid.addWidget(button, row, 1)
        layout.addLayout(grid)

        layout.addWidget(QLabel(self.tr("<b>Páginas</b>")))
        self.page_group = QButtonGroup(self)
        self.this_page = QRadioButton(self.tr("Solo esta página ({0})").format(page + 1))
        self.every_page = QRadioButton(self.tr("Todas las páginas"))
        for button in (self.this_page, self.every_page):
            self.page_group.addButton(button)
            layout.addWidget(button)
        (self.every_page if start.every_page else self.this_page).setChecked(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Añadir margen"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def current(self) -> MarginChoice:
        side = next(s for s, b in self.side_buttons.items() if b.isChecked())
        width = next(w for w, b in self.width_buttons.items() if b.isChecked())
        return MarginChoice(side, width, self.every_page.isChecked())

    def accept(self) -> None:
        self.choice = self.current()
        super().accept()
