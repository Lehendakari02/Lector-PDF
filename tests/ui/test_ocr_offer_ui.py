"""Tests for the offer to recognise the text of a scanned document, made
without interrupting: a strip over the pages."""

import shutil

import pytest

from app.core import ocr
from app.ui.settings_dialog import SettingsDialog


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="escaneado.pdf", target=None):
        path = target or tmp_path / name
        if not path.exists():
            shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: view.page_count and 0 in view.cached_pages())
        return view, path

    return open_it


def looked_at(window, wait_until) -> None:
    """Wait until the helper has looked at every page."""
    wait_until(lambda: window.pdf_view.scanned_known, seconds=30)


def test_a_scanned_document_gets_the_offer(window, opened, wait_until):
    view, _ = opened()
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))
    assert view.scanned_pages == [0, 1, 2]
    assert "escaneado" in banner.message.text()
    assert banner.recognize_button.text() == "Reconocer texto"


def test_a_document_with_text_gets_no_offer(window, opened, wait_until):
    view, _ = opened("boe.pdf")
    looked_at(window, wait_until)
    assert view.scanned_pages == []
    assert not window.current_document.ocr_banner.isVisibleTo(window)


def test_ahora_no_hides_it_and_it_comes_back_next_time(window, opened, wait_until):
    _, path = opened()
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))
    banner.later_button.click()
    assert not banner.isVisibleTo(window)
    window.close_document()
    opened(target=path)
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))


def test_not_again_for_this_document(window, opened, wait_until, settings, sample, tmp_path):
    _, path = opened()
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))
    banner.never_button.click()
    assert ocr.declined(settings, path)
    assert "no te lo volveré a ofrecer" in window.statusBar().currentMessage().lower()
    window.close_document()
    opened(target=path)
    looked_at(window, wait_until)
    assert not window.current_document.ocr_banner.isVisibleTo(window)
    other = tmp_path / "otro.pdf"
    shutil.copy(sample("escaneado.pdf"), other)
    opened(target=other)
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))  # other documents still get it


def test_it_can_be_turned_off_in_the_settings(window, opened, wait_until, settings):
    dialog = SettingsDialog(window)
    assert dialog.ocr_offer_box.isChecked(), "offered unless the user says otherwise"
    dialog.ocr_offer_box.setChecked(False)
    dialog.close()
    assert not ocr.offer_wanted(settings)
    opened()
    looked_at(window, wait_until)
    assert not window.current_document.ocr_banner.isVisibleTo(window)


def test_reconocer_texto_reads_the_whole_document(window, opened, wait_until):
    view, _ = opened()
    banner = window.current_document.ocr_banner
    wait_until(lambda: banner.isVisibleTo(window))
    banner.recognize_button.click()
    assert window.current_document.text_recognition is not None
    assert banner.isVisibleTo(window) and banner.working, "it shows how far it has got"
    assert banner.cancel_button.isVisibleTo(window)
    assert not banner.recognize_button.isVisibleTo(window)
    wait_until(lambda: window.current_document.text_recognition is None, seconds=120)
    assert not banner.isVisibleTo(window)
    assert "Texto reconocido en 3 páginas" in window.statusBar().currentMessage()
    wait_until(lambda: view.modified and not view._changing)
