"""Many PDFs broken in different ways: the window must survive all of them.

Each file is opened in the real window and its last page is asked for. Either
the document is refused with a message, or every page asked for ends up drawn
or marked as damaged. The program never closes and never hangs.
"""

import random

import pytest

KINDS = ("cut short", "bytes changed", "piece removed", "rubbish inserted")


def _broken_copy(original: bytes, number: int) -> bytes:
    rng = random.Random(1000 + number)  # the same broken files in every run
    data = bytearray(original)
    kind = KINDS[number % len(KINDS)]
    if kind == "cut short":
        return bytes(data[: rng.randrange(100, len(data))])
    if kind == "bytes changed":
        for _ in range(rng.randrange(1, 400)):
            data[rng.randrange(len(data))] = rng.randrange(256)
    elif kind == "piece removed":
        start = rng.randrange(len(data))
        del data[start : start + rng.randrange(1, 50_000)]
    else:
        start = rng.randrange(len(data))
        data[start:start] = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 5000)))
    return bytes(data)


@pytest.mark.parametrize("number", range(16))
def test_the_window_survives_a_broken_pdf(window, sample, tmp_path, wait_until, number):
    window.show_problem_dialogs = False
    file = tmp_path / f"roto-{number}.pdf"
    file.write_bytes(_broken_copy(sample("boe.pdf").read_bytes(), number))

    if window.open_document(file):
        view = window.pdf_view
        assert view.page_count >= 1
        last = view.page_count - 1
        gave_up = []
        view.document_failed.connect(gave_up.append)
        view.scroll_to_page(last)

        def settled() -> bool:
            done = set(view.cached_pages()) | set(view.failed_pages())
            return last in done or bool(gave_up)

        wait_until(settled, 40)
        if window.documents:
            window.close_document()
    assert window.isVisible()
    assert window.documents == []
    # And a good document still opens afterwards.
    assert window.open_document(sample("boe.pdf"))
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
