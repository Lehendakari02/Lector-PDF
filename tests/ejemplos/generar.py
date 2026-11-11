"""Create the sample PDFs used by the automatic tests.

Usage (from the repository root):
    python tests/ejemplos/generar.py

The PDFs are committed to the repository; run this only to change them. All
content is invented, so the files can be shared freely. The real BOE document
(``boe.pdf``) is not created here: it is a genuine public file.
"""

import datetime
import io
import random
from pathlib import Path

import pymupdf
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers

HERE = Path(__file__).resolve().parent

PASSWORD = "lector"
CERTIFICATE_PASSWORD = "prueba"
LONG_DOCUMENT_PAGES = 520

A4 = pymupdf.paper_rect("a4")
MARGIN = 72
SAVE_OPTIONS = {"garbage": 4, "deflate": True, "no_new_id": True}

# Typical legal Spanish with accents, "ñ" and the "año"/"ano" trap for the search.
ARTICLE_TEXTS = [
    "Los españoles son iguales ante la ley, sin que pueda prevalecer discriminación "
    "alguna por razón de nacimiento, raza, sexo, religión, opinión o cualquier otra "
    "condición o circunstancia personal o social.",
    "El plazo para presentar la solicitud será de un año, contado desde el día siguiente "
    "al de la publicación de la convocatoria. Transcurrido dicho año sin resolución "
    "expresa, la solicitud se entenderá desestimada.",
    "La Administración pública sirve con objetividad los intereses generales y actúa de "
    "acuerdo con los principios de eficacia, jerarquía, descentralización, "
    "desconcentración y coordinación, con sometimiento pleno a la ley y al Derecho.",
    "El camión de reparto deberá pasar la inspección técnica cada año. El órgano "
    "competente notificará al titular la fecha, el lugar y la documentación necesaria "
    "con una antelación mínima de quince días.",
    "Las señales de tráfico, los niños en edad escolar y los vehículos de enseñanza "
    "gozarán de una protección especial. Ningún cañón, pequeño o grande, podrá "
    "instalarse en la vía pública sin autorización.",
]

# Lines broken exactly as written, with words split by a hyphen at the end of a
# line, the way the BOE prints them. Used to test the search across line breaks.
HYPHENATED_LINES = [
    "Artículo 14. Igualdad ante la ley.",
    "",
    "Los españoles son iguales ante la ley, sin que pueda prevalecer discrimina-",
    "ción alguna por razón de nacimiento, raza, sexo, religión, opinión o cual-",
    "quier otra condición o circunstancia personal o social. Lo dispuesto en este Artícu-",
    "lo se aplicará durante todo el año, también a quienes residan en el extran-",
    "jero. La Administra-",
    "ción velará por su cumplimiento.",
    "",
    "Disposición adicional primera. Régimen de los vehículos pesa-",
    "dos. El camión de más de doce toneladas pasará inspección cada",
    "año natural. No se confunda año con ano: son palabras distintas.",
]


def new_document(title: str) -> pymupdf.Document:
    doc = pymupdf.open()
    doc.set_metadata({"title": title, "author": "Lector-PDF (documento de prueba)"})
    return doc


def save(doc: pymupdf.Document, name: str, **options) -> Path:
    path = HERE / name
    doc.save(path, **(SAVE_OPTIONS | options))
    doc.close()
    return path


def write_article(page: pymupdf.Page, top: float, number: int, body: str) -> float:
    """Write one article and return the vertical position below it."""
    page.insert_text((MARGIN, top), f"Artículo {number}.", fontname="hebo", fontsize=11)
    box = pymupdf.Rect(MARGIN, top + 6, A4.width - MARGIN, top + 90)
    page.insert_textbox(box, body, fontname="helv", fontsize=11, align=pymupdf.TEXT_ALIGN_JUSTIFY)
    return top + 100


