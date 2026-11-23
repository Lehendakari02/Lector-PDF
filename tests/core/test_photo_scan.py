"""Tests for turning photos of paper into a PDF that looks scanned."""

import struct

import pymupdf
import pytest

from app.core import photo_scan
from app.core.photo_scan import (
    BLACK_WHITE,
    DOCUMENT,
    GRAY,
    PHOTO,
    Photo,
    PhotoError,
    clean,
    find_paper,
    in_order,
    is_convex,
    open_photo,
    page_size,
    result_size,
    straighten,
    turned,
    write_pdf,
)


def gray_rows(pix):
    gray = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    width, stride = gray.width, gray.stride
    return [gray.samples[y * stride : y * stride + width] for y in range(gray.height)]


def dark_rows(pix, cut=110):
    """The rows where most of the middle is dark: the lines of writing."""
    rows = gray_rows(pix)
    width = len(rows[0])
    middle = slice(width // 4, 3 * width // 4)
    return [y for y, row in enumerate(rows) if sum(v < cut for v in row[middle]) > width // 4]


def bands(rows):
    found = []
    for y in rows:
        if found and y - found[-1][-1] <= 2:
            found[-1].append(y)
        else:
            found.append([y])
    return found


def with_orientation(jpeg: bytes, value: int) -> bytes:
    """The JPEG with an EXIF note saying how the camera was held."""
    entry = struct.pack(">HHIHH", 0x0112, 3, 1, value, 0)
    tiff = b"MM\x00\x2a" + struct.pack(">IH", 8, 1) + entry + struct.pack(">I", 0)
    body = b"Exif\x00\x00" + tiff
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body + jpeg[2:]


@pytest.fixture
def photo(tmp_path, photo_of_paper):
    return photo_of_paper(tmp_path / "foto.jpg")


@pytest.fixture
def sheet(photo_of_paper):
    return photo_of_paper.sheet


@pytest.fixture
def lines(photo_of_paper):
    return photo_of_paper.lines


def test_the_sheet_is_found_in_the_photo(photo, sheet):
    pix = open_photo(photo)
    corners = find_paper(pix)
    for found, real in zip(corners, sheet, strict=True):
        assert abs(found[0] - real[0]) < 12 and abs(found[1] - real[1]) < 12, (found, real)


def test_straightened_the_lines_of_writing_are_level(photo, lines):
    pix = open_photo(photo)
    page = straighten(pix, find_paper(pix))
    assert page.height > page.width
    found = bands(dark_rows(page))
    assert len(found) == lines
    assert all(len(line) <= 8 for line in found), "each line is level: a few rows thick"


def test_the_page_is_made_an_a4_sheet_when_it_is_close():
    width, height = result_size([(0, 0), (1000, 0), (1000, 1300), (0, 1300)])
    assert height / width == pytest.approx(2**0.5, rel=0.01)
    width, height = result_size([(0, 0), (1000, 0), (1000, 1000), (0, 1000)])
    assert width == height, "a square stays a square"
    width, height = result_size([(0, 0), (4000, 0), (4000, 3000), (0, 3000)])
    assert width == 2339, "never larger than an A4 sheet at 200 ppp"


def test_the_paper_turns_white_and_the_shadow_goes(photo, lines):
    pix = open_photo(photo)
    page = straighten(pix, find_paper(pix))
    for look in (DOCUMENT, GRAY):
        rows = gray_rows(clean(page, look))
        paper = rows[len(rows) * 9 // 10]  # below the writing
        left, right = paper[len(paper) // 5], paper[len(paper) * 4 // 5]
        assert left > 240 and right > 240, f"{look}: the paper is white on both sides"
    shaded = gray_rows(page)[page.height * 9 // 10]
    assert shaded[page.width * 4 // 5] < 225, "in the photo the right was darker"
    assert len(bands(dark_rows(clean(page, DOCUMENT)))) == lines, "the writing stays"


def test_black_and_white_has_only_black_and_white(photo, lines):
    pix = open_photo(photo)
    page = clean(straighten(pix, find_paper(pix)), BLACK_WHITE)
    assert page.n == 1
    assert set(page.samples) <= {0, 255}
    assert len(bands(dark_rows(page))) == lines


def test_photo_keeps_the_colours_as_they_were(photo):
    pix = open_photo(photo)
    page = straighten(pix, find_paper(pix))
    assert clean(page, PHOTO) is page


def test_turning_the_page_a_quarter(photo):
    pix = open_photo(photo)
    corners = find_paper(pix)
    assert turned(corners, 1) == [corners[3], corners[0], corners[1], corners[2]]
    assert turned(corners, 4) == corners
    page = straighten(pix, corners, turns=1)
    assert page.width > page.height, "on its side"


def test_the_corners_are_put_in_order():
    assert in_order([(10, 90), (90, 10), (10, 10), (90, 90)]) == [
        (10, 10),
        (90, 10),
        (90, 90),
        (10, 90),
    ]
    diamond = [(50, 0), (100, 50), (50, 100), (0, 50)]
    assert sorted(in_order(diamond)) == sorted(diamond)


def test_crossed_corners_are_not_a_sheet(photo, sheet):
    assert is_convex(sheet)
    crossed = [sheet[0], sheet[2], sheet[1], sheet[3]]
    assert not is_convex(crossed)
    with pytest.raises(PhotoError):
        straighten(open_photo(photo), crossed)


def test_a_photo_with_no_sheet_uses_all_of_it(tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 200), False)
    pix.clear_with(128)
    path = tmp_path / "gris.png"
    pix.save(path)
    assert find_paper(open_photo(path)) == [(0, 0), (299, 0), (299, 199), (0, 199)]


def test_the_photo_is_turned_as_the_camera_says(tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 200), False)
    pix.clear_with(220)
    pix.set_rect(pymupdf.IRect(0, 0, 60, 60), (0, 0, 255))  # blue at the top left
    path = tmp_path / "girada.jpg"
    path.write_bytes(with_orientation(pix.tobytes("jpg"), 6))  # held turned right
    read = open_photo(path)
    assert (read.width, read.height) == (200, 400)
    red, green, blue = read.pixel(read.width - 10, 10)
    assert blue > 200 and red < 80, "the blue corner is now at the top right"


def test_what_is_not_a_picture_says_so(tmp_path):
    path = tmp_path / "nota.jpg"
    path.write_text("no soy una foto")
    with pytest.raises(PhotoError):
        open_photo(path)


def test_a_pdf_with_a_page_for_each_photo(photo, tmp_path, photo_of_paper):
    other = photo_of_paper(tmp_path / "otra.jpg", shadow=False)
    target = tmp_path / "escaneado.pdf"
    seen = []
    write_pdf([Photo(photo), Photo(other, turns=2)], target, progress=lambda *a: seen.append(a))
    assert seen[0] == (0, 2) and seen[-1] == (2, 2)
    with pymupdf.open(target) as doc:
        assert doc.page_count == 2
        assert doc[0].rect.width == pytest.approx(595)
        assert doc[0].rect.height > 595, "as tall as the sheet in the photo"
        assert doc[0].get_images() and not doc[0].get_text().strip()
    assert not list(tmp_path.glob(".*.tmp")), "nothing is left half written"


def test_stopping_writes_nothing(photo, tmp_path):
    target = tmp_path / "escaneado.pdf"
    with pytest.raises(PhotoError):
        write_pdf([Photo(photo)], target, progress=lambda done, total: False)
    assert not target.exists()


def test_black_and_white_pages_are_small(photo, tmp_path):
    color, plain = tmp_path / "color.pdf", tmp_path / "bn.pdf"
    write_pdf([Photo(photo)], color, DOCUMENT)
    write_pdf([Photo(photo)], plain, BLACK_WHITE)
    assert plain.stat().st_size < color.stat().st_size


def test_the_page_is_as_wide_as_an_a4_sheet():
    assert page_size(1654, 2339) == pytest.approx((595, 841.4), abs=0.5)
    assert page_size(2339, 1654) == pytest.approx((841.4, 595), abs=0.5)
    assert page_size(1000, 1000) == (595, 595)


def test_the_corners_given_are_used(photo, tmp_path, sheet):
    pix = open_photo(photo)
    corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)]  # the top half
    page = photo_scan.scanned(Photo(photo, corners=corners), PHOTO)
    assert page.width > page.height
    small = open_photo(photo, longest=300)
    found = photo_scan.as_shares(small, find_paper(small))
    assert photo_scan.in_pixels(pix, found)[2] == pytest.approx(sheet[2], abs=12), (
        "corners found in a small copy hold for the whole photo"
    )
