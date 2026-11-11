"""Tests for the program entry point."""

from app.main import AUTOCLOSE_FLAG, main


def test_autoclose_opens_and_quits_cleanly():
    assert main(["lector-pdf", AUTOCLOSE_FLAG]) == 0


def test_check_signing_option(sample):
    from app.main import CHECK_SIGNING_FLAG, EXIT_SIGNING_FAILED

    start = ["lector-pdf", CHECK_SIGNING_FLAG, str(sample("formulario.pdf"))]
    certificate = str(sample("certificado-prueba.p12"))
    assert main([*start, certificate, "prueba"]) == 0
    assert main([*start, certificate, "mala"]) == EXIT_SIGNING_FAILED
    assert main(start) == EXIT_SIGNING_FAILED
