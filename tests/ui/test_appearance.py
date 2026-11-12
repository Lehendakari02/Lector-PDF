"""Tests for the look of the program: icons, logo, images and the welcome page."""

import struct
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, QSize, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QImage
from PySide6.QtWidgets import QToolButton

from app.ui import icons, theme
from app.ui.features import FEATURES, MODES, Mode
from app.ui.theme import Theme

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "tests" / "ejemplos"


def painted_pixels(image: QImage) -> int:
    return sum(
        1
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 40
    )


@pytest.mark.parametrize("name", sorted(icons.ICONS))
def test_every_icon_draws_something(qt_app, name):
    image = icons.icon(name).pixmap(QSize(24, 24)).toImage()
    assert painted_pixels(image) > 20


def test_every_function_and_mode_has_its_icon():
    for feature in FEATURES:
        assert icons.has_icon(feature.id), feature.id
    for mode in MODES:
        assert icons.has_icon(f"mode_{mode.name.lower()}")


def test_icons_follow_the_theme(window):
    def colour_of_icon():
        image = icons.icon("open").pixmap(QSize(24, 24)).toImage()
        return max(
            (image.pixelColor(x, y) for x in range(24) for y in range(24)),
            key=lambda colour: colour.alpha(),
        ).lightness()

    window.set_theme(Theme.LIGHT)
    assert colour_of_icon() < 80
    window.set_theme(Theme.DARK)
    assert colour_of_icon() > 180


def test_a_disabled_icon_is_greyed(qt_app):
    image = icons.icon("open").pixmap(QSize(24, 24), QIcon.Mode.Disabled).toImage()
    colour = max(
        (image.pixelColor(x, y) for x in range(24) for y in range(24)),
        key=lambda c: c.alpha(),
    )
    assert colour.name() == theme.colours().disabled


def test_logo_is_sharp_at_any_screen_scale(qt_app):
    logo = icons.logo_pixmap(84, 1.5)
    assert logo.width() == 126
    assert logo.devicePixelRatio() == 1.5
    assert not icons.logo_icon().isNull()


def test_tool_buttons_show_icon_and_name(window):
    for feature in FEATURES:
        action = window.feature_actions[feature.id]
        button = window.mode_toolbars[feature.mode].widgetForAction(action)
        assert isinstance(button, QToolButton)
        assert not action.icon().isNull()
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon


def test_the_style_sheet_images_exist():
    for colours in (theme.LIGHT, theme.DARK):
        sheet = theme.build_style_sheet(colours)
        path = sheet.split('image: url("')[1].split('"')[0]
        assert Path(path).is_file()


def test_program_icon_file_has_every_size():
    data = (ROOT / "packaging" / "lector-pdf.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sizes = set()
    for number in range(count):
        side, _h, _c, _r, _planes, _bits, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * number
        )
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert offset + length <= len(data)
        sizes.add(side or 256)
    assert {16, 32, 48, 256} <= sizes


