"""Reading the drawing orders of a page (its "content stream"), as far as
needed to put new text in the right place among them (task 6.1).

Where text is in the content decides the order in which programs read it:
search, selection, copying and screen readers. Text added at the end of a
page is read after everything else on it, so a corrected word would be
found apart from its sentence. ``insertion_point`` finds, after the text
that comes before it, a place where new text can go without changing how
the rest is drawn.

Only what is needed is followed: the graphics state (``q``, ``Q``, ``cm``),
text objects (``BT``, ``ET``), text positioning and the operators that show
text. Pictures written inside the content (``BI`` … ``ID`` … ``EI``) are
skipped whole.
"""

from dataclasses import dataclass

Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_WHITE = b" \t\r\n\f\x00"
_DELIMITERS = b"()<>[]{}/%"
SHOW = (b"Tj", b"TJ", b"'", b'"')
MOVES = (b"Td", b"TD", b"Tm", b"T*")


class ContentError(Exception):
    """The content cannot be followed (it is damaged or unusual)."""


def multiply(one: Matrix, other: Matrix) -> Matrix:
    """``one`` then ``other`` (PDF order: a point is a row vector)."""
    a, b, c, d, e, f = one
    g, h, i, j, k, m = other
    return (
        a * g + b * i,
        a * h + b * j,
        c * g + d * i,
        c * h + d * j,
        e * g + f * i + k,
        e * h + f * j + m,
    )


def inverse(matrix: Matrix) -> Matrix:
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ContentError("a drawing scale of zero")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_))


def tokens(data: bytes):
    """(start, end, kind, value) for each piece of the content. ``kind`` is
    "op" for operators and "operand" for everything else."""
    at, size = 0, len(data)
    while at < size:
        byte = data[at]
        if byte in _WHITE:
            at += 1
            continue
        if byte == ord("%"):
            while at < size and data[at] not in b"\r\n":
                at += 1
            continue
        start = at
        if byte == ord("("):
            at = _string_end(data, at)
            yield start, at, "operand", data[start:at]
        elif data.startswith(b"<<", at):
            at = _dict_end(data, at)
            yield start, at, "operand", data[start:at]
        elif byte == ord("<"):
            end = data.find(b">", at)
            if end < 0:
                raise ContentError("a hex string without end")
            at = end + 1
            yield start, at, "operand", data[start:at]
        elif byte == ord("["):
            at = _array_end(data, at)
            yield start, at, "operand", data[start:at]
        elif byte == ord("/"):
            at += 1
            while at < size and data[at] not in _WHITE and data[at] not in _DELIMITERS:
                at += 1
            yield start, at, "operand", data[start:at]
        elif byte in b")>]}":
            raise ContentError("a closing bracket without opening")
        else:
            while at < size and data[at] not in _WHITE and data[at] not in _DELIMITERS:
                at += 1
            word = data[start:at]
            if not word:
                raise ContentError("an empty token")
            if _is_number(word) or word in (b"true", b"false", b"null"):
                yield start, at, "operand", word
            elif word == b"BI":
                at = _inline_image_end(data, at)
                yield start, at, "op", b"BI"
            else:
                yield start, at, "op", word


def _is_number(word: bytes) -> bool:
    try:
        float(word)
    except ValueError:
        return False
    return True


def _string_end(data: bytes, at: int) -> int:
    depth, at = 0, at
    size = len(data)
    while at < size:
        byte = data[at]
        if byte == ord("\\"):
            at += 2
            continue
        if byte == ord("("):
            depth += 1
        elif byte == ord(")"):
            depth -= 1
            if depth == 0:
                return at + 1
        at += 1
    raise ContentError("a string without end")


def _dict_end(data: bytes, at: int) -> int:
    depth, size = 0, len(data)
    while at < size:
        if data.startswith(b"<<", at):
            depth += 1
            at += 2
        elif data.startswith(b">>", at):
            depth -= 1
            at += 2
            if depth == 0:
                return at
        elif data[at] == ord("("):
            at = _string_end(data, at)
        else:
            at += 1
    raise ContentError("a dictionary without end")


