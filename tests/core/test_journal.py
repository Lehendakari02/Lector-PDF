"""Tests for the recovery journal."""

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from app.core.commands import HIGHLIGHT, UNDERLINE, AddMarkup, Mark, new_name
from app.core.journal import (
    DISCARDED_MARK,
    DocumentJournal,
    Journal,
    net,
)


def order(kind: str = HIGHLIGHT, page: int = 0) -> AddMarkup:
    mark = Mark(page, ((10.0, 20.0, 110.0, 32.0),), new_name())
    return AddMarkup(kind, (mark,), (1.0, 0.9, 0.2), 0.8)


@pytest.fixture
def journal(tmp_path) -> Journal:
    return Journal(tmp_path / "diario")


@pytest.fixture
def pdf(tmp_path) -> Path:
    path = tmp_path / "tema 5 – año.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    return path


# ---- what is left after doing and undoing ---------------------------------


def test_doing_and_undoing_leaves_nothing():
    one, two = order(), order()
    assert net([(one, False), (one, True)]) == []
    assert net([(one, False), (two, False), (one, True)]) == [(two, False)]
    assert net([(one, False), (one, True), (one, False)]) == [(one, False)]


def test_undoing_something_already_saved_stays():
    one = order()
    assert net([(one, True)]) == [(one, True)]
    assert net([(one, True), (one, False)]) == [], "and redoing it leaves nothing again"


def test_the_order_of_what_is_left_is_kept():
    one, two, three = order(), order(UNDERLINE), order()
    assert net([(one, False), (two, False), (three, False), (two, True)]) == [
        (one, False),
        (three, False),
    ]


# ---- writing down and reading back ----------------------------------------


def test_nothing_is_written_until_there_is_a_change(journal, pdf):
    document = journal.of(pdf)
    assert document.count == 0 and document.entries() == []
    assert not journal.folder.exists()
    assert journal.pending() == [] and journal.discarded() == []


def test_a_change_is_on_disk_at_once_and_can_be_read_back(journal, pdf):
    document = journal.of(pdf)
    one, two = order(), order(UNDERLINE, page=3)
    assert document.record(one) and document.record(two)
    assert document.count == 2
    # Another object reads the same file: nothing was kept only in memory.
    assert journal.of(pdf).entries() == [(one, False), (two, False)]
    (pending,) = journal.pending()
    assert pending.path == pdf and pending.count == 2 and not pending.discarded
    assert pending.entries == ((one, False), (two, False))
    assert abs(pending.when - time.time()) < 60


def test_what_was_undone_is_not_offered(journal, pdf):
    document = journal.of(pdf)
    one, two = order(), order()
    document.record(one)
    document.record(two)
    document.record(two, undone=True)
    (pending,) = journal.pending()
    assert pending.entries == ((one, False),)
    document.record(one, undone=True)
    assert journal.pending() == [], "everything was undone: nothing to recover"


def test_each_document_has_its_own_journal(journal, pdf, tmp_path):
    other = tmp_path / "ley.pdf"
    journal.of(pdf).record(order())
    journal.of(other).record(order())
    journal.of(other).record(order())
    counts = {pending.path.name: pending.count for pending in journal.pending()}
    assert counts == {pdf.name: 1, "ley.pdf": 2}


def test_the_same_file_written_another_way_is_the_same_journal(journal, pdf):
    journal.of(pdf).record(order())
    roundabout = pdf.parent / "." / pdf.name
    assert journal.of(roundabout).count == 1


def test_the_journal_never_touches_the_pdf(journal, pdf):
    before = pdf.read_bytes()
    document = journal.of(pdf)
    document.record(order())
    document.saved(1)
    document.record(order())
    document.discard()
    assert pdf.read_bytes() == before
    assert all(file.parent == journal.folder for file in journal.folder.iterdir())


# ---- saving ----------------------------------------------------------------


def test_saving_empties_the_journal(journal, pdf):
    document = journal.of(pdf)
    document.record(order())
    document.record(order())
    document.saved(2)
    assert document.count == 0 and not document.file.exists()
    assert journal.pending() == []


def test_changes_made_while_saving_stay_in_the_journal(journal, pdf):
    document = journal.of(pdf)
    one, two, late = order(), order(), order()
    document.record(one)
    document.record(two)
    document.record(late)  # made after the save was asked for
    document.saved(2)
    assert document.entries() == [(late, False)] and document.count == 1


def test_after_save_as_the_journal_follows_the_new_file(journal, pdf, tmp_path):
    document = journal.of(pdf)
    late = order()
    document.record(order())
    document.record(late)
    copy = tmp_path / "copia.pdf"
    document.saved(1, copy)
    assert document.path == copy
    (pending,) = journal.pending()
    assert pending.path == copy and pending.entries == ((late, False),)
    assert journal.of(pdf).count == 0, "nothing left under the old name"


# ---- "No guardar" ----------------------------------------------------------


def test_discarding_sets_the_changes_aside_instead_of_deleting_them(journal, pdf):
    document = journal.of(pdf)
    one = order()
    document.record(one)
    document.discard()
    assert document.count == 0 and not document.file.exists()
    assert journal.pending() == [], "not offered when the program starts"
    (aside,) = journal.discarded()
    assert aside.discarded and aside.path == pdf and aside.entries == ((one, False),)
    assert DISCARDED_MARK in aside.file.name


def test_discarding_twice_keeps_both(journal, pdf):
    document = journal.of(pdf)
    document.record(order())
    document.discard()
    time.sleep(0.01)
    document.record(order())
    document.record(order())
    document.discard()
    assert [aside.count for aside in journal.discarded()] == [2, 1], "the newest first"


