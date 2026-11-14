"""Tests for the orders that change a document (so far: marking text)."""

import json

import pymupdf
import pytest

from app.core import commands
from app.core.commands import AddMarkup, CommandError, Mark, command_from_dict, markup_for_selection
from app.core.search import find_in_page, read_page_text


@pytest.fixture
def doc(sample):
    with pymupdf.open(sample("boe.pdf")) as opened:
        yield opened


def texts_of(doc):
    cache = {}

    def page_text(number):
        if number not in cache:
            cache[number] = read_page_text(doc[number])
        return cache[number]

    return page_text


def select_word(doc, page: int, word: str):
    """The two carets around the first ``word`` of a page."""
    text = read_page_text(doc[page])
    start = text.chars.index(word)
    return (page, start), (page, start + len(word))


def annotations(doc, number: int = 0):
    page = doc[number]
    return [(a.type[1], a.info["id"]) for a in page.annots() or ()]


def changed_box(before, after):
    """The box of the pixels that differ between two pictures of a page."""
    assert (before.width, before.height) == (after.width, after.height)
    xs, ys = [], []
    a, b, n = before.samples, after.samples, before.n
    for y in range(before.height):
        row = y * before.stride
        if a[row : row + before.stride] == b[row : row + before.stride]:
            continue
        for x in range(before.width):
            if a[row + x * n : row + x * n + n] != b[row + x * n : row + x * n + n]:
                xs.append(x)
                ys.append(y)
    assert xs, "nothing changed in the picture"
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


@pytest.mark.parametrize(
    ("kind", "pdf_type"),
    [("highlight", "Highlight"), ("underline", "Underline"), ("strikeout", "StrikeOut")],
)
def test_marking_a_word_adds_a_standard_annotation(doc, kind, pdf_type):
    start, stop = select_word(doc, 0, "Constitución")
    order = markup_for_selection(kind, start, stop, texts_of(doc))
    assert order.apply(doc) == [0]
    assert annotations(doc) == [(pdf_type, order.marks[0].name)]
    page = doc[0]  # kept: an annotation dies with its page
    annotation = next(page.annots())
    assert annotation.colors["stroke"] == pytest.approx(commands.DEFAULT_COLORS[kind], abs=0.01)
    word = pymupdf.Rect(doc[0].search_for("Constitución")[0])
    assert annotation.rect.intersects(word)
    assert abs(annotation.rect.x0 - word.x0) < 8 and abs(annotation.rect.x1 - word.x1) < 8


def test_the_mark_is_seen_where_the_word_is(doc):
    before = doc[0].get_pixmap()
    start, stop = select_word(doc, 0, "Constitución")
    markup_for_selection("highlight", start, stop, texts_of(doc)).apply(doc)
    x0, y0, x1, y1 = changed_box(before, doc[0].get_pixmap())
    word = doc[0].search_for("Constitución")[0]
    assert abs(x0 - word.x0) < 4 and abs(x1 - word.x1) < 4
    assert abs(y0 - word.y0) < 4 and abs(y1 - word.y1) < 4


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_the_mark_lands_on_the_word_in_a_page_kept_turned(sample, tmp_path, turn):
    """Scanned pages are often stored sideways: the mark must not fly away."""
    turned = tmp_path / "girado.pdf"
    with pymupdf.open(sample("boe.pdf")) as source:
        source[0].set_rotation(turn)
        source.save(turned)
    with pymupdf.open(turned) as doc:
        assert doc[0].rotation == turn
        text = read_page_text(doc[0])
        hit = find_in_page(text, "Constitución")[0]
        before = doc[0].get_pixmap()
        start = text.chars.index("Constitución")
        order = markup_for_selection(
            "highlight", (0, start), (0, start + len("Constitución")), lambda n: text
        )
        order.apply(doc)
        x0, y0, x1, y1 = changed_box(before, doc[0].get_pixmap())
        wx0, wy0, wx1, wy1 = hit.rects[0]
        assert abs(x0 - wx0) < 4 and abs(x1 - wx1) < 4
        assert abs(y0 - wy0) < 4 and abs(y1 - wy1) < 4


def test_undo_takes_the_mark_away_and_leaves_the_others(doc):
    page_text = texts_of(doc)
    first = markup_for_selection("highlight", *select_word(doc, 0, "Constitución"), page_text)
    second = markup_for_selection("underline", *select_word(doc, 0, "Generales"), page_text)
    before = doc[0].get_pixmap().samples
    first.apply(doc)
    with_first = doc[0].get_pixmap().samples
    second.apply(doc)
    assert second.undo(doc) == [0]
    assert annotations(doc) == [("Highlight", first.marks[0].name)]
    assert doc[0].get_pixmap().samples == with_first
    first.undo(doc)
    assert annotations(doc) == [] and doc[0].get_pixmap().samples == before
    first.undo(doc)  # undoing twice does no harm


