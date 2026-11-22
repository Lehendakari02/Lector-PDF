"""The small bar over what is picked on the page: its colour, and Borrar.

It shows what can be done with a mark, a drawing, a shape, a note or a text
once a click has picked it, without looking for it in a menu: another colour
with one click, any colour with "Más colores…", and taking it away (Supr
does the same).
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QColorDialog, QFrame, QHBoxLayout, QPushButton, QWidget

from app.core.commands import Color
from app.core.marker_styles import QUICK_COLORS, same_color
from app.ui.color_menu import ColorMenu, Swatch, qcolor

SWATCH = 28  # a little smaller than in the menus: the bar sits on the page


class PickedBar(QFrame):
    """``color_chosen`` carries the new colour; ``remove_wanted`` asks to take it away."""

    color_chosen = Signal(object)
    remove_wanted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pickedBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._color: Color = QUICK_COLORS[0]
        # For the tests: what "Más colores…" answers, without showing the dialog.
        self.ask_color = self._ask_with_dialog
        names = ColorMenu.swatch_name  # the same names everywhere

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(1)
        self.swatches: list[Swatch] = []
        for color in QUICK_COLORS:
            swatch = Swatch(color, names(self, color))
            swatch.setFixedSize(QSize(SWATCH, SWATCH))
            swatch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            swatch.clicked.connect(lambda _checked=False, c=color: self._pick(c))
            self.swatches.append(swatch)
            row.addWidget(swatch)
        self.more_button = QPushButton(self.tr("Más…"))
        self.more_button.setToolTip(self.tr("Elegir cualquier otro color"))
        self.more_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.more_button.clicked.connect(self.pick_other)
        row.addSpacing(4)
        row.addWidget(self.more_button)
        row.addSpacing(6)
        self.remove_button = QPushButton(self.tr("Borrar"))
        self.remove_button.setToolTip(self.tr("Quitarlo de la página (Supr)"))
        self.remove_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.remove_button.clicked.connect(self.remove_wanted)
        row.addWidget(self.remove_button)
        self.hide()

    def show_for(self, color: Color | None, recolorable: bool) -> None:
        """Get ready for what was picked: its colour, and whether it can change."""
        if color is not None:
            self._color = tuple(color)
        for swatch in self.swatches:
            swatch.setVisible(recolorable)
            swatch.setChecked(recolorable and same_color(swatch.color, self._color))
        self.more_button.setVisible(recolorable)
        self.adjustSize()

    def _pick(self, color: Color) -> None:
        for swatch in self.swatches:
            swatch.setChecked(same_color(swatch.color, color))
        self._color = tuple(color)
        self.color_chosen.emit(tuple(color))

    def pick_other(self) -> None:
        chosen = self.ask_color(self._color)
        if chosen is not None:
            self._pick(chosen)

    def _ask_with_dialog(self, current: Color) -> Color | None:
        picked = QColorDialog.getColor(qcolor(current), self.window(), self.tr("Elegir un color"))
        if not picked.isValid():
            return None
        return (picked.redF(), picked.greenF(), picked.blueF())
