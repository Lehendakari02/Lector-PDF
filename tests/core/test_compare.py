"""Tests for «Comparar»: what changed between two versions of a document."""

import time
from pathlib import Path

import pymupdf
import pytest

from app.core import compare, file_work
from app.core.combine import NeedsPassword, Source
from app.core.compare import ADDED, CHANGED, REMOVED, Words, compare_files, compare_words

LAW = (
    "Artículo 1. El plazo para presentar la solicitud será de treinta días hábiles, "
    "contado desde el día siguiente al de la publicación de la convocatoria. "
    "Artículo 2. La Administración resolverá en el plazo de tres meses. "
    "Artículo 3. Contra la resolución cabe recurso de alzada."
)


def words(text: str) -> Words:
    texts = text.split()
    return Words(texts, [0] * len(texts), [((0, 0, 1, 1),)] * len(texts), 1)


def make(path, *pages, width=400, password=None):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=width, height=600)
        page.insert_textbox(pymupdf.Rect(40, 40, width - 40, 560), text, fontsize=11)
    if password:
        doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password)
    else:
        doc.save(path)
    return path


def test_same_text_has_no_changes():
    assert compare_words(words(LAW), words(LAW)) == []


def test_a_changed_word_is_one_change_with_the_words_around():
    new = LAW.replace("treinta", "cuarenta")
    (change,) = compare_words(words(LAW), words(new))
    assert change.kind == CHANGED
    assert (change.old_text, change.new_text) == ("treinta", "cuarenta")
    assert change.before.endswith("solicitud será de")
    assert change.after.startswith("días hábiles")


def test_added_and_removed_words():
    new = LAW.replace("Artículo 2. La Administración resolverá en el plazo de tres meses. ", "")
    new += " Disposición final única."
    changes = compare_words(words(LAW), words(new))
    assert [c.kind for c in changes] == [REMOVED, ADDED]
    assert changes[0].old_text.startswith("Artículo 2. La Administración")
    assert changes[0].new_text == ""
    assert changes[0].after.startswith("Artículo 3.")
    assert changes[1].new_text == "Disposición final única."


def test_close_changes_are_shown_as_one():
    new = LAW.replace("treinta días hábiles", "cuarenta días naturales")
    (change,) = compare_words(words(LAW), words(new))
    assert change.old_text == "treinta días hábiles,"
    assert change.new_text == "cuarenta días naturales,"


def test_quotes_and_dashes_do_not_count_but_accents_and_capitals_do():
    old = words("dijo «sí» — y el Artículo")
    assert compare_words(old, words('dijo "sí" - y el Artículo')) == []
    assert len(compare_words(old, words("dijo «si» — y el Artículo"))) == 1
    assert len(compare_words(old, words("dijo «sí» — y el artículo"))) == 1


def test_a_long_text_with_repeated_words_is_quick():
    article = (
        "Artículo {0}. El plazo de la solicitud será de un año y la Administración "
        "resolverá en el plazo de tres meses desde la solicitud. "
    )
    old_text = "".join(article.format(n % 50) for n in range(3000))  # ~80 000 words
    new_text = old_text.replace("Artículo 7. El plazo", "Artículo 7. El término", 1)
    started = time.perf_counter()
    changes = compare_words(words(old_text), words(new_text))
    assert time.perf_counter() - started < 10
    assert [(c.old_text, c.new_text) for c in changes] == [("plazo", "término")]


def test_files_with_other_line_breaks_compare_by_their_words(tmp_path):
    old = make(tmp_path / "old.pdf", LAW, width=400)
    new = make(tmp_path / "new.pdf", LAW.replace("tres meses", "seis meses"), width=550)
    result = compare_files(Source(old), Source(new))
    (change,) = result.changes
    assert (change.old_text, change.new_text) == ("tres", "seis")
    assert result.changed == 1 and result.added == result.removed == 0
    assert change.old_spots[0].page == 0 and change.new_spots[0].page == 0
    # The marks are where the words are on the page.
    with pymupdf.open(new) as doc:
        (found,) = doc[0].search_for("seis")
    x0, y0, x1, y1 = change.new_spots[0].rects[0]
    assert abs(x0 - found.x0) < 1 and abs(y1 - found.y1) < 2


def test_a_change_knows_its_page_in_each_version(tmp_path):
    old = make(tmp_path / "old.pdf", "Primera página.", "Artículo 2. Tres meses.")
    new = make(tmp_path / "new.pdf", "Primera página. Nueva frase.", "Artículo 2. Tres meses.")
    (change,) = compare_files(Source(old), Source(new)).changes
    assert change.kind == ADDED and change.new_text == "Nueva frase."
    assert change.new_page == 0 and change.old_page == 0


def test_a_word_split_at_the_line_end_is_one_word(tmp_path):
    with pymupdf.open(Path(__file__).parents[1] / "ejemplos" / "texto-partido.pdf") as doc:
        read = compare.read_words(doc)
    assert "Artículo" in read.texts
    assert not any(word.endswith("-") and word[:-1].isalpha() for word in read.texts)


def test_passwords_and_documents_without_text(tmp_path):
    locked = make(tmp_path / "locked.pdf", LAW, password="clave")
    plain = make(tmp_path / "plain.pdf", LAW)
    with pytest.raises(NeedsPassword):
        compare_files(Source(plain), Source(locked))
    assert compare_files(Source(plain), Source(locked, "clave")).changes == []
    empty = pymupdf.open()
    empty.new_page()
    empty.save(tmp_path / "empty.pdf")
    with pytest.raises(compare.NoText):
        compare_files(Source(plain), Source(tmp_path / "empty.pdf"))


def test_compared_in_a_process_of_its_own(tmp_path):
    old = make(tmp_path / "old.pdf", LAW)
    new = make(tmp_path / "new.pdf", LAW.replace("alzada", "reposición"))
    answer = file_work.run(file_work.COMPARE, str(old), None, str(new), None)
    assert answer[0] == "compared"
    assert [c.new_text for c in answer[1].changes] == ["reposición."]
    locked = make(tmp_path / "locked.pdf", LAW, password="clave")
    assert file_work.run(file_work.COMPARE, str(old), None, str(locked), None) == (
        "needs_password",
        str(locked),
    )
    work = file_work.FileWork(file_work.COMPARE, old, None, new)
    deadline = time.monotonic() + 60
    while work.answer() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    work.stop()
    assert work.answer()[0] == "compared"
