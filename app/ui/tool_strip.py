"""A row of tools that slides sideways when the window is too narrow for it.

Qt's own tool bar folds what does not fit behind a small button that opens a
second row. That button is easy to miss and the second row is strange, so
the tools of each mode live instead in one row that slides, like the ribbons
of phone apps and the tab strips of browsers: a clear arrow at each side, the
mouse wheel and a finger also slide it, and a tool reached with the keyboard
always comes into view.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from app.ui import icons

ARROW_WIDTH = 34  # wide enough for a finger
SLIDE_SHARE = 0.7  # how much of the row one press of an arrow slides
SLIDE_MS = 180


class ToolStrip(QFrame):
    """Holds the tool bars of every mode; only the visible one takes room."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolStrip")
        # Owned by the strip, so it never fires after the strip is gone.
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.left_button = self._arrow(
            "scroll_left", self.tr("Ver las herramientas de la izquierda")
        )
        self.right_button = self._arrow(
            "scroll_right", self.tr("Ver más herramientas a la derecha")
        )
        self.left_button.clicked.connect(lambda: self.slide(-1))
        self.right_button.clicked.connect(lambda: self.slide(1))

        self.content = QWidget()
        self.content.setObjectName("toolStripContent")
        self._row = QHBoxLayout(self.content)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)

        self.area = QScrollArea()
        self.area.setObjectName("toolStripArea")
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setWidgetResizable(False)
        self.area.setWidget(self.content)
        self.area.viewport().setAutoFillBackground(False)
        self.area.viewport().installEventFilter(self)
        self.content.installEventFilter(self)
        # A finger slides the row as it would on a phone.
        QScroller.grabGesture(self.area.viewport(), QScroller.ScrollerGestureType.TouchGesture)
        self.bar = self.area.horizontalScrollBar()
        self.bar.valueChanged.connect(self._update_arrows)
        self.bar.rangeChanged.connect(self._update_arrows)
        self._animation = QPropertyAnimation(self.bar, b"value", self)
        self._animation.setDuration(SLIDE_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.left_button)
        layout.addWidget(self.area, 1)
        layout.addWidget(self.right_button)

        self._fit()

    def _arrow(self, icon_name: str, tip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("toolStripArrow")
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setAutoRepeat(True)  # keeping it pressed keeps sliding
        button.setAutoRepeatDelay(400)
        button.setAutoRepeatInterval(250)
        button.setFixedWidth(ARROW_WIDTH)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Tab goes through the tools
        button.hide()
        return button

    def add_tool_bar(self, toolbar: QToolBar) -> None:
        toolbar.setProperty("inStrip", True)
        toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toolbar.installEventFilter(self)
        for child in toolbar.findChildren(QWidget):
            child.installEventFilter(self)
        self._row.addWidget(toolbar)
        self._fit_later()

    # ---- sliding ----

    def slide(self, direction: int) -> None:
        """Slide one stretch to the right (1) or to the left (-1)."""
        step = max(80, int(self.area.viewport().width() * SLIDE_SHARE))
        start = self._animation.endValue() if self._animating() else self.bar.value()
        target = max(self.bar.minimum(), min(self.bar.maximum(), int(start) + direction * step))
        self._animation.stop()
        self._animation.setStartValue(self.bar.value())
        self._animation.setEndValue(target)
        self._animation.start()

    def _animating(self) -> bool:
        return self._animation.state() == QPropertyAnimation.State.Running

    def overflows(self) -> bool:
        return self.bar.maximum() > 0

    def _update_arrows(self) -> None:
        overflowing = self.overflows()
        self.left_button.setVisible(overflowing)
        self.right_button.setVisible(overflowing)
        self.left_button.setEnabled(self.bar.value() > self.bar.minimum())
        self.right_button.setEnabled(self.bar.value() < self.bar.maximum())

    # ---- size ----

    def _fit_later(self) -> None:
        self._fit_timer.start()

    def _fit(self) -> None:
        """The row is as wide as its tools and the strip as high as the row."""
        for index in range(self._row.count()):
            toolbar = self._row.itemAt(index).widget()
            if toolbar is not None:
                # Never narrower than all its tools: nothing goes to a hidden row.
                toolbar.setMinimumWidth(toolbar.sizeHint().width())
        hint = self._row.sizeHint()
        height = max(hint.height(), 1)
        self.area.setFixedHeight(height)
        self.content.resize(max(hint.width(), self.area.viewport().width()), height)
        self.updateGeometry()
        self._update_arrows()

    def sizeHint(self) -> QSize:
        return QSize(200, self._row.sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return QSize(3 * ARROW_WIDTH, self._row.sizeHint().height())

    def showEvent(self, event) -> None:
        self._fit()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if watched is self.area.viewport() and kind == QEvent.Type.Wheel:
            # The wheel, up or down, slides the row (as in browser tab strips).
            delta = event.angleDelta()
            amount = delta.x() if abs(delta.x()) > abs(delta.y()) else delta.y()
            if amount and self.overflows():
                self._animation.stop()
                self.bar.setValue(self.bar.value() - amount)
                return True
        elif kind == QEvent.Type.FocusIn and isinstance(watched, QWidget):
            # A tool reached with Tab comes into view.
            if self.content.isAncestorOf(watched):
                self.area.ensureWidgetVisible(watched, ARROW_WIDTH, 0)
        elif kind == QEvent.Type.ChildAdded and isinstance(watched, QToolBar):
            child = event.child()
            if isinstance(child, QWidget):
                child.installEventFilter(self)
        resized = kind in (QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.Hide)
        if resized and (watched is self.content or isinstance(watched, QToolBar)):
            self._fit_later()
        return super().eventFilter(watched, event)