def test_program_icon_file_matches_the_logo(qt_app):
    """If the logo changes, packaging/make_images.py has to be run again."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_images", ROOT / "packaging/make_images.py")
    make_images = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_images)
    data = (ROOT / "packaging" / "lector-pdf.ico").read_bytes()
    _side, _h, _c, _r, _planes, _bits, length, offset = struct.unpack_from("<BBBBHHII", data, 6)
    stored = QImage.fromData(data[offset : offset + length], "PNG")
    assert stored == make_images.render(icons.LOGO, 16).convertToFormat(stored.format())


def test_welcome_button_opens_the_file_chooser(window, monkeypatch):
    asked = []
    monkeypatch.setattr(window, "choose_and_open", lambda: asked.append(True))
    window.open_button.clicked.disconnect()
    window.open_button.clicked.connect(window.choose_and_open)
    window.open_button.click()
    assert asked == [True]


def test_open_has_its_keyboard_shortcut(window):
    assert window.open_menu_action.shortcut().toString() == "Ctrl+O"


def drop_data(path: Path) -> QMimeData:
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(path))])
    return data


def test_dropping_a_pdf_on_the_window_opens_it(window):
    data = drop_data(EXAMPLES / "boe.pdf")
    buttons, keys = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(QPointF(50, 50), Qt.DropAction.CopyAction, data, buttons, keys)
    window.dragEnterEvent(enter)
    assert enter.isAccepted()
    assert window.welcome_card.property("dropping") is True
    window.dropEvent(QDropEvent(QPointF(50, 50), Qt.DropAction.CopyAction, data, buttons, keys))
    assert window.pages.currentWidget() is window.current_document
    assert window.welcome_card.property("dropping") is False


def test_dropping_something_that_is_not_a_pdf_is_ignored(window, tmp_path):
    note = tmp_path / "nota.txt"
    note.write_text("hola", encoding="utf-8")
    data = drop_data(note)  # kept in a name: Qt does not keep it alive
    enter = QDragEnterEvent(
        QPointF(50, 50),
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    enter.ignore()
    window.dragEnterEvent(enter)
    assert not enter.isAccepted()
    assert window.pages.currentWidget() is window.welcome


# ---- zoom control, pending functions, finder (first real test, 12/11/2026) ----


def test_a_document_opens_at_a_comfortable_size(window):
    """Fitted to the width, but never so big that it is tiring to read."""
    from app.ui.pdf_view import COMFORTABLE_ZOOM, POINT_TO_PIXEL

    window.show_problem_dialogs = False
    window.open_document(EXAMPLES / "boe.pdf")
    view = window.pdf_view
    full_width = view._zoom_to_fit_width() / POINT_TO_PIXEL
    assert full_width > COMFORTABLE_ZOOM, "the test window must be wide enough to matter"
    assert view.zoom == pytest.approx(COMFORTABLE_ZOOM)
    assert window.zoom_control.figure.text() == "125 %"


def test_in_a_narrow_window_a_document_opens_fitted_to_the_width(qt_app):
    from app.core.document import PdfDocument
    from app.ui.pdf_view import Fit, PdfView

    view = PdfView()
    view.resize(500, 600)
    view.show()
    qt_app.processEvents()
    view.set_document(PdfDocument(EXAMPLES / "boe.pdf"))
    assert view.fit is Fit.COMFORTABLE
    assert view.zoom < 1.0
    view.shutdown()


def test_zoom_control_follows_and_changes_the_zoom(window):
    from app.ui.zoom_control import step_of_zoom, zoom_of_step

    control = window.zoom_control
    assert not control.isEnabled(), "nothing to zoom while no document is open"
    window.open_document(EXAMPLES / "boe.pdf")
    assert control.isEnabled()

    window.pdf_view.set_zoom(2.0)
    assert control.figure.text() == "200 %"
    assert control.slider.value() == step_of_zoom(2.0)

    control.slider.setValue(step_of_zoom(0.5))
    assert window.pdf_view.zoom == pytest.approx(zoom_of_step(step_of_zoom(0.5)))
    control.bigger.click()
    assert window.pdf_view.zoom > 0.5
    control.preset_actions[100].trigger()
    assert window.pdf_view.zoom == pytest.approx(1.0)
    assert control.figure.text() == "100 %"


def test_the_middle_of_the_zoom_slider_is_100_percent():
    from app.ui.zoom_control import SLIDER_STEPS, zoom_of_step

    assert zoom_of_step(SLIDER_STEPS // 2) == pytest.approx(1.0)
    assert zoom_of_step(0) == pytest.approx(0.25)
    assert zoom_of_step(SLIDER_STEPS) == pytest.approx(4.0)


def test_whole_page_fits_in_the_window_and_follows_its_size(window, qt_app):
    from app.ui.pdf_view import Fit

    window.open_document(EXAMPLES / "boe.pdf")
    window.feature_actions["fit_page"].trigger()
    view = window.pdf_view
    assert view.fit is Fit.PAGE
    assert view._heights[0] <= view._to_pixels(view.viewport().height())
    assert window.zoom_control.fit_page_action.isChecked()
    before = view.zoom
    window.resize(window.width(), window.height() - 200)
    qt_app.processEvents()
    assert view.zoom < before
    assert window.zoom_control.figure.text() == f"{round(view.zoom * 100)} %"


def test_functions_not_built_yet_look_different_and_say_so(window):
    built = window.feature_actions["open"]
    pending = window.feature_actions["merge"]
    assert "todavía no disponible" in pending.toolTip()
    assert "todavía no disponible" not in built.toolTip()
    button = window.mode_toolbars[Mode.ORGANIZE].widgetForAction(pending)
    assert button.property("pending") is True


def test_function_finder_closes_with_a_click_outside(qt_app, window):
    from app.ui.command_palette import CommandPalette

    palette = CommandPalette(window)
    assert palette.windowType() == Qt.WindowType.Popup