def test_applying_twice_does_not_mark_twice(doc):
    order = markup_for_selection("highlight", *select_word(doc, 0, "Constitución"), texts_of(doc))
    order.apply(doc)
    order.apply(doc)
    assert len(annotations(doc)) == 1


def test_a_selection_over_several_lines_is_one_mark_with_one_piece_per_line(doc):
    text = read_page_text(doc[0])
    spans = text.line_spans()
    start, stop = spans[3][0] + 2, spans[5][1] - 2
    order = markup_for_selection("highlight", (0, start), (0, stop), lambda n: text)
    assert len(order.marks) == 1 and len(order.marks[0].rects) >= 2
    order.apply(doc)
    assert len(annotations(doc)) == 1
    page = doc[0]
    assert len(next(page.annots()).vertices) == 4 * len(order.marks[0].rects)


def test_a_selection_over_two_pages_marks_both_and_undoes_both(doc):
    page_text = texts_of(doc)
    end_of_first = len(page_text(0))
    order = markup_for_selection("strikeout", (0, end_of_first - 40), (1, 60), page_text)
    assert [mark.page for mark in order.marks] == [0, 1]
    assert order.apply(doc) == [0, 1]
    assert len(annotations(doc, 0)) == 1 and len(annotations(doc, 1)) == 1
    assert order.undo(doc) == [0, 1]
    assert annotations(doc, 0) == [] and annotations(doc, 1) == []


def test_the_ends_can_come_in_any_order(doc):
    start, stop = select_word(doc, 0, "Constitución")
    page_text = texts_of(doc)
    forwards = markup_for_selection("highlight", start, stop, page_text)
    backwards = markup_for_selection("highlight", stop, start, page_text)
    assert forwards.marks[0].rects == backwards.marks[0].rects


def test_nothing_selected_gives_no_order(doc):
    page_text = texts_of(doc)
    assert markup_for_selection("highlight", (0, 5), (0, 5), page_text) is None


def test_an_unknown_kind_is_refused(doc):
    with pytest.raises(CommandError):
        markup_for_selection("glitter", (0, 0), (0, 5), texts_of(doc))
    with pytest.raises(CommandError):
        AddMarkup("glitter", (Mark(0, ((0, 0, 10, 10),), "x"),), (1, 0, 0)).apply(doc)


def test_a_page_that_does_not_exist_changes_nothing(doc):
    order = AddMarkup(
        "highlight",
        (Mark(0, ((50, 50, 100, 60),), "uno"), Mark(9999, ((50, 50, 100, 60),), "dos")),
        (1, 1, 0),
    )
    with pytest.raises(CommandError):
        order.apply(doc)
    assert annotations(doc) == [], "all or nothing"


def test_colour_and_opacity_are_kept(doc):
    start, stop = select_word(doc, 0, "Constitución")
    order = markup_for_selection("highlight", start, stop, texts_of(doc), (0.2, 0.8, 0.4), 0.5)
    order.apply(doc)
    page = doc[0]  # kept: an annotation dies with its page
    annotation = next(page.annots())
    assert annotation.colors["stroke"] == pytest.approx((0.2, 0.8, 0.4), abs=0.01)
    assert annotation.opacity == pytest.approx(0.5, abs=0.01)


def test_an_order_survives_being_written_down(doc):
    """The recovery journal keeps orders as text and applies them again later."""
    order = markup_for_selection("underline", (0, 100), (1, 50), texts_of(doc), (0.1, 0.2, 0.3))
    written = json.dumps(order.to_dict())
    read = command_from_dict(json.loads(written))
    assert read == order
    read.apply(doc)
    order.undo(doc)  # the copy and the original are the same order
    assert annotations(doc, 0) == [] and annotations(doc, 1) == []


def test_nonsense_is_not_an_order():
    for data in (
        {},
        {"what": "explode"},
        {"what": "add_markup"},
        {"what": "add_markup", "marks": 3},
    ):
        with pytest.raises(CommandError):
            command_from_dict(data)


def test_the_marks_survive_saving_and_are_plain_pdf(doc, tmp_path):
    from app.core.saving import save_to

    order = markup_for_selection("highlight", *select_word(doc, 0, "Constitución"), texts_of(doc))
    order.apply(doc)
    target = tmp_path / "marcado.pdf"
    save_to(doc, target)
    with pymupdf.open(target) as saved:
        assert annotations(saved) == [("Highlight", order.marks[0].name)]
        page = saved[0]
        annotation = next(page.annots())
        # What other viewers need: the standard keys and a drawn appearance.
        keys = saved.xref_get_keys(annotation.xref)
        assert {"Subtype", "QuadPoints", "Rect", "C", "AP"} <= set(keys)
        order.undo(saved)  # found again in the saved file by its name
        assert annotations(saved) == []
