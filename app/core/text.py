"""Text helpers shared by the document search and the function finder."""

import unicodedata

# "ñ" is a letter of its own in Spanish: "año" (year) must never match "ano".
_KEEP = {"ñ"}


def normalize_for_search(text: str) -> str:
    """Lower-case ``text`` and remove accents, keeping "ñ" as it is.

    "Artículo" becomes "articulo" and "CAMIÓN" becomes "camion", but "Año"
    becomes "año", not "ano".
    """
    result = []
    for char in unicodedata.normalize("NFC", text).lower():
        if char in _KEEP:
            result.append(char)
            continue
        decomposed = unicodedata.normalize("NFD", char)
        result.append("".join(c for c in decomposed if not unicodedata.combining(c)))
    return "".join(result)
