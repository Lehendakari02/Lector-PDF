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


def test_the_program_starts_again_when_the_window_asked_for_it(monkeypatch):
    import app.main as program

    class WindowThatWantsToRestart(program.MainWindow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.restart_wanted = True

    started = []
    monkeypatch.setattr(program, "MainWindow", WindowThatWantsToRestart)
    monkeypatch.setattr(program, "relaunch", lambda: started.append(True))
    assert main(["lector-pdf", AUTOCLOSE_FLAG]) == 0
    assert started == [True]


def test_the_program_does_not_start_again_by_itself(monkeypatch):
    import app.main as program

    started = []
    monkeypatch.setattr(program, "relaunch", lambda: started.append(True))
    assert main(["lector-pdf", AUTOCLOSE_FLAG]) == 0
    assert started == []
