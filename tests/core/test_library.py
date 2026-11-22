"""Tests for the syllabus library: the topics of a folder, searched all at once."""

import shutil
import time

import pymupdf

from app.core.library import LibraryWork, natural_key, search_topic, topic_info, topics_in


def folder_of(tmp_path, sample):
    root = tmp_path / "temario"
    (root / "Bloque 2").mkdir(parents=True)
    (root / ".oculta").mkdir()
    shutil.copy(sample("boe.pdf"), root / "Tema 10.pdf")
    shutil.copy(sample("texto-partido.pdf"), root / "Tema 2.pdf")
    shutil.copy(sample("boe.pdf"), root / "Bloque 2" / "Tema 1.PDF")
    shutil.copy(sample("boe.pdf"), root / ".oculta" / "no.pdf")
    (root / "notas.txt").write_text("no es un pdf")
    (root / "roto.pdf").write_bytes(b"%PDF-1.7 roto")
    return root


def test_the_topics_of_a_folder_in_natural_order(tmp_path, sample):
    root = folder_of(tmp_path, sample)
    names = [str(path.relative_to(root)).replace("\\", "/") for path in topics_in(root)]
    assert names == ["Bloque 2/Tema 1.PDF", "roto.pdf", "Tema 2.pdf", "Tema 10.pdf"]
    assert topics_in(None) == [] and topics_in(tmp_path / "no-existe") == []
    assert natural_key(root / "Tema 9.pdf") < natural_key(root / "tema 10.pdf")


def test_what_is_known_of_each_topic(tmp_path, sample):
    root = folder_of(tmp_path, sample)
    path = root / "Tema 10.pdf"
    with pymupdf.open(path) as doc:
        doc[0].add_highlight_annot(doc[0].rect + (50, 50, -400, -600))
        doc.saveIncr()
    info = topic_info(path)
    assert info.pages > 1 and info.marks == 1 and info.problem == ""
    assert topic_info(root / "roto.pdf").problem == "damaged"


def test_searching_a_topic_follows_the_search_rules(tmp_path, sample):
    root = folder_of(tmp_path, sample)
    hits = list(search_topic(root / "Tema 10.pdf", "constitucion"))
    assert hits and all(hit.path == root / "Tema 10.pdf" for hit in hits)
    assert "onstituci" in hits[0].match
    assert list(search_topic(root / "roto.pdf", "a")) == []


def wait_for(work, seconds=60):
    found, end = [], time.monotonic() + seconds
    while not work.finished and time.monotonic() < end:
        found += work.messages()
        time.sleep(0.02)
    return found


def test_the_work_is_done_in_another_process_and_can_be_stopped(tmp_path, sample):
    root = folder_of(tmp_path, sample)
    topics = topics_in(root)
    looked = wait_for(LibraryWork(topics))
    infos = [message[1] for message in looked if message[0] == "info"]
    assert [info.path for info in infos] == topics
    searched = wait_for(LibraryWork(topics, "constitución"))
    hits = [message[1] for message in searched if message[0] == "hit"]
    assert {hit.path.name for hit in hits} == {"Tema 1.PDF", "Tema 10.pdf"}
    assert searched[-1] == ("done",)
    work = LibraryWork(topics * 50, "a")
    work.stop()
    assert work.finished
