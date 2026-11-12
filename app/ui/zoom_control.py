"""The zoom control of the status bar: smaller, a slider, bigger and the figure."""

import math

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSlider, QToolButton, QWidget

from app.ui import icons
from app.ui.pdf_view import Fit, PdfView

# The slider goes from 25 % to 400 %, with 100 % in the middle: each step
# changes the size by the same proportion, which is how the eye judges it.
SLIDER_MIN, SLIDER_MAX = 0.25, 4.0
SLIDER_STEPS = 200
PRESETS = (50, 75, 100, 125, 150, 200, 300, 400)


def zoom_of_step(step: int) -> float:
    return SLIDER_MIN * (SLIDER_MAX / SLIDER_MIN) ** (step / SLIDER_STEPS)


def step_of_zoom(zoom: float) -> int:
    zoom = max(SLIDER_MIN, min(SLIDER_MAX, zoom))
    return round(SLIDER_STEPS * math.log(zoom / SLIDER_MIN) / math.log(SLIDER_MAX / SLIDER_MIN))


class ZoomControl(QWidget):
    """Shows how big the document is and lets the person change it."""

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view

        self.smaller = self._button("minus", self.tr("Alejar"), self.tr("Alejar (Ctrl+rueda)"))
        self.bigger = self._button("plus", self.tr("Acercar"), self.tr("Acercar (Ctrl+rueda)"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("zoomSlider")
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setPageStep(SLIDER_STEPS // 8)
        self.slider.setFixedWidth(150)
        self.slider.setAccessibleName(self.tr("Tamaño del documento"))
        self.slider.setToolTip(self.tr("Arrastra para ver el documento más grande o más pequeño"))

        self.figure = QToolButton()
        self.figure.setObjectName("zoomFigure")
        self.figure.setAccessibleName(self.tr("Tamaño del documento, en tanto por ciento"))
        self.figure.setToolTip(self.tr("Elegir un tamaño"))
        self.figure.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.figure.setMinimumWidth(68)
        menu = QMenu(self.figure)
        self.fit_width_action = menu.addAction(self.tr("Ajustar al ancho"), view.fit_width)
        self.fit_page_action = menu.addAction(self.tr("Ver página entera"), view.fit_page)
        menu.addSeparator()
        self.preset_actions = {
            percent: menu.addAction(f"{percent} %", lambda p=percent: view.set_zoom(p / 100))
            for percent in PRESETS
        }
        self.figure.setMenu(menu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(2)
        layout.addWidget(self.smaller)
        layout.addWidget(self.slider)
        layout.addWidget(self.bigger)
        layout.addWidget(self.figure)

        self.smaller.clicked.connect(view.zoom_out)
        self.bigger.clicked.connect(view.zoom_in)
        self.slider.valueChanged.connect(self._slider_moved)
        view.zoom_changed.connect(lambda _zoom: self.refresh())
        self.refresh()

    def _button(self, icon_name: str, name: str, tip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("iconButton")
        button.setIcon(icons.icon(icon_name, icons.MUTED))
        button.setIconSize(QSize(16, 16))
        button.setAccessibleName(name)
        button.setToolTip(tip)
        button.setAutoRepeat(True)
        return button

    def _slider_moved(self, step: int) -> None:
        self.view.set_zoom(zoom_of_step(step))

    def refresh(self) -> None:
        """Show the zoom the view has now."""
        has_document = self.view.page_count > 0
        self.setEnabled(has_document)
        zoom = self.view.zoom
        self.slider.blockSignals(True)  # moving it here must not change the zoom back
        self.slider.setValue(step_of_zoom(zoom))
        self.slider.blockSignals(False)
        self.figure.setText(f"{round(zoom * 100)} %" if has_document else "")
        fit = self.view.fit
        marks = {
            self.fit_width_action: fit is Fit.WIDTH,
            self.fit_page_action: fit is Fit.PAGE,
        }
        for action, on in marks.items():
            action.setCheckable(True)
            action.setChecked(on)
