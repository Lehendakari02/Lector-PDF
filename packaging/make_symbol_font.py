"""Make the small font of symbols the program carries (run by hand, rarely).

It takes DejaVu Sans (free: Bitstream Vera licence, changes in the public
domain) and keeps only the symbols of ``app.core.symbols``. The result is
``app/recursos/letras/simbolos.ttf``, with another name, as its licence asks.

    pip install fonttools
    python packaging/make_symbol_font.py /path/to/DejaVuSans.ttf

fontTools is only needed here: the program itself does not use it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.symbols import FONT_FAMILY, SYMBOLS, font_file  # noqa: E402


def main(source: str) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.layout_features = []
    options.hinting = False
    options.notdef_outline = True
    options.drop_tables += ["FFTM"]
    font = TTFont(source)
    chooser = subset.Subsetter(options)
    chooser.populate(unicodes=[ord(symbol) for symbol in SYMBOLS])
    chooser.subset(font)
    compact = FONT_FAMILY.replace(" ", "")
    for record in font["name"].names:
        if record.nameID in (1, 4, 16):
            record.string = FONT_FAMILY
        elif record.nameID == 6:
            record.string = compact
        elif record.nameID == 3:
            record.string = f"{compact}; from DejaVu Sans"
    missing = SYMBOLS - {chr(code) for code in font.getBestCmap()}
    if missing:
        raise SystemExit(f"the source font lacks: {''.join(sorted(missing))}")
    target = font_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    font.save(target)
    print(f"{target}: {target.stat().st_size} bytes, {len(SYMBOLS)} symbols")


if __name__ == "__main__":
    main(sys.argv[1])
