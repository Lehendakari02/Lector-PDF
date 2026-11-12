"""Tests for drawing pages in the helper process."""

import threading
import time

import pymupdf
import pytest

from app.core import render_service
from app.core.render_service import RenderedPage, RenderRequest, RenderService, render_page

WAIT_SECONDS = 30  # generous: starting a process on a busy test machine is slow


class Collector:
    """Receives what the service delivers and lets a test wait for it."""

    def __init__(self):
        self.pages: list[RenderedPage] = []
        self.thumbnails: list[RenderedPage] = []
        self.outlines: list[list] = []
        self.page_failures: list[tuple[int, float, str]] = []
        self.open_failures: list[str] = []
        self.crashes = 0
        self._changed = threading.Condition()
        self.service = RenderService(
            on_page=lambda page: self._add(self.pages, page),
            on_page_failed=lambda *failure: self._add(self.page_failures, failure),
            on_open_failed=lambda message: self._add(self.open_failures, message),
            on_crashed=self._crashed,
            on_outline=lambda entries: self._add(self.outlines, entries),
            on_thumbnail=lambda page: self._add(self.thumbnails, page),
        )

    def _add(self, where, item):
        with self._changed:
            where.append(item)
            self._changed.notify_all()

    def _crashed(self):
        with self._changed:
            self.crashes += 1
            self._changed.notify_all()

    def wait(self, condition):
        with self._changed:
            assert self._changed.wait_for(condition, WAIT_SECONDS), "timed out"


@pytest.fixture
def collector():
    made = Collector()
    yield made
    made.service.shutdown()


