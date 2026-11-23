"""The "Teclado" tab of the settings: the keys of every function, to change.

Like the controls of a video game, or the keyboard settings of Visual Studio
Code or Photoshop: a list of every function with its key and another one; a
double click (or "Cambiar tecla…") and the next key pressed is the new one.
The list can be searched by the name of a function or by a key. A key that is
already another function's is taken from it, and the window says so (a key
on two functions would make both stop working). The keys that move through
the document (arrows, Space, Esc…) cannot be given.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import shortcuts, symbols
from app.core.text import normalize_for_search
from app.core.tool_keys import TOOL_KEYS_SETTING, tool_keys_wanted
from app.ui.key_names import shown

ID_ROLE = Qt.ItemDataRole.UserRole


def portable(sequence: QKeySequence) -> str:
    """The first combination of a sequence, written the same on every system."""
    if sequence.isEmpty():
        return ""
    return QKeySequence(sequence[0]).toString(QKeySequence.SequenceFormat.PortableText)


class KeyCaptureDialog(QDialog):
    """ "Press the new key": shows at once whether it is free."""

    def __init__(self, tab: "KeysTab", command_id: str, parent=None) -> None:
        super().__init__(parent)
        self.tab = tab
        self.command_id = command_id
        self.key = ""
        name = tab.window_.key_commands[command_id].name
        self.setWindowTitle(self.tr("Tecla para «{0}»").format(name))
        layout = QVBoxLayout(self)
        intro = QLabel(self.tr("Pulsa la tecla o la combinación (por ejemplo Ctrl+U)."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.edit = QKeySequenceEdit()
        self.edit.setMaximumSequenceLength(1)
        self.edit.setAccessibleName(self.tr("Tecla nueva"))
        self.edit.keySequenceChanged.connect(self._pressed)
        layout.addWidget(self.edit)
        self.note = QLabel()
        self.note.setObjectName("dialogNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Poner esta"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.setMinimumWidth(380)
        self.edit.setFocus()

    def _pressed(self, sequence: QKeySequence) -> None:
        self.key = portable(sequence)
        self.note.setText(self.tab.verdict(self.command_id, self.key))
        usable = bool(self.key) and not shortcuts.is_reserved(self.key)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(usable)


class KeysTab(QWidget):
    """The list of every function and its keys."""

    changed = Signal()

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self.window_ = window
        self.settings = window.settings
        # For the tests: what the capture window would answer (a key, or "").
        self.capture_answer: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self.tool_keys_box = QCheckBox(
            self.tr("Teclas &sueltas en el documento (R resalta, S subraya…)")
        )
        self.tool_keys_box.setToolTip(
            self.tr(
                "Las teclas sin Ctrl ni Alt solo valen con el documento delante: en el "
                "buscador o escribiendo un texto, una letra sigue siendo una letra. Quien "
                "pulse teclas sin querer puede quitarlas aquí."
            )
        )
        self.tool_keys_box.setChecked(tool_keys_wanted(self.settings))
        self.tool_keys_box.toggled.connect(self._tool_keys_chosen)
        layout.addWidget(self.tool_keys_box)
        self.typed_arrows_box = QCheckBox(
            self.tr("Al escribir un texto, -> se convierte en &flecha")
        )
        self.typed_arrows_box.setToolTip(
            self.tr(
                "Escribiendo sobre la página: -> o --> da →, <- da ←, <-> da ↔, "
                "=> da ⇒ y <=> da ⇔. Ctrl+Z justo después lo deja como se tecleó."
            )
        )
        self.typed_arrows_box.setChecked(symbols.typed_wanted(self.settings))
        self.typed_arrows_box.toggled.connect(self._typed_arrows_chosen)
        layout.addWidget(self.typed_arrows_box)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(self.tr("Buscar una función o una tecla"))
        self.filter.setAccessibleName(self.tr("Buscar una función o una tecla"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._filter)
        layout.addWidget(self.filter)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([self.tr("Función"), self.tr("Tecla"), self.tr("Otra tecla")])
        self.tree.setAccessibleName(self.tr("Teclas de cada función"))
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumHeight(260)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        self.tree.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        self.change_button = QPushButton(self.tr("&Cambiar tecla…"))
        self.change_button.clicked.connect(lambda: self.change(self.current_id(), 0))
        self.other_button = QPushButton(self.tr("&Otra tecla…"))
        self.other_button.clicked.connect(lambda: self.change(self.current_id(), 1))
        self.clear_button = QPushButton(self.tr("&Quitar teclas"))
        self.clear_button.clicked.connect(lambda: self.clear(self.current_id()))
        self.reset_button = QPushButton(self.tr("&Restablecer"))
        self.reset_button.setToolTip(self.tr("Volver a la tecla de siempre de esta función"))
        self.reset_button.clicked.connect(lambda: self.reset(self.current_id()))
        self.reset_all_button = QPushButton(self.tr("Restablecer &todas"))
        self.reset_all_button.clicked.connect(lambda: self.reset())
        for button in (self.change_button, self.other_button, self.clear_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        resets = QHBoxLayout()
        resets.addWidget(self.reset_button)
        resets.addStretch(1)
        resets.addWidget(self.reset_all_button)
        layout.addLayout(resets)

        self.message = QLabel()
        self.message.setObjectName("dialogNote")
        self.message.setWordWrap(True)
        self.message.setAccessibleName(self.tr("Aviso de teclas"))
        layout.addWidget(self.message)

        self._items: dict[str, QTreeWidgetItem] = {}
        self._fill()
        self._refresh_buttons()

    # ---- the list --------------------------------------------------------------

    def _fill(self) -> None:
        self.tree.clear()
        self._items.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        bold = QFont(self.tree.font())
        bold.setBold(True)
        for command in self.window_.key_commands.values():
            group = groups.get(command.group)
            if group is None:
                group = QTreeWidgetItem([command.group])
                group.setFont(0, bold)
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tree.addTopLevelItem(group)
                groups[command.group] = group
            item = QTreeWidgetItem([command.name, "", ""])
            item.setData(0, ID_ROLE, command.id)
            group.addChild(item)
            self._items[command.id] = item
        self.tree.expandAll()
        self._show_keys()

    def _show_keys(self) -> None:
        for command_id, item in self._items.items():
            keys = shortcuts.keys_of(self.settings, command_id)
            for column in (1, 2):
                key = keys[column - 1] if len(keys) >= column else ""
                item.setText(column, shown(key) if key else "")
            changed = shortcuts.is_changed(self.settings, command_id)
            font = QFont(self.tree.font())
            font.setItalic(changed)  # what was changed by hand stands out
            item.setFont(0, font)
            item.setToolTip(0, self.tr("Cambiada por ti") if changed else "")
        self._filter(self.filter.text())

    def _filter(self, text: str) -> None:
        wanted = normalize_for_search(text.strip())
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            any_shown = False
            for row in range(group.childCount()):
                item = group.child(row)
                words = normalize_for_search(" ".join(item.text(c) for c in range(3)))
                hidden = bool(wanted) and wanted not in words
                item.setHidden(hidden)
                any_shown |= not hidden
            group.setHidden(not any_shown)

    def current_id(self) -> str | None:
        item = self.tree.currentItem()
        return item.data(0, ID_ROLE) if item is not None else None

    def _refresh_buttons(self) -> None:
        command_id = self.current_id()
        for button in (self.change_button, self.other_button, self.clear_button):
            button.setEnabled(command_id is not None)
        self.reset_button.setEnabled(
            command_id is not None and shortcuts.is_changed(self.settings, command_id)
        )

    def _double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        command_id = item.data(0, ID_ROLE)
        if command_id:
            self.change(command_id, 1 if column == 2 else 0)

    def select(self, command_id: str) -> None:
        self.tree.setCurrentItem(self._items[command_id])

    # ---- changing keys -----------------------------------------------------------

    def _name(self, command_id: str) -> str:
        return self.window_.key_commands[command_id].name

    def verdict(self, command_id: str, key: str) -> str:
        """What happens if this key is given to this function, in words."""
        if not key:
            return ""
        if shortcuts.is_reserved(key):
            return self.tr(
                "{0} sirve para moverse por el documento o las ventanas: elige otra."
            ).format(shown(key))
        users = shortcuts.users_of(self.settings, key, self.window_.key_commands, but=command_id)
        if users:
            return self.tr("Ahora es de «{0}»: si la pones aquí, se le quita.").format(
                "», «".join(self._name(user) for user in users)
            )
        if shortcuts.is_plain(key):
            return self.tr("Libre. Sin Ctrl ni Alt, vale con el documento delante.")
        return self.tr("Libre.")

    def change(self, command_id: str | None, slot: int = 0) -> bool:
        """Ask for a key and give it to the function, in its first or second place."""
        if command_id is None:
            return False
        if self.capture_answer is not None:
            key = self.capture_answer
        else:
            dialog = KeyCaptureDialog(self, command_id, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            key = dialog.key
        return self.assign(command_id, key, slot)

    def assign(self, command_id: str, key: str, slot: int = 0) -> bool:
        """Give a key to a function. If another function had it, it is taken from it."""
        if not key or shortcuts.is_reserved(key):
            self.message.setText(self.verdict(command_id, key))
            return False
        taken_from = shortcuts.users_of(
            self.settings, key, self.window_.key_commands, but=command_id
        )
        for other in taken_from:
            kept = [k for k in shortcuts.keys_of(self.settings, other) if k != key]
            shortcuts.set_keys(self.settings, other, kept)
        keys = [k for k in shortcuts.keys_of(self.settings, command_id) if k != key]
        slot = min(slot, len(keys))
        if slot < len(keys):
            keys[slot] = key
        else:
            keys.append(key)
        shortcuts.set_keys(self.settings, command_id, keys)
        said = self.tr("«{0}» es ahora la tecla de «{1}».").format(
            shown(key), self._name(command_id)
        )
        if taken_from:
            said += " " + self.tr("Se ha quitado de «{0}».").format(
                "», «".join(self._name(other) for other in taken_from)
            )
        self._applied(said)
        return True

    def clear(self, command_id: str | None) -> None:
        if command_id is None:
            return
        shortcuts.set_keys(self.settings, command_id, [])
        self._applied(self.tr("«{0}» ya no tiene tecla.").format(self._name(command_id)))

    def reset(self, command_id: str | None = None) -> None:
        """Back to the usual keys, of one function or of all. A usual key that
        another function had been given is taken from it, so none clash."""
        if command_id is None:
            shortcuts.reset(self.settings)
            self._applied(self.tr("Todas las teclas vuelven a ser las de siempre."))
            return
        for key in shortcuts.defaults_of(command_id):
            for other in shortcuts.users_of(
                self.settings, key, self.window_.key_commands, but=command_id
            ):
                kept = [k for k in shortcuts.keys_of(self.settings, other) if k != key]
                shortcuts.set_keys(self.settings, other, kept)
        shortcuts.reset(self.settings, command_id)
        self._applied(
            self.tr("«{0}» vuelve a tener su tecla de siempre.").format(self._name(command_id))
        )

    def _applied(self, said: str) -> None:
        self.window_.apply_shortcuts()
        self._show_keys()
        self._refresh_buttons()
        self.message.setText(said)
        self.changed.emit()

    # ---- the two boxes -------------------------------------------------------------

    def _tool_keys_chosen(self, on: bool) -> None:
        self.settings.set(TOOL_KEYS_SETTING, on)
        self.window_.apply_shortcuts()

    def _typed_arrows_chosen(self, on: bool) -> None:
        self.settings.set(symbols.TYPED_SETTING, on)
        self.window_.apply_pen_settings()
