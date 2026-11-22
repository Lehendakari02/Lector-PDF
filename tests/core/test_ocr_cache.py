"""Tests for the pages recognised kept apart while a run goes on."""

import os
import time

from app.core.ocr import OcrPage, OcrWord
from app.core.ocr_cache import OcrCache, picture_key


def test_a_page_read_comes_back_as_it_was_under_its_new_number(tmp_path):
    cache = OcrCache(tmp_path / "reconocido")
    read = OcrPage(
        3, (OcrWord((1.0, 2.0, 3.0, 4.0), "camión"),), (1, 0, 0, 1, 5, 6), 300, 1.5, 0.4, "camión"
    )
    key = picture_key(10, 20, 300, b"\x00\xff" * 100)
    assert cache.get(key, 7) is None
    assert cache.put(key, read)
    again = cache.get(key, 7)
    assert again.page == 7 and again.words == read.words and again.matrix == read.matrix
    assert again.text == "camión" and again.turned == 0.4
    cache.forget([key])
    assert cache.get(key, 7) is None


def test_another_picture_has_another_fingerprint():
    assert picture_key(10, 20, 300, b"a" * 200) != picture_key(10, 20, 300, b"b" * 200)
    assert picture_key(10, 20, 300, b"a" * 200) != picture_key(20, 10, 300, b"a" * 200)


def test_what_is_left_of_old_runs_goes_after_some_days(tmp_path):
    cache = OcrCache(tmp_path)
    read = OcrPage(0, ())
    cache.put("viejo", read)
    cache.put("nuevo", read)
    old = time.time() - 8 * 86400
    os.utime(tmp_path / "viejo.json", (old, old))
    assert cache.forget_old() == 1
    assert cache.get("viejo", 0) is None and cache.get("nuevo", 0) is not None


def test_a_damaged_file_is_not_used(tmp_path):
    cache = OcrCache(tmp_path)
    (tmp_path / "roto.json").write_text("{no", encoding="utf-8")
    assert cache.get("roto", 0) is None
