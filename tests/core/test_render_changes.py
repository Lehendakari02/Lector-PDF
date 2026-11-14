"""Tests for changing the document that the helper process has open."""

import os
import threading
from pathlib import Path

import pymupdf
import pytest

from app.core.commands import AddMarkup
from app.core.render_service import RenderRequest, RenderService
from app.core.search import read_page_text

WAIT_SECONDS = 30


class Editor:
    """A service with a document open, that lets a test wait for the answers."""

    def __init__(self):
        self.changed: list[tuple] = []
        self.failed: list[tuple] = []
        self.saved: list[tuple] = []
        self.save_failures: list[tuple] = []
        self.pages = []
        self.crashes = []
        self._moved = threading.Condition()
        self.service = RenderService(
            on_page=lambda page: self._add(self.pages, page),
            on_crashed=lambda: self._add(self.crashes, True),
            on_changed=lambda *change: self._add(self.changed, change),
            on_change_failed=lambda *failure: self._add(self.failed, failure),
            on_saved=lambda *saved: self._add(self.saved, saved),
            on_save_failed=lambda *failure: self._add(self.save_failures, failure),
        )

    def _add(self, where, item):
        with self._moved:
            where.append(item)
            self._moved.notify_all()

    def wait(self, condition):
        with self._moved:
            assert self._moved.wait_for(condition, WAIT_SECONDS), "timed out"

    def draw(self, page: int = 0):
        """The picture of a page as the helper sees it now."""
        already = len(self.pages)
        self.service.want([RenderRequest(page, 1.0)])
        self.wait(lambda: len(self.pages) > already)
        return self.pages[-1].samples

    def mark(self, kind, start, stop, **more):
        already = len(self.changed) + len(self.failed)
        number = self.service.mark_text(kind, start, stop, **more)
        self.wait(lambda: len(self.changed) + len(self.failed) > already)
        return number

    def save(self, target=None):
        already = len(self.saved) + len(self.save_failures)
        self.service.save(target)
        self.wait(lambda: len(self.saved) + len(self.save_failures) > already)


@pytest.fixture
def editor():
    made = Editor()
    yield made
    made.service.shutdown()


@pytest.fixture
def path(sample, tmp_path):
    target = tmp_path / "boe.pdf"
    target.write_bytes(Path(sample("boe.pdf")).read_bytes())
    return target


def word_carets(path, word: str, page: int = 0):
    with pymupdf.open(path) as doc:
        start = read_page_text(doc[page]).chars.index(word)
    return (page, start), (page, start + len(word))


def marks_in_file(path, page: int = 0):
    with pymupdf.open(path) as doc:
        sheet = doc[page]
        return [annotation.type[1] for annotation in sheet.annots() or ()]


def test_marking_text_changes_the_picture_and_not_the_file(editor, path):
    on_disk = path.read_bytes()
    editor.service.open(path)
    clean = editor.draw()
    number = editor.mark("highlight", *word_carets(path, "Constitución"))
    assert editor.failed == []
    got, order, pages, undo = editor.changed[0]
    assert got == number and pages == [0] and undo is False
    assert isinstance(order, AddMarkup) and order.kind == "highlight"
    assert editor.draw() != clean, "the mark is seen at once"
    assert path.read_bytes() == on_disk, "the PDF only changes when it is saved"


def test_saving_writes_the_marks_into_the_file(editor, path):
    editor.service.open(path)
    editor.mark("highlight", *word_carets(path, "Constitución"))
    editor.mark("underline", *word_carets(path, "Generales"))
    editor.save()
    assert editor.save_failures == []
    assert marks_in_file(path) == ["Highlight", "Underline"]
    editor.mark("strikeout", *word_carets(path, "Española"))  # goes on after saving
    editor.save()
    assert marks_in_file(path) == ["Highlight", "Underline", "StrikeOut"]


def test_an_order_can_be_undone_and_done_again(editor, path):
    editor.service.open(path)
    clean = editor.draw()
    editor.mark("highlight", *word_carets(path, "Constitución"))
    order = editor.changed[0][1]
    marked = editor.draw()
    editor.service.apply(order, undo=True)
    editor.wait(lambda: len(editor.changed) == 2)
    assert editor.changed[1][3] is True
    assert editor.draw() == clean
    editor.service.apply(order)
    editor.wait(lambda: len(editor.changed) == 3)
    assert editor.draw() == marked
    editor.save()
    assert marks_in_file(path) == ["Highlight"]


def test_a_mark_over_two_pages(editor, path):
    with pymupdf.open(path) as doc:
        end = len(read_page_text(doc[0]))
    editor.service.open(path)
    editor.mark("underline", (0, end - 30), (1, 40))
    assert editor.changed[0][2] == [0, 1]
    editor.save()
    assert marks_in_file(path, 0) == ["Underline"] and marks_in_file(path, 1) == ["Underline"]


def test_colour_and_opacity_reach_the_file(editor, path):
    editor.service.open(path)
    editor.mark("highlight", *word_carets(path, "Constitución"), color=(0.1, 0.9, 0.3), opacity=0.6)
    editor.save()
    with pymupdf.open(path) as doc:
        page = doc[0]
        annotation = next(page.annots())
        assert annotation.colors["stroke"] == pytest.approx((0.1, 0.9, 0.3), abs=0.01)
        assert annotation.opacity == pytest.approx(0.6, abs=0.01)


def test_nothing_to_mark_is_a_failure_and_changes_nothing(editor, path):
    editor.service.open(path)
    number = editor.mark("highlight", (0, 10), (0, 10))
    assert editor.changed == [] and editor.failed[0][0] == number
    number = editor.mark("glitter", (0, 0), (0, 10))
    assert editor.failed[1][0] == number
    editor.draw()  # the helper is alive and well


def test_marking_with_nothing_open_fails_at_once(editor):
    number = editor.service.mark_text("highlight", (0, 0), (0, 5))
    assert editor.failed == [(number, "no document is open")]


def test_unsaved_marks_survive_a_crash_of_the_helper(editor, path):
    """Until the recovery journal exists (task 2.5), at least a helper that dies
    must not take the unsaved marks with it."""
    editor.service.open(path)
    editor.mark("highlight", *word_carets(path, "Constitución"))
    editor.mark("underline", *word_carets(path, "Generales"))
    order = editor.changed[1][1]
    editor.service.apply(order, undo=True)  # the second one is undone
    editor.wait(lambda: len(editor.changed) == 3)
    marked = editor.draw()
    os.kill(editor.service.process_id, 9)
    editor.wait(lambda: editor.crashes)
    assert editor.draw() == marked, "the new helper has the same marks"
    assert len(editor.changed) == 3, "nothing is announced twice"
    editor.save()
    assert marks_in_file(path) == ["Highlight"]


def test_after_saving_a_crash_does_not_mark_twice(editor, path):
    editor.service.open(path)
    editor.mark("highlight", *word_carets(path, "Constitución"))
    editor.save()
    os.kill(editor.service.process_id, 9)
    editor.wait(lambda: editor.crashes)
    editor.draw()
    editor.mark("underline", *word_carets(path, "Generales"))
    editor.save()
    assert marks_in_file(path) == ["Highlight", "Underline"]


def test_opening_another_document_forgets_the_marks_of_the_first(editor, path, sample):
    editor.service.open(path)
    editor.mark("highlight", *word_carets(path, "Constitución"))
    editor.service.open(sample("formulario.pdf"))
    clean = editor.draw()
    os.kill(editor.service.process_id, 9)
    editor.wait(lambda: editor.crashes)
    assert editor.draw() == clean
