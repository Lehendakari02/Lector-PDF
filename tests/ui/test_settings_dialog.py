"""Tests for the settings window, the paper tone and the reading mode."""

from PySide6.QtGui import QColor

from app.core.history import RESTORE_SETTING
from app.core.interface_size import SIZE_SETTING
from app.core.settings import Settings
from app.ui import theme
from app.ui.features import FEATURES
from app.ui.main_window import MainWindow
from app.ui.theme import PAPER_SETTING, THEME_SETTING, Paper, Theme


def _choose(box, value) -> None:
    """Pick an entry the way a person does (it tells the window)."""
    box.setCurrentIndex(box.findData(value))
    box.activated.emit(box.currentIndex())


def _paper_colour(window, wait_until) -> QColor:
    """The colour of a blank spot of the first page, as painted on screen."""
    view = window.pdf_view
    wait_until(lambda: 0 in view._cache)
    image = view.viewport().grab().toImage()
    left = view._page_left(0) / view._scale() / image.devicePixelRatio()
    return image.pixelColor(int(left * image.devicePixelRatio()) + 4, 14)


# ---- paper tone ----


def test_paper_is_white_unless_chosen(window):
    assert window.paper is Paper.WHITE
    assert window.paper_actions[Paper.WHITE].isChecked()


def test_sepia_warms_the_page_and_night_darkens_it(window, sample, wait_until):
    window.open_document(sample("boe.pdf"))
    white = _paper_colour(window, wait_until)
    assert white.red() > 250 and white.blue() > 250

    window.set_paper(Paper.SEPIA)
    sepia = _paper_colour(window, wait_until)
    assert sepia.red() > sepia.blue() + 15  # warm
    assert sepia.lightness() > 200  # still light paper

    window.set_paper(Paper.NIGHT)
    night = _paper_colour(window, wait_until)
    assert night.lightness() < 60

    window.set_paper(Paper.WHITE)
    assert _paper_colour(window, wait_until) == white


def test_the_paper_is_remembered(qt_app, tmp_path):
    path = tmp_path / "ajustes.json"
    first = MainWindow(Settings(path))
    first.set_paper(Paper.SEPIA)
    first.close()
    first.deleteLater()
    second = MainWindow(Settings(path))
    assert second.paper is Paper.SEPIA
    assert theme.paper() is Paper.SEPIA
    second.set_paper(Paper.WHITE)
    second.close()
    second.deleteLater()


def test_reading_mode_button_switches_sepia_on_and_off(window):
    feature = next(f for f in FEATURES if f.id == "reading_mode")
    window.run_feature(feature)
    assert window.paper is Paper.SEPIA
    assert window.paper_actions[Paper.SEPIA].isChecked()
    assert "Modo lectura" in window.statusBar().currentMessage()
    window.run_feature(feature)
    assert window.paper is Paper.WHITE


def test_reading_mode_from_night_goes_to_sepia(window):
    window.set_paper(Paper.NIGHT)
    window.toggle_reading_mode()
    assert window.paper is Paper.SEPIA


def test_a_strange_stored_paper_means_white():
    assert Paper.from_setting("verde") is Paper.WHITE
    assert Paper.from_setting(None) is Paper.WHITE


# ---- settings window ----


def test_settings_window_shows_what_is_in_use(window, settings):
    window.set_theme(Theme.DARK)
    window.set_paper(Paper.SEPIA)
    dialog = window.open_settings()
    assert dialog.theme_box.currentData() is Theme.DARK
    assert dialog.paper_box.currentData() is Paper.SEPIA
    assert dialog.size_box.currentData() == 100
    assert dialog.restore_box.isChecked()
    assert not dialog.restart_row.isVisibleTo(dialog)
    dialog.close()


def test_changes_apply_and_are_saved_at_once(window, settings):
    dialog = window.open_settings()
    _choose(dialog.theme_box, Theme.DARK)
    assert window.theme is Theme.DARK
    assert settings.get(THEME_SETTING) == "oscuro"
    assert window.theme_actions[Theme.DARK].isChecked()

    _choose(dialog.paper_box, Paper.NIGHT)
    assert window.paper is Paper.NIGHT
    assert settings.get(PAPER_SETTING) == "noche"

    dialog.restore_box.setChecked(False)
    assert settings.get(RESTORE_SETTING) is False
    assert not window.history.restore_wanted
    dialog.close()


def test_another_size_offers_to_restart(window, settings):
    dialog = window.open_settings()
    _choose(dialog.size_box, 125)
    assert settings.get(SIZE_SETTING) == 125
    assert dialog.restart_row.isVisibleTo(dialog)
    _choose(dialog.size_box, 100)  # back to the size in use: nothing to restart
    assert not dialog.restart_row.isVisibleTo(dialog)
    dialog.close()


def test_restart_now_closes_the_window_and_asks_for_a_restart(window, settings):
    dialog = window.open_settings()
    _choose(dialog.size_box, 150)
    assert not window.restart_wanted
    dialog.restart_button.click()
    assert window.restart_wanted
    assert not window.isVisible()


def test_settings_have_a_menu_entry_and_a_shortcut(window):
    assert window.settings_action.shortcut().toString() == "Ctrl+,"
    assert "justes" in window.settings_action.text()
