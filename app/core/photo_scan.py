"""From photos of paper to a PDF that looks scanned.

A photo taken with a phone shows the sheet slanted, with the table around it
and darker where the light was weaker. Each photo goes through three steps:

1. **Find the paper**: its four corners. The paper is the largest light patch
   of the photo; its corners are the points furthest out of that patch. When
   that does not work (light paper on a light table) MuPDF's own document
   finder is asked, and if that fails too the whole photo is used. The
   person can always move the corners by hand.
2. **Straighten** it: the four corners are pulled out to a rectangle
   (``fz_warp_pixmap``), turned a quarter at a time if the person asks.
3. **Clean** it: the light of the paper is measured in a small copy (the
   lightest tone around each spot, so the letters do not count) and the photo
   is divided by it, which makes the paper white everywhere and the shadows
   go away. Then the letters are made darker. This division is done by
   MuPDF, drawing the photo with the light "colour-dodged" on top of it,
   so no picture library is needed and it takes a fraction of a second.

Everything here works on PyMuPDF pixmaps, never Qt (``app.core`` rule).
"""

import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from app.core.page_orders import A4, IMAGE_TYPES

# How the result looks.
DOCUMENT = "documento"  # white paper, dark letters, colours kept (default)
GRAY = "gris"  # the same in shades of grey
BLACK_WHITE = "blanco_negro"  # only black and white, like a fax or a photocopy
PHOTO = "foto"  # only straightened, the colours as they were
LOOKS = (DOCUMENT, GRAY, BLACK_WHITE, PHOTO)

MAX_SIDE = 3200  # the photo is read at most this long (pixels): enough for 300 ppp
FIND_SIDE = 300  # the paper is looked for in a copy about this long
LONG_SIDE = 2339  # the result's long side: an A4 sheet at 200 ppp
LIGHT_WIDTH = 80  # the light of the paper is measured in a copy this wide
LIGHT_REACH = 2  # ...as the lightest spot this many steps around
MIN_PAPER = 0.12  # the paper covers at least this share of the photo...
MAX_PAPER = 0.97  # ...and less than this (more: the light patch is the table)
QUAD_LIKE = 0.85  # the patch fills this much of the corners' shape
SHEET_RATIO = 2**0.5  # an A4 sheet, tall side / short side
# A page this close to that shape is made an A4 sheet: seen from an angle,
# a sheet looks shorter than it is.
SNAP = 0.12
INSET = 1.5  # the corners found go in this many pixels of the small copy
JPEG_QUALITY = 85

Point = tuple[float, float]


class PhotoError(Exception):
    """A photo cannot be read or turned into a page."""


@dataclass
class Photo:
    """One photo and what to do with it: the paper's corners in the photo
    (top left, top right, bottom right, bottom left, as the photo is seen,
    each as shares of its width and height, from 0 to 1, so they hold for a
    small copy and for the whole photo alike; none: found when it is made)
    and how many quarter turns to the right the page gets."""

    path: Path
    corners: list[Point] = field(default_factory=list)
    turns: int = 0


# ---- reading --------------------------------------------------------------


def is_photo(path) -> bool:
    return Path(path).suffix.lower().lstrip(".") in IMAGE_TYPES


def open_photo(path, longest: int = MAX_SIDE):
    """The photo as an RGB pixmap, turned the way the camera noted (EXIF)
    and no longer than ``longest`` pixels. Raises PhotoError."""
    import pymupdf

    try:
        with pymupdf.open(path) as picture:
            page = picture[0]
            images = page.get_image_info()
            native = max(images[0]["width"], images[0]["height"]) if images else longest
            side = max(page.rect.width, page.rect.height)
            zoom = min(native, longest) / side
            # Opening it as a document turns it as the camera says.
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    except Exception as error:
        raise PhotoError(f"{Path(path).name} cannot be read as a picture: {error}") from error
    if pix.width < 8 or pix.height < 8:
        raise PhotoError(f"{Path(path).name} is too small")
    if pix.colorspace is None or pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return pix


# ---- finding the paper ----------------------------------------------------


def whole(pix) -> list[Point]:
    """The corners of the whole photo."""
    width, height = pix.width - 1, pix.height - 1
    return [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]


def _gray_rows(pix, longest: int) -> tuple[bytes, int, int]:
    import pymupdf

    gray = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    while max(gray.width, gray.height) > longest * 2:
        gray.shrink(1)
    width, height, stride = gray.width, gray.height, gray.stride
    samples = gray.samples
    return b"".join(samples[y * stride : y * stride + width] for y in range(height)), width, height


