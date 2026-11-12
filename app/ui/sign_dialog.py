"""Choose the certificate to sign with: one installed in Windows or a file."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import windows_store
from app.core.signing import SigningError, WindowsStoreSigner, load_p12_signer
from app.core.windows_store import StoreCertificate, StoreError


def describe_certificate(certificate: StoreCertificate, tr=str) -> str:
    """One line for the list: who, issued by whom, until when."""
    text = tr("{0}\nEmitido por {1} · Caduca el {2}").format(
        certificate.name, certificate.issuer, certificate.valid_until.strftime("%d/%m/%Y")
    )
    if not certificate.is_valid_now():
        text += tr(" · CADUCADO o todavía no válido")
    elif not certificate.personal:
        text += tr(" · Es del ordenador, no identifica a una persona")
    elif not certificate.for_signing:
        text += tr(" · No sirve para firmar")
    return text


class CertificateDialog(QDialog):
    """Lists the certificates of Windows; a file can be used instead.

    After ``exec()`` returns ``Accepted``, ``signer`` is ready to sign.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        certificates: list[StoreCertificate] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Firmar con certificado"))
        self.setMinimumSize(560, 380)
        self.signer = None
        self.problem = ""

        if certificates is None:
            certificates = []
            if windows_store.is_available():
                try:
                    certificates = windows_store.list_certificates()
                except StoreError as error:
                    self.problem = str(error)
        self.certificates = certificates

        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        if certificates:
            self.explanation.setText(
                self.tr(
                    "Elige el certificado con el que quieres firmar. Si está protegido, "
                    "Windows te pedirá su contraseña o PIN; el programa nunca la ve."
                )
            )
        elif windows_store.is_available():
            self.explanation.setText(
                self.tr(
                    "No hay ningún certificado con clave instalado en Windows. "
                    "Puedes firmar con un archivo de certificado (.p12 o .pfx)."
                )
            )
        else:
            self.explanation.setText(
                self.tr(
                    "Los certificados instalados solo se pueden usar en Windows. "
                    "Aquí puedes firmar con un archivo de certificado (.p12 o .pfx)."
                )
            )

        self.list = QListWidget()
        self.list.setAccessibleName(self.tr("Certificados instalados en Windows"))
        self.list.setSpacing(4)
        for certificate in certificates:
            item = QListWidgetItem(describe_certificate(certificate, self.tr))
            if not certificate.usable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.list.addItem(item)
        self.list.setVisible(bool(certificates))
        self.list.itemDoubleClicked.connect(lambda _item: self.use_selected())
        self.list.currentRowChanged.connect(lambda _row: self._update_buttons())

        self.buttons = QDialogButtonBox()
        self.sign_button = self.buttons.addButton(
            self.tr("Firmar con este"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.file_button = QPushButton(self.tr("Usar un archivo .p12 o .pfx…"))
        self.buttons.addButton(self.file_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.addButton(self.tr("Cancelar"), QDialogButtonBox.ButtonRole.RejectRole)
        self.sign_button.clicked.connect(self.use_selected)
        self.file_button.clicked.connect(self.choose_file)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.explanation)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.buttons)

        first_usable = next(
            (row for row, certificate in enumerate(certificates) if certificate.usable),
            -1,
        )
        self.list.setCurrentRow(first_usable)
        self._update_buttons()

    def selected(self) -> StoreCertificate | None:
        row = self.list.currentRow()
        if 0 <= row < len(self.certificates):
            certificate = self.certificates[row]
            if certificate.usable:
                return certificate
        return None

    def _update_buttons(self) -> None:
        self.sign_button.setEnabled(self.selected() is not None)

    def use_selected(self) -> None:
        certificate = self.selected()
        if certificate is None:
            return
        try:
            self.signer = WindowsStoreSigner(certificate, window_handle=int(self.winId()))
        except Exception as error:
            self.problem = str(error)
            self.explanation.setText(
                self.tr(
                    "No se ha podido preparar ese certificado. Prueba con otro o con un archivo."
                )
            )
            return
        self.accept()

    def choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Elegir el archivo del certificado"),
            "",
            self.tr("Certificados (*.p12 *.pfx)"),
        )
        if not path:
            return
        password, accepted = QInputDialog.getText(
            self,
            self.tr("Contraseña del certificado"),
            self.tr("Contraseña del archivo (no se guarda):"),
            QLineEdit.EchoMode.Password,
        )
        if accepted:
            self.use_file(path, password)

    def use_file(self, path: str, password: str) -> bool:
        try:
            self.signer = load_p12_signer(path, password)
        except SigningError as error:
            self.problem = str(error)
            self.explanation.setText(
                self.tr(
                    "No se ha podido abrir ese archivo de certificado. "
                    "Comprueba la contraseña e inténtalo otra vez."
                )
            )
            return False
        self.accept()
        return True
