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


# ---- what was remembered is never thrown away by accident ------------------


def held(monkeypatch, path, times: int):
    """Make ``path`` impossible to read the next ``times`` times, as if another
    program held it. Returns the list where each try is noted."""
    from pathlib import Path

    tries = []
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self == path and len(tries) < times:
            tries.append(1)
            raise PermissionError(13, "held by another program")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr("app.core.settings.READ_PAUSE", 0)
    return tries


def test_a_file_held_for_a_moment_is_read_at_the_next_try(tmp_path, monkeypatch):
    path = tmp_path / "ajustes.json"
    Settings(path).set("tema", "oscuro")
    tries = held(monkeypatch, path, 2)
    assert Settings(path).get("tema") == "oscuro"
    assert len(tries) == 2


def test_a_file_that_cannot_be_read_is_never_written_over(tmp_path, monkeypatch):
    path = tmp_path / "ajustes.json"
    first = Settings(path)
    first.set("tema", "oscuro")
    first.set("recientes", ["a.pdf", "b.pdf"])
    before = path.read_bytes()
    held(monkeypatch, path, 1000)
    settings = Settings(path)
    assert settings.get("tema") is None, "could not be read: the defaults for now"
    settings.set("tamano", "grande")
    assert settings.save_failed
    assert settings.get("tamano") == "grande", "still usable in this session"
    assert path.read_bytes() == before, "the file with everything remembered is untouched"


def test_what_changed_meanwhile_is_added_once_the_file_can_be_read(tmp_path, monkeypatch):
    path = tmp_path / "ajustes.json"
    first = Settings(path)
    first.set("tema", "oscuro")
    first.set("recientes", ["a.pdf"])
    tries = held(monkeypatch, path, 5)  # the four tries of the start and one more
    settings = Settings(path)
    settings.set("tamano", "grande")  # fifth try: still held
    assert len(tries) == 5 and settings.save_failed
    settings.set("tema", "claro")  # now it can be read
    assert not settings.save_failed
    assert settings.get("recientes") == ["a.pdf"], "what was remembered is back"
    again = Settings(path)
    assert again.get("recientes") == ["a.pdf"]
    assert again.get("tema") == "claro" and again.get("tamano") == "grande"


def test_a_damaged_file_is_set_aside_and_the_last_good_copy_is_used(tmp_path):
    path = tmp_path / "ajustes.json"
    Settings(path).set("tema", "oscuro")
    Settings(path)  # a start that reads it well keeps a copy
    path.write_text('{"tema": "osc', encoding="utf-8")  # cut short
    settings = Settings(path)
    assert settings.get("tema") == "oscuro", "from the copy"
    assert settings.damaged_path.read_text(encoding="utf-8") == '{"tema": "osc'
    assert Settings(path).get("tema") == "oscuro"


def test_a_damaged_file_without_a_copy_gives_defaults_and_is_kept_aside(tmp_path):
    path = tmp_path / "ajustes.json"
    path.write_bytes(b"\xff\xfe\x00 not text at all")
    settings = Settings(path)
    assert settings.get("tema") is None
    assert settings.damaged_path.exists() and not path.exists()
    settings.set("tema", "claro")
    assert Settings(path).get("tema") == "claro"


def test_the_copy_is_only_made_of_a_file_that_was_read_well(tmp_path):
    path = tmp_path / "ajustes.json"
    Settings(path).set("tema", "oscuro")
    settings = Settings(path)
    assert json.loads(settings.backup_path.read_text(encoding="utf-8")) == {"tema": "oscuro"}
    path.write_text("[]", encoding="utf-8")
    Settings(path)
    assert json.loads(settings.backup_path.read_text(encoding="utf-8")) == {"tema": "oscuro"}


def test_saving_again_after_a_failure_clears_the_warning(tmp_path):
    folder = tmp_path / "datos"
    blocker = folder
    blocker.write_text("x", encoding="utf-8")
    settings = Settings(folder / "ajustes.json")
    settings.set("tema", "oscuro")
    assert settings.save_failed
    blocker.unlink()
    assert settings.save() and not settings.save_failed
