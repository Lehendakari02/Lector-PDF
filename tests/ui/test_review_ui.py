"""Tests for the review mode: what is marked is covered, and a click uncovers it."""

import shutil

import pymupdf
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


def open_marked(window, sample, tmp_path, wait_until):
    """A copy of the BOE with "Constitución" highlighted and "Generales" underlined."""
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view._texts and 0 in view.cached_pages())
    for word, kind in (("Constitución", "highlight"), ("Generales", "underline")):
        start = view._texts[0].chars.index(word)
        view.select((0, start), (0, start + len(word)))
        assert view.mark_selection(kind)
        wait_until(lambda: not view._changing)
    wait_until(lambda: len(view.covers_of(0)) == 2)
    return view, path


def centre(view, item) -> QPoint:
    x0, y0, x1, y1 = view._shown_rect(item.page, item.rects[0])
    zoom = view._render_zoom()
    x = view._page_left(item.page) + (x0 + x1) / 2 * zoom
    y = view._tops[item.page] - view._scroll_y() + (y0 + y1) / 2 * zoom
    return QPoint(view._to_units(x), view._to_units(y))


def colour_at(view, point: QPoint):
    return view.viewport().grab().toImage().pixelColor(point)


def test_the_marks_are_covered_and_a_click_uncovers_one(window, sample, tmp_path, wait_until):
    view, path = open_marked(window, sample, tmp_path, wait_until)
    highlight, underline = view.covers_of(0)
    before = colour_at(view, centre(view, highlight))
    window.feature_actions["review"].trigger()
    assert view.review and window.feature_actions["review"].isChecked()
    assert "Modo repaso" in window.statusBar().currentMessage()
    view.viewport().repaint()
    covered = colour_at(view, centre(view, highlight))
    assert covered != before, "the word is under a block of its colour"
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, centre(view, highlight))
    assert view.uncovered(highlight.name) and not view.uncovered(underline.name)
    assert not view.has_selection, "the click does nothing else"
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, centre(view, highlight))
    assert not view.uncovered(highlight.name), "another click covers it again"
    assert view._changes == 2, "only the two marks: covering is not a change"
    with pymupdf.open(path) as doc:
        assert len(list(doc[0].annots())) == 0, "nothing was saved"


def test_escape_or_the_button_leaves_it(window, sample, tmp_path, wait_until):
    view, _path = open_marked(window, sample, tmp_path, wait_until)
    view.set_review(True)
    highlight = view.covers_of(0)[0]
    view.toggle_cover(highlight.name)
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert not view.review
    view.set_review(True)
    assert not view.uncovered(highlight.name), "every time it starts all covered"
    window.feature_actions["review"].trigger()
    assert not view.review and not window.feature_actions["review"].isChecked()


def test_hiding_the_annotations_ends_it(window, sample, tmp_path, wait_until):
    view, _path = open_marked(window, sample, tmp_path, wait_until)
    view.set_review(True)
    window.toggle_annotations()
    assert not view.review


def test_strike_outs_and_drawings_are_not_covered(window, sample, tmp_path, wait_until):
    view, _path = open_marked(window, sample, tmp_path, wait_until)
    start = view._texts[0].chars.index("Española")
    view.select((0, start), (0, start + 8))
    assert view.mark_selection("strikeout")
    wait_until(lambda: not view._changing and len(view.drawings_of(0)) == 3)
    assert [item.kind for item in view.covers_of(0)] == ["highlight", "underline"]
