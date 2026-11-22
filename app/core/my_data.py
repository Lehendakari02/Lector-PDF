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
SURNAMES_NAME = "surnames_name"  # "García López, Ana"
FIRST_SURNAME = "first_surname"
SECOND_SURNAME = "second_surname"
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

# A field about someone or something else is never filled with one's data:
# "Nombre del representante", "DNI del cónyuge", "Lugar de nacimiento",
# "Tipo de documento", "Tipo de vía"…
_NOT_MINE = re.compile(
    r"\b(representante|apoderad[oa]|empresa|entidad|sociedad|razon social|padre|madre"
    r"|progenitor(a|es)?|conyuge|pareja|tutor(a|es)?|menor|hij[oa]s?|beneficiari[oa]"
    r"|testigo|cotitular|otr[oa])\b"
    r"|\b(lugar|pais|provincia|localidad|municipio|poblacion|ciudad) (de )?nacimiento\b"
    r"|\btipo\b"
)

# What a field is called, as words (no accents, lower case) -> the datum.
# The first rule that matches wins, so the longer ones go first. The words
# that only say whose it is ("del solicitante", "del interesado") come last:
# "DNI del solicitante" asks for the DNI.
_RULES: tuple[tuple[str, str], ...] = (
    (r"\bnombre (y|e) apellidos?\b", FULL_NAME),
    (r"\bapellidos? (y|,)? ?nombre\b", SURNAMES_NAME),
    (r"\bnombre completo\b", FULL_NAME),
    # "Nombre del solicitante" alone asks for the whole name.
    (r"\bnombre (del?|de la) (solicitante|interesad[oa]|firmante|titular|declarante)\b", FULL_NAME),
    (r"\bcorreo\b|\be ?mail\b|\bemail\b", EMAIL),
    (r"\bcodigo postal\b|\bcod postal\b|\bc ?p\b", POSTCODE),
    (r"\bfecha( de)? nacimiento\b|\bnacimiento\b", BIRTH),
    (r"\b(primer|1 ?e?r?) apellido\b|\bapellido (1|primero)\b", FIRST_SURNAME),
    (r"\bsegundo apellido\b|\b2 ?o? apellido\b|\bapellido (2|segundo)\b", SECOND_SURNAME),
    (r"\bapellidos?\b", SURNAMES),
    (r"\bnombre de la (via|calle)\b", ADDRESS),
    (r"\bnombre\b", NAME),
    (r"\b(dni|nif|nie|n i f|d n i|n i e)\b|\bdocumento( de)? identidad\b", ID),
    (r"\b(numero )?(de )?documento\b|\bidentificacion\b", ID),
    (r"\bdireccion\b|\bdomicilio\b|\bcalle\b|\bvia\b", ADDRESS),
    (r"\blocalidad\b|\bmunicipio\b|\bpoblacion\b|\bciudad\b", TOWN),
    (r"\bprovincia\b", PROVINCE),
    (r"\btelefono\b|\bmovil\b|\btlf\b|\btfno\b|\btel\b", PHONE),
    (r"\b(solicitante|interesad[oa]|firmante|titular|declarante)\b", FULL_NAME),
)

# The little words that belong to the surname after them ("de la Fuente").
_PARTICLES = {"de", "del", "la", "las", "los", "y", "san", "santa", "da", "das", "dos"}


def split_surnames(surnames: str) -> tuple[str, str]:
    """The first and the second surname: "de la Fuente García" is
    ("de la Fuente", "García")."""
    words = surnames.split()
    first: list[str] = []
    while words:
        word = words.pop(0)
        first.append(word)
        if word.lower() not in _PARTICLES:
            break
    return " ".join(first), " ".join(words)


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
        if _NOT_MINE.search(words):
            return None
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
        name, surnames = self.values.get(NAME, ""), self.values.get(SURNAMES, "")
        if key == FULL_NAME:
            return " ".join(part for part in (name, surnames) if part)
        if key == SURNAMES_NAME:
            return ", ".join(part for part in (surnames, name) if part)
        if key == FIRST_SURNAME:
            return split_surnames(surnames)[0]
        if key == SECOND_SURNAME:
            return split_surnames(surnames)[1]
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
