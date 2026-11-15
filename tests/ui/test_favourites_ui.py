"""Tests for the bar of favourite tools."""

import shutil

import pytest

from app.core.commands import HIGHLIGHT
from app.core.drawing import DRAW, OVAL, SHAPE_TOOL
from app.core.notes import TEXT_BOX
from app.ui.features import Mode
from app.ui.main_window import FAVOURITES_SETTING, MainWindow

GREEN = (0.1, 0.55, 0.25)
BLUE = (0.13, 0.39, 0.85)
ODD = (0.2, 0.3, 0.4)


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    window.set_mode(Mode.STUDY)
    return view


def names(window) -> list[str]:
    return [button.text() for button in window.favourites_bar.buttons]


def test_the_bar_only_takes_room_once_there_is_a_favourite(window):
    window.set_mode(Mode.STUDY)
    assert not window.favourites_bar.isVisible()
    window.set_line_width(DRAW, 4)
    window.favourite_actions[DRAW].trigger()
    assert window.favourites_bar.isVisible()
    assert names(window) == ["Dibujar · azul · grueso"]
    assert "Guardada en favoritas" in window.statusBar().currentMessage()
    window.set_mode(Mode.READ)
    assert not window.favourites_bar.isVisible(), "they are tools of the mode Estudiar"
    window.set_mode(Mode.STUDY)
    window.remove_favourite(0)
    assert not window.favourites_bar.isVisible()


def test_every_tool_with_a_style_can_be_kept(window):
    for kind, menu in window.color_menus.items():
        assert window.favourite_actions[kind] in menu.actions()
        window.favourite_actions[kind].trigger()
    assert len(window.favourites) == len(window.color_menus)
    assert names(window)[0] == "Resaltar · amarillo"


def test_the_names_say_what_each_one_is(window):
    window.set_marker_opacity(HIGHLIGHT, 0.5)
    window.add_favourite(HIGHLIGHT)
    window.set_shape(OVAL)
    window.set_marker_color(SHAPE_TOOL, BLUE)
    window.add_favourite(SHAPE_TOOL)
    window.set_text_size(18)
    window.add_favourite(TEXT_BOX)
    window.set_marker_color(DRAW, ODD)
    window.add_favourite(DRAW)
    assert names(window) == [
        "Resaltar · amarillo · 50 %",
        "Óvalo · azul",
        "Cuadro de texto · negro · 18",
        "Dibujar · color #334c66",
    ]


def test_the_same_one_is_not_kept_twice(window):
    assert window.add_favourite(DRAW) == 0
    assert window.add_favourite(DRAW) == 0
    assert "Ya estaba" in window.statusBar().currentMessage()
    assert len(window.favourites_bar.buttons) == 1


def test_a_full_bar_says_so(window):
    for width in (1, 2, 4, 8):
        for color in (GREEN, BLUE, ODD):
            window.marker_styles.set_width(DRAW, width)
            window.marker_styles.set_color(DRAW, color)
            window.add_favourite(DRAW)
    assert len(window.favourites) == 12
    window.marker_styles.set_opacity(DRAW, 0.5)
    assert window.add_favourite(DRAW) == -1
    assert "llena" in window.statusBar().currentMessage()
    assert len(window.favourites_bar.buttons) == 12


def test_a_click_sets_the_tool_that_way_and_takes_it(window, opened, wait_until):
    view = opened
    window.set_marker_color(DRAW, GREEN)
    window.set_line_width(DRAW, 8)
    window.set_marker_opacity(DRAW, 0.5)
    window.add_favourite(DRAW)
    window.set_marker_color(DRAW, BLUE)
    window.set_line_width(DRAW, 1)
    window.set_marker_opacity(DRAW, 1.0)
    window.use_writing_tool(DRAW)  # put it down
    assert view.markup_tool == "" and not window.favourites_bar.buttons[0].isChecked()
    window.favourites_bar.buttons[0].click()
    assert view.markup_tool == DRAW
    assert view.draw_color == pytest.approx(GREEN, abs=0.01)
    assert (view.draw_width, view.draw_opacity) == (8, 0.5)
    assert window.favourites_bar.buttons[0].isChecked()
    assert window.width_actions[DRAW][8.0].isChecked()
    assert view.draw_ink(0, [[(100, 100), (200, 150)]])
    wait_until(lambda: not view._changing and not view._asked_notes)
    (stroke,) = view.drawings_of(0)
    assert stroke.width == 8 and stroke.opacity == pytest.approx(0.5)


