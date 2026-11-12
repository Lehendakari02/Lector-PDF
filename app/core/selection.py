"""Selecting text on a page with the mouse and copying it.

A selection is a stretch of the letters of a page, in reading order, between
two "carets". A caret is a position between two letters: caret 0 is before the
first letter of the page and caret ``len(text)`` after the last one.
"""

from app.core.search import _LINE_END_HYPHENS, _SOFT_HYPHEN, PageText, Rect, _line_rects

# How far from a line (in points) the pointer still counts as being on it.
NEAR_TEXT_POINTS = 4.0


def _line_boxes(text: PageText) -> list[Rect]:
    """The rectangle around every line of the page."""
    boxes = []
    values = text.boxes
    for start, stop in text.line_spans():
        xs0, ys0 = values[4 * start : 4 * stop : 4], values[4 * start + 1 : 4 * stop : 4]
        xs1, ys1 = values[4 * start + 2 : 4 * stop : 4], values[4 * start + 3 : 4 * stop : 4]
        boxes.append((min(xs0), min(ys0), max(xs1), max(ys1)))
    return boxes


def _nearest_line(boxes: list[Rect], x: float, y: float) -> int:
    """The line a point refers to: one at its height if there is any (the nearest
    sideways, which matters with columns); otherwise the nearest above or below."""

    def sideways(box: Rect) -> float:
        return max(box[0] - x, 0.0, x - box[2])

    def up_or_down(box: Rect) -> float:
        return max(box[1] - y, 0.0, y - box[3])

    return min(range(len(boxes)), key=lambda n: (up_or_down(boxes[n]), sideways(boxes[n])))


def caret_at(text: PageText, x: float, y: float) -> int | None:
    """The caret nearest to a point of the page (in points). None on a page without text."""
    if not len(text):
        return None
    boxes = _line_boxes(text)
    nearest = _nearest_line(boxes, x, y)
    start, stop = text.line_spans()[nearest]
    caret = start
    for letter in range(start, stop):
        middle = (text.boxes[4 * letter] + text.boxes[4 * letter + 2]) / 2
        if x < middle:
            break
        caret = letter + 1
    return caret


def is_on_text(text: PageText, x: float, y: float) -> bool:
    """True if the point is on a line of text, or very close to one."""
    near = NEAR_TEXT_POINTS
    return any(
        x0 - near <= x <= x1 + near and y0 - near <= y <= y1 + near
        for x0, y0, x1, y1 in _line_boxes(text)
    )


def word_at(text: PageText, caret: int) -> tuple[int, int]:
    """The carets around the word next to ``caret`` (what a double click selects)."""
    if not len(text):
        return 0, 0
    letter = min(max(caret, 0), len(text) - 1)
    chars, lines = text.chars, text.lines
    if not chars[letter].isalnum() and letter > 0 and chars[letter - 1].isalnum():
        letter -= 1  # a click just after a word still means that word
    if not chars[letter].isalnum():
        return letter, letter + 1
    start = letter
    while start > 0 and chars[start - 1].isalnum() and lines[start - 1] == lines[letter]:
        start -= 1
    stop = letter + 1
    while stop < len(chars) and chars[stop].isalnum() and lines[stop] == lines[letter]:
        stop += 1
    return start, stop


def selection_rects(text: PageText, start: int, stop: int) -> tuple[Rect, ...]:
    """One rectangle per line for the letters between two carets."""
    start, stop = max(0, start), min(stop, len(text))
    return _line_rects(text, list(range(start, stop)))


def selected_text(text: PageText, start: int, stop: int) -> str:
    """The text between two carets, ready to paste somewhere else.

    The lines of a paragraph are joined into running text (a word split by a
    hyphen at the end of a line becomes one word again); every paragraph of
    the page starts on a new line.
    """
    start, stop = max(0, start), min(stop, len(text))
    chars, lines, blocks = text.chars, text.lines, text.line_blocks
    out: list[str] = []
    joined = False  # the line before ended in a split word
    for letter in range(start, stop):
        char = chars[letter]
        if letter > start and lines[letter] != lines[letter - 1]:
            same_paragraph = (
                lines[letter] < len(blocks) and blocks[lines[letter]] == blocks[lines[letter - 1]]
            )
            if not joined:
                while out and out[-1] == " ":
                    out.pop()
                out.append(" " if same_paragraph else "\n")
            joined = False
        if char == _SOFT_HYPHEN:
            continue
        if letter in text.split_hyphens and char in _LINE_END_HYPHENS:
            joined = True
            continue
        if char.isspace():
            if joined or (out and out[-1] in " \n"):
                continue
            char = " "
        out.append(char)
    return "".join(out).strip()
