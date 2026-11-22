"""Where «Mis datos» are written: kept only on this computer."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.my_data import (
    ADDRESS,
    BIRTH,
    EMAIL,
    ID,
    KEYS,
    NAME,
    PHONE,
    POSTCODE,
    PROVINCE,
    SURNAMES,
    TOWN,
    MyData,
)


def datum_names(widget: QWidget) -> dict[str, str]:
    """How each datum is called to the user."""
    return {
        NAME: widget.tr("Nombre"),
        SURNAMES: widget.tr("Apellidos"),
        ID: widget.tr("DNI / NIE"),
        BIRTH: widget.tr("Fecha de nacimiento"),
        ADDRESS: widget.tr("Dirección"),
        POSTCODE: widget.tr("Código postal"),
        TOWN: widget.tr("Localidad"),
        PROVINCE: widget.tr("Provincia"),
        PHONE: widget.tr("Teléfono"),
        EMAIL: widget.tr("Correo electrónico"),
    }


class MyDataDialog(QDialog):
    """``data`` is what was written once it is accepted."""

    def __init__(self, data: MyData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data
        self.setWindowTitle(self.tr("Mis datos"))
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        intro = QLabel(
            self.tr(
                "Escríbelos una vez y ponlos en los formularios con un clic. Se guardan "
                "solo en este ordenador y nunca se envían a ningún sitio. Deja en blanco "
                "lo que no quieras guardar."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.boxes: dict[str, QLineEdit] = {}
        names = datum_names(self)
        for key in KEYS:
            box = QLineEdit(data.values.get(key, ""))
            box.setAccessibleName(names[key])
            if key == BIRTH:
                box.setPlaceholderText(self.tr("dd/mm/aaaa"))
            form.addRow(names[key], box)
            self.boxes[key] = box
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.tr("Guardar"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.data = MyData.from_setting({key: box.text() for key, box in self.boxes.items()})
        super().accept()
