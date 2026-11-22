"""The summary of a document: everything marked and written on it, page by
page, to read, print or go on working with apart from the PDF.

What goes in: the words highlighted, underlined or struck out (with their
colour, and its name if the user gave it one), the notes and the texts
written on the pages. Drawings have no words and are left out.

It is written as a PDF (``write_pdf``) or as a Word document (``write_docx``,
a plain .docx made here, without any other library).
"""

from __future__ import annotations

import html
import os
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.annotation_list import Entry
from app.core.commands import HIGHLIGHT, STRIKEOUT, UNDERLINE
from app.core.notes import NOTE, TEXT_BOX

Color = tuple[float, float, float]

# The words of the summary. The interface gives them translated.
LABELS = {
    "title": "Resumen de {0}",
    "made": "Lo subrayado y anotado, página a página.",
    "page": "Página {0}",
    HIGHLIGHT: "Resaltado",
    UNDERLINE: "Subrayado",
    STRIKEOUT: "Tachado",
    NOTE: "Nota",
    TEXT_BOX: "Texto",
    "empty": "Este documento no tiene nada subrayado ni anotado.",
}
KINDS = (HIGHLIGHT, UNDERLINE, STRIKEOUT, NOTE, TEXT_BOX)
MARK_KINDS = (HIGHLIGHT, UNDERLINE, STRIKEOUT)


@dataclass(frozen=True)
class Item:
    kind: str
    text: str
    color: Color
    color_name: str = ""


@dataclass(frozen=True)
class Page:
    number: int  # from 0
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Summary:
    title: str  # the document's name
    pages: tuple[Page, ...]
    labels: dict = field(default_factory=lambda: dict(LABELS))

    @property
    def empty(self) -> bool:
        return not self.pages

    def label(self, key: str, *values) -> str:
        return str(self.labels.get(key, LABELS.get(key, key))).format(*values)


def summary_of(
    title: str,
    entries: Iterable[Entry],
    name_of: Callable[[Color], str] = lambda _color: "",
    labels: dict | None = None,
) -> Summary:
    """The summary of the annotations of a document, in reading order."""
    pages: dict[int, list[Item]] = {}
    for entry in entries:
        text = " ".join(entry.text.split())
        if entry.kind not in KINDS or not text:
            continue
        pages.setdefault(entry.page, []).append(
            Item(entry.kind, text, tuple(entry.color), name_of(entry.color))
        )
    return Summary(
        title,
        tuple(Page(number, tuple(items)) for number, items in sorted(pages.items())),
        {**LABELS, **(labels or {})},
    )


def _hex(color: Color) -> str:
    return "".join(f"{round(max(0.0, min(1.0, part)) * 255):02x}" for part in color)


def _light(color: Color) -> Color:
    """A highlight colour as it looks on paper, light enough to read on."""
    return tuple(0.55 * part + 0.45 for part in color)


def _kind_line(summary: Summary, item: Item) -> str:
    kind = summary.label(item.kind)
    return f"{kind} · {item.color_name}" if item.color_name else kind


# ---- PDF ---------------------------------------------------------------------

PAGE = (0, 0, 595, 842)  # A4, points
MARGIN = 56

