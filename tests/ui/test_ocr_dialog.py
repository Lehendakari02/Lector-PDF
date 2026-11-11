"""Tests for the "recognise text" proof of concept in the window."""

from app.core.ocr import recognize_file_page
from app.main import CHECK_OCR_FLAG, EXIT_OCR_FAILED, main
from app.ui.ocr_dialog import OcrResultDialog


def test_recognising_needs_an_open_document(window):
    window.feature_actions["ocr"].trigger()
    assert "Abre un documento" in window.statusBar().currentMessage()


def test_window_recognises_the_page_on_screen_without_freezing(window, sample, wait_until):
    window.show_problem_dialogs = False
    window.open_document(sample("escaneado.pdf"))
    window.pdf_view.scroll_to_page(2)
    window.feature_actions["ocr"].trigger()
    assert "Reconociendo el texto de la página 3" in window.statusBar().currentMessage()
    window.feature_actions["ocr"].trigger()  # a second click while working does nothing
    wait_until(lambda: window.last_ocr is not None, seconds=120)
    assert window.last_ocr.page == 2
    assert "Artículo 11" in window.last_ocr.text
    assert "Texto reconocido" in window.statusBar().currentMessage()


def test_closing_the_window_stops_a_recognition_in_progress(qt_app, settings, sample):
    from app.ui.main_window import MainWindow

    window = MainWindow(settings)
    window.show_problem_dialogs = False
    window.show()
    window.open_document(sample("escaneado.pdf"))
    window.recognize_current_page()
    process = window._ocr_job._process
    window.close()
    assert not process.is_alive()


def test_result_dialog_shows_and_copies_the_text(qt_app, sample):
    result = recognize_file_page(sample("escaneado.pdf"), 0)
    dialog = OcrResultDialog(result)
    assert "Página 1" in dialog.summary.text()
    assert "palabras" in dialog.summary.text()
    assert "Artículo 1" in dialog.text.toPlainText()
    assert dialog.text.isReadOnly()
    dialog.copy_button.click()
    assert "Artículo 1" in qt_app.clipboard().text()


def test_check_ocr_option(sample):
    start = ["lector-pdf", CHECK_OCR_FLAG]
    assert main([*start, str(sample("escaneado.pdf")), "Artículo"]) == 0
    assert main([*start, str(sample("escaneado.pdf")), "Xilófono"]) == EXIT_OCR_FAILED
    assert main([*start, str(sample("escaneado.pdf"))]) == EXIT_OCR_FAILED