def _split_level(levels: bytes) -> int:
    """The grey that best splits light from dark (Otsu's method)."""
    counts = [0] * 256
    for value in levels:
        counts[value] += 1
    total, everything = len(levels), sum(level * count for level, count in enumerate(counts))
    dark = dark_sum = 0
    best, best_level = -1.0, 127
    for level, count in enumerate(counts):
        dark += count
        if dark == 0:
            continue
        light = total - dark
        if light == 0:
            break
        dark_sum += level * count
        apart = dark_sum / dark - (everything - dark_sum) / light
        spread = dark * light * apart * apart
        if spread > best:
            best, best_level = spread, level
    return best_level


def _largest_patch(light: bytearray, width: int, height: int) -> list[int]:
    """The places of the largest group of touching light pixels."""
    seen = bytearray(len(light))
    best: list[int] = []
    for start, is_light in enumerate(light):
        if not is_light or seen[start]:
            continue
        seen[start] = 1
        patch, waiting = [], deque([start])
        while waiting:
            place = waiting.popleft()
            patch.append(place)
            x = place % width
            for near in (
                place - 1 if x else -1,
                place + 1 if x < width - 1 else -1,
                place - width,
                place + width,
            ):
                if 0 <= near < len(light) and light[near] and not seen[near]:
                    seen[near] = 1
                    waiting.append(near)
        if len(patch) > len(best):
            best = patch
    return best


def _area(corners: list[Point]) -> float:
    total = 0.0
    for index, (x, y) in enumerate(corners):
        next_x, next_y = corners[(index + 1) % len(corners)]
        total += x * next_y - next_x * y
    return abs(total) / 2


def in_order(points: list[Point]) -> list[Point]:
    """Four points as top left, top right, bottom right, bottom left."""
    by_sum = sorted(points, key=lambda p: p[0] + p[1])
    by_difference = sorted(points, key=lambda p: p[0] - p[1])
    corners = [by_sum[0], by_difference[-1], by_sum[-1], by_difference[0]]
    if len(set(corners)) == 4:
        return corners
    # A sheet turned about 45 degrees: go round its middle instead.
    import math

    middle_x = sum(p[0] for p in points) / 4
    middle_y = sum(p[1] for p in points) / 4
    around = sorted(points, key=lambda p: math.atan2(p[1] - middle_y, p[0] - middle_x))
    first = min(range(4), key=lambda i: around[i][0] + around[i][1])
    return around[first:] + around[:first]


