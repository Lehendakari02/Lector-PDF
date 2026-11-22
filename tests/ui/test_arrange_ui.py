"""Tests for picking, moving, resizing, copying and removing annotations in the window."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.commands import HIGHLIGHT
from app.core.drawing import ARROW, BOX, DRAW, INK
from app.core.notes import NOTE, TEXT_BOX
from app.ui.pdf_view import PdfView

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


@pytest.fixture(autouse=True)
def nothing_copied():
    PdfView.copied = None
    yield
    PdfView.copied = None


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
        return view, path

    return open_it


def place(view, page: int, x: float, y: float) -> QPoint:
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def drag(view, page: int, *points) -> None:
    spots = [place(view, page, x, y) for x, y in points]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[-1])


def click(view, page: int, x: float, y: float) -> None:
    drag(view, page, (x, y))


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def near(first, second, by: float = 1.5) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


@pytest.fixture
def with_box(window, opened, wait_until):
    """A document with a box from (100, 100) to (200, 160), and nothing in hand."""
    view, path = opened()
    assert view.draw_shape(BOX, 0, (100, 100), (200, 160))
    settle(view, wait_until)
    return view, path


# ---- picking ---------------------------------------------------------------------


def test_a_click_on_a_drawing_picks_it_and_a_click_elsewhere_lets_it_go(
    window, with_box, wait_until
):
    view, _ = with_box
    assert view.picked_item() is None and not window.delete_action.isEnabled()
    click(view, 0, 100, 130)  # on its left edge
    assert view.picked_item().kind == BOX
    assert window.delete_action.isEnabled() and window.duplicate_action.isEnabled()
    assert not view.modified or view.can_undo
    click(view, 0, 300, 400)
    assert view.picked_item() is None and not window.delete_action.isEnabled()


def test_escape_lets_go_of_what_is_picked(window, with_box):
    view, _ = with_box
    click(view, 0, 100, 130)
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.picked_item() is None


def test_with_the_pen_in_hand_a_tap_picks_and_a_stroke_draws(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    window.use_writing_tool(DRAW)
    assert view.picked_item() is None, "taking a tool lets go"
    click(view, 0, 100, 130)  # a tap on the box (16/11 test): it is picked
    settle(view, wait_until)
    assert view.picked_item().kind == BOX and len(view.drawings_of(0)) == 1
    QTest.keyClick(view, Qt.Key.Key_Delete)  # and Supr takes it away
    settle(view, wait_until)
    assert view.drawings_of(0) == []
    drag(view, 0, (300, 300), (340, 320), (380, 300))  # a stroke still draws
    settle(view, wait_until)
    assert [item.kind for item in view.drawings_of(0)] == [INK]
    click(view, 0, 500, 700)  # a tap on nothing draws as before
    settle(view, wait_until)
    assert view.picked_item() is None


def test_a_tapped_shape_is_dragged_with_the_pen_still_in_hand(window, with_box, wait_until):
    view, _ = with_box
    window.use_writing_tool(DRAW)
    click(view, 0, 100, 130)
    drag(view, 0, (100, 130), (130, 150), (150, 170))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect[:2], (150, 140), 2), "moved, not drawn over"


def test_with_a_marker_in_hand_a_click_on_a_mark_picks_it(window, opened, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    settle(view, wait_until)
    (mark,) = view.drawings_of(0)
    x0, y0, x1, y1 = mark.rects[0]
    window.use_marker(HIGHLIGHT)
    click(view, 0, (x0 + x1) / 2, (y0 + y1) / 2)
    assert view.picked_item().kind == HIGHLIGHT
    QTest.keyClick(view, Qt.Key.Key_Delete)
    settle(view, wait_until)
    assert view.drawings_of(0) == []
    drag(view, 0, (x0 + 1, (y0 + y1) / 2), (x1 - 1, (y0 + y1) / 2))
    settle(view, wait_until)
    assert [item.kind for item in view.drawings_of(0)] == [HIGHLIGHT], "dragging still marks"


def test_a_click_on_a_mark_picks_it_but_dragging_still_selects_text(
    window, opened, wait_until, capsys
):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    settle(view, wait_until)
    (mark,) = view.drawings_of(0)
    x0, y0, x1, y1 = mark.rects[0]
    click(view, 0, (x0 + x1) / 2, (y0 + y1) / 2)
    assert view.picked_item().kind == HIGHLIGHT
    view.viewport().grab()
    assert "Traceback" not in capsys.readouterr().err, "its frame is painted without trouble"
    assert window.delete_action.isEnabled() and not window.duplicate_action.isEnabled()
    drag(view, 0, (x0 + 1, (y0 + y1) / 2), (x1 - 1, (y0 + y1) / 2))
    assert view.has_selection and view.picked_item() is None
    assert not view.move_picked(10, 10)


def test_what_another_program_made_is_picked_but_does_not_move(
    window, sample, tmp_path, wait_until
):
    path = tmp_path / "ajeno.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        page = doc[0]
        page.add_rect_annot(pymupdf.Rect(100, 100, 200, 160))
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    click(view, 0, 100, 130)
    picked = view.picked_item()
    assert picked is not None and not picked.ours
    drag(view, 0, (100, 130), (150, 180))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert box.rect == picked.rect and not view.modified, "it stays where it was"
    assert not view.copy_picked() and not view.move_picked(10, 10)
    assert not view.resize_picked(0, 10, 10)


# ---- moving ----------------------------------------------------------------------


def test_dragging_a_drawing_moves_it(window, with_box, wait_until, capsys):
    view, _ = with_box
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, place(view, 0, 100, 130))
    QTest.mouseMove(view.viewport(), place(view, 0, 120, 150))
    view.viewport().grab()  # painted while it is dragged
    assert "Traceback" not in capsys.readouterr().err
    QTest.mouseMove(view.viewport(), place(view, 0, 150, 180))
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, place(view, 0, 150, 180))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect, (150, 150, 250, 210))
    assert view.picked_item().name == box.name, "it stays picked"
    window.undo()
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect, (100, 100, 200, 160))


def test_a_stroke_and_a_text_move_too(window, opened, wait_until):
    view, _ = opened()
    assert view.draw_ink(0, [[(100, 300), (150, 320), (200, 300)]])
    assert view.put_text_box(0, 100, 400, "apunte")
    settle(view, wait_until)
    drag(view, 0, (150, 320), (170, 350))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.kind == INK and near(stroke.strokes[0][0], (120, 330))
    (text,) = view.notes_of(0)
    x0, y0, x1, y1 = text.rect
    drag(view, 0, ((x0 + x1) / 2, (y0 + y1) / 2), ((x0 + x1) / 2 + 50, (y0 + y1) / 2 - 40))
    settle(view, wait_until)
    (text,) = view.notes_of(0)
    assert text.kind == TEXT_BOX and text.text == "apunte"
    assert near(text.rect[:2], (x0 + 50, y0 - 40))
    assert view.note_panel is None, "dragging does not open it"


def test_a_note_moves_when_dragged_and_opens_when_clicked(window, opened, wait_until):
    view, _ = opened()
    assert view.put_note(0, 300, 200, "ojo")
    settle(view, wait_until)
    drag(view, 0, (300, 200), (340, 260))
    settle(view, wait_until)
    (note,) = view.notes_of(0)
    assert note.kind == NOTE and near(note.rect[:2], (332, 252))
    assert view.note_panel is None
    click(view, 0, 340, 260)
    assert view.note_panel is not None and view.note_panel.edit.toPlainText() == "ojo"
    view.close_note_panel()


def test_nothing_is_dragged_out_of_its_page(window, with_box, wait_until):
    view, _ = with_box
    size = view.page_sizes()[0]
    drag(view, 0, (100, 130), (100 + 2 * size.width, 130))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert box.rect[2] == pytest.approx(size.width, abs=0.5)


def test_the_arrow_keys_move_what_is_picked(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    QTest.keyClick(view, Qt.Key.Key_Right)
    QTest.keyClick(view, Qt.Key.Key_Right)  # at once: before the page is read again
    QTest.keyClick(view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect, (102, 110, 202, 170), 0.05)
    scroll = view.verticalScrollBar().value()
    QTest.keyClick(view, Qt.Key.Key_Escape)
    QTest.keyClick(view, Qt.Key.Key_Down)
    assert view.verticalScrollBar().value() > scroll, "with nothing picked they scroll"


def test_on_a_turned_view_things_move_the_way_they_are_seen(window, with_box, wait_until):
    view, _ = with_box
    view.rotate_view()
    wait_until(lambda: 0 in view.cached_pages())
    view.pick(view.drawings_of(0)[0])
    QTest.keyClick(view, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect, (100, 90, 200, 150), 0.05), "right on the turned sheet is up the page"


# ---- resizing --------------------------------------------------------------------


def test_dragging_a_handle_resizes(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    drag(view, 0, (200, 160), (230, 200), (260, 220))  # its bottom right corner
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.rect, (100, 100, 260, 220))
    window.undo()
    settle(view, wait_until)
    assert near(view.drawings_of(0)[0].rect, (100, 100, 200, 160))


def test_the_end_of_an_arrow_can_be_taken_elsewhere(window, opened, wait_until):
    view, _ = opened()
    assert view.draw_shape(ARROW, 0, (100, 300), (200, 300))
    settle(view, wait_until)
    click(view, 0, 150, 300)
    drag(view, 0, (200, 300), (260, 360))
    settle(view, wait_until)
    (arrow,) = view.drawings_of(0)
    start, end = arrow.strokes[0]
    assert near(start, (100, 300)) and near(end, (260, 360))


def test_a_text_gets_a_bigger_letter(window, opened, wait_until):
    view, _ = opened()
    assert view.put_text_box(0, 100, 400, "apunte")
    settle(view, wait_until)
    (text,) = view.notes_of(0)
    x0, y0, x1, y1 = text.rect
    click(view, 0, (x0 + x1) / 2, (y0 + y1) / 2)
    drag(view, 0, (x1, y1), (x0 + 2 * (x1 - x0), y0 + 2 * (y1 - y0)))
    settle(view, wait_until)
    (bigger,) = view.notes_of(0)
    assert bigger.size > text.size * 1.7 and bigger.text == "apunte"


# ---- removing, copying, pasting ----------------------------------------------------


def test_delete_removes_what_is_picked(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    window.delete_action.trigger()
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and view.picked_item() is None
    window.undo()
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    click(view, 0, 100, 130)
    QTest.keyClick(view, Qt.Key.Key_Backspace)
    settle(view, wait_until)
    assert view.drawings_of(0) == []


def test_without_anything_picked_the_menu_says_how(window, opened):
    opened()
    window.delete_picked()
    assert "clic" in window.statusBar().currentMessage()
    window.duplicate_picked()
    assert "clic" in window.statusBar().currentMessage()
    window.paste()
    assert "copiada" in window.statusBar().currentMessage()


def test_duplicate_puts_a_copy_next_to_it_and_picks_it(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    original = view.picked_item().name
    window.duplicate_action.trigger()
    settle(view, wait_until)
    first, second = view.drawings_of(0)
    assert near(second.rect, (112, 112, 212, 172))
    assert view.picked_item().name == second.name != original
    window.undo()
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1


def test_copy_and_paste_repeat_a_drawing(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    assert not window.paste_action.isEnabled()
    window.copy()
    assert "copiada" in window.statusBar().currentMessage()
    assert window.paste_action.isEnabled()
    window.paste_action.trigger()
    window.paste_action.trigger()
    settle(view, wait_until)
    rects = [item.rect for item in view.drawings_of(0)]
    assert len(rects) == 3
    assert near(rects[1], (112, 112, 212, 172)) and near(rects[2], (124, 124, 224, 184))


def test_paste_lands_where_it_is_asked(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    assert view.copy_picked()
    assert view.paste(place(view, 0, 300, 400))
    settle(view, wait_until)
    assert near(view.drawings_of(0)[1].rect, (250, 370, 350, 430))


def test_a_copy_can_be_pasted_in_another_document(window, opened, wait_until):
    view, _ = opened("boe.pdf")
    assert view.put_note(0, 300, 200, "ojo")
    settle(view, wait_until)
    view.pick(view.notes_of(0)[0])
    window.copy()
    other, _ = opened("largo.pdf")
    assert other is not view
    window.paste()
    settle(other, wait_until)
    (note,) = other.notes_of(other.current_page)
    assert note.text == "ojo" and other.modified


def test_copy_with_nothing_picked_still_copies_text(window, opened, wait_until, qt_app):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    copied = []
    view.text_copied.connect(copied.append)
    window.copy()
    wait_until(lambda: copied)
    assert copied[0] > 0 and PdfView.copied is None


def test_the_right_button_offers_what_can_be_done(window, with_box, wait_until):
    view, _ = with_box
    menu = view.context_menu(place(view, 0, 100, 130))
    names = [action.text() for action in menu.actions() if action.text()]
    assert names[:3] == ["Copiar la anotación", "Duplicar", "Borrar la forma"]
    assert "Pegar aquí" not in names
    assert view.picked_item() is not None
    next(a for a in menu.actions() if a.text() == "Copiar la anotación").trigger()
    menu.deleteLater()
    menu = view.context_menu(place(view, 0, 300, 400))
    paste = next(a for a in menu.actions() if a.text() == "Pegar aquí")
    paste.trigger()
    settle(view, wait_until)
    menu.deleteLater()
    assert len(view.drawings_of(0)) == 2


def test_moves_are_saved_in_the_file(window, with_box, wait_until):
    view, path = with_box
    drag(view, 0, (100, 130), (150, 180))
    settle(view, wait_until)
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    with pymupdf.open(path) as doc:
        page = doc[0]
        (annotation,) = page.annots()
        assert annotation.type[1] == "Square"
        assert near(annotation.rect, (149, 149, 251, 211))


# ---- the bar over what is picked: colour and Borrar (16/11 test) -------------------

GREEN = (0.56, 0.88, 0.42)


def test_the_bar_over_a_picked_mark_changes_its_colour(window, opened, wait_until, capsys):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    settle(view, wait_until)
    (mark,) = view.drawings_of(0)
    x0, y0, x1, y1 = mark.rects[0]
    assert not view.picked_bar.isVisible()
    click(view, 0, (x0 + x1) / 2, (y0 + y1) / 2)
    bar = view.picked_bar
    assert bar.isVisible() and all(s.isVisible() for s in bar.swatches)
    assert bar.geometry().bottom() < place(view, 0, x0, y0).y(), "just over the mark"
    green = next(s for s in bar.swatches if s.color == GREEN)
    green.click()
    settle(view, wait_until)
    (mark,) = view.drawings_of(0)
    assert mark.color == pytest.approx(GREEN, abs=0.01) and mark.kind == HIGHLIGHT
    assert view.picked_item() is not None and bar.isVisible(), "still picked"
    view.viewport().grab()
    assert "Traceback" not in capsys.readouterr().err
    window.undo()
    settle(view, wait_until)
    assert view.drawings_of(0)[0].color != pytest.approx(GREEN, abs=0.01)


def test_any_colour_and_borrar_from_the_bar(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    bar = view.picked_bar
    bar.ask_color = lambda _current: (0.2, 0.3, 0.4)
    bar.more_button.click()
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert box.color == pytest.approx((0.2, 0.3, 0.4), abs=0.01) and box.kind == BOX
    bar.remove_button.click()
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and not bar.isVisible()


def test_the_bar_hides_while_dragging_and_for_other_programs_only_borrar(
    window, sample, tmp_path, wait_until
):
    path = tmp_path / "ajeno.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        doc[0].add_rect_annot(pymupdf.Rect(100, 300, 200, 360))
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    click(view, 0, 100, 330)
    bar = view.picked_bar
    assert bar.isVisible() and bar.remove_button.isVisible()
    assert not any(s.isVisible() for s in bar.swatches) and not bar.more_button.isVisible()


def test_the_bar_goes_away_while_a_drawing_is_dragged(window, with_box, wait_until):
    view, _ = with_box
    click(view, 0, 100, 130)
    spots = [place(view, 0, x, y) for x, y in ((100, 130), (120, 150), (140, 170))]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    assert not view.picked_bar.isVisible()
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[-1])
    assert view.picked_bar.isVisible()
