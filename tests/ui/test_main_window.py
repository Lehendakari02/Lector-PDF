"""Tests for the main window: modes, tools, theme."""

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel

from app import APP_NAME, __version__
from app.core.settings import Settings
from app.ui.features import FEATURES, MODES, Mode, features_of
from app.ui.main_window import MIN_BUTTON_HEIGHT, MainWindow
from app.ui.theme import Theme


def visible_tools(window) -> set[str]:
    return {
        feature.id
        for mode, toolbar in window.mode_toolbars.items()
        for feature in features_of(mode)
        if toolbar.isVisible()
    }


def test_main_window_shows_name_and_versions(window):
    assert window.isVisible()
    assert window.windowTitle() == APP_NAME
    assert window.findChild(QLabel, "welcomeTitle").text() == APP_NAME
    details = window.findChild(QLabel, "welcomeDetails").text()
    assert __version__ in details and "PyMuPDF" in details


def test_starts_in_read_mode_with_only_its_tools(window):
    assert window.mode is Mode.READ
    assert visible_tools(window) == {feature.id for feature in features_of(Mode.READ)}


def test_there_are_four_mode_tabs_in_order(window):
    names = [window.mode_tabs.tabText(i) for i in range(window.mode_tabs.count())]
    assert names == ["Leer", "Estudiar", "Rellenar y firmar", "Organizar"]


@pytest.mark.parametrize("mode", MODES)
def test_changing_mode_changes_the_visible_tools(window, qt_app, mode):
    window.set_mode(mode)
    qt_app.processEvents()
    assert visible_tools(window) == {feature.id for feature in features_of(mode)}
    assert window.mode_tabs.currentIndex() == MODES.index(mode)


def test_clicking_a_tab_changes_the_mode(window):
    window.mode_tabs.setCurrentIndex(2)
    assert window.mode is Mode.FILL_SIGN
    assert window.mode_toolbars[Mode.FILL_SIGN].isVisible()
    assert not window.mode_toolbars[Mode.READ].isVisible()


@pytest.mark.parametrize(("number", "mode"), list(enumerate(MODES, start=1)))
def test_each_mode_has_its_keyboard_shortcut(window, number, mode):
    action = window.mode_actions[mode]
    assert action.shortcut().toString() == f"Ctrl+{number}"
    action.trigger()
    assert window.mode is mode


def test_function_finder_has_its_keyboard_shortcut(window):
    assert window.finder_action.shortcut().toString() == "Ctrl+K"


def test_every_tool_has_a_name_a_description_and_a_big_button(window):
    for feature in FEATURES:
        action = window.feature_actions[feature.id]
        assert action.text() and action.toolTip()
        button = window.mode_toolbars[feature.mode].widgetForAction(action)
        assert button.minimumHeight() >= MIN_BUTTON_HEIGHT


def test_a_tool_that_is_not_built_yet_says_so(window):
    window.feature_actions["merge"].trigger()
    assert "Unir" in window.statusBar().currentMessage()
    assert "todavía no está disponible" in window.statusBar().currentMessage()


def test_going_to_a_function_switches_to_its_mode(window):
    merge = next(feature for feature in FEATURES if feature.id == "merge")
    window.go_to_feature(merge)
    assert window.mode is Mode.ORGANIZE
    assert "Unir" in window.statusBar().currentMessage()


def window_colour(qt_app) -> int:
    return qt_app.palette().color(QPalette.ColorRole.Window).lightness()


def test_dark_and_light_themes_change_the_colours(window, qt_app):
    window.set_theme(Theme.DARK)
    assert window_colour(qt_app) < 80
    assert window.theme_actions[Theme.DARK].isChecked()
    window.set_theme(Theme.LIGHT)
    assert window_colour(qt_app) > 200
    assert window.theme_actions[Theme.LIGHT].isChecked()


def test_theme_is_remembered_next_time(qt_app, tmp_path):
    path = tmp_path / "ajustes.json"
    first = MainWindow(Settings(path))
    first.set_theme(Theme.DARK)
    first.close()

    second = MainWindow(Settings(path))
    assert second.theme is Theme.DARK
    assert window_colour(qt_app) < 80
    second.close()


def test_unknown_theme_in_settings_falls_back_to_system(qt_app, settings):
    settings.set("tema", "fucsia")
    window = MainWindow(settings)
    assert window.theme is Theme.SYSTEM
    window.close()