def test_the_one_in_hand_is_the_one_pressed(window, opened):
    window.add_favourite(DRAW)
    window.set_line_width(DRAW, 8)
    window.add_favourite(DRAW)
    first, second = window.favourites_bar.buttons
    assert second.isChecked() and not first.isChecked()
    first.click()
    assert first.isChecked() and not second.isChecked()
    window.set_marker_color(DRAW, ODD)  # no longer any of them
    first, second = window.favourites_bar.buttons
    assert not first.isChecked() and not second.isChecked()
    second.click()
    window.use_writing_tool(DRAW)  # put down
    assert not window.favourites_bar.buttons[1].isChecked()


def test_a_marker_favourite_marks_the_selected_text(window, opened, wait_until):
    view = opened
    wait_until(lambda: 0 in view._texts)
    window.set_marker_color(HIGHLIGHT, GREEN)
    window.add_favourite(HIGHLIGHT)
    view.set_markup_tool("")
    view.select((0, 0), (0, 12))
    window.favourites_bar.buttons[0].click()
    wait_until(lambda: not view._changing and not view._asked_notes)
    (mark,) = view.drawings_of(0)
    assert mark.kind == HIGHLIGHT and mark.color == pytest.approx(GREEN, abs=0.01)


def test_without_a_document_a_favourite_still_sets_the_tool(window):
    window.set_line_width(DRAW, 8)
    window.add_favourite(DRAW)
    window.set_line_width(DRAW, 1)
    window.use_favourite(0)
    assert window.marker_styles.width_of(DRAW) == 8
    assert window.pdf_view.markup_tool == ""


def test_rename_move_and_remove(window):
    window.add_favourite(DRAW)
    window.add_favourite(HIGHLIGHT)
    window.ask_favourite_name = lambda current: "  Mi boli  "
    window.rename_favourite(0)
    assert names(window) == ["Mi boli", "Resaltar · amarillo"]
    window.ask_favourite_name = lambda current: None  # cancelled
    window.rename_favourite(0)
    assert names(window)[0] == "Mi boli"
    menu = window.favourites_bar.menu_for(0)
    entries = {action.text(): action for action in menu.actions() if action.text()}
    assert list(entries) == [
        "Cambiar el nombre…",
        "Mover a la izquierda",
        "Mover a la derecha",
        "Quitar de favoritas",
    ]
    assert not entries["Mover a la izquierda"].isEnabled()
    entries["Mover a la derecha"].trigger()
    assert names(window) == ["Resaltar · amarillo", "Mi boli"]
    menu.deleteLater()
    menu = window.favourites_bar.menu_for(1)
    next(a for a in menu.actions() if a.text() == "Quitar de favoritas").trigger()
    menu.deleteLater()
    assert names(window) == ["Resaltar · amarillo"]
    window.ask_favourite_name = lambda current: ""
    window.rename_favourite(0)
    assert names(window) == ["Resaltar · amarillo"], "an empty name gives back the description"


def test_favourites_are_remembered(window, settings):
    window.set_line_width(DRAW, 8)
    window.add_favourite(DRAW)
    window.ask_favourite_name = lambda current: "Gordo"
    window.rename_favourite(0)
    assert settings.get(FAVOURITES_SETTING)[0]["name"] == "Gordo"
    again = MainWindow(settings)
    try:
        assert [button.text() for button in again.favourites_bar.buttons] == ["Gordo"]
        assert again.favourites[0].width == 8
    finally:
        again.close()
        again.deleteLater()


def test_a_damaged_setting_does_not_break_the_bar(settings, qt_app):
    settings.set(FAVOURITES_SETTING, [{"tool": "laser"}, 7, {"tool": DRAW, "color": "#00ff00"}])
    window = MainWindow(settings)
    try:
        assert len(window.favourites_bar.buttons) == 1
    finally:
        window.close()
        window.deleteLater()


def test_the_buttons_have_names_for_screen_readers_and_follow_the_toolbar_setting(window):
    window.add_favourite(DRAW)
    (button,) = window.favourites_bar.buttons
    assert button.accessibleName() == "Favorita: Dibujar · azul"
    assert "Botón derecho" in button.toolTip()
    from PySide6.QtCore import Qt

    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    window.set_toolbar_icons_only(True, remember=False)
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
