"""Tests for app.core.error_log."""

import json
import sys
from pathlib import Path

import pytest

from app import __version__
from app.core import error_log
from app.core.error_log import ErrorLog, hide_personal_folder


def record(log: ErrorLog, message: str = "boom", where: str = "") -> None:
    try:
        raise ValueError(message)
    except ValueError:
        log.record(*sys.exc_info(), where=where)


def test_no_file_until_the_first_error(tmp_path):
    log = ErrorLog(tmp_path / "datos" / "errores.jsonl")
    assert log.entries() == []
    assert not log.path.exists()
    assert not log.path.parent.exists()


def test_records_an_error_with_its_details(tmp_path):
    log = ErrorLog(tmp_path / "datos" / "errores.jsonl")
    record(log, "algo falló con la eñe", where="al guardar")
    (entry,) = log.entries()
    assert "ValueError: algo falló con la eñe" in entry.details
    assert "test_error_log.py" in entry.details
    assert entry.where == "al guardar"
    assert entry.version == __version__


def test_errors_are_kept_in_order_and_survive_restarts(tmp_path):
    path = tmp_path / "errores.jsonl"
    record(ErrorLog(path), "first")
    record(ErrorLog(path), "second")
    assert ["first" in e.details for e in ErrorLog(path).entries()] == [True, False]


def test_damaged_lines_are_skipped(tmp_path):
    path = tmp_path / "errores.jsonl"
    record(ErrorLog(path), "good")
    with path.open("a", encoding="utf-8") as file:
        file.write('not json\n{"time": 1}\n[]\n')
    record(ErrorLog(path), "also good")
    assert len(ErrorLog(path).entries()) == 2


def test_recording_never_raises_even_if_the_disk_fails(tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    log = ErrorLog(blocker / "errores.jsonl")
    record(log)  # must not raise
    assert log.entries() == []


def test_file_stays_small(tmp_path, monkeypatch):
    monkeypatch.setattr(error_log, "MAX_LOG_BYTES", 20_000)
    log = ErrorLog(tmp_path / "errores.jsonl")
    for number in range(200):
        record(log, f"error {number} " + "x" * 300)
    assert log.path.stat().st_size <= 20_000
    entries = log.entries()
    assert 0 < len(entries) < 200
    assert "error 199 " in entries[-1].details
    assert not log.path.with_name("errores.jsonl.tmp").exists()


def test_report_without_errors(tmp_path):
    report = ErrorLog(tmp_path / "errores.jsonl").build_report()
    assert report.startswith("Informe de error de Lector-PDF")
    assert f"Programa: {__version__}" in report
    assert "PyMuPDF" in report and "Sistema:" in report
    assert "No hay errores registrados." in report


def test_report_shows_the_last_errors_newest_first(tmp_path):
    log = ErrorLog(tmp_path / "errores.jsonl")
    for number in range(1, 9):
        record(log, f"error number {number}")
    report = log.build_report(["Qt: 6.x"])
    assert "Qt: 6.x" in report
    assert "Errores registrados: 8. Últimos 5:" in report
    assert "error number 3" not in report
    assert report.index("error number 8") < report.index("error number 4")


def test_personal_folder_is_hidden(tmp_path, monkeypatch):
    home = tmp_path / "Users" / "Nombre Apellido"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    text = f'File "{home}/Documents/tema.pdf" and again {str(home).upper()}/x'
    hidden = hide_personal_folder(text)
    assert "Nombre Apellido" not in hidden
    assert "NOMBRE APELLIDO" not in hidden
    assert "~/Documents/tema.pdf" in hidden


def test_personal_folder_is_hidden_with_windows_slashes(monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("C:/Users/Nombre")))
    hidden = hide_personal_folder("File C:\\Users\\Nombre\\tema.pdf y C:/Users/Nombre/x.pdf")
    assert "Nombre" not in hidden
    assert "~\\tema.pdf" in hidden and "~/x.pdf" in hidden


def test_a_very_short_home_folder_is_never_replaced(monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/")))
    assert hide_personal_folder("/usr/lib/python") == "/usr/lib/python"


def test_report_and_log_hide_the_personal_folder(tmp_path, monkeypatch):
    home = tmp_path / "Users" / "Nombre Apellido"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    log = ErrorLog(tmp_path / "errores.jsonl")
    record(log, f"cannot open {home}/Oposición/tema 5.pdf")
    assert "Nombre Apellido" not in log.path.read_text(encoding="utf-8")
    assert "Nombre Apellido" not in log.build_report()
    assert "~/Oposición/tema 5.pdf" in log.build_report()


def test_log_file_is_one_json_object_per_line(tmp_path):
    log = ErrorLog(tmp_path / "errores.jsonl")
    record(log, "one")
    record(log, "two")
    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert [set(json.loads(line)) for line in lines] == [
        {"time", "version", "where", "details"}
    ] * 2


@pytest.mark.parametrize(("label", "frozen", "expected"), [("", True, False), ("PR 6", True, True)])
def test_test_helpers_only_in_test_builds(monkeypatch, label, frozen, expected):
    monkeypatch.setattr(error_log, "BUILD_LABEL", label)
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    assert error_log.running_from_source_or_test_build() is expected
