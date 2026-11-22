"""PDF forms: the fields of a page and filling them in.

A form PDF has fields (AcroForm): boxes to write in, check boxes, round
options (radio buttons), drop-down lists and lists. Filling one is a change
like any other (``FillField``): it can be undone, it goes to the recovery
journal, and it is saved as a standard form, so every reader shows the
value. The engine draws again how the field looks with the new value.

A list may keep a code for each choice and show a name ("28" is shown as
"Madrid"): here a choice is always its name, and the code is what is written
in the PDF, as the standard asks.

Signature fields and push buttons are not filled here, nor hidden fields.
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
# Annotation flags (PDF 1.7, 12.5.3): not shown on the screen.
_HIDDEN = (1 << 1) | (1 << 5)


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
    password: bool = False  # what is written is not shown
    several: bool = False  # a list with more than one choice taken

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
        value = value[0] if value else ""
    value = "" if value is None else str(value)
    if kind in (COMBO, LIST):
        return _names(widget).get(value, value)
    return value


def _pairs(widget) -> list[tuple[str, str]]:
    """(code written in the PDF, name shown) of each choice of a list."""
    found = []
    for choice in widget.choice_values or ():
        # PDF 1.7, 12.7.4.4: a choice is a text, or [code, name shown].
        if isinstance(choice, (list, tuple)) and len(choice) >= 2:
            found.append((str(choice[0]), str(choice[1])))
        elif isinstance(choice, (list, tuple)):
            found.append((str(choice[0]), str(choice[0])) if choice else ("", ""))
        else:
            found.append((str(choice), str(choice)))
    return found


def _names(widget) -> dict[str, str]:
    return {code: name for code, name in _pairs(widget)}


def _choices(widget) -> tuple[str, ...]:
    return tuple(name for _code, name in _pairs(widget))


def _several(doc, widget) -> bool:
    """Whether a list has more than one choice taken (which PyMuPDF cannot write)."""
    kind, value = doc.xref_get_key(_field_object(doc, widget.xref), "V")
    return kind == "array" and value.count("(") + value.count("<") > 1


def _hidden(doc, xref: int) -> bool:
    kind, flags = doc.xref_get_key(xref, "F")
    try:
        return kind == "int" and bool(int(flags) & _HIDDEN)
    except ValueError:
        return False


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
            if _hidden(doc, widget.xref):
                continue  # not on the screen: nothing to fill there
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
                    password=kind == TEXT and bool(flags & PASSWORD),
                    several=kind == LIST and _several(doc, widget),
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
    import pymupdf

    if kind in (TEXT, COMBO, LIST) and not value:
        # The engine leaves a value as it was when given an empty one.
        doc.xref_set_key(_field_object(doc, widget.xref), "V", "()")
        widget.field_value = ""
        widget.update()
        return
    if kind in (CHECK, RADIO):
        # Only the box whose "on" is the one chosen is on: several boxes with
        # one name ("Sí" and "No") are one answer, like round options.
        on = _on_state(widget)
        chosen = bool(value) and value == on
        if kind == CHECK:
            widget.field_value = chosen
        else:
            widget.field_value = on if chosen else False
        widget.update()
        return
    code = value
    if kind in (COMBO, LIST):
        # The name is shown (and drawn); the code of that choice is written.
        code = next((code for code, name in _pairs(widget) if name == value), value)
    widget.field_value = value
    widget.update()
    if code != value:
        doc.xref_set_key(_field_object(doc, widget.xref), "V", pymupdf.get_pdf_str(code))


def _set_state(doc, widgets, value: str) -> None:
    """The value of a group of boxes written as the standard wants it: the
    name of the "on" chosen (/Off for none), the same as the box shows."""
    kind, state = "name", "/Off"
    for widget in widgets:
        if value and _on_state(widget) == value:
            kind, state = doc.xref_get_key(widget.xref, "AS")
            break
    if kind == "name" and widgets:
        doc.xref_set_key(_field_object(doc, widgets[0].xref), "V", state)


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
        boxes = self.kind in (CHECK, RADIO)
        later, every = [], []
        for number in range(doc.page_count):
            page = doc[number]
            widgets = [w for w in page.widgets() or () if w.field_name == self.name]
            for widget in widgets:
                every.append(widget)
                if boxes and value and _on_state(widget) == value:
                    later.append(widget)  # the one chosen goes last
                    continue
                _set(doc, widget, self.kind, value)
            if widgets:
                changed.append(number)
        for widget in later:  # its "on" must not be turned off by the others
            _set(doc, widget, self.kind, value)
        if not changed:
            raise CommandError(f"no field {self.name}")
        if boxes:
            _set_state(doc, every, value)
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
