"""The sample PDFs exist and really are what their names say.

Later tests rely on these properties (a scanned page has no text, the signed
file has a valid signature...), so they are checked here once.
"""

import pymupdf
import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from app.core.document import read_document_info

SAMPLE_PASSWORD = "lector"


def test_boe_document_is_the_real_constitution(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        assert doc.page_count == 39
        assert "Boletín Oficial del Estado" in doc.metadata["author"]
        assert len(doc.get_toc()) > 100
        text = "\n".join(page.get_text() for page in doc)
    assert "Artículo 14." in text
    assert "Los españoles son iguales ante la ley" in text
    # Sentences run over several lines, as in every BOE text.
    assert "discriminación alguna \npor razón de nacimiento" in text


def test_long_document_has_more_than_500_pages_with_text_and_outline(sample):
    path = sample("largo.pdf")
    assert read_document_info(path).page_count > 500
    with pymupdf.open(path) as doc:
        assert len(doc.get_toc()) >= 20
        assert "Artículo" in doc[0].get_text()
        assert "Página 520" in doc[519].get_text()


def test_hyphenated_text_splits_words_at_line_ends(sample):
    with pymupdf.open(sample("texto-partido.pdf")) as doc:
        text = doc[0].get_text()
    assert "Artícu-\nlo" in text
    assert "discrimina-\nción" in text
    assert "año" in text and "ano" in text


def test_form_has_text_fields_check_boxes_and_a_list(sample):
    with pymupdf.open(sample("formulario.pdf")) as doc:
        assert doc.is_form_pdf
        kinds = {widget.field_name: widget.field_type for widget in doc[0].widgets()}
    assert kinds["nombre"] == pymupdf.PDF_WIDGET_TYPE_TEXT
    assert kinds["acepto"] == pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    assert kinds["provincia"] == pymupdf.PDF_WIDGET_TYPE_COMBOBOX


def test_password_protected_document_opens_only_with_its_password(sample):
    path = sample("con-contrasena.pdf")
    assert read_document_info(path).needs_password is True
    with pymupdf.open(path) as doc:
        assert not doc.authenticate("wrong password")
        assert doc.authenticate(SAMPLE_PASSWORD)
        assert "Artículo" in doc[0].get_text()


def test_scanned_document_is_only_pictures(sample):
    with pymupdf.open(sample("escaneado.pdf")) as doc:
        assert doc.page_count == 3
        for page in doc:
            assert page.get_text().strip() == ""
            assert len(page.get_images()) == 1


def test_bad_ocr_document_has_a_hidden_text_layer_full_of_mistakes(sample):
    with pymupdf.open(sample("ocr-malo.pdf")) as doc:
        page = doc[0]
        text = page.get_text()
        assert len(page.get_images()) == 1
    assert "Articu1o" in text  # "Artículo" misread
    assert "Artículo" not in text
    assert "ano" in text and "año" not in text


def test_signed_document_has_an_intact_signature(sample):
    path = sample("firmado.pdf")
    with pymupdf.open(path) as doc:
        assert doc.get_sigflags() == 3
    with path.open("rb") as file:
        signatures = PdfFileReader(file).embedded_signatures
        assert len(signatures) == 1
        # No trusted authorities at all, so the result is the same on every computer.
        context = ValidationContext(trust_roots=[])
        status = validate_pdf_signature(signatures[0], context)
        assert status.intact and status.valid
        # Self-signed test certificate: correct signature, but nobody vouches for it.
        assert not status.trusted
        assert "PERSONA DE PRUEBA FICTICIA" in status.signing_cert.subject.human_friendly


def test_test_certificate_is_available(sample):
    assert sample("certificado-prueba.p12").stat().st_size > 0


@pytest.mark.parametrize(
    "name",
    [
        "boe.pdf",
        "largo.pdf",
        "texto-partido.pdf",
        "formulario.pdf",
        "con-contrasena.pdf",
        "escaneado.pdf",
        "ocr-malo.pdf",
        "firmado.pdf",
    ],
)
def test_every_sample_opens_without_errors(sample, name):
    assert read_document_info(sample(name)).page_count >= 1
