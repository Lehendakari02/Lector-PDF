"""Tests for app.core.settings."""

import json

from app.core.settings import Settings


def test_missing_file_gives_defaults(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    assert settings.get("tema") is None
    assert settings.get("tema", "sistema") == "sistema"


def test_values_survive_closing_the_program(tmp_path):
    path = tmp_path / "datos" / "ajustes.json"
    Settings(path).set("tema", "oscuro")
    assert Settings(path).get("tema") == "oscuro"


def test_file_is_readable_text_with_spanish_characters(tmp_path):
    path = tmp_path / "ajustes.json"
    Settings(path).set("carpeta", "C:/Oposición/año 2026")
    assert "Oposición/año" in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == {"carpeta": "C:/Oposición/año 2026"}


def test_damaged_file_gives_defaults_and_can_be_saved_again(tmp_path):
    path = tmp_path / "ajustes.json"
    path.write_text("{ this is not valid", encoding="utf-8")
    settings = Settings(path)
    assert settings.get("tema") is None
    settings.set("tema", "claro")
    assert Settings(path).get("tema") == "claro"


def test_file_with_unexpected_content_gives_defaults(tmp_path):
    path = tmp_path / "ajustes.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert Settings(path).get("tema") is None


def test_no_temporary_file_is_left_behind(tmp_path):
    path = tmp_path / "ajustes.json"
    Settings(path).set("tema", "oscuro")
    assert [file.name for file in tmp_path.iterdir()] == ["ajustes.json"]


def test_failing_to_save_does_not_break_the_program(tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    settings = Settings(blocker / "ajustes.json")
    settings.set("tema", "oscuro")  # must not raise
    assert settings.save() is False
    assert settings.get("tema") == "oscuro"
