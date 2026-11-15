"""Moving, resizing and copying what was put on a page.

Nothing is changed in place: an annotation that moves is taken away and put
again somewhere else, in one order (``notes.Replace``), so undo brings it back
exactly where it was. Everything here works on the orders that put things
(``AddNote``, ``AddTextBox``, ``AddInk``, ``AddShape``), which is what
``PageNote.order()`` and ``PageDrawing.order()`` give for what is on a page.

A mark on the text (highlight, underline, strike-out) belongs to its words: it
can be picked and removed, not moved.
"""

from dataclasses import replace

from app.core.commands import AddMarkup, Command, new_name
from app.core.drawing import BOX, MIN_SHAPE, OVAL, AddInk, AddShape
from app.core.notes import (
    MAX_SIZE,
    MIN_BOX_WIDTH,
    MIN_SIZE,
    NOTE_SIZE,
    PAGE_MARGIN,
    AddNote,
    AddTextBox,
    Replace,
    box_layout,
)
from app.core.search import Rect

Point = tuple[float, float]
Size = tuple[float, float]  # width and height of a page, as it is shown

MIN_SIDE = 4.0  # points; nothing is squeezed smaller than this
PASTE_STEP = 12.0  # how far from the original a copy lands

# The corners of a frame, in the order the handles are numbered. A text has
# two more, in the middle of its sides, that make it wider or narrower.
TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT = range(4)
RIGHT_SIDE, LEFT_SIDE = 4, 5


def can_move(order: Command) -> bool:
    return isinstance(order, AddNote | AddTextBox | AddInk | AddShape)


def can_resize(order: Command) -> bool:
    """A note is an icon of a fixed size; everything else that moves can be resized."""
    return isinstance(order, AddTextBox | AddInk | AddShape)


def bounds(order: Command, page_width: float = 1e9) -> Rect:
    """The rectangle around what an order puts, as the page is shown."""
    if isinstance(order, AddNote):
        x, y = order.point
        return (x, y, x + NOTE_SIZE, y + NOTE_SIZE)
    if isinstance(order, AddTextBox):
        return box_layout(
            order.text,
            order.font,
            order.size,
            order.origin,
            page_width,
            order.width,
            order.bold,
        )[1]
    if isinstance(order, AddInk):
        points = [point for stroke in order.strokes for point in stroke]
    elif isinstance(order, AddShape):
        points = [order.start, order.end]
    elif isinstance(order, AddMarkup):
        points = [
            corner
            for mark in order.marks
            for x0, y0, x1, y1 in mark.rects
            for corner in ((x0, y0), (x1, y1))
        ]
    else:
        raise TypeError(f"not something on a page: {order!r}")
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))


def handles(order: Command, page_width: float = 1e9) -> list[Point]:
    """Where an order can be grabbed to resize it.

    A line or an arrow, by its two ends; the rest, by the four corners of its
    frame (``TOP_LEFT``…). A text also by the middle of its right and left
    sides (``RIGHT_SIDE``, ``LEFT_SIDE``): they change how wide it is, and its
    lines are cut again to fit. A note has none.
    """
    if not can_resize(order):
        return []
    if isinstance(order, AddShape) and order.kind not in (BOX, OVAL):
        return [order.start, order.end]
    x0, y0, x1, y1 = bounds(order, page_width)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if isinstance(order, AddTextBox):
        middle = (y0 + y1) / 2
        corners += [(x1, middle), (x0, middle)]
    return corners


def _shifted(order: Command, dx: float, dy: float) -> Command:
    def move(point: Point) -> Point:
        return (point[0] + dx, point[1] + dy)

    if isinstance(order, AddNote):
        return replace(order, point=move(order.point))
    if isinstance(order, AddTextBox):
        return replace(order, origin=move(order.origin))
    if isinstance(order, AddInk):
        return replace(
            order, strokes=tuple(tuple(move(point) for point in stroke) for stroke in order.strokes)
        )
    if isinstance(order, AddShape):
        return replace(order, start=move(order.start), end=move(order.end))
    raise TypeError(f"it cannot be moved: {order!r}")


def _kept_inside(order: Command, dx: float, dy: float, page: Size) -> tuple[float, float]:
    """The same movement, cut short where the thing would leave the page."""
    width, height = page
    x0, y0, x1, y1 = bounds(order, width)
    if isinstance(order, AddTextBox):
        # Nearer the edge than this, its lines would be cut again to fit.
        width -= PAGE_MARGIN - 2
    dx = max(-x0, min(width - x1, dx)) if x1 - x0 <= width else 0.0
    dy = max(-y0, min(height - y1, dy)) if y1 - y0 <= height else 0.0
    return dx, dy


def moved(order: Command, dx: float, dy: float, page: Size) -> Replace | None:
    """The order that moves something by that much, without leaving its page.

    None if it cannot be moved or would not move at all.
    """
    if not can_move(order):
        return None
    dx, dy = _kept_inside(order, dx, dy, page)
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return None
    return Replace(order, _shifted(order, dx, dy))


def _inside(point: Point, page: Size) -> Point:
    return (max(0.0, min(page[0], point[0])), max(0.0, min(page[1], point[1])))


