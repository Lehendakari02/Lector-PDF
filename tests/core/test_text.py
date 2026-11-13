"""Tests for app.core.text."""

import unicodedata

import pytest

from app.core.text import normalize_for_search


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Artículo", "articulo"),
        ("CAMIÓN", "camion"),
        ("pingüino", "pinguino"),
        ("Índice", "indice"),
        ("Rellenar y firmar", "rellenar y firmar"),
        ("", ""),
    ],
)
def test_removes_accents_and_capitals(text, expected):
    assert normalize_for_search(text) == expected


def test_enye_is_its_own_letter():
    assert normalize_for_search("Año") == "año"
    assert normalize_for_search("AÑO") == "año"
    assert normalize_for_search("año") != normalize_for_search("ano")
    assert normalize_for_search("España") == "españa"


def test_enye_written_as_n_plus_tilde_mark_is_still_enye():
    decomposed = unicodedata.normalize("NFD", "año")
    assert len(decomposed) == 4
    assert normalize_for_search(decomposed) == "año"


def test_accent_written_as_separate_mark_is_removed():
    assert normalize_for_search(unicodedata.normalize("NFD", "artículo")) == "articulo"


def test_typographic_quotes_and_dashes_become_the_keyboard_ones():
    assert normalize_for_search("d\u2019Hondt") == "d'hondt"
    assert normalize_for_search("\u201cHola\u201d \u00abadiós\u00bb") == '"hola" "adios"'
    assert normalize_for_search("coste\u2013beneficio \u2014así\u2014") == "coste-beneficio -asi-"
    assert len(normalize_for_search("semi\u2010nuevo")) == len("semi-nuevo")