def _array_end(data: bytes, at: int) -> int:
    depth, size = 0, len(data)
    while at < size:
        byte = data[at]
        if byte == ord("("):
            at = _string_end(data, at)
            continue
        if byte == ord("["):
            depth += 1
        elif byte == ord("]"):
            depth -= 1
            if depth == 0:
                return at + 1
        at += 1
    raise ContentError("an array without end")


def _inline_image_end(data: bytes, at: int) -> int:
    found = data.find(b"ID", at)
    if found < 0:
        raise ContentError("a picture without data")
    at = found + 3
    size = len(data)
    while True:
        found = data.find(b"EI", at)
        if found < 0:
            raise ContentError("a picture without end")
        before_ok = found > 0 and data[found - 1] in _WHITE
        after = found + 2
        after_ok = after >= size or data[after] in _WHITE or data[after] in _DELIMITERS
        if before_ok and after_ok:
            return after
        at = found + 2


def _numbers(operands: list[bytes], count: int) -> list[float]:
    found = operands[-count:] if count else []
    if len(found) != count:
        raise ContentError("an operator without its numbers")
    try:
        return [float(value) for value in found]
    except ValueError as error:
        raise ContentError("an operator with a wrong number") from error


@dataclass
class Shown:
    """One operator that shows text."""

    start: int  # where the operator and its operands begin in the content
    end: int  # just after the operator
    origin: tuple[float, float] | None  # where its first letter starts (PDF space)
    size: float  # font size times the scaling of the drawing


@dataclass
class Place:
    """Where new text can go: ``at`` (a position in the content), what to
    write before and after it, and the drawing matrix in force there."""

    at: int
    ctm: Matrix
    in_text: bool  # inside a text object: it is closed and opened again
    line_matrix: Matrix


@dataclass
class _State:
    ctm: Matrix = IDENTITY
    size: float = 0.0
    leading: float = 0.0
    scaling: float = 1.0
    rise: float = 0.0
    render: int = 0


def read(data: bytes) -> tuple[list[Shown], list]:
    """The operators that show text, and every operator with the state at it:
    (start, end, name, ctm, in_text, line matrix, tagged pieces open since the
    text object began, render mode)."""
    shown: list[Shown] = []
    ops: list = []
    stack: list[_State] = []
    state = _State()
    in_text = False
    tm = tlm = IDENTITY
    tm_known = True
    marked = 0  # tagged pieces (BDC, BMC) opened inside the text object
    operands: list[bytes] = []
    first_operand = None
    for start, end, kind, value in tokens(data):
        if kind == "operand":
            if first_operand is None:
                first_operand = start
            operands.append(value)
            continue
        op_start = first_operand if first_operand is not None else start
        first_operand = None
        ops.append((op_start, end, value, state.ctm, in_text, tlm, marked, state.render))
        if value in (b"BDC", b"BMC") and in_text:
            marked += 1
        elif value == b"EMC" and in_text and marked:
            marked -= 1
        if value == b"q":
            stack.append(_State(**state.__dict__))
        elif value == b"Q":
            if stack:
                state = stack.pop()
        elif value == b"cm":
            state.ctm = multiply(tuple(_numbers(operands, 6)), state.ctm)
        elif value == b"BT":
            in_text, tm, tlm, tm_known, marked = True, IDENTITY, IDENTITY, True, 0
        elif value == b"ET":
            in_text = False
        elif value == b"Tf":
            state.size = _numbers(operands, 1)[0]
        elif value == b"TL":
            state.leading = _numbers(operands, 1)[0]
        elif value == b"Tz":
            state.scaling = _numbers(operands, 1)[0] / 100
        elif value == b"Ts":
            state.rise = _numbers(operands, 1)[0]
        elif value == b"Tr":
            state.render = int(_numbers(operands, 1)[0])
        elif value in (b"Td", b"TD"):
            tx, ty = _numbers(operands, 2)
            if value == b"TD":
                state.leading = -ty
            tlm = multiply((1, 0, 0, 1, tx, ty), tlm)
            tm, tm_known = tlm, True
        elif value == b"Tm":
            tlm = tm = tuple(_numbers(operands, 6))
            tm_known = True
        elif value == b"T*":
            tlm = multiply((1, 0, 0, 1, 0, -state.leading), tlm)
            tm, tm_known = tlm, True
        elif value in SHOW:
            if value in (b"'", b'"'):
                tlm = multiply((1, 0, 0, 1, 0, -state.leading), tlm)
                tm, tm_known = tlm, True
            origin = None
            if tm_known:
                shift = 0.0
                if value == b"TJ" and operands:
                    inside = operands[-1][1:].lstrip()
                    number = inside.split(b"<")[0].split(b"(")[0].split()
                    if number and _is_number(number[0]):
                        shift = -float(number[0]) / 1000 * state.size * state.scaling
                point = multiply((1, 0, 0, 1, shift, state.rise), multiply(tm, state.ctm))
                origin = (point[4], point[5])
            scale = multiply(tm, state.ctm)
            size = state.size * (abs(scale[3]) or 1)
            shown.append(Shown(op_start, end, origin, size))
            tm_known = False  # the letters moved it by their widths
        operands = []
    return shown, ops


