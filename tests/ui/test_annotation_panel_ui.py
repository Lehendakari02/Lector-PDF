"""Tests for the annotations panel: everything put on the document, by
colours, and a click goes to each one."""

import shutil

import pytest

from app.core.commands import HIGHLIGHT, UNDERLINE
from app.core.drawing import BOX
from app.ui.side_panel import Tab

YELLOW = (1.0, 0.92, 0.23)
GREEN = (0.56, 0.88, 0.42)


@pytest.fixture
def marked(window, sample, tmp_path, wait_until):
    """The BOE with a yellow and a green highlight, an underline, a note and a box."""
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._texts)
    view.markup_colors[HIGHLIGHT] = YELLOW
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    view.markup_colors[HIGHLIGHT] = GREEN
    view.select((0, 20), (0, 30))
    view.mark_selection(HIGHLIGHT)
    view.select((0, 40), (0, 50))
    view.mark_selection(UNDERLINE)
    assert view.put_note(2, 300, 300, "Repasar el artículo 14")
    assert view.draw_shape(BOX, 4, (100, 100), (200, 160))
    wait_until(lambda: not view._changing)
    return view


def panel_of(window, wait_until):
    window.show_side_panel(Tab.ANNOTATIONS)
    panel = window.side_panel.annotations
    wait_until(lambda: len(panel.entries) == 5)
    return panel


def texts(panel) -> list[str]:
    return [panel.list.item(row).text() for row in range(panel.list.count())]


def test_everything_is_listed_in_order_with_its_words(window, marked, wait_until):
    panel = panel_of(window, wait_until)
    assert panel.isVisible()
    rows = texts(panel)
    assert [row.split("\n")[0] for row in rows] == [
        "Pág. 1 · Resaltado",
        "Pág. 1 · Resaltado",
        "Pág. 1 · Subrayado",
        "Pág. 3 · Nota",
        "Pág. 5 · Forma",
    ]
    assert rows[3].endswith("Repasar el artículo 14")
    assert all(len(row.split("\n")) == 2 for row in rows[:3]), "a mark shows its words"


def test_keeping_one_colour_and_one_kind(window, marked, wait_until):
    panel = panel_of(window, wait_until)
    green = next(b for b in panel.color_buttons if b.color == pytest.approx(GREEN, abs=0.01))
    green.click()
    assert [e.kind for e in panel.shown()] == [HIGHLIGHT]
    panel.all_button.click()
    panel.keep_group("notes")
    assert [e.kind for e in panel.shown()] == ["note"]
    panel.keep_color(GREEN)
    assert panel.shown() == [] and panel.stack.currentWidget() is panel.empty


def test_a_click_goes_there_and_picks_it(window, marked, wait_until):
    panel = panel_of(window, wait_until)
    view = window.pdf_view
    item = panel.list.item(4)  # the box on page 5
    panel.list.itemClicked.emit(item)
    wait_until(lambda: view.picked_item() is not None)
    assert view.current_page == 4 and view.picked_item().kind == BOX
    assert view.picked_bar.isVisible()


def test_the_list_follows_the_changes(window, marked, wait_until):
    panel = panel_of(window, wait_until)
    view = window.pdf_view
    view.undo()  # the box goes
    wait_until(lambda: len(panel.entries) == 4)
    assert "Forma" not in "".join(texts(panel))


def test_an_empty_document_says_how_it_fills(window, sample, wait_until):
    window.show_problem_dialogs = False
    assert window.open_document(sample("texto-partido.pdf"))
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    window.show_side_panel(Tab.ANNOTATIONS)
    panel = window.side_panel.annotations
    wait_until(lambda: panel.stack.currentWidget() is panel.empty)
    assert "Aún no hay nada" in panel.empty.text()


def test_the_feature_finder_opens_it(window, marked, wait_until):
    window.feature_actions["annotations"].trigger()
    assert window.side_panel.isVisible() and window.side_panel.tab is Tab.ANNOTATIONS


def test_a_colour_of_ones_own_names_its_marks(window, marked, wait_until, monkeypatch):
    from app.ui import color_menu, color_naming

    panel = panel_of(window, wait_until)
    green = next(b for b in panel.color_buttons if b.color == pytest.approx(GREEN, abs=0.01))
    monkeypatch.setattr(color_menu, "ask_color_name", lambda _parent, _current: "Definiciones")
    green.ask_name()
    assert color_naming.name_of(GREEN) == "Definiciones"
    rows = [row.split("\n")[0] for row in texts(panel)]
    assert rows[:2] == ["Pág. 1 · Resaltado", "Pág. 1 · Resaltado · Definiciones"]
    assert any("Definiciones" in b.accessibleName() for b in panel.color_buttons)
    # Kept for the next time the program starts.
    color_naming.install(window.settings)
    assert color_naming.name_of(GREEN) == "Definiciones"
    # Cancelling changes nothing; an empty name takes it away.
    monkeypatch.setattr(color_menu, "ask_color_name", lambda _parent, _current: None)
    green = next(b for b in panel.color_buttons if b.color == pytest.approx(GREEN, abs=0.01))
    green.ask_name()
    assert color_naming.name_of(GREEN) == "Definiciones"
    color_naming.set_name(GREEN, "")
    assert all("Definiciones" not in row for row in texts(panel))
