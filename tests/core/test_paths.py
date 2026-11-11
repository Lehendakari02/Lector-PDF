"""Tests for app.core.paths."""

import sys
from pathlib import Path

import pytest

from app.core import paths


@pytest.fixture
def packaged_in(tmp_path, monkeypatch):
    """Pretend to be the built program located in ``tmp_path``."""
    exe = tmp_path / "Lector-PDF.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return tmp_path


def test_running_from_source_is_never_portable():
    assert paths.is_packaged() is False
    assert paths.is_portable() is False
    assert (paths.program_dir() / "pyproject.toml").is_file()


def test_marker_next_to_source_code_does_not_make_it_portable(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "program_dir", lambda: tmp_path)
    (tmp_path / paths.PORTABLE_MARKER).write_text("x", encoding="utf-8")
    assert paths.is_portable() is False


def test_portable_build_keeps_data_next_to_the_program(packaged_in):
    (packaged_in / paths.PORTABLE_MARKER).write_text("x", encoding="utf-8")
    assert paths.is_portable() is True
    assert paths.data_dir() == packaged_in.resolve() / paths.PORTABLE_DATA_FOLDER


def test_portable_build_ignores_appdata(packaged_in, monkeypatch):
    (packaged_in / paths.PORTABLE_MARKER).write_text("x", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(packaged_in / "elsewhere"))
    monkeypatch.setenv("XDG_DATA_HOME", str(packaged_in / "elsewhere"))
    assert "elsewhere" not in paths.data_dir().parts


def test_installed_build_is_not_portable(packaged_in):
    assert paths.is_portable() is False
    assert packaged_in.resolve() not in paths.data_dir().parents


def test_installed_data_folder_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.data_dir() == tmp_path / "Lector-PDF"


def test_installed_data_folder_on_windows_without_variable(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert paths.data_dir() == Path.home() / "AppData" / "Local" / "Lector-PDF"


def test_installed_data_folder_elsewhere(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.data_dir() == tmp_path / "Lector-PDF"


def test_data_dir_is_not_created_by_asking_for_it(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    paths.data_dir()
    assert not (tmp_path / "Lector-PDF").exists()