@pytest.mark.parametrize("dark", [False, True])
def test_text_contrast_is_good_in_both_themes(dark):
    from app.ui.theme import build_palette

    def luminance(colour) -> float:
        def channel(value: float) -> float:
            return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(colour.redF())
            + 0.7152 * channel(colour.greenF())
            + 0.0722 * channel(colour.blueF())
        )

    def contrast(first, second) -> float:
        lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
        return (lighter + 0.05) / (darker + 0.05)

    palette = build_palette(dark)
    role = QPalette.ColorRole
    pairs = [
        (role.WindowText, role.Window),
        (role.Text, role.Base),
        (role.ButtonText, role.Button),
        (role.HighlightedText, role.Highlight),
        (role.PlaceholderText, role.Base),
    ]
    for text, background in pairs:
        # 4.5 is the accessibility guideline (WCAG AA) for normal text.
        assert contrast(palette.color(text), palette.color(background)) >= 4.5


def test_just_opening_the_program_writes_no_settings_file(window, settings):
    assert not settings.path.exists()


# ---- compact bars: the menu button, the search box at the top, icons only ----


def test_the_menus_live_behind_the_menu_button(window):
    assert not window.menuBar().isVisible()
    assert window.menu_button.isVisible()
    names = [action.text().replace("&", "") for action in window.main_menu.actions()]
    assert names == ["Archivo", "Editar", "Ver", "Ayuda"]
    assert all(action.menu() is not None for action in window.main_menu.actions())
    assert window.menu_button.accessibleName() and window.menu_button.toolTip()


def test_shortcuts_of_the_hidden_menus_still_work(window, sample, qt_app):
    """An action of a hidden menu bar loses its shortcut unless the window holds it too."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    for action in (window.print_action, window.settings_action, window.full_screen_action):
        assert action in window.actions()
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.activateWindow()
    qt_app.processEvents()
    QTest.keyClick(window.pdf_view, Qt.Key.Key_F11)
    qt_app.processEvents()
    assert window.full_screen
    window.set_full_screen(False)


def test_typing_in_the_top_box_searches_the_document(window, sample, wait_until):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    assert not window.search_panel.isVisible()
    QTest.keyClicks(window.search_box, "articulo 14")
    panel = window.search_panel
    assert panel.isVisible() and panel.box.text() == "articulo 14"
    wait_until(lambda: panel.hits and not panel._searching)
    QTest.keyClick(window.search_box, Qt.Key.Key_Return)
    first = panel.current
    assert first >= 0
    QTest.keyClick(window.search_box, Qt.Key.Key_Down)
    assert panel.current == (first + 1) % len(panel.hits)
    QTest.keyClick(window.search_box, Qt.Key.Key_Up)
    assert panel.current == first
    QTest.keyClick(window.search_box, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert panel.current == (first - 1) % len(panel.hits)
    QTest.keyClick(window.search_box, Qt.Key.Key_Escape)
    assert not panel.isVisible() and window.search_box.text() == ""


def test_the_top_box_and_the_panel_say_the_same(window, sample):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.show_search()
    window.search_panel.box.setText("corona")
    assert window.search_box.text() == "corona"
    # Another document has its own search: the box follows the tab in front.
    assert window.open_document(sample("largo.pdf"))
    assert window.search_box.text() == ""
    window.document_tabs.setCurrentIndex(0)
    assert window.search_box.text() == "corona"


def test_the_top_box_without_a_document_explains_itself(window):
    from PySide6.QtTest import QTest

    QTest.keyClicks(window.search_box, "ley")
    assert "Abre un documento" in window.statusBar().currentMessage()


def test_tools_can_be_shown_as_icons_only(window, settings):
    from PySide6.QtCore import Qt

    from app.ui.main_window import TOOLBAR_SETTING

    bar = window.mode_toolbars[window.mode]
    assert bar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    with_names = bar.sizeHint().height()
    window.set_toolbar_icons_only(True)
    assert all(
        b.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        for b in window.mode_toolbars.values()
    )
    assert bar.sizeHint().height() < with_names
    assert settings.get(TOOLBAR_SETTING) == "iconos"
    for action in bar.actions():
        if not action.isSeparator():
            button = bar.widgetForAction(action)
            assert button.minimumHeight() >= MIN_BUTTON_HEIGHT  # still easy to press
            assert button.minimumWidth() >= MIN_BUTTON_HEIGHT
            assert action.toolTip()  # the name is still there for whoever asks
    again = MainWindow(settings)
    assert again.toolbar_icons_only
    again.deleteLater()
    window.set_toolbar_icons_only(False)
    assert settings.get(TOOLBAR_SETTING) == "nombres"


def test_the_bars_leave_most_of_a_laptop_screen_to_the_document(window, sample, qt_app):
    window.show_problem_dialogs = False
    window.setMinimumHeight(0)
    window.resize(1366, 728)
    assert window.open_document(sample("boe.pdf"))
    qt_app.processEvents()
    taken = window.height() - window.pdf_view.viewport().height()
    assert taken <= 200, f"the bars take {taken} px"
