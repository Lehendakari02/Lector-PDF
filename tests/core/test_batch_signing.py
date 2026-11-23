"""Tests for signing several documents at once (task 4.4)."""

import shutil

import pymupdf
import pytest
from pyhanko.pdf_utils.reader import PdfFileReader

from app.core import batch_signing, signing
from app.core.batch_signing import (
    BOTTOM_RIGHT,
    FAILED,
    FIRST,
    LAST,
    PASSWORD,
    SIGNED,
    TOP_LEFT,
    Placement,
    sign_many,
    signed_copy_name,
    visible_in,
)
from app.core.signing import load_p12_signer
from app.core.windows_store import SigningCancelled


@pytest.fixture
def signer(sample):
    return load_p12_signer(sample("certificado-prueba.p12"), "prueba")


@pytest.fixture
def documents(sample, tmp_path):
    """Ten documents to sign, in a folder of their own."""
    folder = tmp_path / "contratos"
    folder.mkdir()
    made = []
    for number in range(10):
        path = folder / f"contrato {number + 1}.pdf"
        shutil.copy(sample("formulario.pdf" if number % 2 else "largo.pdf"), path)
        made.append(path)
    return made


def signatures(path):
    with path.open("rb") as handle:
        return len(PdfFileReader(handle, strict=False).embedded_signatures)


def test_ten_documents_are_signed_with_one_certificate(documents, signer):
    before = [path.read_bytes() for path in documents]
    seen = []
    outcomes = sign_many(documents, signer, progress=lambda done, path: seen.append(done) or True)
    assert seen == list(range(10))
    assert [outcome.result for outcome in outcomes] == [SIGNED] * 10
    for source, outcome, original in zip(documents, outcomes, before, strict=True):
        assert outcome.target == source.with_name(f"{source.stem}-firmado.pdf")
        assert signatures(outcome.target) == 1
        assert source.read_bytes() == original, "the originals are never touched"


def test_the_same_corner_of_the_last_or_first_page_of_each(documents, signer, tmp_path):
    with pymupdf.open(documents[0]) as doc:
        pages, size = doc.page_count, doc[-1].rect
    last = visible_in(documents[0], Placement(LAST, BOTTOM_RIGHT), None)
    assert last.page == pages - 1
    x0, y0, x1, y1 = last.rect
    assert (round(size.width - x1), round(size.height - y1)) == (36, 36)
    first = visible_in(documents[0], Placement(FIRST, TOP_LEFT), b"PNG")
    assert first.page == 0 and first.rect[:2] == (36, 36) and first.png == b"PNG"

    outcomes = sign_many(documents[:2], signer, Placement(LAST, BOTTOM_RIGHT))
    for outcome in outcomes:
        with pymupdf.open(outcome.target) as doc:
            (box,) = [w for w in doc[-1].widgets() if w.field_type_string == "Signature"]
            assert box.rect.x1 == pytest.approx(doc[-1].rect.width - 36, abs=0.5)


def test_a_tiny_page_still_holds_the_box(tmp_path):
    path = tmp_path / "ticket.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=120, height=40)
        doc.save(path)
    box = visible_in(path, Placement(), None)
    assert box.rect == (0, 0, 120, 40)


def test_one_that_cannot_be_signed_is_told_and_the_rest_go_on(documents, signer, sample):
    locked = documents[0].with_name("con contraseña.pdf")
    shutil.copy(sample("con-contrasena.pdf"), locked)
    broken = documents[0].with_name("roto.pdf")
    broken.write_bytes(b"not a pdf")
    outcomes = sign_many([locked, documents[1], broken], signer, Placement())
    assert [outcome.result for outcome in outcomes] == [PASSWORD, SIGNED, FAILED]
    assert not locked.with_name("con contraseña-firmado.pdf").exists()
    assert not broken.with_name("roto-firmado.pdf").exists()


def test_a_name_already_taken_is_not_overwritten(documents, signer):
    taken = documents[0].with_name(f"{documents[0].stem}-firmado.pdf")
    taken.write_bytes(b"mine")
    assert signed_copy_name(documents[0]).name == f"{documents[0].stem}-firmado (2).pdf"
    (outcome,) = sign_many(documents[:1], signer)
    assert taken.read_bytes() == b"mine"
    assert outcome.target.name.endswith("(2).pdf") and signatures(outcome.target) == 1
    signed = outcome.target.with_name("ya-firmado.pdf")
    assert signed_copy_name(signed).name == "ya-firmado.pdf"


def test_stopping_or_cancelling_the_pin_stops_the_batch(documents, signer, monkeypatch):
    outcomes = sign_many(documents, signer, progress=lambda done, _path: done < 3)
    assert len(outcomes) == 3

    real = signing.sign_pdf
    calls = []

    def cancelled_on_the_third(source, target, *rest):
        calls.append(source)
        if len(calls) == 3:
            raise SigningCancelled("closed")
        return real(source, target, *rest)

    monkeypatch.setattr(batch_signing, "sign_pdf", cancelled_on_the_third)
    others = [path.with_name(f"otro {path.name}") for path in documents]
    for path, other in zip(documents, others, strict=True):
        shutil.copy(path, other)
    with pytest.raises(SigningCancelled) as stopped:
        sign_many(others, signer)
    assert len(stopped.value.outcomes) == 2 and len(calls) == 3


def test_without_the_timestamp_server_it_asks_once(documents, signer):
    asked = []
    outcomes = sign_many(
        documents[:3],
        signer,
        timestamp_server="http://127.0.0.1:9/tsa",
        without_timestamp=lambda: asked.append(1) or True,
    )
    assert asked == [1], "asked once for the whole batch"
    assert [outcome.result for outcome in outcomes] == [SIGNED] * 3

    with pytest.raises(SigningCancelled):
        sign_many(documents[3:5], signer, timestamp_server="http://127.0.0.1:9/tsa")


def test_a_certificate_of_windows_keeps_its_key_open_for_the_batch(documents, monkeypatch):
    """The key is opened once for all the documents (the PIN, once)."""
    from app.core import windows_store
    from app.core.windows_store import describe
    from tests import certificates

    key = certificates.new_key()
    made = certificates.make_certificate("PRUEBA VENTANAS", key)
    opened, signed = [], []

    class FakeKey:
        def __init__(self, thumbprint, window_handle=None):
            opened.append(thumbprint)

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            pass

        def sign(self, digest, digest_algorithm, key_algorithm):
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding, utils

            signed.append(digest)
            return key.sign(digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))

    monkeypatch.setattr(windows_store, "OpenKey", FakeKey)
    monkeypatch.setattr(
        windows_store,
        "sign_digest",
        lambda *args, **kwargs: pytest.fail("each signature would open the key again"),
    )
    store_signer = signing.WindowsStoreSigner(describe(certificates.der(made)), chain_candidates=[])
    outcomes = sign_many(documents[:4], store_signer)
    assert [outcome.result for outcome in outcomes] == [SIGNED] * 4
    assert len(opened) == 1 and len(signed) == 4