def make_long_document() -> Path:
    """More than 500 pages of text with an outline, for speed tests."""
    doc = new_document("Temario de prueba (documento largo)")
    outline = []
    article = 1
    for page_number in range(1, LONG_DOCUMENT_PAGES + 1):
        page = doc.new_page(width=A4.width, height=A4.height)
        top = MARGIN
        if page_number % 20 == 1:
            topic = page_number // 20 + 1
            title = f"Tema {topic}. Materia de prueba número {topic}"
            page.insert_text((MARGIN, top), title, fontname="hebo", fontsize=16)
            outline.append([1, title, page_number])
            top += 40
        while top < A4.height - MARGIN - 100:
            top = write_article(page, top, article, ARTICLE_TEXTS[article % len(ARTICLE_TEXTS)])
            article += 1
        page.insert_text(
            (A4.width / 2 - 20, A4.height - 40),
            f"Página {page_number}",
            fontname="helv",
            fontsize=9,
        )
    doc.set_toc(outline)
    return save(doc, "largo.pdf")


def make_hyphenated_text() -> Path:
    """One page with words split by a hyphen at the end of the line."""
    doc = new_document("Texto con palabras partidas")
    page = doc.new_page(width=A4.width, height=A4.height)
    top = MARGIN
    for line in HYPHENATED_LINES:
        if line:
            page.insert_text((MARGIN, top), line, fontname="helv", fontsize=11)
        top += 16
    return save(doc, "texto-partido.pdf")


def make_form() -> Path:
    """A fillable form: text fields, check boxes and a drop-down list."""
    doc = new_document("Formulario de prueba")
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_text((MARGIN, MARGIN), "Solicitud de prueba", fontname="hebo", fontsize=16)

    def add(kind, name, label, top, **extra):
        page.insert_text((MARGIN, top + 14), label, fontname="helv", fontsize=11)
        widget = pymupdf.Widget()
        widget.field_type = kind
        widget.field_name = name
        widget.field_label = label
        widget.rect = extra.pop("rect", pymupdf.Rect(220, top, 500, top + 20))
        widget.border_color = (0, 0, 0)
        widget.border_width = 0.5
        widget.text_fontsize = 11
        for key, value in extra.items():
            setattr(widget, key, value)
        page.add_widget(widget)

    add(pymupdf.PDF_WIDGET_TYPE_TEXT, "nombre", "Nombre y apellidos", 110)
    add(pymupdf.PDF_WIDGET_TYPE_TEXT, "dni", "DNI", 145)
    add(pymupdf.PDF_WIDGET_TYPE_TEXT, "direccion", "Dirección", 180)
    add(
        pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
        "provincia",
        "Provincia",
        215,
        choice_values=["Álava", "Bizkaia", "Gipuzkoa", "Madrid", "A Coruña"],
    )
    add(
        pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
        "acepto",
        "Acepto las condiciones",
        250,
        rect=pymupdf.Rect(220, 252, 236, 268),
    )
    add(
        pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
        "notificacion_electronica",
        "Notificación electrónica",
        285,
        rect=pymupdf.Rect(220, 287, 236, 303),
    )
    add(
        pymupdf.PDF_WIDGET_TYPE_TEXT,
        "observaciones",
        "Observaciones",
        320,
        rect=pymupdf.Rect(220, 320, 500, 420),
        field_flags=pymupdf.PDF_TX_FIELD_IS_MULTILINE,
    )
    return save(doc, "formulario.pdf")


def make_password_protected() -> Path:
    """A PDF that asks for a password to open (the password is "lector")."""
    doc = new_document("Documento con contraseña")
    page = doc.new_page(width=A4.width, height=A4.height)
    write_article(page, MARGIN, 1, ARTICLE_TEXTS[0])
    return save(
        doc,
        "con-contrasena.pdf",
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=PASSWORD,
        owner_pw=PASSWORD + "-propietario",
    )


