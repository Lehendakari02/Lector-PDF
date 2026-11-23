"""Creates the protected PDFs of the signing tests, as most programs write them.

Run once with ``python tests/ejemplos/generar_protegidos.py``. It needs
pikepdf (``pip install pikepdf``), which the program does not use: PyMuPDF
writes protected files in another way, and real ones mostly come like these.
"""

import io
from pathlib import Path

import pikepdf
import pymupdf

HERE = Path(__file__).parent


def _page() -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "Documento protegido de prueba", fontsize=16)
        page.insert_text((72, 130), "Texto inventado para las pruebas de firma.")
        return doc.tobytes()


def _protected(name: str, user: str, allow: pikepdf.Permissions) -> None:
    pdf = pikepdf.open(io.BytesIO(_page()))
    pdf.save(
        HERE / name,
        encryption=pikepdf.Encryption(owner="propietario", user=user, R=6, allow=allow),
    )


if __name__ == "__main__":
    # Opens without a password; printing and copying forbidden; filling in allowed.
    _protected(
        "restringido.pdf",
        "",
        pikepdf.Permissions(
            extract=False, print_lowres=False, print_highres=False, modify_other=False
        ),
    )
    # Opens without a password, and its author forbids filling it in or signing it.
    _protected(
        "no-se-firma.pdf",
        "",
        pikepdf.Permissions(
            modify_annotation=False, modify_form=False, modify_other=False, modify_assembly=False
        ),
    )
    # Asks for a password to open it: «lector».
    _protected("contrasena-firmable.pdf", "lector", pikepdf.Permissions())
