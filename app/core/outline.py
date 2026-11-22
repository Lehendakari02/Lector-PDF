"""The outline of a document: its sections and the page where each one starts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OutlineEntry:
    """One line of the outline. ``page`` counts from 0; -1 means it leads nowhere."""

    level: int  # 1 for the main sections, 2 for those inside them...
    title: str
    page: int
    top: float | None = None  # where on the page (points, from the top), if known
    bookmark: str = ""  # the name of one of the user's bookmarks (app.core.bookmarks)
    group: bool = False  # the item that holds the user's bookmarks


def read_outline(doc) -> list[OutlineEntry]:
    """Read the outline of an open PyMuPDF document. Empty if it has none.

    Outlines written by other programs are often sloppy: empty titles, pages
    that do not exist, levels that skip steps. They are tidied here so the
    interface can show them as they come.
    """
    from app.core.bookmarks import GROUP_KEY, NAME_KEY

    try:
        raw = doc.get_toc(simple=False)
    except Exception:
        return []  # a damaged outline is the same as no outline
    entries: list[OutlineEntry] = []
    previous_level = 0
    for level, title, page, *rest in raw:
        title = " ".join(str(title).split())
        if not title:
            continue
        level = max(1, min(int(level), previous_level + 1))  # never skip a step down
        previous_level = level
        page = int(page) - 1
        if not 0 <= page < doc.page_count:
            page = -1
        details = rest[0] if rest and isinstance(rest[0], dict) else {}
        top, name, group = None, "", False
        xref = details.get("xref", 0)
        try:
            if xref:
                kind, value = doc.xref_get_key(xref, NAME_KEY)
                name = value if kind == "string" else ""
                group = doc.xref_get_key(xref, GROUP_KEY)[1] == "true"
            point = details.get("to")
            if name and point is not None and page >= 0:
                top = float(point.y)  # PyMuPDF gives it on the page as shown
        except Exception:
            pass  # a sloppy item still leads to its page
        entries.append(OutlineEntry(level, title, page, top, name, group))
    return entries
