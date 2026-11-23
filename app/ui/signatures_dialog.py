"""«Comprobar firmas»: who signed the document, when, and whether it holds."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.signature_check import (
    ANNOTATED,
    CHANGED,
    FORM_FILLED,
    MORE_SIGNATURES,
    UNCHANGED,
    SignatureReport,
)

GOOD, DOUBT, BAD = "✔", "⚠", "✖"


def verdict(report: SignatureReport, tr=str) -> tuple[str, str]:
    """A mark and a headline for one signature, in plain words."""
    if report.problem:
        return BAD, tr("No se ha podido comprobar esta firma")
    if not report.intact:
        return BAD, tr("Firma rota: el documento firmado se ha cambiado")
    if report.after == CHANGED:
        return BAD, tr("El documento se ha cambiado después de esta firma")
    if not report.trusted:
        return DOUBT, tr("Firma correcta, pero no se reconoce quién emitió el certificado")
    return GOOD, tr("Firma válida")


def details(report: SignatureReport, tr=str) -> list[str]:
    """The lines under the headline."""
    lines = []
    if report.signer:
        lines.append(tr("Firmado por: {0}").format(report.signer))
    if report.issuer:
        lines.append(tr("Certificado emitido por: {0}").format(report.issuer))
    if report.signed_at is not None:
        when = report.signed_at.astimezone().strftime("%d/%m/%Y %H:%M")
        if report.timestamped:
            lines.append(tr("Fecha: {0} (con sello de tiempo)").format(when))
        else:
            lines.append(tr("Fecha: {0} (la del ordenador que firmó)").format(when))
    if report.problem:
        return lines
    after = {
        UNCHANGED: tr("Nada se ha cambiado desde que se firmó."),
        MORE_SIGNATURES: tr("Después solo se añadieron otras firmas o datos de validación."),
        FORM_FILLED: tr(
            "Después se rellenaron campos o se añadieron firmas: está permitido y no la anula."
        ),
        ANNOTATED: tr("Después se añadieron notas o marcas: no cambian lo firmado."),
        CHANGED: tr("Después de firmar se cambió el contenido del documento."),
    }.get(report.after, "")
    if report.intact and after:
        lines.append(after)
    if report.intact and not report.trusted:
        lines.append(
            tr(
                "Este ordenador no conoce la autoridad que emitió el certificado. "
                "No significa que sea falsa: compruébala en VALIDe."
            )
        )
    return lines


class SignaturesDialog(QDialog):
    """The signatures of one document, one block each."""

    go_to_page = Signal(int)

    def __init__(
        self,
        parent: QWidget | None,
        name: str,
        reports: list[SignatureReport],
        unsaved: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Firmas de «{0}»").format(name))
        self.setMinimumSize(520, 360)
        self.reports = reports
        self.blocks: list[QLabel] = []

        inside = QWidget()
        column = QVBoxLayout(inside)
        column.setSpacing(12)
        if not reports:
            empty = QLabel(self.tr("Este documento no tiene firmas con certificado."))
            empty.setWordWrap(True)
            column.addWidget(empty)
        for number, report in enumerate(reports, start=1):
            mark, headline = verdict(report, self.tr)
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            box = QVBoxLayout(frame)
            title = QLabel(f"<b>{mark} {headline}</b>")
            title.setTextFormat(Qt.TextFormat.RichText)
            title.setAccessibleName(self.tr("Firma {0}: {1}").format(number, headline))
            title.setWordWrap(True)
            box.addWidget(title)
            text = QLabel("\n".join(details(report, self.tr)))
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(text)
            self.blocks.append(title)
            if report.page is not None:
                go = QPushButton(self.tr("Ir a la firma (página {0})").format(report.page + 1))
                go.clicked.connect(lambda _checked=False, p=report.page: self._go(p))
                box.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
            column.addWidget(frame)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inside)

        notes = [
            self.tr(
                "La comprobación se hace en este ordenador, sin internet, y no mira si el "
                "certificado se ha anulado. Para la comprobación oficial, sube el documento "
                "a VALIDe (valide.redsara.es)."
            )
        ]
        if unsaved:
            notes.insert(
                0,
                self.tr(
                    "Tienes cambios sin guardar: se comprueba el documento tal como está guardado."
                ),
            )
        note = QLabel("\n\n".join(notes))
        note.setObjectName("dialogNote")
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr("Cerrar"))
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _go(self, page: int) -> None:
        self.go_to_page.emit(page)
        self.accept()
