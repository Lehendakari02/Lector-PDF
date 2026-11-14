"""The little menu that hangs from a marking tool: its colour and its opacity."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.core.commands import Color
from app.core.marker_styles import MIN_OPACITY, QUICK_COLORS, same_color, to_hex
from app.ui import theme

SWATCH_SIZE = 32  # big enough for a finger
COLUMNS = 5


def qcolor(color: Color) -> QColor:
    return QColor.fromRgbF(*color)


class Swatch(QToolButton):
    """A round button of one colour. The one in use has a ring around it."""

    def __init__(self, color: Color, name: str) -> None:
        super().__init__()
        self.color = color
        self.setCheckable(True)
        self.setFixedSize(QSize(SWATCH_SIZE, SWATCH_SIZE))
        self.setToolTip(name)
        self.setAccessibleName(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        c = theme.colours()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        box = QRectF(self.rect())
        if self.isChecked() or self.hasFocus() or self.underMouse():
            ring = c.accent if (self.isChecked() or self.hasFocus()) else c.border
            painter.setPen(QPen(QColor(ring), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(box.adjusted(1.5, 1.5, -1.5, -1.5))
        painter.setPen(QPen(QColor(c.border), 1))
        painter.setBrush(qcolor(self.color))
        painter.drawEllipse(box.adjusted(5, 5, -5, -5))
        painter.end()


class ColorMenu(QMenu):
    """Quick palette, colours used lately, "Más colores…" and the opacity.

    ``color_chosen`` carries the colour picked (red, green, blue from 0 to 1);
    ``opacity_chosen`` the new opacity (from 0 to 1) once the slider is let go.
    """

    color_chosen = Signal(object)
    opacity_chosen = Signal(float)

    def __init__(self, tool_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color: Color = QUICK_COLORS[0]
        self._recent: list[Color] = []
        self.swatches: list[Swatch] = []
        self.recent_swatches: list[Swatch] = []
        # For the tests: what "Más colores…" answers, without showing the dialog.
        self.ask_color = self._ask_with_dialog

        panel = QWidget()
        panel.setObjectName("colorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        title = QLabel(self.tr("Color de «{0}»").format(tool_name))
        title.setObjectName("colorPanelTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)
        for index, color in enumerate(QUICK_COLORS):
            swatch = Swatch(color, self.swatch_name(color))
            swatch.clicked.connect(lambda _checked=False, c=color: self._pick(c))
            self.swatches.append(swatch)
            grid.addWidget(swatch, index // COLUMNS, index % COLUMNS)
        layout.addLayout(grid)

        self.recent_label = QLabel(self.tr("Usados hace poco"))
        self.recent_label.setObjectName("dialogNote")
        layout.addWidget(self.recent_label)
        self._recent_row = QHBoxLayout()
        self._recent_row.setSpacing(2)
        self._recent_row.addStretch(1)
        layout.addLayout(self._recent_row)

        self.more_button = QPushButton(self.tr("Más colores…"))
        self.more_button.setToolTip(self.tr("Elegir cualquier otro color"))
        self.more_button.clicked.connect(self.pick_other)
        layout.addWidget(self.more_button)

        self.opacity_label = QLabel()
        layout.addWidget(self.opacity_label)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setAccessibleName(self.tr("Opacidad"))
        self.opacity_slider.setToolTip(
            self.tr("Cuánto tapa el color: a la izquierda, más transparente")
        )
        self.opacity_slider.setRange(round(MIN_OPACITY * 100), 100)
        self.opacity_slider.setSingleStep(5)
        self.opacity_slider.setPageStep(10)
        self.opacity_slider.setTracking(False)  # tell only when it is let go
        self.opacity_slider.sliderMoved.connect(self._show_opacity)
        self.opacity_slider.valueChanged.connect(self._opacity_set)
        layout.addWidget(self.opacity_slider)

        action = QWidgetAction(self)
        action.setDefaultWidget(panel)
        self.addAction(action)
        self.set_recent([])
        self.set_style(self._color, 1.0)

    # ---- what it shows ---------------------------------------------------

    def set_style(self, color: Color, opacity: float) -> None:
        """Show this colour as the one in use, and this opacity."""
        self._color = color
        for swatch in (*self.swatches, *self.recent_swatches):
            swatch.setChecked(same_color(swatch.color, color))
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(round(opacity * 100))
        self.opacity_slider.blockSignals(False)
        self._show_opacity(self.opacity_slider.value())

    def set_recent(self, colors: list[Color]) -> None:
        """The colours chosen lately with "Más colores…", the newest first."""
        self._recent = list(colors)
        for swatch in self.recent_swatches:
            self._recent_row.removeWidget(swatch)
            swatch.hide()  # or it stays in sight, loose, until it is really deleted
            swatch.setParent(None)
            swatch.deleteLater()
        self.recent_swatches = []
        for position, color in enumerate(self._recent):
            swatch = Swatch(color, self.swatch_name(color))
            swatch.setChecked(same_color(color, self._color))
            swatch.clicked.connect(lambda _checked=False, c=color: self._pick(c))
            self.recent_swatches.append(swatch)
            self._recent_row.insertWidget(position, swatch)
        self.recent_label.setVisible(bool(self._recent))

    @property
    def color(self) -> Color:
        return self._color

    @property
    def opacity(self) -> float:
        return self.opacity_slider.value() / 100

    # ---- choosing --------------------------------------------------------

    def pick_other(self) -> None:
        """ "Más colores…": any colour at all."""
        self.close()
        color = self.ask_color(self._color)
        if color is not None:
            self._pick(color)

    def _ask_with_dialog(self, current: Color) -> Color | None:
        chosen = QColorDialog.getColor(
            qcolor(current), self.parentWidget(), self.tr("Elegir color")
        )
        if not chosen.isValid():
            return None
        return (chosen.redF(), chosen.greenF(), chosen.blueF())

    def _pick(self, color: Color) -> None:
        self.close()
        self.color_chosen.emit(color)

    def _show_opacity(self, percent: int) -> None:
        self.opacity_label.setText(self.tr("Opacidad: {0} %").format(percent))

    def _opacity_set(self, percent: int) -> None:
        self._show_opacity(percent)
        self.opacity_chosen.emit(percent / 100)

    def swatch_name(self, color: Color) -> str:
        names = (
            self.tr("Amarillo"),
            self.tr("Verde"),
            self.tr("Azul claro"),
            self.tr("Rosa"),
            self.tr("Naranja"),
            self.tr("Morado"),
            self.tr("Rojo"),
            self.tr("Azul"),
            self.tr("Verde oscuro"),
            self.tr("Negro"),
        )
        for name, quick in zip(names, QUICK_COLORS, strict=True):
            if same_color(color, quick):
                return name
        return self.tr("Color {0}").format(to_hex(color).upper())
