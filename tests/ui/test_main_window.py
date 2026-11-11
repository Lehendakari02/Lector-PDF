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
    assert __version__ in window.findChild(QLabel, "placeholderTitle").text()
    assert "PyMuPDF" in window.findChild(QLabel, "placeholderVersions").text()


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
