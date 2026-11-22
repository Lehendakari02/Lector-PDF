"""PDF forms: the fields of a page and filling them in.

A form PDF has fields (AcroForm): boxes to write in, check boxes, round
options (radio buttons), drop-down lists and lists. Filling one is a change
like any other (``FillField``): it can be undone, it goes to the recovery
journal, and it is saved as a standard form, so every reader shows the
value. The engine draws again how the field looks with the new value.

Signature fields and push buttons are not filled here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.commands import CommandError, register_reader

TEXT = "text"
CHECK = "check"
RADIO = "radio"
COMBO = "combo"
LIST = "list"
KINDS = (TEXT, CHECK, RADIO, COMBO, LIST)

Rect = tuple[float, float, float, float]

# Field flags (PDF 1.7, 12.7.3 and 12.7.4).
READ_ONLY = 1 << 0
MULTILINE = 1 << 12
PASSWORD = 1 << 13
EDIT = 1 << 18  # a drop-down list where one can also write
MULTI_SELECT = 1 << 21


@dataclass(frozen=True)
class FormField:
    """One place of a page where a form field is shown, as this program reads it."""

    page: int
    xref: int  # of this widget (a field shown twice has two)
    name: str  # the whole name of the field ("datos.nombre")
    kind: str  # one of KINDS
    rect: Rect  # on the page as shown
    value: str  # text or choice; for a check box or an option, its "on" name or ""
    on: str = ""  # check box and option: the name of its "on" state
    choices: tuple[str, ...] = ()
    label: str = ""  # the description the form gives, if any
    read_only: bool = False
    multiline: bool = False
    max_length: int = 0  # 0: no limit
    editable: bool = False  # a drop-down list where one can also write
    font_size: float = 0.0  # 0: it fits the box

    @property
    def checked(self) -> bool:
        return self.kind in (CHECK, RADIO) and bool(self.value) and self.value == self.on

    @property
    def title(self) -> str:
        """How the field is called to the user."""
        return self.label or self.name.rsplit(".", 1)[-1].replace("_", " ")


def _kind(widget) -> str | None:
    import pymupdf

    return {
        pymupdf.PDF_WIDGET_TYPE_TEXT: TEXT,
        pymupdf.PDF_WIDGET_TYPE_CHECKBOX: CHECK,
        pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: RADIO,
        pymupdf.PDF_WIDGET_TYPE_COMBOBOX: COMBO,
        pymupdf.PDF_WIDGET_TYPE_LISTBOX: LIST,
    }.get(widget.field_type)


def _on_state(widget) -> str:
    try:
        state = widget.on_state()
    except Exception:
        return ""
    return state if isinstance(state, str) and state not in ("Off", "") else ""


def _value(widget, kind: str, on: str) -> str:
    value = widget.field_value
    if kind in (CHECK, RADIO):
        if isinstance(value, bool):
            return on if value else ""
        value = str(value or "")
        return value if value and value == on else ""
    if isinstance(value, (list, tuple)):  # a list with more than one chosen
        return str(value[0]) if value else ""
    return "" if value is None else str(value)


def _choices(widget) -> tuple[str, ...]:
    found = []
    for choice in widget.choice_values or ():
        # A choice may be [shown, exported]: what is shown is chosen.
        found.append(str(choice[0] if isinstance(choice, (list, tuple)) else choice))
    return tuple(found)


def page_fields(doc, number: int) -> list[FormField]:
    """The form fields of a page that can be filled, in the order of the form
    (top to bottom, left to right)."""
    page = doc[number]
    found = []
    for widget in page.widgets() or ():
        kind = _kind(widget)
        if kind is None:
            continue
        try:
            flags = int(widget.field_flags or 0)
            on = _on_state(widget) if kind in (CHECK, RADIO) else ""
            rect = (widget.rect * page.rotation_matrix).normalize()
            found.append(
                FormField(
                    page=number,
                    xref=widget.xref,
                    name=str(widget.field_name or ""),
                    kind=kind,
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                    value=_value(widget, kind, on),
                    on=on,
                    choices=_choices(widget) if kind in (COMBO, LIST) else (),
                    label=str(widget.field_label or ""),
                    read_only=bool(flags & READ_ONLY),
                    multiline=kind == TEXT and bool(flags & MULTILINE),
                    max_length=int(widget.text_maxlen or 0) if kind == TEXT else 0,
                    editable=kind == COMBO and bool(flags & EDIT),
                    font_size=float(widget.text_fontsize or 0.0),
                )
            )
        except Exception:
            continue  # a damaged field is left out; the rest are filled
    found.sort(key=lambda field: (round(field.rect[1]), field.rect[0]))
    return found


def _field_object(doc, xref: int) -> int:
    """The object of the field a widget shows: the first one up with a name."""
    for _step in range(20):
        if doc.xref_get_key(xref, "T")[0] != "null":
            return xref
        kind, parent = doc.xref_get_key(xref, "Parent")
        if kind != "xref":
            return xref
        xref = int(parent.split()[0])
    return xref


def _set(doc, widget, kind: str, value: str) -> None:
    if kind in (TEXT, COMBO, LIST) and not value:
        # The engine leaves a value as it was when given an empty one.
        doc.xref_set_key(_field_object(doc, widget.xref), "V", "()")
        widget.field_value = ""
        widget.update()
        return
    if kind == CHECK:
        widget.field_value = bool(value)
    elif kind == RADIO:
        widget.field_value = _on_state(widget) if value and value == _on_state(widget) else False
    else:
        widget.field_value = value
    widget.update()


@dataclass(frozen=True)
class FillField:
    """The value of a field (every place where it is shown) changes from
    ``before`` to ``after``. For a check box or an option the value is the
    name of the "on" state chosen, or "" for none. Undoing puts ``before`` back."""

    page: int  # where it was filled (the others with the same name change too)
    name: str
    kind: str
    before: str
    after: str

    def pages(self) -> list[int]:
        return [self.page]

    def _put(self, doc, value: str) -> list[int]:
        if self.kind not in KINDS or not self.name:
            raise CommandError("not a field")
        changed: list[int] = []
        later = []
        for number in range(doc.page_count):
            page = doc[number]
            widgets = [w for w in page.widgets() or () if w.field_name == self.name]
            for widget in widgets:
                if self.kind == RADIO and value and _on_state(widget) == value:
                    later.append((page, widget))  # the one chosen goes last
                    continue
                _set(doc, widget, self.kind, value)
            if widgets:
                changed.append(number)
        for _page, widget in later:  # its "on" must not be turned off by the others
            _set(doc, widget, self.kind, value)
        if not changed:
            raise CommandError(f"no field {self.name}")
        return changed

    def apply(self, doc) -> list[int]:
        return self._put(doc, self.after)

    def undo(self, doc) -> list[int]:
        return self._put(doc, self.before)

    def to_dict(self) -> dict:
        return {
            "what": "fill_field",
            "page": self.page,
            "name": self.name,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FillField:
        return cls(
            int(data["page"]),
            str(data["name"]),
            str(data["kind"]),
            str(data["before"]),
            str(data["after"]),
        )


register_reader("fill_field", FillField.from_dict)


@dataclass(frozen=True)
class FillFields:
    """Several fields filled at once (with «Mis datos»): one change, undone at once."""

    fills: tuple[FillField, ...]

    def pages(self) -> list[int]:
        return sorted({fill.page for fill in self.fills})

    def apply(self, doc) -> list[int]:
        changed: set[int] = set()
        for fill in self.fills:
            changed.update(fill.apply(doc))
        return sorted(changed)

    def undo(self, doc) -> list[int]:
        changed: set[int] = set()
        for fill in reversed(self.fills):
            changed.update(fill.undo(doc))
        return sorted(changed)

    def to_dict(self) -> dict:
        return {"what": "fill_fields", "fills": [fill.to_dict() for fill in self.fills]}

    @classmethod
    def from_dict(cls, data: dict) -> FillFields:
        return cls(tuple(FillField.from_dict(fill) for fill in data["fills"]))


register_reader("fill_fields", FillFields.from_dict)
