"""Tests for what the program remembers about the documents used."""

from pathlib import Path

import pytest

from app.core import history
from app.core.history import History, Place
from app.core.settings import Settings


@pytest.fixture
def store(tmp_path):
    return History(Settings(tmp_path / "ajustes.json"))


def make_files(folder: Path, count: int) -> list[Path]:
    files = []
    for number in range(count):
        file = folder / f"tema-{number}.pdf"
        file.write_bytes(b"%PDF")
        files.append(file)
    return files


def test_nothing_is_remembered_at_first(store, tmp_path):
    assert store.session() == ([], -1)
    assert store.recent() == []
    assert store.place_of(tmp_path / "x.pdf") == Place(0, "")
    assert store.restore_wanted


def test_session_survives_closing_the_program(tmp_path):
    settings_file = tmp_path / "ajustes.json"
    files = make_files(tmp_path, 3)
    History(Settings(settings_file)).save_session(files, 1)
    assert History(Settings(settings_file)).session() == (files, 1)


def test_place_of_every_document_is_kept(store, tmp_path):
    first, second = make_files(tmp_path, 2)
    store.remember_place(first, 41, "study")
    store.remember_place(second, 3)
    store.remember_place(first, 42, "study")
    assert store.place_of(first) == Place(42, "study")
    assert store.place_of(second) == Place(3, "")
    # The same file written another way is the same document.
    assert store.place_of(str(first.parent / "." / first.name)) == Place(42, "study")


def test_only_so_many_places_are_kept(store, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "MAX_PLACES", 3)
    clock = iter(range(1000, 2000))
    monkeypatch.setattr(history.time, "time", lambda: next(clock))
    files = make_files(tmp_path, 5)
    for number, file in enumerate(files):
        store.remember_place(file, number + 1)
    assert store.place_of(files[0]) == Place()  # the oldest ones are forgotten
    assert store.place_of(files[1]) == Place()
    assert [store.place_of(file).page for file in files[2:]] == [3, 4, 5]


def test_recent_files_newest_first_without_repeats(store, tmp_path):
    first, second, third = make_files(tmp_path, 3)
    for file in (first, second, third, first):
        store.add_recent(file)
    assert store.recent() == [first, third, second]


def test_recent_list_has_a_limit(store, tmp_path):
    files = make_files(tmp_path, history.MAX_RECENT + 4)
    for file in files:
        store.add_recent(file)
    recent = store.recent()
    assert len(recent) == history.MAX_RECENT
    assert recent[0] == files[-1]


def test_files_that_no_longer_exist_are_left_out(store, tmp_path):
    first, second = make_files(tmp_path, 2)
    store.add_recent(first)
    store.add_recent(second)
    second.unlink()
    assert store.recent() == [first]


def test_recent_list_can_be_emptied(store, tmp_path):
    store.add_recent(make_files(tmp_path, 1)[0])
    store.forget_recent()
    assert store.recent() == []


def test_damaged_memories_do_not_break_anything(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    settings.set(history.SESSION_SETTING, "nonsense")
    settings.set(history.PLACES_SETTING, [1, 2])
    settings.set(history.RECENT_SETTING, {"a": 1})
    store = History(settings)
    assert store.session() == ([], -1)
    assert store.recent() == []
    assert store.place_of(tmp_path / "x.pdf") == Place()
    settings.set(history.PLACES_SETTING, {history.file_key(tmp_path / "x.pdf"): {"pagina": "7"}})
    assert store.place_of(tmp_path / "x.pdf") == Place()


def test_restoring_can_be_turned_off(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    settings.set(history.RESTORE_SETTING, False)
    assert not History(settings).restore_wanted


# ---- tabs whose file is not there right now --------------------------------


def test_absent_tabs_are_waited_for(store, tmp_path):
    files = make_files(tmp_path, 2)
    away = tmp_path / "usb" / "tema.pdf"
    store.save_session(files, 0, [away])
    assert store.session() == (files, 0), "they are not counted among the open ones"
    assert store.absent_tabs() == [away]


def test_an_absent_tab_that_is_open_again_is_no_longer_absent(store, tmp_path):
    files = make_files(tmp_path, 2)
    store.save_session(files, 0, [files[1], tmp_path / "otro.pdf"])
    assert store.absent_tabs() == [tmp_path / "otro.pdf"]


def test_absent_tabs_are_forgotten_after_some_weeks(store, tmp_path):
    import time

    from app.core.history import ABSENT_DAYS

    away = tmp_path / "usb" / "tema.pdf"
    store.save_session([], -1, [away])
    store.save_session([], -1, [away])  # saved again later: the first day counts
    later = time.time() + (ABSENT_DAYS - 1) * 86400
    assert store.absent_tabs(now=later) == [away]
    assert store.absent_tabs(now=later + 2 * 86400) == []


def test_damaged_absent_tabs_are_ignored(store):
    from app.core.history import SESSION_SETTING

    store.settings.set(SESSION_SETTING, {"abiertos": [], "ausentes": [3, {"ruta": 5}, "x"]})
    assert store.absent_tabs() == []
    store.settings.set(SESSION_SETTING, {"abiertos": [], "ausentes": "no"})
    assert store.absent_tabs() == []
