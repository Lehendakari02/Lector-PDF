"""Check that pages reach the screen pixel for pixel, at the current screen scale.

Run by ``test_sharpness.py`` in a separate program, because the screen scale
(``QT_SCALE_FACTOR``: 1.25 for 125 %, 1.5 for 150 %) can only be set before Qt
starts. Prints the scale and exits with 0 when every pixel matches.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def is_different(view, path: Path) -> bool:
    import pymupdf
    from PySide6.QtGui import QImage

    zoom = view._render_zoom()
    page = view.current_page
    with pymupdf.open(path) as doc:
        pixmap = doc[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    expected = QImage(
        pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888
    )
    shown = view.viewport().grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
    left = view._page_left(page)
    top = view._tops[page] - view._scroll_y()
    first_row = max(0, -top)
    rows = min(expected.height(), shown.height() - top) - first_row
    assert rows * expected.width() > 100_000, "the page is not on screen"
    on_screen = shown.copy(left, top + first_row, expected.width(), rows)
    return on_screen != expected.copy(0, first_row, expected.width(), rows)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.document import PdfDocument
    from app.ui.pdf_view import PdfView

    path = Path(sys.argv[1])
    app = QApplication([])
    view = PdfView()
    view.resize(900, 700)
    view.show()
    view.set_document(PdfDocument(path))
    view.set_zoom(1.0)  # 100 %: the usual case
    view.scroll_to_page(1)
    deadline = time.monotonic() + 30
    try:
        while view.cached_pages().get(view.current_page) != view._render_zoom():
            if time.monotonic() > deadline:
                print("timed out")
                return 2
            app.processEvents()
            time.sleep(0.005)
        app.processEvents()
        different = is_different(view, path)
        print(f"scale={view.devicePixelRatioF()} zoom={view._render_zoom()} exact={not different}")
        return 1 if different else 0
    finally:
        view.shutdown()


if __name__ == "__main__":
    sys.exit(main())