def insertion_point(data: bytes, after: tuple[float, float] | None) -> Place:
    """Where to put new text so that it is read right after the letter that
    starts at ``after`` (PDF space; None: at the very start).

    It goes after that operator, at the first place where nothing else
    depends on where the letters left the pen: before the next positioning
    of a line, or after the end of the text object."""
    shown, ops = read(data)
    if after is None:
        return Place(0, IDENTITY, False, IDENTITY)
    # The operator that shows that letter: on its line, the nearest one that
    # starts before it (or at it).
    best = None
    for item in shown:
        if item.origin is None:
            continue
        ox, oy = item.origin
        tolerance = max(0.5, 0.3 * abs(item.size))
        if abs(oy - after[1]) > tolerance or ox > after[0] + 0.5:
            continue
        if best is None or ox >= best.origin[0] - 0.01:
            best = item
    if best is None:
        raise ContentError("the text before is not in the page's own content")
    for op_start, end, name, ctm, in_text, line_matrix, marked, render in ops:
        if op_start < best.end:
            continue
        if name == b"ET":
            return Place(end, ctm, False, IDENTITY)
        # Not inside a tagged piece opened in the text object (it would be
        # cut in two), nor while letters are making a clipping path.
        if in_text and name in MOVES and render < 4 and not marked:
            return Place(op_start, ctm, True, line_matrix)
        if not in_text:
            return Place(op_start, ctm, False, IDENTITY)
    return Place(len(data), IDENTITY, False, IDENTITY)


def number(value: float) -> str:
    text = f"{value:.5f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def matrix_text(matrix: Matrix) -> str:
    return " ".join(number(value) for value in matrix)


def splice(data: bytes, place: Place, text: bytes) -> bytes:
    """The content with ``text`` (drawing orders in PDF space, balanced)
    put at ``place``."""
    parts = []
    if place.in_text:
        parts.append(b"ET\n")
    parts.append(b"q\n")
    if place.ctm != IDENTITY:
        parts.append(matrix_text(inverse(place.ctm)).encode() + b" cm\n")
    parts.append(text)
    parts.append(b"Q\n")
    if place.in_text:
        parts.append(b"BT\n" + matrix_text(place.line_matrix).encode() + b" Tm\n")
    middle = b"".join(parts)
    before, after = data[: place.at], data[place.at :]
    return before + b"\n" + middle + after
