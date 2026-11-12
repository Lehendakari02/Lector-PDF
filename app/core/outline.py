"""The outline of a document: its sections and the page where each one starts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OutlineEntry:
    """One line of the outline. ``page`` counts from 0; -1 means it leads nowhere."""

    level: int  # 1 for the main sections, 2 for those inside them...
    title: str
    page: int


def read_outline(doc) -> list[OutlineEntry]:
    """Read the outline of an open PyMuPDF document. Empty if it has none.

    Outlines written by other programs are often sloppy: empty titles, pages
    that do not exist, levels that skip steps. They are tidied here so the
    interface can show them as they come.
    """
    try:
        raw = doc.get_toc(simple=True)
    except Exception:
        return []  # a damaged outline is the same as no outline
    entries: list[OutlineEntry] = []
    previous_level = 0
    for level, title, page, *_rest in raw:
        title = " ".join(str(title).split())
        if not title:
            continue
        level = max(1, min(int(level), previous_level + 1))  # never skip a step down
        previous_level = level
        page = int(page) - 1
        if not 0 <= page < doc.page_count:
            page = -1
        entries.append(OutlineEntry(level, title, page))
    return entries
