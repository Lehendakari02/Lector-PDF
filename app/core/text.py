"""Text helpers shared by the document search and the function finder."""

import unicodedata

# "ñ" is a letter of its own in Spanish: "año" (year) must never match "ano".
_KEEP = {"ñ"}

# Documents carry typographic quotes and dashes; the keyboard writes ' " and -.
# Each one becomes the keyboard sign, so that "d'Hondt" finds "d’Hondt" and
# "coste-beneficio" finds "coste–beneficio".
_KEYBOARD_SIGNS = {
    **dict.fromkeys("’‘‚‛′´`", "'"),
    **dict.fromkeys("“”„‟″«»", '"'),
    **dict.fromkeys("‐‑‒–—―−", "-"),
}


def normalize_for_search(text: str) -> str:
    """Lower-case ``text`` and remove accents, keeping "ñ" as it is.

    "Artículo" becomes "articulo" and "CAMIÓN" becomes "camion", but "Año"
    becomes "año", not "ano". Typographic quotes, apostrophes and dashes become
    the ones of the keyboard. The result has as many characters as ``text``
    has after joining separate accents.
    """
    result = []
    for char in unicodedata.normalize("NFC", text).lower():
        if char in _KEEP:
            result.append(char)
            continue
        sign = _KEYBOARD_SIGNS.get(char)
        if sign is not None:
            result.append(sign)
            continue
        decomposed = unicodedata.normalize("NFD", char)
        result.append("".join(c for c in decomposed if not unicodedata.combining(c)))
    return "".join(result)