def resized(order: Command, handle: int, point: Point, page: Size) -> Replace | None:
    """The order that takes a handle of something to another point.

    ``handle`` is the place in ``handles(order)`` of the one that is dragged.
    The opposite corner (or the other end of a line) stays where it is. None
    if nothing would change.
    """
    grips = handles(order, page[0])
    if not 0 <= handle < len(grips):
        return None
    point = _inside(point, page)
    if isinstance(order, AddShape) and len(grips) == 2:
        ends = [order.start, order.end]
        ends[handle] = point
        new = replace(order, start=ends[0], end=ends[1])
        if abs(ends[0][0] - ends[1][0]) + abs(ends[0][1] - ends[1][1]) < MIN_SHAPE:
            return None
    elif handle in (RIGHT_SIDE, LEFT_SIDE):
        new = _widened(order, handle, point[0], bounds(order, page[0]), page)
    else:
        fixed = grips[(handle + 2) % 4]
        new = _stretched(order, fixed, point, bounds(order, page[0]), page)
    if new is None or new == order:
        return None
    return Replace(order, new)


def _widened(order: AddTextBox, handle: int, x: float, old: Rect, page: Size) -> AddTextBox:
    """A text with one of its sides taken to ``x``: the other side stays."""
    if handle == RIGHT_SIDE:
        left = old[0]
        right = min(x, page[0] - (PAGE_MARGIN - 2))
    else:
        right = old[2]
        left = max(0.0, x)
    width = max(MIN_BOX_WIDTH, right - left)
    if handle == LEFT_SIDE:
        left = right - width
    return replace(order, origin=(max(0.0, left), order.origin[1]), width=round(width, 2))


def _stretched(order: Command, fixed: Point, point: Point, old: Rect, page: Size):
    """What is in the frame ``old``, in the frame from ``fixed`` to ``point``."""
    # The dragged corner never crosses the fixed one: the frame keeps a size.
    right, below = fixed[0] <= (old[0] + old[2]) / 2, fixed[1] <= (old[1] + old[3]) / 2
    x = max(point[0], fixed[0] + MIN_SIDE) if right else min(point[0], fixed[0] - MIN_SIDE)
    y = max(point[1], fixed[1] + MIN_SIDE) if below else min(point[1], fixed[1] - MIN_SIDE)
    x0, x1 = sorted((fixed[0], x))
    y0, y1 = sorted((fixed[1], y))
    if isinstance(order, AddShape):
        return replace(order, start=(x0, y0), end=(x1, y1))
    old_width, old_height = old[2] - old[0], old[3] - old[1]
    if isinstance(order, AddInk):
        # A stroke that is a flat line has no height to stretch: it only moves.
        scale_x = (x1 - x0) / old_width if old_width >= 0.01 else 1.0
        scale_y = (y1 - y0) / old_height if old_height >= 0.01 else 1.0

        left = x0 if old_width >= 0.01 else old[0]
        top = y0 if old_height >= 0.01 else old[1]

        def fit(spot: Point) -> Point:
            return (left + (spot[0] - old[0]) * scale_x, top + (spot[1] - old[1]) * scale_y)

        return replace(
            order, strokes=tuple(tuple(fit(spot) for spot in stroke) for stroke in order.strokes)
        )
    if isinstance(order, AddTextBox):
        # A text grows or shrinks whole: its letter changes size, in half points.
        grow = max((x1 - x0) / max(old_width, 0.01), (y1 - y0) / max(old_height, 0.01))
        size = max(MIN_SIZE, min(MAX_SIZE, round(order.size * grow * 2) / 2))
        if size == order.size:
            return None
        # A width chosen by hand grows with the letter: the lines stay as they are.
        sized = replace(order, size=size, width=round(order.width * size / order.size, 2))
        new = bounds(replace(sized, origin=(0.0, 0.0)))
        width, height = new[2] - new[0], new[3] - new[1]
        left = fixed[0] if right else fixed[0] - width
        top = fixed[1] if below else fixed[1] - height
        left = max(0.0, min(page[0] - (PAGE_MARGIN - 2) - width, left))
        top = max(0.0, min(page[1] - height, top))
        return replace(sized, origin=(left, top))
    return None


def copy_of(
    order: Command,
    page: int,
    size: Size,
    center: Point | None = None,
) -> Command | None:
    """The order that puts a copy of something on a page, with a name of its own.

    With ``center``, the copy is centred there; without, a little down and to
    the right of the original. It never leaves the page. None if it is
    something that cannot be copied (a mark on the text belongs to its words).
    """
    if not can_move(order):
        return None
    copy = replace(order, page=page, name=new_name())
    x0, y0, x1, y1 = bounds(copy, size[0])
    if center is None:
        dx = dy = PASTE_STEP
    else:
        dx, dy = center[0] - (x0 + x1) / 2, center[1] - (y0 + y1) / 2
    if isinstance(copy, AddTextBox):
        # A text is wrapped again where it lands: it must have its room there.
        dx = min(dx, size[0] - x1)
    dx, dy = _kept_inside(copy, dx, dy, size)
    return _shifted(copy, dx, dy)
