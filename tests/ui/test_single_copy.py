"""Tests for opening a second PDF while the program is already open."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_files_from_another_copy_open_in_tabs_and_the_window_comes_forward(window, sample):
    window.open_document(sample("boe.pdf"))
    window.showMinimized()
    window.open_from_another_copy([str(sample("largo.pdf")), str(sample("boe.pdf"))])
    assert [page.path.name for page in window.documents] == ["boe.pdf", "largo.pdf"]
    assert window.current_document.path.name == "boe.pdf"  # the last one asked for
    assert not window.isMinimized()


def test_starting_again_without_files_only_brings_the_window_forward(window, sample):
    window.open_document(sample("boe.pdf"))
    window.showMinimized()
    window.open_from_another_copy([])
    assert len(window.documents) == 1
    assert not window.isMinimized()


def _session(settings_file: Path) -> list[str]:
    try:
        stored = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [Path(p).name for p in stored.get("sesion", {}).get("abiertos", [])]


def test_a_second_start_hands_its_pdf_to_the_program_already_open(tmp_path, sample):
    """The real thing: two starts of the program, one window, two tabs."""
    environment = dict(os.environ)
    environment["LOCALAPPDATA"] = environment["XDG_DATA_HOME"] = str(tmp_path)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    command = [sys.executable, "-m", "app.main"]
    settings_file = tmp_path / "Lector-PDF" / "ajustes.json"

    first = subprocess.Popen([*command, str(sample("boe.pdf"))], cwd=ROOT, env=environment)
    try:
        deadline = time.monotonic() + 60
        while _session(settings_file) != ["boe.pdf"]:
            assert first.poll() is None, "the program ended by itself"
            assert time.monotonic() < deadline, "the program did not open the first PDF"
            time.sleep(0.1)

        # Started again with another PDF: it ends at once, without a second window…
        second = subprocess.run(
            [*command, str(sample("largo.pdf"))], cwd=ROOT, env=environment, timeout=60
        )
        assert second.returncode == 0
        # …and the window that was open has both documents.
        deadline = time.monotonic() + 60
        while _session(settings_file) != ["boe.pdf", "largo.pdf"]:
            assert time.monotonic() < deadline, "the second PDF did not reach the first window"
            time.sleep(0.1)
        assert first.poll() is None
    finally:
        first.kill()
        first.wait(30)