def _light_patch_corners(pix) -> list[Point] | None:
    levels, width, height = _gray_rows(pix, FIND_SIDE)
    cut = _split_level(levels)
    light = bytearray(levels.translate(bytes(1 if level > cut else 0 for level in range(256))))
    patch = _largest_patch(light, width, height)
    share = len(patch) / (width * height)
    if not MIN_PAPER <= share <= MAX_PAPER:
        return None
    points = [(place % width, place // width) for place in patch]
    corners = [
        min(points, key=lambda p: p[0] + p[1]),
        max(points, key=lambda p: p[0] - p[1]),
        max(points, key=lambda p: p[0] + p[1]),
        min(points, key=lambda p: p[0] - p[1]),
    ]
    if len(set(corners)) < 4 or len(patch) < QUAD_LIKE * _area(corners):
        return None  # not a sheet: a shape with more than four corners
    # A little inwards, so no strip of the table is left at the edges.
    middle_x = sum(x for x, _ in corners) / 4
    middle_y = sum(y for _, y in corners) / 4
    inset = []
    for x, y in corners:
        away = max(1.0, _distance((x, y), (middle_x, middle_y)))
        inset.append((x + (middle_x - x) * INSET / away, y + (middle_y - y) * INSET / away))
    scale_x, scale_y = (pix.width - 1) / max(1, width - 1), (pix.height - 1) / max(1, height - 1)
    return [(x * scale_x, y * scale_y) for x, y in inset]


def _mupdf_corners(pix) -> list[Point] | None:
    import pymupdf

    small = pymupdf.Pixmap(pix.colorspace, pix)  # a copy without see-through
    while max(small.width, small.height) > FIND_SIDE * 4:
        small.shrink(1)
    quad = pymupdf.mupdf.FzQuad()
    try:
        if not pymupdf.mupdf.fz_detect_document(quad, small.this):
            return None
    except Exception:
        return None
    scale = pix.width / small.width
    points = [(p.x * scale, p.y * scale) for p in (quad.ul, quad.ur, quad.lr, quad.ll)]
    corners = in_order(points)
    if _area(corners) < MIN_PAPER * pix.width * pix.height:
        return None
    return [_inside(pix, point) for point in corners]


def _inside(pix, point: Point) -> Point:
    return (min(max(point[0], 0.0), pix.width - 1.0), min(max(point[1], 0.0), pix.height - 1.0))


def as_shares(pix, corners: list[Point]) -> list[Point]:
    """Corners in pixels of ``pix`` as shares of its width and height."""
    width, height = max(1, pix.width - 1), max(1, pix.height - 1)
    return [(x / width, y / height) for x, y in corners]


def in_pixels(pix, shares: list[Point]) -> list[Point]:
    """Corners given as shares, in pixels of ``pix``."""
    width, height = pix.width - 1, pix.height - 1
    return [(x * width, y * height) for x, y in shares]


def find_paper(pix) -> list[Point]:
    """The corners of the sheet in the photo (the whole photo if no sheet is
    found): top left, top right, bottom right, bottom left."""
    return _light_patch_corners(pix) or _mupdf_corners(pix) or whole(pix)


def is_convex(corners: list[Point]) -> bool:
    """Whether the four corners make a shape that can be straightened."""
    signs = set()
    for index in range(4):
        (ax, ay), (bx, by), (cx, cy) = (corners[(index + step) % 4] for step in range(3))
        turn = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if turn == 0:
            return False
        signs.add(turn > 0)
    return len(signs) == 1


# ---- straightening --------------------------------------------------------


def _distance(a: Point, b: Point) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def turned(corners: list[Point], turns: int) -> list[Point]:
    """The corners as seen after turning the page ``turns`` quarters right."""
    turns %= 4
    return corners[-turns:] + corners[:-turns] if turns else list(corners)


def sheet_shape(width: float, height: float) -> float:
    """Height / width of the page: a known sheet when it is close to one."""
    ratio = height / width
    for shape in (SHEET_RATIO, 1 / SHEET_RATIO):
        if abs(ratio - shape) / shape <= SNAP:
            return shape
    return ratio


def result_size(corners: list[Point], longest: int = LONG_SIDE) -> tuple[int, int]:
    """Width and height in pixels of the straightened page."""
    top_left, top_right, bottom_right, bottom_left = corners
    width = (_distance(top_left, top_right) + _distance(bottom_left, bottom_right)) / 2
    height = (_distance(top_left, bottom_left) + _distance(top_right, bottom_right)) / 2
    width, height = max(width, 1.0), max(height, 1.0)
    ratio = sheet_shape(width, height)
    long_side = min(longest, max(width, height))  # never larger than the photo gives
    if ratio >= 1:
        return max(1, round(long_side / ratio)), max(1, round(long_side))
    return max(1, round(long_side)), max(1, round(long_side * ratio))


def straighten(pix, corners: list[Point], turns: int = 0, longest: int = LONG_SIDE):
    """The sheet within ``corners`` pulled out to a rectangle and turned."""
    import pymupdf

    corners = turned([_inside(pix, point) for point in corners], turns)
    if not is_convex(corners):
        raise PhotoError("the corners do not make a sheet")
    width, height = result_size(corners, longest)
    top_left, top_right, bottom_right, bottom_left = corners
    # MuPDF reads the four points of the quad in the order they are kept,
    # going round the sheet: top left, top right, bottom right, bottom left.
    quad = pymupdf.mupdf.fz_make_quad(*top_left, *top_right, *bottom_right, *bottom_left)
    result = pymupdf.Pixmap(pymupdf.mupdf.fz_warp_pixmap(pix.this, quad, width, height))
    return pymupdf.Pixmap(result, 0) if result.alpha else result


# ---- cleaning -------------------------------------------------------------


def _paper_light(pix):
    """A small picture of how light the paper is around each spot, as its
    opposite (dark where the paper is light), ready to divide by it."""
    import pymupdf

    small = pymupdf.Pixmap(pix.colorspace, pix)  # a copy without see-through
    while small.width > LIGHT_WIDTH * 2:
        small.shrink(1)
    width, height, n, stride = small.width, small.height, small.n, small.stride
    samples = small.samples
    rows = [samples[y * stride : y * stride + width * n] for y in range(height)]
    reach = LIGHT_REACH
    # The lightest spot around, first along the rows, then down the columns.
    along = []
    for row in rows:
        lightest = bytearray(width * n)
        for channel in range(n):
            values = row[channel::n]
            for x in range(width):
                lightest[x * n + channel] = max(values[max(0, x - reach) : x + reach + 1])
        along.append(lightest)
    out = bytearray(width * height * n)
    for y in range(height):
        band = along[max(0, y - reach) : y + reach + 1]
        start = y * width * n
        for place in range(width * n):
            out[start + place] = 255 - max(row[place] for row in band)
    return pymupdf.Pixmap(small.colorspace, width, height, bytes(out), 0)


def _evened(pix):
    """The photo divided by the light of its paper: the paper turns white
    everywhere and shadows go. MuPDF does the sums: it draws the photo and,
    on top, the opposite of the light with the "colour dodge" blend, which
    is exactly a division."""
    import pymupdf

    width, height = pix.width, pix.height
    light = _paper_light(pix)
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=width, height=height)
        page.insert_image(page.rect, pixmap=pix)
        page.insert_image(page.rect, pixmap=light, keep_proportion=False)
        names = {image[0]: image[7] for image in page.get_images()}
        photo_name = names[min(names)]
        light_xref = max(names)
        doc.xref_set_key(light_xref, "Interpolate", "true")  # smooth, not in squares
        streams = page.get_contents()
        doc.update_stream(
            streams[0],
            (
                f"q {width} 0 0 {height} 0 0 cm /{photo_name} Do Q "
                f"q /Dodge gs {width} 0 0 {height} 0 0 cm /{names[light_xref]} Do Q"
            ).encode(),
        )
        for stream in streams[1:]:
            doc.update_stream(stream, b" ")
        kind, value = doc.xref_get_key(page.xref, "Resources")
        if kind == "xref":
            doc.xref_set_key(int(value.split()[0]), "ExtGState", "<</Dodge<</BM/ColorDodge>>>>")
        else:
            doc.xref_set_key(page.xref, "Resources/ExtGState", "<</Dodge<</BM/ColorDodge>>>>")
        return page.get_pixmap(colorspace=pix.colorspace, alpha=False)
    finally:
        doc.close()


def _levels(black: int, white: int) -> bytes:
    """Everything darker than ``black`` becomes black, lighter than ``white``
    white, and in between it is spread out."""
    table = bytearray(256)
    for level in range(256):
        share = (level - black) / (white - black)
        table[level] = max(0, min(255, round(255 * share)))
    return bytes(table)


def _with_table(pix, table: bytes):
    import pymupdf

    width, height, n = pix.width, pix.height, pix.n
    samples = pix.samples
    if pix.stride != width * n:
        samples = b"".join(
            samples[y * pix.stride : y * pix.stride + width * n] for y in range(height)
        )
    return pymupdf.Pixmap(pix.colorspace, width, height, samples.translate(table), 0)


INK = 40  # after evening, this dark or darker is ink
PAPER = 215  # and this light or lighter is paper
BLACK_WHITE_CUT = 170  # darker than this is black in black and white


def clean(pix, look: str = DOCUMENT):
    """The straightened page with the look asked for."""
    import pymupdf

    if look == PHOTO:
        return pix
    evened = _evened(pix)
    if look == GRAY:
        evened = pymupdf.Pixmap(pymupdf.csGRAY, evened)
    elif look == BLACK_WHITE:
        evened = pymupdf.Pixmap(pymupdf.csGRAY, evened)
        cut = bytes(0 if level < BLACK_WHITE_CUT else 255 for level in range(256))
        return _with_table(evened, cut)
    return _with_table(evened, _levels(INK, PAPER))


def scanned(photo: Photo, look: str = DOCUMENT, longest: int = LONG_SIDE):
    """The page made from one photo."""
    pix = open_photo(photo.path)
    corners = in_pixels(pix, photo.corners) if photo.corners else find_paper(pix)
    return clean(straighten(pix, corners, photo.turns, longest), look)


# ---- the PDF --------------------------------------------------------------


def page_size(width: int, height: int) -> tuple[float, float]:
    """The page a picture of ``width`` × ``height`` pixels goes on, in points:
    an A4 sheet (or as wide as one, when it has another shape)."""
    short, tall = A4
    if height >= width:
        return short, short * height / width
    return short * width / height, short


def picture_bytes(pix, look: str) -> bytes:
    """The page picture as it is kept in the PDF: JPEG for photos and
    greys, PNG (sharp and small) for black and white."""
    if look == BLACK_WHITE:
        return pix.tobytes("png")
    return pix.tobytes("jpg", jpg_quality=JPEG_QUALITY)


def write_pdf(pages, target: Path, look: str = DOCUMENT, progress=None) -> Path:
    """Make a PDF at ``target`` with one page for each of ``pages`` (Photo,
    or a ready pixmap). ``progress(done, total)`` may return False to stop.
    Written beside its place and then put there. Raises PhotoError."""
    import pymupdf

    target = Path(target)
    pages = list(pages)
    doc = pymupdf.open()
    try:
        for done, item in enumerate(pages):
            if progress is not None and progress(done, len(pages)) is False:
                raise PhotoError("stopped")
            pix = scanned(item, look) if isinstance(item, Photo) else item
            width, height = page_size(pix.width, pix.height)
            page = doc.new_page(width=width, height=height)
            page.insert_image(page.rect, stream=picture_bytes(pix, look))
        doc.set_metadata({"creator": "Lector-PDF", "producer": "Lector-PDF"})
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            doc.save(temporary, garbage=3, deflate=True)
            os.replace(temporary, target)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            raise PhotoError(f"{target.name} cannot be written: {error}") from error
    finally:
        doc.close()
    if progress is not None:
        progress(len(pages), len(pages))
    return target
