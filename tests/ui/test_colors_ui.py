"""Tests for choosing the colour and the opacity of the marking tools."""

import shutil

import pymupdf
import pytest
from PySide6.QtWidgets import QToolButton

from app.core.commands import DEFAULT_COLORS, HIGHLIGHT, MARKUP_KINDS, STRIKEOUT, UNDERLINE
from app.core.marker_styles import QUICK_COLORS, same_color
from app.core.settings import Settings
from app.ui.color_menu import ColorMenu
from app.ui.features import Mode
from app.ui.main_window import MARKERS_SETTING, MainWindow

GREEN, PINK = QUICK_COLORS[1], QUICK_COLORS[3]
OWN = (0.3, 0.2, 0.9)  # a colour that is not in the quick palette


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    """The window with a copy of a sample open and the letters of its first page ready."""
    window.show_problem_dialogs = False
    path = tmp_path / "texto-partido.pdf"
    shutil.copy(sample("texto-partido.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view._texts and 0 in view.cached_pages())
    return view, path


def settle(view, wait_until, changes: int) -> None:
    wait_until(lambda: view._changes >= changes and not view._changing and not view._stale)


def marks_in_file(path):
    with pymupdf.open(path) as doc:
        page = doc[0]
        return [
            (annotation.type[1], tuple(annotation.colors["stroke"]), annotation.opacity)
            for annotation in page.annots() or ()
        ]


# ---- the menu itself -----------------------------------------------------


def test_the_menu_offers_the_palette_more_colours_and_opacity(qt_app):
    menu = ColorMenu("Resaltar")
    assert [swatch.color for swatch in menu.swatches] == list(QUICK_COLORS)
    names = [swatch.accessibleName() for swatch in menu.swatches]
    assert names[0] == "Amarillo" and len(set(names)) == len(names), "each one says its name"
    assert all(swatch.toolTip() for swatch in menu.swatches)
    assert menu.more_button.text() == "Más colores…"
    assert menu.opacity_slider.minimum() == 10 and menu.opacity_slider.maximum() == 100
    assert menu.recent_label.isHidden() and not menu.recent_swatches


def test_the_colour_in_use_is_the_one_marked(qt_app):
    menu = ColorMenu("Resaltar")
    menu.set_style(PINK, 0.4)
    assert [swatch.isChecked() for swatch in menu.swatches].count(True) == 1
    assert menu.swatches[3].isChecked()
    assert menu.opacity == 0.4 and "40" in menu.opacity_label.text()


def test_picking_a_swatch_tells_its_colour(qt_app):
    menu = ColorMenu("Resaltar")
    chosen = []
    menu.color_chosen.connect(chosen.append)
    menu.swatches[1].click()
    assert chosen == [GREEN]


def test_more_colours_tells_the_colour_chosen_or_nothing_if_cancelled(qt_app):
    menu = ColorMenu("Resaltar")
    chosen = []
    menu.color_chosen.connect(chosen.append)
    menu.ask_color = lambda current: None  # the dialog was cancelled
    menu.pick_other()
    assert chosen == []
    menu.ask_color = lambda current: OWN
    menu.pick_other()
    assert chosen == [OWN]


def test_colours_used_lately_appear_and_can_be_picked_again(qt_app):
    menu = ColorMenu("Resaltar")
    menu.set_recent([OWN, (0.5, 0.5, 0.5)])
    assert not menu.recent_label.isHidden() and len(menu.recent_swatches) == 2
    assert menu.recent_swatches[0].accessibleName().startswith("Color #")
    chosen = []
    menu.color_chosen.connect(chosen.append)
    menu.recent_swatches[0].click()
    assert chosen == [OWN]
    menu.set_recent([])
    assert menu.recent_label.isHidden() and not menu.recent_swatches


def test_the_opacity_is_told_when_the_slider_is_let_go(qt_app):
    menu = ColorMenu("Resaltar")
    told = []
    menu.opacity_chosen.connect(told.append)
    menu.opacity_slider.sliderMoved.emit(35)  # still dragging: only the label follows
    assert "35" in menu.opacity_label.text() and told == []
    menu.opacity_slider.setValue(35)
    assert told == [0.35]


# ---- in the window -------------------------------------------------------


def test_each_marking_tool_has_its_colour_menu(window):
    toolbar = window.mode_toolbars[Mode.STUDY]
    for kind in MARKUP_KINDS:
        button = toolbar.widgetForAction(window.feature_actions[kind])
        assert button.menu() is window.color_menus[kind]
        assert button.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup
        assert button.accessibleDescription(), "a screen reader says the colour in use"
        assert same_color(window.color_menus[kind].color, DEFAULT_COLORS[kind])


def test_a_colour_chosen_with_text_selected_marks_it(window, opened, wait_until):
    view, path = opened
    view.select((0, 0), (0, 12))
    window.set_marker_color(HIGHLIGHT, GREEN)
    settle(view, wait_until, 1)
    assert view.markup_tool == "", "it was one mark, the marker is not left in hand"
    window.save_document()
    wait_until(lambda: not view.saving)
    ((kind, color, _opacity),) = marks_in_file(path)
    assert kind == "Highlight" and same_color(color, GREEN)


def test_a_colour_chosen_with_nothing_selected_takes_the_marker(window, opened, wait_until):
    view, path = opened
    window.set_marker_color(UNDERLINE, QUICK_COLORS[7])
    assert view.markup_tool == UNDERLINE
    assert window.feature_actions[UNDERLINE].isChecked()
    window.set_marker_color(UNDERLINE, GREEN)  # changing colour does not put it away
    assert view.markup_tool == UNDERLINE
    view.select((0, 0), (0, 12))
    view.mark_selection(UNDERLINE)
    settle(view, wait_until, 1)
    window.save_document()
    wait_until(lambda: not view.saving)
    ((kind, color, _opacity),) = marks_in_file(path)
    assert kind == "Underline" and same_color(color, GREEN)


def test_each_tool_keeps_its_colour_and_the_others_do_not_change(window, opened):
    window.set_marker_color(HIGHLIGHT, PINK)
    assert same_color(window.color_menus[HIGHLIGHT].color, PINK)
    assert same_color(window.color_menus[UNDERLINE].color, DEFAULT_COLORS[UNDERLINE])
    assert same_color(window.pdf_view.markup_colors[STRIKEOUT], DEFAULT_COLORS[STRIKEOUT])


def test_the_opacity_reaches_the_file(window, opened, wait_until):
    view, path = opened
    window.set_marker_opacity(HIGHLIGHT, 0.4)
    assert view.markup_tool == "", "changing the opacity does not take the marker"
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    settle(view, wait_until, 1)
    window.save_document()
    wait_until(lambda: not view.saving)
    ((_kind, _color, opacity),) = marks_in_file(path)
    assert opacity == pytest.approx(0.4, abs=0.01)


def test_marks_already_made_keep_their_colour(window, opened, wait_until):
    view, path = opened
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    settle(view, wait_until, 1)
    view.select((0, 30), (0, 42))
    window.set_marker_color(HIGHLIGHT, GREEN)
    settle(view, wait_until, 2)
    window.save_document()
    wait_until(lambda: not view.saving)
    colors = [color for _kind, color, _opacity in marks_in_file(path)]
    assert len(colors) == 2
    assert any(same_color(c, DEFAULT_COLORS[HIGHLIGHT]) for c in colors)
    assert any(same_color(c, GREEN) for c in colors)


def test_undo_and_redo_keep_the_colour_of_the_mark(window, opened, wait_until):
    view, path = opened
    view.select((0, 0), (0, 12))
    window.set_marker_color(HIGHLIGHT, PINK)
    settle(view, wait_until, 1)
    window.set_marker_color(HIGHLIGHT, GREEN)  # another colour is chosen afterwards
    view.set_markup_tool("")
    view.undo()
    settle(view, wait_until, 2)
    view.redo()
    settle(view, wait_until, 3)
    window.save_document()
    wait_until(lambda: not view.saving)
    ((_kind, color, _opacity),) = marks_in_file(path)
    assert same_color(color, PINK)


def test_the_colours_apply_to_every_tab_and_to_the_ones_opened_later(
    window, opened, sample, tmp_path
):
    window.set_marker_color(HIGHLIGHT, PINK)
    other = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), other)
    assert window.open_document(other)
    assert same_color(window.pdf_view.markup_colors[HIGHLIGHT], PINK)
    window.set_marker_opacity(HIGHLIGHT, 0.6)
    for page in window.documents:
        assert page.view.markup_opacity[HIGHLIGHT] == 0.6


