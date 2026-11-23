"""Tests for joining, cutting and taking pages out into new documents."""

import pymupdf
import pytest

from app.core.combine import (
    CombineError,
    NeedsPassword,
    Source,
    every,
    extract,
    free_name,
    merge,
    outline_parts,
    parse_ranges,
    part_names,
    safe_name,
    split,
)


def make(path, name, count, outline=None):
    doc = pymupdf.open()
    for number in range(count):
        page = doc.new_page()
        page.insert_text((72, 72), f"{name} {number + 1}")
    doc[0].add_text_annot((100, 100), f"nota de {name}")
    if outline:
        doc.set_toc(outline)
    doc.save(path)
    doc.close()
    return path


def texts(path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text().strip() for page in doc]


def outline(path):
    with pymupdf.open(path) as doc:
        return doc.get_toc()


@pytest.fixture
def three(tmp_path):
    return [
        make(tmp_path / "tema1.pdf", "A", 2, [[1, "Intro", 1], [2, "Detalle", 2]]),
        make(tmp_path / "tema2.pdf", "B", 1),
        make(tmp_path / "tema3.pdf", "C", 3),
    ]


def test_joining_puts_every_page_in_order(three, tmp_path):
    target = tmp_path / "unido.pdf"
    assert merge([Source(path) for path in three], target) == 6
    assert texts(target) == ["A 1", "A 2", "B 1", "C 1", "C 2", "C 3"]
    with pymupdf.open(target) as doc:
        assert [annot.info["content"] for annot in doc[2].annots()] == ["nota de B"]


def test_each_document_is_an_entry_of_the_outline(three, tmp_path):
    target = tmp_path / "unido.pdf"
    merge([Source(path) for path in three], target)
    assert outline(target) == [
        [1, "tema1", 1],
        [2, "Intro", 1],
        [3, "Detalle", 2],
        [1, "tema2", 3],
        [1, "tema3", 4],
    ]


def test_a_document_with_a_password_needs_it(tmp_path, sample):
    locked = sample("con-contrasena.pdf")
    other = make(tmp_path / "a.pdf", "A", 1)
    with pytest.raises(NeedsPassword) as told:
        merge([Source(other), Source(locked)], tmp_path / "u.pdf")
    assert told.value.path == locked
    assert merge([Source(other), Source(locked, "lector")], tmp_path / "u.pdf") >= 2


def test_a_damaged_document_is_told_and_nothing_is_left(tmp_path):
    bad = tmp_path / "roto.pdf"
    bad.write_bytes(b"esto no es un pdf")
    good = make(tmp_path / "a.pdf", "A", 1)
    with pytest.raises(CombineError):
        merge([Source(good), Source(bad)], tmp_path / "u.pdf")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a.pdf", "roto.pdf"]


def test_the_result_never_goes_over_a_document_used(three):
    with pytest.raises(CombineError):
        merge([Source(path) for path in three], three[1])
    assert texts(three[1]) == ["B 1"]


def test_ranges_as_people_write_them():
    assert parse_ranges("1-3, 5, 7-", 9) == [[0, 1, 2], [4], [6, 7, 8]]
    assert parse_ranges("-2; 3–4", 4) == [[0, 1], [2, 3]]
    for wrong in ("", "0", "3-1", "1-12", "a", "-"):
        with pytest.raises(ValueError):
            parse_ranges(wrong, 10)


def test_parts_of_so_many_pages():
    assert every(7, 3) == [[0, 1, 2], [3, 4, 5], [6]]
    assert every(2, 5) == [[0, 1]]


def test_file_names_of_the_parts():
    assert part_names("ley", 2) == ["ley - parte 1.pdf", "ley - parte 2.pdf"]
    assert part_names("ley", 10)[0] == "ley - parte 01.pdf"
    assert part_names("ley", 2, ["Título I: ¿qué?", ""]) == [
        "ley - 1 Título I ¿qué.pdf",
        "ley - parte 2.pdf",
    ]
    assert safe_name('a/b\\c:"d"*?') == "a b c d"


def test_cutting_into_parts_keeps_their_sections(tmp_path):
    source = make(
        tmp_path / "ley.pdf",
        "L",
        6,
        [[1, "Título I", 1], [2, "Art 1", 2], [1, "Título II", 4], [2, "Art 5", 5]],
    )
    made = split(Source(source), [[0, 1, 2], [3, 4, 5]], tmp_path, part_names("ley", 2))
    assert [path.name for path in made] == ["ley - parte 1.pdf", "ley - parte 2.pdf"]
    assert texts(made[1]) == ["L 4", "L 5", "L 6"]
    assert outline(made[0]) == [[1, "Título I", 1], [2, "Art 1", 2]]
    assert outline(made[1]) == [[1, "Título II", 1], [2, "Art 5", 2]]
    assert texts(source) == [f"L {n}" for n in range(1, 7)], "the original is not touched"


def test_parts_never_go_over_files_already_there(tmp_path):
    source = make(tmp_path / "ley.pdf", "L", 2)
    (tmp_path / "ley - parte 1.pdf").write_bytes(b"mio")
    made = split(Source(source), [[0], [1]], tmp_path, part_names("ley", 2))
    assert made[0].name == "ley - parte 1 (2).pdf"
    assert (tmp_path / "ley - parte 1.pdf").read_bytes() == b"mio"
    assert free_name(tmp_path / "otro.pdf") == tmp_path / "otro.pdf"


def test_the_main_sections_of_the_outline(tmp_path):
    source = make(
        tmp_path / "ley.pdf",
        "L",
        6,
        [[1, "Preámbulo", 2], [1, "Título I", 3], [2, "Art 1", 3], [1, "Título II", 5]],
    )
    assert outline_parts(source) == [
        ("Preámbulo", [0, 1]),
        ("Título I", [2, 3]),
        ("Título II", [4, 5]),
    ]
    assert outline_parts(make(tmp_path / "sin.pdf", "S", 3)) == []


def test_taking_pages_out_into_a_new_document(tmp_path):
    source = make(tmp_path / "doc.pdf", "D", 5)
    target = tmp_path / "trozo.pdf"
    target.write_bytes(b"viejo")
    assert extract(Source(source), [3, 0], target) == target
    assert texts(target) == ["D 4", "D 1"]
    with pytest.raises(CombineError):
        extract(Source(source), [0], source)


def test_under_a_single_title_the_sections_inside_it(tmp_path):
    source = make(
        tmp_path / "ley.pdf",
        "L",
        5,
        [[1, "Ley", 1], [2, "Preámbulo", 2], [2, "Título I", 2], [2, "Título II", 4]],
    )
    assert outline_parts(source) == [("Preámbulo", [0, 1, 2]), ("Título II", [3, 4])]


def test_the_boe_is_cut_by_its_titles(sample):
    parts = outline_parts(sample("boe.pdf"))
    assert len(parts) > 5
    assert parts[0][0] == "[Preámbulo]"
    assert any(title.startswith("TÍTULO I") for title, _pages in parts)