def test_render_page_gives_rgb_pixels_at_the_asked_size(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        result = render_page(doc, 0, 2.0)
        assert result.width == round(doc[0].rect.width * 2)
        assert result.height == round(doc[0].rect.height * 2)
    assert result.stride == result.width * 3
    assert len(result.samples) == result.stride * result.height
    assert result.page == 0


def test_render_page_never_makes_a_gigantic_image(sample, monkeypatch):
    monkeypatch.setattr(render_service, "MAX_PIXELS_PER_PAGE", 100_000)
    with pymupdf.open(sample("boe.pdf")) as doc:
        result = render_page(doc, 0, 4.0)
    assert result.width * result.height <= 101_000
    assert result.zoom < 4.0


def test_helper_draws_the_wanted_pages_in_order(collector, sample):
    collector.service.open(sample("boe.pdf"))
    collector.service.want([RenderRequest(2, 1.0), RenderRequest(0, 1.0), RenderRequest(5, 1.5)])
    collector.wait(lambda: len(collector.pages) == 3)
    assert [(page.page, page.zoom) for page in collector.pages] == [(2, 1.0), (0, 1.0), (5, 1.5)]
    with pymupdf.open(sample("boe.pdf")) as doc:
        direct = render_page(doc, 2, 1.0)
    assert collector.pages[0].samples == direct.samples


def test_the_helper_is_another_process(collector, sample):
    import os

    collector.service.open(sample("boe.pdf"))
    assert collector.service.is_running()
    assert collector.service.process_id not in (None, os.getpid())


def test_a_new_list_replaces_the_old_one(collector, sample):
    collector.service.open(sample("largo.pdf"))
    # Both lists are sent before the helper has even started: only the newest counts.
    collector.service.want([RenderRequest(page, 2.0) for page in range(100, 300)])
    collector.service.want([RenderRequest(7, 1.0)])
    collector.wait(lambda: any(page.page == 7 for page in collector.pages))
    time.sleep(0.3)
    assert len(collector.pages) < 50, "pages nobody wants any more were still drawn"


def test_results_of_a_closed_document_are_dropped(collector, sample):
    collector.service.open(sample("largo.pdf"))
    collector.service.want([RenderRequest(page, 1.0) for page in range(50)])
    collector.service.open(sample("escaneado.pdf"))
    collector.service.want([RenderRequest(0, 0.5)])
    collector.wait(lambda: any(page.zoom == 0.5 for page in collector.pages))
    with pymupdf.open(sample("escaneado.pdf")) as doc:
        expected = render_page(doc, 0, 0.5)
    newest = collector.pages[-1]
    assert (newest.width, newest.height) == (expected.width, expected.height)


def test_a_file_that_is_not_a_pdf_reports_open_failed(collector, tmp_path):
    bad = tmp_path / "roto.pdf"
    bad.write_bytes(b"this is not a PDF")
    collector.service.open(bad)
    collector.wait(lambda: collector.open_failures)
    assert collector.service.is_running(), "a bad file must not kill the helper"


def test_password_protected_document(collector, sample):
    collector.service.open(sample("con-contrasena.pdf"))
    collector.wait(lambda: collector.open_failures)
    collector.service.open(sample("con-contrasena.pdf"), password="lector")
    collector.service.want([RenderRequest(0, 1.0)])
    collector.wait(lambda: collector.pages)


def test_a_page_that_does_not_exist_reports_page_failed(collector, sample):
    collector.service.open(sample("escaneado.pdf"))
    collector.service.want([RenderRequest(999, 1.0), RenderRequest(0, 0.5)])
    collector.wait(lambda: collector.page_failures and collector.pages)
    assert collector.page_failures[0][0] == 999


def test_helper_is_started_again_after_a_crash(collector, sample):
    collector.service.open(sample("boe.pdf"))
    collector.service.want([RenderRequest(0, 1.0)])
    collector.wait(lambda: collector.pages)
    first_helper = collector.service.process_id

    collector.service._process.kill()
    collector.wait(lambda: collector.crashes == 1)
    assert collector.service.restarts == 1

    collector.service.want([RenderRequest(1, 1.0)])
    collector.wait(lambda: any(page.page == 1 for page in collector.pages))
    assert collector.service.process_id != first_helper


def test_gives_up_when_a_document_keeps_crashing_the_helper(collector, sample):
    collector.service.open(sample("boe.pdf"))
    for crash in range(1, render_service.MAX_CRASHES_PER_DOCUMENT + 1):
        collector.service.want([RenderRequest(0, 1.0)])
        assert collector.service.is_running()
        collector.service._process.kill()
        collector.wait(lambda crash=crash: collector.service.restarts == crash)
    collector.wait(lambda: collector.open_failures)
    collector.service.want([RenderRequest(0, 1.0)])
    assert not collector.service.is_running(), "it must stop restarting"

    # Another document gets a fresh start.
    collector.service.open(sample("escaneado.pdf"))
    assert collector.service.is_running()


def test_shutdown_stops_the_helper_and_can_be_repeated(sample):
    collector = Collector()
    collector.service.open(sample("boe.pdf"))
    process = collector.service._process
    collector.service.shutdown()
    collector.service.shutdown()
    assert not process.is_alive()
    collector.service.want([RenderRequest(0, 1.0)])
    assert not collector.service.is_running(), "nothing starts again after shutdown"


def test_drawing_does_not_hold_up_the_main_thread(collector, sample):
    """The reason for the helper process: the window must keep moving."""
    collector.service.open(sample("escaneado.pdf"))
    collector.service.want([RenderRequest(0, 0.5)])
    collector.wait(lambda: collector.pages)  # helper is up
    collector.pages.clear()

    collector.service.want([RenderRequest(page % 3, 3.0 + page / 100) for page in range(12)])
    longest_gap, last = 0.0, time.perf_counter()
    while len(collector.pages) < 12:
        time.sleep(0.001)  # stands in for the window handling the mouse
        now = time.perf_counter()
        longest_gap, last = max(longest_gap, now - last), now
        assert now - last < WAIT_SECONDS
    # Measured: about 10 ms here, 80 ms and more when drawing in a thread.
    # The limit is loose because test machines are shared and noisy.
    assert longest_gap < 0.2, f"main thread stalled for {longest_gap * 1000:.0f} ms"


# ---- searching in the helper ------------------------------------------------


class SearchCollector(Collector):
    def __init__(self):
        super().__init__()
        self.hits = []
        self.finished: list[tuple[int, bool]] = []
        self.service._on_hits = lambda search_id, hits: self._add(self.hits, (search_id, hits))
        self.service._on_search_done = lambda search_id, too_many: self._add(
            self.finished, (search_id, too_many)
        )

    def all_hits(self, search_id):
        return [hit for number, hits in self.hits if number == search_id for hit in hits]


@pytest.fixture
def searcher():
    made = SearchCollector()
    yield made
    made.service.shutdown()


def test_helper_searches_the_whole_document(searcher, sample):
    searcher.service.open(sample("boe.pdf"))
    search_id = searcher.service.search("derecho a la educacion")
    searcher.wait(lambda: searcher.finished)
    assert searcher.finished == [(search_id, False)]
    found = searcher.all_hits(search_id)
    assert [(hit.page, hit.match) for hit in found] == [(7, "derecho a la educación")]


def test_helper_search_respects_the_options(searcher, sample):
    from app.core.search import SearchOptions

    searcher.service.open(sample("texto-partido.pdf"))
    plain = searcher.service.search("año")
    searcher.wait(lambda: len(searcher.finished) == 1)
    whole = searcher.service.search("año", SearchOptions(whole_word=True))
    searcher.wait(lambda: len(searcher.finished) == 2)
    assert len(searcher.all_hits(plain)) == 4  # includes "españoles"
    assert len(searcher.all_hits(whole)) == 3


def test_a_new_search_replaces_the_one_running(searcher, sample):
    searcher.service.open(sample("largo.pdf"))
    old = searcher.service.search("articulo")
    new = searcher.service.search("zzzz")
    searcher.wait(lambda: searcher.finished)
    assert searcher.finished == [(new, False)]
    assert searcher.all_hits(old) == []


def test_search_stops_when_there_are_too_many_results(searcher, sample, monkeypatch):
    searcher.service.open(sample("largo.pdf"))
    search_id = searcher.service.search("a")
    searcher.wait(lambda: searcher.finished)
    assert searcher.finished == [(search_id, True)]
    assert len(searcher.all_hits(search_id)) == render_service.MAX_SEARCH_HITS


def test_pages_are_still_drawn_while_searching(searcher, sample):
    searcher.service.open(sample("largo.pdf"))
    searcher.service.search("articulo")
    searcher.service.want([RenderRequest(400, 1.0)])
    searcher.wait(lambda: searcher.pages)
    assert not searcher.finished, "the page must not wait for the search to end"
    searcher.wait(lambda: searcher.finished)


def test_cancelled_search_delivers_nothing_more(searcher, sample):
    searcher.service.open(sample("largo.pdf"))
    searcher.service.search("articulo")
    searcher.service.cancel_search()
    searcher.service.want([RenderRequest(0, 1.0)])
    searcher.wait(lambda: searcher.pages)
    time.sleep(0.2)
    assert searcher.hits == [] and searcher.finished == []


def test_search_without_document_does_nothing(searcher):
    searcher.service.search("algo")
    assert not searcher.service.is_running()


def test_a_search_cut_short_by_a_crash_still_ends(searcher, sample):
    searcher.service.open(sample("largo.pdf"))
    searcher.service.want([RenderRequest(0, 1.0)])
    searcher.wait(lambda: searcher.pages)
    search_id = searcher.service.search("a b c d e f g que no existe")
    searcher.service._process.kill()
    searcher.wait(lambda: searcher.finished)
    assert searcher.finished[-1][0] == search_id


def test_render_page_can_turn_the_page(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        upright = render_page(doc, 0, 1.0)
        sideways = render_page(doc, 0, 1.0, rotation=90)
        upside_down = render_page(doc, 0, 1.0, rotation=180)
    assert (sideways.width, sideways.height) == (upright.height, upright.width)
    assert (upside_down.width, upside_down.height) == (upright.width, upright.height)
    assert sideways.rotation == 90
    assert upside_down.samples != upright.samples


def test_helper_draws_turned_pages(collector, sample):
    collector.service.open(sample("boe.pdf"))
    collector.service.want([RenderRequest(0, 1.0, 270)])
    collector.wait(lambda: len(collector.pages) == 1)
    page = collector.pages[0]
    assert page.rotation == 270
    assert page.width > page.height


def test_helper_sends_the_outline_when_it_opens_a_document(collector, sample):
    collector.service.open(sample("boe.pdf"))
    collector.wait(lambda: len(collector.outlines) == 1)
    outline = collector.outlines[0]
    assert len(outline) > 100
    assert outline[0].title == "Constitución Española."
    assert outline[0].page == 0


def test_a_document_without_outline_sends_an_empty_one(collector, sample):
    collector.service.open(sample("formulario.pdf"))
    collector.wait(lambda: len(collector.outlines) == 1)
    assert collector.outlines[0] == []


def test_small_pictures_wait_for_the_pages_being_read(collector, sample):
    collector.service.open(sample("largo.pdf"))
    collector.service.want_thumbnails([RenderRequest(page, 0.2) for page in range(30)])
    collector.service.want([RenderRequest(100, 1.0)])
    collector.wait(lambda: len(collector.thumbnails) == 30 and len(collector.pages) == 1)
    assert [picture.page for picture in collector.thumbnails] == list(range(30))
    assert collector.thumbnails[0].width < 200
    assert collector.pages[0].page == 100


def test_a_new_list_of_small_pictures_replaces_the_old_one(collector, sample):
    collector.service.open(sample("largo.pdf"))
    collector.service.want_thumbnails([RenderRequest(page, 0.2) for page in range(400)])
    collector.service.want_thumbnails([RenderRequest(500, 0.2)])
    collector.wait(lambda: any(picture.page == 500 for picture in collector.thumbnails))
    assert len(collector.thumbnails) < 400
