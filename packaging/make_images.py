"""Draw the image files that are kept in the repository.

Usage (from the repository root, only after changing the logo or the colours):
    python packaging/make_images.py

Result:
- ``packaging/lector-pdf.ico``: the icon of the program file and the installer.
- ``app/recursos/interfaz/marca-*.png``: the tick of a checked box, one per theme.
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

from app.ui import icons, theme  # noqa: E402

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
TICK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" fill="none" stroke="{colour}" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4.5 9.3l3 3 6-6.3"/></svg>'
)
TICK_PIXELS = 54  # three times the size on screen: sharp at any Windows scale


def render(svg: str, pixels: int) -> QImage:
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter, QRectF(0, 0, pixels, pixels))
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def ico_bytes(images: list[bytes], sizes: tuple[int, ...]) -> bytes:
    """An .ico file is a small index followed by one PNG per size."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b""
    for data, size in zip(images, sizes, strict=True):
        side = 0 if size >= 256 else size  # 0 means 256 in this format
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(images)


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(["make_images", "-platform", "offscreen"])
    logos = [png_bytes(render(icons.LOGO, size)) for size in ICO_SIZES]
    (ROOT / "packaging" / "lector-pdf.ico").write_bytes(ico_bytes(logos, ICO_SIZES))
    folder = ROOT / "app" / "recursos" / "interfaz"
    folder.mkdir(parents=True, exist_ok=True)
    for name, colours in (("clara", theme.LIGHT), ("oscura", theme.DARK)):
        tick = render(TICK.format(colour=colours.on_accent), TICK_PIXELS)
        (folder / f"marca-{name}.png").write_bytes(png_bytes(tick))
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