_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.35; color: #222; }
h1 { font-size: 18pt; margin: 0 0 4pt 0; }
p.made { color: #666; margin: 0 0 14pt 0; }
h2 { font-size: 13pt; margin: 14pt 0 6pt 0; color: #333; }
p.kind { font-size: 8.5pt; color: #666; margin: 6pt 0 1pt 0; }
p.text { margin: 0 0 4pt 0; }
"""


def _pdf_html(summary: Summary) -> str:
    out = [
        f"<h1>{html.escape(summary.label('title', summary.title))}</h1>",
        f"<p class='made'>{html.escape(summary.label('made'))}</p>",
    ]
    if summary.empty:
        out.append(f"<p>{html.escape(summary.label('empty'))}</p>")
    for page in summary.pages:
        out.append(f"<h2>{html.escape(summary.label('page', page.number + 1))}</h2>")
        for item in page.items:
            out.append(f"<p class='kind'>{html.escape(_kind_line(summary, item))}</p>")
            words = html.escape(item.text)
            color = _hex(item.color)
            if item.kind == HIGHLIGHT:
                words = (
                    f"<span style='background-color: #{_hex(_light(item.color))}'>{words}</span>"
                )
            elif item.kind == UNDERLINE:
                words = f"<span style='text-decoration: underline; color: #{color}'>{words}</span>"
            elif item.kind == STRIKEOUT:
                words = f"<s>{words}</s>"
            elif item.kind == NOTE:
                words = f"<i>{words}</i>"
            out.append(f"<p class='text'>{words}</p>")
    return "\n".join(out)


def _safely(path: str | Path, write: Callable[[str], None]) -> None:
    """Write a file whole next to where it goes and then put it there: a
    failure never leaves half a file (nor spoils one that was there)."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        write(str(temporary))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_pdf(summary: Summary, path: str | Path) -> None:
    """Write the summary as a PDF (A4) in ``path``."""
    _safely(path, lambda target: _write_pdf(summary, target))


def _write_pdf(summary: Summary, path: str) -> None:
    import pymupdf

    story = pymupdf.Story(html=_pdf_html(summary), user_css=_CSS)
    writer = pymupdf.DocumentWriter(path)
    page_rect = pymupdf.Rect(PAGE)
    room = page_rect + (MARGIN, MARGIN, -MARGIN, -MARGIN)
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _filled = story.place(room)
        story.draw(device)
        writer.end_page()
    writer.close()


# ---- Word --------------------------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/\
vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Target="word/document.xml" Type="http://schemas.openxmlformats.org/\
officeDocument/2006/relationships/officeDocument"/>
</Relationships>"""


def _run(text: str, size: float = 11, **look) -> str:
    props = [f'<w:sz w:val="{round(size * 2)}"/>']
    if look.get("bold"):
        props.insert(0, "<w:b/>")
    if look.get("italic"):
        props.insert(0, "<w:i/>")
    if look.get("strike"):
        props.append("<w:strike/>")
    if look.get("grey"):
        props.append('<w:color w:val="666666"/>')
    if look.get("color"):
        props.append(f'<w:color w:val="{look["color"]}"/>')
    if look.get("underline"):
        props.append('<w:u w:val="single"/>')
    if look.get("fill"):
        props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{look["fill"]}"/>')
    words = html.escape(text, quote=False)
    return f'<w:r><w:rPr>{"".join(props)}</w:rPr><w:t xml:space="preserve">{words}</w:t></w:r>'


def _paragraph(runs: str, after: int = 80, before: int = 0) -> str:
    spacing = f'<w:spacing w:before="{before}" w:after="{after}"/>'
    return f"<w:p><w:pPr>{spacing}</w:pPr>{runs}</w:p>"


def _docx_body(summary: Summary) -> str:
    out = [
        _paragraph(_run(summary.label("title", summary.title), 18, bold=True), 60),
        _paragraph(_run(summary.label("made"), 11, grey=True), 240),
    ]
    if summary.empty:
        out.append(_paragraph(_run(summary.label("empty"))))
    for page in summary.pages:
        out.append(
            _paragraph(_run(summary.label("page", page.number + 1), 13, bold=True), 100, 240)
        )
        for item in page.items:
            out.append(_paragraph(_run(_kind_line(summary, item), 8.5, grey=True), 0, 100))
            look = {}
            if item.kind == HIGHLIGHT:
                look["fill"] = _hex(_light(item.color))
            elif item.kind == UNDERLINE:
                look.update(underline=True, color=_hex(item.color))
            elif item.kind == STRIKEOUT:
                look["strike"] = True
            elif item.kind == NOTE:
                look["italic"] = True
            out.append(_paragraph(_run(item.text, **look)))
    return "".join(out)


def write_docx(summary: Summary, path: str | Path) -> None:
    """Write the summary as a Word document (.docx) in ``path``."""
    _safely(path, lambda target: _write_docx(summary, target))


def _write_docx(summary: Summary, path: str) -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>{_docx_body(summary)}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"'
        ' w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("[Content_Types].xml", _CONTENT_TYPES)
        out.writestr("_rels/.rels", _RELS)
        out.writestr("word/document.xml", document)