def test_discarding_nothing_leaves_nothing(journal, pdf):
    document = journal.of(pdf)
    document.discard()
    one = order()
    document.record(one)
    document.record(one, undone=True)
    document.discard()
    assert journal.discarded() == [] and not list(journal.folder.iterdir())


def test_discarded_changes_are_forgotten_after_some_days(journal, pdf):
    document = journal.of(pdf)
    document.record(order())
    document.discard()
    assert journal.forget_old(days=7) == 0
    assert journal.forget_old(days=7, now=time.time() + 6 * 86400) == 0
    assert journal.forget_old(days=7, now=time.time() + 8 * 86400) == 1
    assert journal.discarded() == []


def test_changes_never_saved_nor_discarded_are_never_forgotten(journal, pdf):
    journal.of(pdf).record(order())
    assert journal.forget_old(days=7, now=time.time() + 400 * 86400) == 0
    assert len(journal.pending()) == 1


def test_setting_aside_what_was_not_recovered(journal, pdf):
    journal.of(pdf).record(order())
    (pending,) = journal.pending()
    journal.set_aside(pending)
    assert journal.pending() == [] and len(journal.discarded()) == 1
    journal.forget(journal.discarded()[0])
    assert journal.discarded() == []


def test_recovering_leaves_exactly_what_is_recovered(journal, pdf):
    document = journal.of(pdf)
    one, two = order(), order()
    document.record(one)
    document.record(two)
    document.record(two, undone=True)
    document.restart([(one, False)])
    assert document.count == 1 and document.entries() == [(one, False)]
    document.restart([])
    assert not document.file.exists()


# ---- damage ----------------------------------------------------------------


def test_a_line_cut_short_is_left_out_and_the_rest_is_good(journal, pdf):
    document = journal.of(pdf)
    one, two = order(), order()
    document.record(one)
    document.record(two)
    whole = document.file.read_bytes()
    document.file.write_bytes(whole[:-25])  # the power went while writing the last one
    assert journal.of(pdf).entries() == [(one, False)]
    (pending,) = journal.pending()
    assert pending.count == 1
    # And writing goes on after it without spoiling anything.
    again = journal.of(pdf)
    three = order()
    again.record(three)
    assert (three, False) in journal.of(pdf).entries()


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\x00\xff\xfe not a journal",
        b"[1, 2, 3]\n",
        b'{"what":"do","order":{"what":"add_markup"}}\n',
        b'{"what":"document","path":7}\n{"what":"do","order":{}}\n',
        b'{"what":"do","order":{"what":"something from the future"}}\n',
    ],
)
def test_files_that_are_not_journals_are_ignored(journal, content):
    journal.folder.mkdir(parents=True)
    (journal.folder / "raro.jsonl").write_bytes(content)
    assert journal.pending() == [] and journal.discarded() == []


def test_an_order_of_a_newer_version_is_skipped_and_the_others_kept(journal, pdf):
    document = journal.of(pdf)
    one = order()
    document.record(one)
    with open(document.file, "a", encoding="utf-8") as file:
        file.write(json.dumps({"what": "do", "order": {"what": "add_hologram"}}) + "\n")
    assert journal.of(pdf).entries() == [(one, False)]


def test_a_folder_that_cannot_be_written_does_not_stop_the_work(tmp_path, pdf):
    blocked = tmp_path / "archivo"
    blocked.write_text("this is a file, not a folder")
    document = Journal(blocked / "diario").of(pdf)
    assert document.record(order()) is False
    assert document.count == 0
    document.saved(3)
    document.discard()
    assert Journal(blocked / "diario").pending() == []


# ---- killed by force (CLAUDE.md, section 5.9) ------------------------------

WRITER = """
import sys, time
from pathlib import Path
from app.core.commands import AddMarkup, Mark
from app.core.journal import Journal

document = Journal(Path(sys.argv[1])).of(sys.argv[2])
number = 0
while True:
    mark = Mark(0, ((10.0, 20.0, 110.0, 32.0),), f"lectorpdf-{number:06d}")
    document.record(AddMarkup("highlight", (mark,), (1.0, 0.9, 0.2)))
    print(number, flush=True)  # told only once it is on disk
    number += 1
"""


@pytest.mark.parametrize("after", [0.05, 0.12, 0.2, 0.33, 0.5, 0.8])
def test_killed_while_writing_loses_nothing_that_was_written_down(tmp_path, after):
    folder, pdf = tmp_path / "diario", tmp_path / "tema.pdf"
    script = tmp_path / "writer.py"
    script.write_text(textwrap.dedent(WRITER))
    root = Path(__file__).resolve().parents[2]
    process = subprocess.Popen(
        [sys.executable, str(script), str(folder), str(pdf)],
        stdout=subprocess.PIPE,
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    try:
        first = process.stdout.readline()  # it has started writing
        assert first.strip() == b"0"
        time.sleep(after)
        if os.name == "nt":
            process.kill()
        else:
            process.send_signal(signal.SIGKILL)  # no chance to tidy anything up
        told = [first, *process.stdout.readlines()]
    finally:
        process.kill()
        process.wait()
    confirmed = [int(line) for line in told if line.strip().isdigit()]
    (pending,) = Journal(folder).pending()
    names = [entry[0].marks[0].name for entry in pending.entries]
    # Every change it said was written is there, in order and whole.
    assert names[: len(confirmed)] == [f"lectorpdf-{n:06d}" for n in confirmed]
    assert len(names) in (len(confirmed), len(confirmed) + 1), "at most the one being written"
    # The journal still works after it.
    again = DocumentJournal(folder, pdf)
    assert again.count == len(names)
    assert again.record(order())
    assert Journal(folder).pending()[0].count == len(names) + 1