def scanned_page_image(page_number: int) -> bytes:
    """Render a text page the way a cheap scanner would: tilted, grey and noisy."""
    source = pymupdf.open()
    page = source.new_page(width=A4.width, height=A4.height)
    top = MARGIN
    for offset in range(5):
        number = (page_number - 1) * 5 + offset + 1
        top = write_article(page, top, number, ARTICLE_TEXTS[number % len(ARTICLE_TEXTS)])
    tilt = (-1.3, 0.9, -0.6)[(page_number - 1) % 3]
    matrix = pymupdf.Matrix(150 / 72, 150 / 72).prerotate(tilt)
    pixmap = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False)
    source.close()

    # Salt-and-pepper noise and a slightly grey background, always the same.
    noise = random.Random(page_number)
    samples = bytearray(pixmap.samples)
    for index in range(len(samples)):
        if samples[index] > 200:
            samples[index] = 236
    for _ in range(len(samples) // 400):
        samples[noise.randrange(len(samples))] = noise.choice((40, 120, 255))
    noisy = pymupdf.Pixmap(pymupdf.csGRAY, pixmap.width, pixmap.height, bytes(samples), False)
    return noisy.tobytes("jpeg", jpg_quality=55)


def make_scanned(pages: int = 3) -> Path:
    """Pages that are only a picture, with no text: what a scanner produces."""
    doc = new_document("Documento escaneado")
    for page_number in range(1, pages + 1):
        page = doc.new_page(width=A4.width, height=A4.height)
        page.insert_image(A4, stream=scanned_page_image(page_number))
    return save(doc, "escaneado.pdf")


def spoil(text: str) -> str:
    """Introduce the mistakes a poor text recognition typically makes."""
    replacements = [("ñ", "n"), ("ó", "o"), ("í", "i"), ("á", "a"), ("é", "e"), ("ú", "u")]
    replacements += [("m", "rn"), ("l", "1"), ("O", "0"), ("cl", "d"), ("fi", "f i")]
    for good, bad in replacements:
        text = text.replace(good, bad)
    return text


def make_bad_ocr(pages: int = 2) -> Path:
    """Scanned pages with a hidden, low-quality text layer on top."""
    doc = new_document("Documento escaneado con OCR malo")
    for page_number in range(1, pages + 1):
        page = doc.new_page(width=A4.width, height=A4.height)
        page.insert_image(A4, stream=scanned_page_image(page_number))
        top = MARGIN
        for offset in range(5):
            number = (page_number - 1) * 5 + offset + 1
            body = ARTICLE_TEXTS[number % len(ARTICLE_TEXTS)]
            # render_mode 3 = invisible text, the standard way to store OCR results.
            page.insert_text(
                (MARGIN, top), spoil(f"Artículo {number}."), fontsize=11, render_mode=3
            )
            box = pymupdf.Rect(MARGIN, top + 6, A4.width - MARGIN, top + 90)
            page.insert_textbox(box, spoil(body), fontsize=11, render_mode=3)
            top += 100
    return save(doc, "ocr-malo.pdf")


def make_test_certificate() -> Path:
    """A made-up, self-signed certificate. It identifies nobody and protects nothing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Lector-PDF (pruebas)"),
            x509.NameAttribute(NameOID.COMMON_NAME, "PERSONA DE PRUEBA FICTICIA - 00000000T"),
        ]
    )
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(start + datetime.timedelta(days=365 * 30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    path = HERE / "certificado-prueba.p12"
    path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"lector-pdf-prueba",
            key,
            certificate,
            None,
            serialization.BestAvailableEncryption(CERTIFICATE_PASSWORD.encode()),
        )
    )
    return path


def make_signed(certificate: Path) -> Path:
    """A PDF signed with the test certificate."""
    doc = new_document("Documento firmado")
    page = doc.new_page(width=A4.width, height=A4.height)
    write_article(page, MARGIN, 1, ARTICLE_TEXTS[2])
    unsigned = doc.tobytes(**SAVE_OPTIONS)
    doc.close()

    signer = signers.SimpleSigner.load_pkcs12(
        str(certificate), passphrase=CERTIFICATE_PASSWORD.encode()
    )
    signed = signers.sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(unsigned)),
        signers.PdfSignatureMetadata(field_name="Firma1", reason="Prueba", location="España"),
        signer=signer,
    )
    path = HERE / "firmado.pdf"
    path.write_bytes(signed.getvalue())
    return path


def main() -> None:
    certificate = HERE / "certificado-prueba.p12"
    if not certificate.exists():
        make_test_certificate()
    created = [
        make_long_document(),
        make_hyphenated_text(),
        make_form(),
        make_password_protected(),
        make_scanned(),
        make_bad_ocr(),
        make_signed(certificate),
    ]
    for path in [certificate, *created]:
        print(f"{path.name:28} {path.stat().st_size / 1024:8.0f} KB")


if __name__ == "__main__":
    main()
