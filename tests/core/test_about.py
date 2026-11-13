"""Tests for what the program says about itself and the licences it carries."""

import importlib.util
from pathlib import Path

from app.core import about

ROOT = Path(__file__).resolve().parents[2]


def _build_script():
    spec = importlib.util.spec_from_file_location("build_script", ROOT / "packaging" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_notices_name_the_licence_the_source_and_the_main_parts():
    text = about.notices_text()
    assert "Affero" in text and about.SOURCE_URL in text
    for part in ("PyMuPDF", "Qt", "Tesseract", "pyHanko", "cryptography", "Python"):
        assert part in text


def test_every_licence_the_notices_mention_is_there():
    folder = about.licence_folder()
    for name in ("LGPL-3.0.txt", "GPL-3.0.txt", "Apache-2.0.txt"):
        assert name in about.notices_text()
        assert (folder / name).stat().st_size > 5000
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in about.own_licence_file().read_text("utf-8")


def test_the_built_program_looks_next_to_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(about, "is_packaged", lambda: True)
    monkeypatch.setattr(about, "program_dir", lambda: tmp_path)
    assert about.licence_folder() == tmp_path / "licencias"
    assert about.own_licence_file() == tmp_path / "licencias" / "AGPL-3.0.txt"
    assert about.notices_text() == ""  # missing files never break the window


def test_the_build_collects_the_licences_of_what_it_ships(tmp_path):
    build = _build_script()
    names = {package.name.lower().replace("_", "-") for package in build.shipped_packages()}
    assert {"pymupdf", "pyside6-essentials", "pyhanko", "cryptography", "asn1crypto"} <= names
    assert not names & build.NOT_SHIPPED

    target = tmp_path / "licencias"
    assert build.copy_licences(target) >= 8
    assert (target / about.NOTICES_NAME).is_file()
    assert (target / about.OWN_LICENCE_NAME).read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert any((target / "paquetes").glob("cryptography-*/LICENSE*"))
    assert any((target / "paquetes").glob("[pP]y[hH]anko-*/LICENSE"))
    assert build.LICENCE_FOLDER == about.BUILT_FOLDER_NAME
    assert build.OWN_LICENCE_NAME == about.OWN_LICENCE_NAME


def test_the_pinned_versions_agree_with_the_project_file():
    pinned = {}
    for line in (ROOT / "packaging" / "versiones-fijadas.txt").read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pinned[name.lower().replace("_", "-")] = version
    project = (ROOT / "pyproject.toml").read_text("utf-8")
    direct = ["PySide6_Essentials", "PyMuPDF", "pyHanko", "pytest", "ruff", "pyinstaller"]
    for name in direct:
        version = pinned[name.lower().replace("_", "-")]
        assert f'"{name}=={version}"' in project
    assert len(pinned) > len(direct)  # what they bring along is pinned too
