"""«Mis datos»: the personal data one writes again and again in forms.

They are kept only on this computer, in the settings of the program, and are
never sent anywhere. Each datum has a fixed key; the fields of a form are
matched to them by their names and descriptions ("DNI", "N.I.F.", "Domicilio",
"Código postal"…), the way people write them in Spanish forms.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SETTING = "mis_datos"

FULL_NAME = "full_name"
NAME = "name"
SURNAMES = "surnames"
ID = "id"
BIRTH = "birth"
ADDRESS = "address"
POSTCODE = "postcode"
TOWN = "town"
PROVINCE = "province"
PHONE = "phone"
EMAIL = "email"

# In the order they are shown and asked for.
KEYS = (NAME, SURNAMES, ID, BIRTH, ADDRESS, POSTCODE, TOWN, PROVINCE, PHONE, EMAIL)

# What a field is called, as words (no accents, lower case) -> the datum.
# The first rule that matches wins, so the longer ones go first.
_RULES: tuple[tuple[str, str], ...] = (
    (r"\bnombre (y|e) apellidos?\b", FULL_NAME),
    (r"\bapellidos? (y|,)? ?nombre\b", FULL_NAME),
    (r"\bnombre completo\b", FULL_NAME),
    (r"\b(solicitante|interesad[oa]|firmante|titular)\b", FULL_NAME),
    (r"\bcorreo\b|\be ?mail\b|\bemail\b", EMAIL),
    (r"\bcodigo postal\b|\bcod postal\b|\bc ?p\b", POSTCODE),
    (r"\bfecha( de)? nacimiento\b|\bnacimiento\b", BIRTH),
    (r"\bapellidos?\b|\b(primer|segundo) apellido\b", SURNAMES),
    (r"\bnombre\b", NAME),
    (r"\b(dni|nif|nie|n i f|d n i|n i e)\b|\bdocumento( de)? identidad\b", ID),
    (r"\b(numero )?(de )?documento\b|\bidentificacion\b", ID),
    (r"\bdireccion\b|\bdomicilio\b|\bcalle\b|\bvia\b", ADDRESS),
    (r"\blocalidad\b|\bmunicipio\b|\bpoblacion\b|\bciudad\b", TOWN),
    (r"\bprovincia\b", PROVINCE),
    (r"\btelefono\b|\bmovil\b|\btlf\b|\btfno\b|\btel\b", PHONE),
)


def plain_words(text: str) -> str:
    """Lower case, no accents (the ñ is kept), only letters and numbers."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(
        char
        for index, char in enumerate(text)
        # The tilde of the ñ stays; any other accent goes.
        if unicodedata.category(char) != "Mn"
        or (char == "̃" and index > 0 and text[index - 1] == "n")
    )
    text = unicodedata.normalize("NFC", text)
    # Split joined names: "codigoPostal" -> "codigo postal".
    text = re.sub(r"[^0-9a-zñ]+", " ", text)
    return " ".join(text.split())


def _camel_split(text: str) -> str:
    return re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", text)


def datum_for(*names: str) -> str | None:
    """The datum a field asks for, by what it is called (its description
    first, then its name), or None."""
    for name in names:
        words = plain_words(_camel_split(name or ""))
        if not words:
            continue
        for pattern, key in _RULES:
            if re.search(pattern, words):
                return key
    return None


@dataclass(frozen=True)
class MyData:
    """The data saved: key -> value ("" if not given)."""

    values: dict

    @classmethod
    def from_setting(cls, stored) -> MyData:
        values = {}
        if isinstance(stored, dict):
            for key in KEYS:
                value = stored.get(key, "")
                values[key] = value.strip() if isinstance(value, str) else ""
        else:
            values = {key: "" for key in KEYS}
        return cls(values)

    def to_setting(self) -> dict:
        return {key: self.values.get(key, "") for key in KEYS if self.values.get(key)}

    @property
    def empty(self) -> bool:
        return not any(self.values.get(key) for key in KEYS)

    def value(self, key: str) -> str:
        if key == FULL_NAME:
            return " ".join(
                part for part in (self.values.get(NAME, ""), self.values.get(SURNAMES, "")) if part
            )
        return self.values.get(key, "")

    def filled(self) -> list[tuple[str, str]]:
        """(key, value) of the data given, in their order."""
        return [(key, self.values[key]) for key in KEYS if self.values.get(key)]


def choice_for(value: str, choices: tuple[str, ...]) -> str | None:
    """The choice of a list that is ``value`` ("bizkaia" is "Bizkaia")."""
    wanted = plain_words(value)
    for choice in choices:
        if plain_words(choice) == wanted:
            return choice
    return None