def test_the_choice_is_remembered_the_next_time(qt_app, window, settings):
    window.set_marker_color(HIGHLIGHT, OWN)
    window.set_marker_opacity(STRIKEOUT, 0.5)
    saved = Settings(settings.path).get(MARKERS_SETTING)
    assert saved["tools"][HIGHLIGHT]["color"].startswith("#")
    again = MainWindow(Settings(settings.path))
    try:
        assert same_color(again.color_menus[HIGHLIGHT].color, OWN)
        assert again.color_menus[STRIKEOUT].opacity == 0.5
        assert len(again.color_menus[UNDERLINE].recent_swatches) == 1, "shared by the tools"
        assert same_color(again.pdf_view.markup_colors[HIGHLIGHT], OWN)
    finally:
        again.close()
        again.deleteLater()


def test_damaged_settings_do_not_break_the_window(qt_app, settings):
    settings.set(MARKERS_SETTING, {"tools": {"highlight": "no"}, "recent": 7})
    window = MainWindow(settings)
    try:
        assert same_color(window.color_menus[HIGHLIGHT].color, DEFAULT_COLORS[HIGHLIGHT])
    finally:
        window.close()
        window.deleteLater()


def test_choosing_a_colour_without_a_document_only_remembers_it(window):
    window.set_marker_color(HIGHLIGHT, GREEN)
    assert window.pdf_view.markup_tool == ""
    assert same_color(window.color_menus[HIGHLIGHT].color, GREEN)
