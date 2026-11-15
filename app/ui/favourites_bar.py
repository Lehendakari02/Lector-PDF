"""The bar of favourite tools: each one a button that takes that tool, set its way.

It only shows what the window gives it and tells what was asked for: using a
favourite, removing it, renaming it or moving it along the bar.
"""

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QMenu, QToolBar, QToolButton, QWidget

from app.core.favourites import Favourites
from app.ui import icons

MIN_BUTTON_HEIGHT = 32  # enough for a finger


class FavouritesBar(QToolBar):
    used = Signal(int)
    removed = Signal(int)
    rename_asked = Signal(int)
    moved = Signal(int, int)  # which one, and how many places (negative: to the left)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Herramientas favoritas"))
        self.setObjectName("favouritesBar")
        self.setMovable(False)
        self.setFloatable(False)
        self.toggleViewAction().setEnabled(False)
        self.setProperty("tools", True)  # the same look as the tools above
        self.setIconSize(QSize(18, 18))
        self.buttons: list[QToolButton] = []
        self._icons_only = False
        self.label = QLabel(self.tr("Favoritas"))
        self.label.setObjectName("favouritesLabel")
        self.addWidget(self.label)

    def show_favourites(self, favourites: Favourites, names: list[str], current: int) -> None:
        """Put one button per favourite; ``current`` is the one in hand (or -1)."""
        for button in self.buttons:
            button.hide()
            button.setParent(None)
            button.deleteLater()
        self.buttons = []
        for action in self.actions()[1:]:
            self.removeAction(action)
        for index, (favourite, name) in enumerate(zip(favourites, names, strict=True)):
            button = QToolButton()
            button.setCheckable(True)
            button.setChecked(index == current)
            button.setIcon(icons.marker_icon(favourite.kind, favourite.color))
            button.setText(name)
            button.setAccessibleName(self.tr("Favorita: {0}").format(name))
            button.setToolTip(
                self.tr("{0}\nBotón derecho: quitarla, cambiarle el nombre o moverla").format(name)
            )
            button.setMinimumHeight(MIN_BUTTON_HEIGHT)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, i=index: self.used.emit(i))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda where, i=index, b=button: self._open_menu(i, b.mapToGlobal(where))
            )
            self.addWidget(button)
            self.buttons.append(button)
        self.set_icons_only(self._icons_only)

    def set_current(self, current: int) -> None:
        for index, button in enumerate(self.buttons):
            button.setChecked(index == current)

    def set_icons_only(self, icons_only: bool) -> None:
        """With names beside the drawings (the default) or only the drawings."""
        self._icons_only = icons_only
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if icons_only
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        for button in self.buttons:
            button.setToolButtonStyle(style)

    def menu_for(self, index: int) -> QMenu:
        """What the right button offers on a favourite."""
        menu = QMenu(self)
        menu.addAction(self.tr("Cambiar el nombre…")).triggered.connect(
            lambda _checked=False: self.rename_asked.emit(index)
        )
        left = menu.addAction(self.tr("Mover a la izquierda"))
        left.setEnabled(index > 0)
        left.triggered.connect(lambda _checked=False: self.moved.emit(index, -1))
        right = menu.addAction(self.tr("Mover a la derecha"))
        right.setEnabled(index < len(self.buttons) - 1)
        right.triggered.connect(lambda _checked=False: self.moved.emit(index, 1))
        menu.addSeparator()
        menu.addAction(self.tr("Quitar de favoritas")).triggered.connect(
            lambda _checked=False: self.removed.emit(index)
        )
        return menu

    def _open_menu(self, index: int, where: QPoint) -> None:
        menu = self.menu_for(index)
        menu.exec(where)
        menu.deleteLater()
