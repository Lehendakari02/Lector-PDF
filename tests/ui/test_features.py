"""Tests for the list of functions and the search used by the finder."""

from app.ui.features import FEATURES, MODES, Mode, features_of, search_features


def ids(query: str) -> list[str]:
    return [feature.id for feature in search_features(query)]


def test_every_mode_has_tools_and_ids_are_unique():
    for mode in MODES:
        assert features_of(mode)
    all_ids = [feature.id for feature in FEATURES]
    assert len(all_ids) == len(set(all_ids))


def test_empty_search_lists_everything():
    assert len(search_features("")) == len(FEATURES)
    assert len(search_features("   ")) == len(FEATURES)


def test_finds_functions_whatever_their_mode():
    assert ids("firmar")[:2] == ["sign_drawn", "sign_certificate"]
    assert ids("unir")[0] == "merge"
    assert ids("rotar")[0] == "rotate"


def test_ignores_accents_and_capitals():
    assert ids("indice")[0] == "outline"
    assert ids("ÍNDICE")[0] == "outline"
    assert ids("contrasena") == []  # "ñ" is not "n"
    assert ids("contraseña")[0] == "password"


def test_finds_by_other_words_people_use():
    assert "merge" in ids("juntar")
    assert "highlight" in ids("fosforito")
    assert "sign_certificate" in ids("dnie")
    assert "redact" in ids("censurar")


def test_several_words_must_all_match():
    assert ids("firmar certificado") == ["sign_certificate"]
    assert ids("firmar zzz") == []


def test_typing_a_mode_name_lists_its_functions():
    found = search_features("organizar")
    assert found and all(feature.mode is Mode.ORGANIZE for feature in found)


def test_nothing_found_gives_an_empty_list():
    assert search_features("xyzxyz") == []
