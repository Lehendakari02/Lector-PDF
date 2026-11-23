"""Make the small font of symbols the program carries (run by hand, rarely).

It takes DejaVu Sans and DejaVu Sans Bold (free: Bitstream Vera licence, changes
in the public domain), version 2.37, and keeps only the symbols of
``app.core.symbols`` and the letters of other languages in its ``EXTRA_RANGES``
(those the built-in letters lack). The results are
``app/recursos/letras/simbolos.ttf`` and ``simbolos-negrita.ttf``, with another
name, as the licence asks. Both carry exactly the same letters.

    pip install fonttools
    python packaging/make_symbol_font.py /path/to/DejaVuSans.ttf /path/to/DejaVuSans-Bold.ttf

fontTools is only needed here: the program itself does not use it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.symbols import EXTRA_RANGES, FONT_FAMILY, SYMBOLS, font_file  # noqa: E402


def make(source: str, bold: bool) -> set[int]:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.layout_features = []
    options.hinting = False
    options.notdef_outline = True
    options.drop_tables += ["FFTM"]
    font = TTFont(source)
    has = set(font.getBestCmap())
    letters = [
        code for first, last in EXTRA_RANGES for code in range(first, last + 1) if code in has
    ]
    chooser = subset.Subsetter(options)
    chooser.populate(unicodes=[ord(symbol) for symbol in SYMBOLS] + letters)
    chooser.subset(font)
    compact = FONT_FAMILY.replace(" ", "")
    style = "Bold" if bold else "Book"
    for record in font["name"].names:
        if record.nameID in (1, 16):
            record.string = FONT_FAMILY
        elif record.nameID == 4:
            record.string = f"{FONT_FAMILY} {style}" if bold else FONT_FAMILY
        elif record.nameID == 6:
            record.string = f"{compact}-{style}" if bold else compact
        elif record.nameID == 3:
            record.string = f"{compact}-{style}; from DejaVu Sans"
    covered = set(font.getBestCmap())
    missing = SYMBOLS - {chr(code) for code in covered}
    if missing:
        raise SystemExit(f"the source font lacks: {''.join(sorted(missing))}")
    target = font_file(bold)
    target.parent.mkdir(parents=True, exist_ok=True)
    font.save(target)
    print(
        f"{target}: {target.stat().st_size} bytes, {len(SYMBOLS)} symbols, "
        f"{len(letters)} letters of other languages"
    )
    return covered


def main(normal: str, bold: str) -> None:
    if make(normal, False) != make(bold, True):
        raise SystemExit("the normal and the bold font do not carry the same letters")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
