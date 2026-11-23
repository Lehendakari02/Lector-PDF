"""Tests for pages seen very close: drawn by pieces ("tiles")."""

import pymupdf
import pytest

from app.core.document import PdfDocument
from app.core.render_service import render_page
from app.ui import pdf_view
from app.ui.pdf_view import PdfView


@pytest.fixture
def view(qt_app):
    made = PdfView()
    made.resize(800, 600)
    made.show()
    qt_app.processEvents()
    yield made
    made.shutdown()
    made.close()


def close_up(view, sample, wait_until, zoom=8.0, name="boe.pdf"):
    view.set_document(PdfDocument(sample(name)))
    wait_until(lambda: view.current_page in view.cached_pages())
    view.set_zoom(zoom)
    page = view.current_page
    wait_until(lambda: view.cached_pages().get(page) == view._page_zoom(page))
    wait_until(lambda: not view._waiting_tiles(page))
    return page


def test_a_page_seen_very_close_is_drawn_by_pieces(view, sample, wait_until):
    page = close_up(view, sample, wait_until)
    assert view._tiled(page)
    whole = view._widths[page] * view._heights[page]
    assert whole > pdf_view.TILES_FROM_PIXELS
    # The whole page is drawn light; only the pieces near the window are sharp.
    zoom = view.cached_pages()[page]
    assert zoom < view._render_zoom()
    drawn = sum(tile[1].width() * tile[1].height() for tile in view._tiles.values())
    assert drawn < whole / 3
    assert view._tile_bytes <= pdf_view.TILE_CACHE_BYTES


def test_the_pieces_are_the_same_as_the_whole_page(view, sample, wait_until):
    """No seams and nothing out of place: each piece matches the page drawn whole."""
    page = close_up(view, sample, wait_until, zoom=4.0)
    zoom = view._render_zoom()
    with pymupdf.open(sample("boe.pdf")) as doc:
        whole = render_page(doc, page, zoom)
    for (_page, _column, _row), (_zoom, image, left, top, _edition) in view._tiles.items():
        for y in range(0, image.height(), 97):
            for x in range(0, image.width(), 89):
                offset = (top + y) * whole.stride + (left + x) * 3
                expected = tuple(whole.samples[offset : offset + 3])
                colour = image.pixelColor(x, y)
                assert (colour.red(), colour.green(), colour.blue()) == expected


def test_scrolling_very_close_asks_only_for_the_new_pieces(view, sample, wait_until, qt_app):
    page = close_up(view, sample, wait_until)
    before = set(view._tiles)
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 600)
    qt_app.processEvents()
    asked = {
        (r.page, r.tile[0] // pdf_view.TILE_SIZE, r.tile[1] // pdf_view.TILE_SIZE)
        for r in view._wanted
        if r.tile is not None
    }
    assert not asked & before  # those already drawn are not drawn again
    wait_until(lambda: not view._waiting_tiles(page))


def test_a_change_on_the_page_draws_its_pieces_again(view, sample, wait_until):
    from app.core import notes

    page = close_up(view, sample, wait_until, zoom=4.0)
    old = {key: tile[4] for key, tile in view._tiles.items()}
    assert view._do(notes.new_text_box(page, (60, 80), "de cerca"))
    wait_until(lambda: view._editions.get(page, 0) > 0)
    wait_until(lambda: not view._waiting_tiles(page) and page not in view._stale)
    for key in view._tiles_in_sight(page):
        assert view._tiles[(page, *key)][4] == view._editions[page] != old.get((page, *key))


def test_turning_or_closing_forgets_the_pieces(view, sample, wait_until):
    close_up(view, sample, wait_until, zoom=4.0)
    assert view.tile_count()
    view.set_rotation(90)
    assert view.tile_count() == 0
    page = view.current_page
    wait_until(lambda: not view._waiting_tiles(page))
    view.close_document()
    assert view.tile_count() == 0 and view._tile_bytes == 0


def test_normal_zoom_draws_whole_pages(view, sample, wait_until):
    view.set_document(PdfDocument(sample("boe.pdf")))
    wait_until(lambda: view.current_page in view.cached_pages())
    assert not view._tiled(view.current_page)
    assert view.cached_pages()[view.current_page] == view._render_zoom()
    assert view.tile_count() == 0
