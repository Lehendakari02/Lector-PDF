"""Tests for the side panel: thumbnails and outline."""

from app.ui.main_window import SIDE_PANEL_SETTING, MainWindow
from app.ui.side_panel import MAX_PICTURES, Tab


def open_sample(window, sample, name="boe.pdf"):
    window.show_problem_dialogs = False
    assert window.open_document(sample(name))


def test_panel_is_closed_until_asked(window, sample):
    open_sample(window, sample)
    assert not window.side_dock.isVisible()
    window.feature_actions["thumbnails"].trigger()
    assert window.side_dock.isVisible()
    assert window.side_panel.tab is Tab.THUMBNAILS
    assert window.side_panel_action.isChecked()


def test_buttons_switch_and_close_the_panel(window, sample):
    open_sample(window, sample)
    window.feature_actions["thumbnails"].trigger()
    window.feature_actions["outline"].trigger()  # other tab: switches, stays open
    assert window.side_dock.isVisible()
    assert window.side_panel.tab is Tab.OUTLINE
    window.feature_actions["outline"].trigger()  # same tab: closes
    assert not window.side_dock.isVisible()
    window.side_panel_action.trigger()  # F4
    assert window.side_dock.isVisible()
    window.side_panel.close_button.click()
    assert not window.side_dock.isVisible()


def test_panel_needs_a_document(window):
    window.feature_actions["outline"].trigger()
    assert not window.side_dock.isVisible()
    assert "Abre primero" in window.statusBar().currentMessage()


def test_thumbnails_are_drawn_for_the_pages_in_sight(window, sample, wait_until):
    open_sample(window, sample, "largo.pdf")
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    assert thumbnails.count() == 520
    wait_until(lambda: 0 in thumbnails.drawn_pages())
    assert max(thumbnails.drawn_pages()) < 60  # only those near the top, not all 520
    assert not thumbnails.item(0).icon().isNull()


def test_clicking_a_thumbnail_goes_to_the_page(window, sample):
    open_sample(window, sample)
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    thumbnails.itemClicked.emit(thumbnails.item(20))
    assert window.pdf_view.current_page == 20
    assert thumbnails.currentRow() == 20


def test_thumbnails_follow_the_page_being_read(window, sample, wait_until):
    open_sample(window, sample, "largo.pdf")
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    window.pdf_view.scroll_to_page(300)
    assert thumbnails.currentRow() == 300
    wait_until(lambda: 300 in thumbnails.drawn_pages())


def test_thumbnails_turn_with_the_view(window, sample, wait_until):
    open_sample(window, sample)
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    wait_until(lambda: 0 in thumbnails.drawn_pages())
    window.pdf_view.rotate_view()
    assert thumbnails.count() == 39
    assert 0 not in thumbnails.drawn_pages()
    wait_until(lambda: 0 in thumbnails.drawn_pages())
    sizes = thumbnails.item(0).icon().availableSizes()
    assert sizes[0].width() > sizes[0].height()  # lying on its side


def test_old_thumbnails_are_forgotten(window, sample, wait_until, qt_app):
    open_sample(window, sample, "largo.pdf")
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    thumbnails._drawn.update(range(100, 100 + MAX_PICTURES))  # as if many were drawn
    wait_until(lambda: 0 in thumbnails.drawn_pages())
    assert len(thumbnails.drawn_pages()) <= MAX_PICTURES


def test_outline_shows_the_sections(window, sample, wait_until):
    open_sample(window, sample)
    window.show_side_panel(Tab.OUTLINE)
    outline = window.side_panel.outline
    wait_until(lambda: outline.topLevelItemCount() > 0)
    assert window.side_panel.stack.currentWidget() is outline
    root = outline.topLevelItem(0)
    assert root.text(0) == "Constitución Española."
    assert root.isExpanded()  # a single root is opened
    titles = [root.child(i).text(0) for i in range(root.childCount())]
    assert "TÍTULO PRELIMINAR" in titles


def test_clicking_a_section_goes_there(window, sample, wait_until):
    open_sample(window, sample, "largo.pdf")
    window.show_side_panel(Tab.OUTLINE)
    outline = window.side_panel.outline
    wait_until(lambda: outline.topLevelItemCount() > 0)
    item = outline.topLevelItem(2)  # "Tema 3", page 41
    outline.itemClicked.emit(item, 0)
    assert window.pdf_view.current_page == 40
    assert outline.currentItem() is item


def test_outline_follows_the_page_being_read(window, sample, wait_until):
    open_sample(window, sample, "largo.pdf")
    window.show_side_panel(Tab.OUTLINE)
    outline = window.side_panel.outline
    wait_until(lambda: outline.topLevelItemCount() > 0)
    window.pdf_view.scroll_to_page(25)  # inside "Tema 2" (pages 21 to 40)
    assert outline.currentItem().text(0).startswith("Tema 2.")


def test_document_without_outline_says_so(window, sample, wait_until, qt_app):
    open_sample(window, sample, "formulario.pdf")
    window.show_side_panel(Tab.OUTLINE)
    qt_app.processEvents()
    assert window.side_panel.stack.currentWidget() is window.side_panel.no_outline
    assert "no trae índice" in window.side_panel.no_outline.text()


def test_outline_of_the_previous_document_goes_away(window, sample, wait_until):
    open_sample(window, sample)
    window.show_side_panel(Tab.OUTLINE)
    wait_until(lambda: window.side_panel.outline.topLevelItemCount() > 0)
    open_sample(window, sample, "formulario.pdf")
    assert window.side_panel.outline.topLevelItemCount() == 0


def test_panel_comes_back_as_it_was_left(window, sample, settings, qt_app):
    open_sample(window, sample)
    window.show_side_panel(Tab.OUTLINE)
    assert settings.get(SIDE_PANEL_SETTING) == "indice"
    again = MainWindow(settings)
    again.show_problem_dialogs = False
    again.show()
    try:
        assert not again.side_dock.isVisible()  # nothing open yet
        assert again.open_document(sample("boe.pdf"))
        assert again.side_dock.isVisible()
        assert again.side_panel.tab is Tab.OUTLINE
        again.close_side_panel()
        assert settings.get(SIDE_PANEL_SETTING) == ""
    finally:
        again.pdf_view.shutdown()
        again.close()


def test_full_screen_hides_the_panel_and_brings_it_back(window, sample, qt_app):
    open_sample(window, sample)
    window.show_side_panel(Tab.THUMBNAILS)
    window.set_full_screen(True)
    assert not window.side_dock.isVisible()
    window.set_full_screen(False)
    assert window.side_dock.isVisible()
