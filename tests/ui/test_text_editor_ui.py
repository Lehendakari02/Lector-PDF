"""Tests for writing text straight on the page: in its place, with its look."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core import notes, symbols
from app.core.marker_styles import MarkerStyles
from app.core.notes import NOTE, SERIF, TEXT_BOX
from app.ui.main_window import MARKERS_SETTING
from app.ui.note_panel import NotePanel
from app.ui.text_editor import TextEditor

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier
RED = (0.85, 0.15, 0.15)
BLUE = (0.13, 0.39, 0.85)


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


def click(view, x: float, y: float, page: int = 0) -> None:
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, page, x, y))


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def start(window, view, x: float = 60, y: float = 300) -> TextEditor:
    if view.markup_tool != TEXT_BOX:
        window.use_writing_tool(TEXT_BOX)
    click(view, x, y)
    assert isinstance(view.note_panel, TextEditor)
    return view.note_panel


def text_start(editor: TextEditor) -> QPoint:
    """Where the first letter is written, in the page area of the window."""
    return editor.edit.mapTo(editor.parentWidget(), QPoint(0, 0))


# ---- writing ---------------------------------------------------------------------


def test_the_text_is_written_on_the_page_itself(window, opened, wait_until, capsys):
    view, path = opened()
    editor = start(window, view, 60, 300)
    assert editor.parentWidget() is view.viewport(), "not in a panel: on the page"
    assert editor.isVisible() and editor.edit.hasFocus() and not editor.existing
    spot, first = place(view, 0, 60, 300), text_start(editor)
    assert abs(first.x() - spot.x()) <= 1, "the letters start where the click was"
    assert first.y() < spot.y() < first.y() + 12 * view._zoom + 4, "at the height of the click"
    QTest.keyClicks(editor.edit, "Art. 14")
    QTest.keyClick(editor.edit, Qt.Key.Key_Return)  # Intro is just another line
    QTest.keyClicks(editor.edit, "igualdad")
    assert view.note_panel is editor
    QTest.keyClick(editor.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    settle(view, wait_until)
    assert view.note_panel is None
    (box,) = view.notes_of(0)
    assert (box.kind, box.text) == (TEXT_BOX, "Art. 14\nigualdad")
    assert abs(box.rect[0] - 60) < 1 and box.rect[1] < 300 < box.rect[1] + 12
    view.viewport().grab()
    assert "Traceback" not in capsys.readouterr().err


def test_a_click_elsewhere_keeps_the_text_and_starts_the_next(window, opened, wait_until):
    view, _ = opened()
    editor = start(window, view, 60, 300)
    editor.edit.setPlainText("primero")
    click(view, 300, 500)
    second = view.note_panel
    assert isinstance(second, TextEditor) and second is not editor
    assert abs(text_start(second).x() - place(view, 0, 300, 500).x()) <= 1
    second.edit.setPlainText("segundo")
    click(view, 60, 600)
    view.note_panel.cancel()
    settle(view, wait_until)
    assert sorted(box.text for box in view.notes_of(0)) == ["primero", "segundo"]


def test_a_click_elsewhere_with_nothing_written_leaves_nothing(window, opened, wait_until):
    view, _ = opened()
    start(window, view, 60, 300)
    click(view, 300, 500)
    view.note_panel.cancel()
    settle(view, wait_until)
    assert view.notes_of(0) == [] and not view.modified


def test_esc_leaves_everything_as_it_was(window, opened, wait_until):
    view, _ = opened()
    editor = start(window, view)
    editor.edit.setPlainText("me arrepiento")
    QTest.keyClick(editor.edit, Qt.Key.Key_Escape)
    settle(view, wait_until)
    assert view.note_panel is None and view.notes_of(0) == [] and not view.modified
    assert view.markup_tool == TEXT_BOX, "the tool stays in hand"


def test_a_note_is_still_written_in_its_panel(window, opened):
    view, _ = opened()
    window.use_writing_tool(NOTE)
    click(view, 300, 200)
    assert isinstance(view.note_panel, NotePanel)
    view.close_note_panel()


def test_with_the_pages_turned_the_text_is_written_in_the_panel(window, opened, wait_until):
    view, _ = opened()
    view.set_rotation(90)
    wait_until(lambda: 0 in view.cached_pages())
    window.use_writing_tool(TEXT_BOX)
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, QPoint(300, 200))
    assert isinstance(view.note_panel, NotePanel)
    view.close_note_panel()


# ---- its look ----------------------------------------------------------------------


def test_the_bar_gives_size_weight_and_colour(window, opened, wait_until, tmp_path):
    view, path = opened()
    editor = start(window, view)
    editor.edit.setPlainText("Importante")
    assert editor.size == 12 and not editor.bold
    editor.bigger_button.click()
    editor.bigger_button.click()
    assert editor.size == 18 and editor.size_label.text() == "18"
    editor.smaller_button.click()
    assert editor.size == 14
    editor.bold_button.click()
    editor.ink_buttons[2].click()  # red
    assert editor.bold and editor.color == pytest.approx(RED)
    assert editor.ink_buttons[2].isChecked() and not editor.ink_buttons[0].isChecked()
    assert view.note_panel is editor and editor.edit.hasFocus(), "writing goes on"
    assert editor.edit.document().defaultFont().bold()
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert (box.size, box.bold) == (14, True) and box.color == pytest.approx(RED, abs=0.01)
    # The next text is written the same way, also after the program is closed.
    again = start(window, view, 60, 500)
    assert (again.size, again.bold) == (14, True) and again.color == pytest.approx(RED)
    again.cancel()
    kept = MarkerStyles.from_setting(window.settings.get(MARKERS_SETTING))
    assert (kept.text_size, kept.text_bold) == (14, True)
    assert kept.of(TEXT_BOX).color == pytest.approx(RED, abs=0.01)


def test_ctrl_b_makes_it_bold(window, opened):
    view, _ = opened()
    editor = start(window, view)
    QTest.keyClick(editor.edit, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    assert editor.bold and view.text_bold
    QTest.keyClick(editor.edit, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    assert not editor.bold and not view.text_bold
    editor.cancel()


def test_a_look_chosen_in_the_tool_bar_reaches_the_text_being_written(window, opened, wait_until):
    view, _ = opened()
    editor = start(window, view)
    editor.edit.setPlainText("sigo escribiendo")
    window.set_marker_color(TEXT_BOX, BLUE)
    window.set_text_font(SERIF)
    window.set_text_size(24)
    assert view.note_panel is editor, "choosing a look does not close it"
    assert (editor.font_name, editor.size) == (SERIF, 24) and editor.color == pytest.approx(BLUE)
    window.set_marker_color(NOTE, RED)  # another tool: nothing to do with this text
    assert editor.color == pytest.approx(BLUE)
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert (box.font, box.size) == (SERIF, 24)


def test_the_letters_have_the_size_they_will_have_on_the_page(window, opened):
    view, _ = opened()
    editor = start(window, view)
    assert editor.edit.document().defaultFont().pixelSize() == round(12 * view._zoom)
    view.set_zoom(view.zoom * 1.5)
    assert editor.edit.document().defaultFont().pixelSize() == round(12 * view._zoom)
    editor.cancel()


def test_the_text_stays_on_its_place_when_the_page_moves(window, opened):
    view, _ = opened()
    editor = start(window, view, 60, 300)
    before = text_start(editor)
    bar = view.verticalScrollBar()
    bar.setValue(bar.value() + 80)
    after = text_start(editor)
    assert (after.x(), after.y()) == (before.x(), before.y() - 80)
    editor.cancel()


# ---- its width ---------------------------------------------------------------------


def test_the_edge_is_dragged_to_choose_the_width(window, opened, wait_until):
    view, _ = opened()
    editor = start(window, view, 60, 300)
    editor.edit.setPlainText("Un texto largo que se va a cortar en varias líneas al estrecharlo")
    one_line = editor.box.height()
    assert editor.width_chosen == 0
    editor.grip.dragged.emit(-round(200 * view._zoom))
    editor.grip.released.emit()
    assert editor.width_chosen > 0 and editor.box.height() > one_line, "narrower: more lines"
    width = editor.width_chosen
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert box.width == pytest.approx(width, abs=0.01)
    assert box.rect[2] - box.rect[0] == pytest.approx(width, abs=0.5)
    assert len(notes.box_layout(box.text, box.font, box.size, box.rect[:2], 595, box.width)[0]) > 1


def test_a_double_click_on_the_edge_goes_back_to_the_width_of_the_text(window, opened):
    view, _ = opened()
    editor = start(window, view)
    editor.edit.setPlainText("corto")
    editor.set_width(200)
    wide = editor.box.width()
    editor.grip.reset.emit()
    assert editor.width_chosen == 0 and editor.box.width() < wide
    editor.cancel()


def test_the_text_never_goes_past_the_right_edge_of_the_page(window, opened):
    view, _ = opened()
    editor = start(window, view, 400, 300)
    editor.edit.setPlainText("palabra " * 40)
    right = editor.box.mapTo(view.viewport(), QPoint(editor.box.width(), 0)).x()
    assert right <= place(view, 0, view._sizes[0].width, 0).x()
    assert editor.box.height() > 3 * 12 * view._zoom, "it goes on in more lines"
    editor.cancel()


# ---- a text that is already there ----------------------------------------------------


@pytest.fixture
def with_text(window, opened, wait_until):
    view, path = opened()
    assert view.put_text_box(0, 60, 300, "antes", 0.0, size=18, color=BLUE, bold=True)
    settle(view, wait_until)
    return view, path


def open_it(view) -> TextEditor:
    QTest.mouseDClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 70, 310))
    assert isinstance(view.note_panel, TextEditor)
    return view.note_panel


def test_a_double_click_opens_a_text_in_its_place(window, with_text, wait_until):
    view, _ = with_text
    editor = open_it(view)
    assert editor.existing and editor.edit.toPlainText() == "antes"
    assert (editor.size, editor.bold) == (18, True) and editor.color == pytest.approx(
        BLUE, abs=0.01
    )
    assert editor.remove_button.isVisible()
    spot, first = place(view, 0, 60, 300), text_start(editor)
    assert abs(first.x() - spot.x()) <= 1 and abs(first.y() - spot.y()) <= 0.3 * 18 * view._zoom
    editor.edit.setPlainText("después")
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert (box.text, box.size, box.bold) == ("después", 18, True)
    assert box.rect[:2] == pytest.approx((60, 300), abs=0.01), "it has not moved"
    view.undo()
    settle(view, wait_until)
    assert [box.text for box in view.notes_of(0)] == ["antes"]


def test_only_its_look_can_be_changed(window, with_text, wait_until):
    view, _ = with_text
    editor = open_it(view)
    editor.smaller_button.click()
    editor.bold_button.click()
    editor.set_width(120)
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert (box.text, box.size, box.bold, box.width) == ("antes", 14, False, 120)


def test_opened_and_left_as_it_was_nothing_changes(window, with_text, wait_until):
    view, _ = with_text
    undo_steps = len(view._undo)
    open_it(view).save()
    settle(view, wait_until)
    assert len(view._undo) == undo_steps


def test_emptied_or_with_its_button_a_text_is_removed(window, with_text, wait_until):
    view, _ = with_text
    editor = open_it(view)
    editor.edit.setPlainText("  ")
    editor.save()
    settle(view, wait_until)
    assert view.notes_of(0) == []
    view.undo()
    settle(view, wait_until)
    open_it(view).remove_button.click()
    settle(view, wait_until)
    assert view.notes_of(0) == [] and view.note_panel is None


def test_intro_opens_the_text_that_is_picked(window, with_text):
    view, _ = with_text
    click(view, 70, 310)
    assert view.picked_item() is not None and view.note_panel is None
    QTest.keyClick(view, Qt.Key.Key_Return)
    assert isinstance(view.note_panel, TextEditor) and view.note_panel.existing
    view.note_panel.cancel()


def test_the_side_of_a_picked_text_is_dragged_to_change_its_width(window, with_text, wait_until):
    view, _ = with_text
    click(view, 70, 310)
    box = view.picked_item()
    x0, y0, x1, y1 = box.rect
    middle = (y0 + y1) / 2
    spots = [place(view, 0, x, middle) for x in (x1, x1 + 40, x1 + 100)]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[-1])
    settle(view, wait_until)
    (after,) = view.notes_of(0)
    assert after.width == pytest.approx(x1 - x0 + 100, abs=2) and after.size == 18


def test_a_saved_text_is_a_standard_one(window, with_text, wait_until):
    view, path = with_text
    window.save_document()
    wait_until(lambda: not view.modified)
    with pymupdf.open(path) as doc:
        page = doc[0]
        (annotation,) = page.annots()
        assert annotation.type[1] == "FreeText" and annotation.info["content"] == "antes"


def test_the_wheel_over_the_text_still_moves_the_page(window, opened):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    view, _ = opened()
    editor = start(window, view, 60, 300)
    target = editor.edit.viewport()
    spot = QPointF(5, 5)
    wheel = QWheelEvent(
        spot,
        QPointF(target.mapToGlobal(spot.toPoint())),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        NO_KEYS,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(target, wheel)
    assert view.verticalScrollBar().value() > 0
    assert view.note_panel is editor
    editor.cancel()


def test_with_the_tool_in_hand_a_click_picks_an_earlier_text_and_another_opens_it(
    window, opened, wait_until
):
    view, _ = opened()
    first = start(window, view, 60, 300)
    first.edit.setPlainText("el primero")
    click(view, 300, 500)  # keeps the first and starts the second
    view.note_panel.edit.setPlainText("el segundo")
    settle(view, wait_until)
    click(view, 70, 300)  # back on the first one: it is picked
    settle(view, wait_until)
    assert view.note_panel is None
    assert view.picked_item() is not None and view.picked_item().text == "el primero"
    click(view, 70, 300)  # a second click opens it to write
    again = view.note_panel
    assert isinstance(again, TextEditor) and again.existing
    assert again.edit.toPlainText() == "el primero"
    again.edit.setPlainText("el primero, corregido")
    click(view, 310, 500)  # and on to the second one
    settle(view, wait_until)
    click(view, 310, 500)
    assert view.note_panel.existing and view.note_panel.edit.toPlainText() == "el segundo"
    view.note_panel.cancel()
    settle(view, wait_until)
    assert sorted(box.text for box in view.notes_of(0)) == ["el primero, corregido", "el segundo"]


# ---- arrows and symbols ----------------------------------------------------------


def test_a_symbol_is_put_with_a_click(window, opened, wait_until):
    view, path = opened()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "Art. 81 ")
    assert set(editor.symbol_buttons) == set(symbols.SYMBOLS)
    editor.symbol_buttons["→"].click()
    QTest.keyClicks(editor.edit, " mayor")
    assert editor.edit.toPlainText() == "Art. 81 → mayor" and editor.edit.hasFocus()
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert box.text == "Art. 81 → mayor"
    window.save_document()
    wait_until(lambda: not view.modified)
    with pymupdf.open(path) as doc:
        assert "→" in doc[0].get_text()


def test_typing_plain_keys_gives_an_arrow(window, opened):
    view, _ = opened()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "a -> b <- c <-> d => e")
    assert editor.edit.toPlainText() == "a → b ← c ↔ d ⇒ e"
    QTest.keyClicks(editor.edit, " x->")
    editor.edit.undo()  # Ctrl+Z right after: as it was typed
    assert editor.edit.toPlainText().endswith("x->")
    editor.cancel()


def test_typed_arrows_follow_the_setting(window, opened):
    view, _ = opened()
    window.settings.set(symbols.TYPED_SETTING, False)
    window.apply_pen_settings()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "a -> b")
    assert editor.edit.toPlainText() == "a -> b"
    editor.cancel()


def test_a_text_with_symbols_is_seen_and_opened_again(window, opened, wait_until, capsys):
    view, _ = opened()
    assert view.put_text_box(0, 60, 300, "① uno ⇒ dos ✓")
    settle(view, wait_until)
    wait_until(lambda: 0 not in view._stale)
    QTest.mouseDClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 70, 308))
    editor = view.note_panel
    assert isinstance(editor, TextEditor) and editor.edit.toPlainText() == "① uno ⇒ dos ✓"
    editor.cancel()
    view.viewport().grab()
    assert "Traceback" not in capsys.readouterr().err


def test_typed_arrows_are_turned_off_in_the_settings(window, opened):
    view, _ = opened()
    dialog = window.open_settings()
    assert dialog.typed_arrows_box.isChecked()
    dialog.typed_arrows_box.setChecked(False)
    dialog.close()
    assert window.settings.get(symbols.TYPED_SETTING) is False and not view.typed_arrows
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "a -> b")
    assert editor.edit.toPlainText() == "a -> b"
    editor.cancel()


# ---- moving it, and what is under it (16/11 test) ----------------------------------


def drag(widget, start: QPoint, by: QPoint) -> None:
    """Press, move and let go, as a hand would: the widget may move under it."""
    first = widget.mapToGlobal(start)
    QTest.mousePress(widget, LEFT, NO_KEYS, start)
    for step in range(1, 5):
        QTest.mouseMove(widget, widget.mapFromGlobal(first + by * step / 4))
    QTest.mouseRelease(widget, LEFT, NO_KEYS, widget.mapFromGlobal(first + by))


def test_bigger_letters_on_the_left_and_smaller_on_the_right(window, opened):
    view, _ = opened()
    editor = start(window, view)
    assert editor.bigger_button.x() < editor.size_label.x() < editor.smaller_button.x()
    editor.cancel()


def test_an_open_text_is_moved_by_its_handle(window, with_text, wait_until):
    view, _ = with_text
    editor = open_it(view)
    assert editor.mover.isVisible()
    centre = editor.mover.rect().center()
    drag(editor.mover, centre, QPoint(round(40 * view._zoom), round(30 * view._zoom)))
    spot, first = place(view, 0, 100, 330), text_start(editor)
    assert abs(first.x() - spot.x()) <= 2, "the editor goes with the hand"
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert box.text == "antes" and box.rect[:2] == pytest.approx((100, 330), abs=1.5)
    view.undo()
    settle(view, wait_until)
    assert view.notes_of(0)[0].rect[:2] == pytest.approx((60, 300), abs=0.01)


def test_a_new_text_is_moved_before_it_is_left(window, opened, wait_until):
    view, _ = opened()
    editor = start(window, view, 60, 300)
    QTest.keyClicks(editor.edit, "nuevo")
    origin = view._editor_place[1:]
    centre = editor.mover.rect().center()
    drag(editor.mover, centre, QPoint(round(-20 * view._zoom), round(50 * view._zoom)))
    editor.save()
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert box.rect[:2] == pytest.approx((origin[0] - 20, origin[1] + 50), abs=1.5)


def test_with_the_text_tool_in_hand_a_text_is_dragged_and_removed_with_supr(
    window, with_text, wait_until
):
    view, _ = with_text
    window.use_writing_tool(TEXT_BOX)
    drag(
        view.viewport(), place(view, 0, 70, 310), place(view, 0, 170, 410) - place(view, 0, 70, 310)
    )
    settle(view, wait_until)
    assert view.note_panel is None, "dragged: moved, not opened"
    (box,) = view.notes_of(0)
    assert box.rect[:2] == pytest.approx((160, 400), abs=1.5)
    assert view.picked_item() is not None
    QTest.keyClick(view, Qt.Key.Key_Delete)
    settle(view, wait_until)
    assert view.notes_of(0) == []


def test_while_a_text_is_changed_the_page_under_it_is_seen(window, with_text, wait_until):
    view, _ = with_text
    name = view.notes_of(0)[0].name
    editor = open_it(view)
    assert view._look(0) == (name,)
    wait_until(lambda: not editor._covering)
    assert "transparent" in editor.box.styleSheet(), "no white frame over the page"
    editor.cancel()
    assert view._look(0) is True
    wait_until(lambda: 0 not in view._stale)


# ---- what is being typed is never lost unasked -----------------------------------


def texts_in(path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [a.info.get("content", "") for page in doc for a in page.annots() or ()]


def test_ctrl_s_keeps_the_text_still_being_typed(window, opened, wait_until):
    view, path = opened()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "Apunte importante")
    assert window.save_document()
    wait_until(lambda: not view.saving and not view._changing)
    assert view.note_panel is None and not view.modified
    assert any("Apunte importante" in text for text in texts_in(path))


def test_closing_the_tab_asks_about_the_text_still_being_typed(window, opened, wait_until):
    view, _path = opened()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "No me pierdas")
    asked = []
    # Cancel now; the end of the test answers "No guardar" to close for good.
    window._ask_unsaved = lambda pages: asked.append(pages) or window.unsaved_answer or "cancel"
    window.close_document()
    assert asked, "it asked before closing"
    assert view.modified and window.documents
    settle(view, wait_until)
    wait_until(lambda: not view._stale)


def test_closing_the_window_asks_about_the_text_still_being_typed(window, opened, wait_until):
    view, _path = opened()
    editor = start(window, view)
    QTest.keyClicks(editor.edit, "No me pierdas")
    asked = []
    # Cancel now; the end of the test answers "No guardar" to close for good.
    window._ask_unsaved = lambda pages: asked.append(pages) or window.unsaved_answer or "cancel"
    window.close()
    assert asked and window.isVisible()
    settle(view, wait_until)
    wait_until(lambda: not view._stale)
