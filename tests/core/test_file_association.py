"""Tests for offering the program to Windows as a PDF program."""

import re
import sys
import uuid
from pathlib import Path

import pytest

from app.core import file_association as fa

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = r"C:\Programas\Lector-PDF\Lector-PDF.exe"
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows registry")


def test_the_open_command_passes_the_document_in_quotes():
    assert fa.open_command(PROGRAM) == f'"{PROGRAM}" "%1"'


def test_entries_offer_the_program_for_pdf_and_nothing_else():
    entries = fa.registry_entries(PROGRAM)
    keys = [key for key, _name, _value in entries]
    assert rf"Software\Classes\{fa.PROG_ID}\shell\open\command" in keys
    assert (r"Software\Classes\.pdf\OpenWithProgids", fa.PROG_ID, "") in entries
    assert (r"Software\RegisteredApplications", "Lector-PDF", fa._CAPABILITIES) in entries
    # It never makes itself the default program: the ".pdf" key itself is not written.
    assert all(key.lower() != r"software\classes\.pdf" for key in keys)
    assert all(key.startswith("Software\\") for key in keys)


def test_everything_written_is_also_removed():
    for key, name, _value in fa.registry_entries(PROGRAM):
        own = any(key == k or key.startswith(k + "\\") for k in fa.OWN_KEYS)
        assert own or (key, name) in fa.SHARED_VALUES, key


def test_the_installer_writes_the_same_entries():
    script = (ROOT / "packaging" / "instalador.iss").read_text(encoding="utf-8")
    assert "ChangesAssociations=yes" in script
    lines = [line for line in script.splitlines() if line.startswith("Root: HKA;")]
    written = set()
    for line in lines:
        key = re.search(r'Subkey: "([^"]*)"', line).group(1)
        name = re.search(r'ValueName: "([^"]*)"', line)
        written.add((key, name.group(1) if name else ""))
    wanted = {(key, name) for key, name, _value in fa.registry_entries(PROGRAM)}
    assert written == wanted


def test_outside_windows_nothing_is_done():
    if sys.platform == "win32":
        pytest.skip("only where there is no registry")
    assert fa.available() is False
    assert fa.register(PROGRAM) is False
    assert fa.is_registered(PROGRAM) is False
    assert fa.unregister() is False
    assert fa.open_windows_default_programs() is False


@pytest.fixture
def scratch():
    """A corner of the registry only for this test, removed afterwards."""
    import winreg

    prefix = rf"Software\Lector-PDF-pruebas\{uuid.uuid4().hex}" + "\\"
    yield prefix
    fa._delete_tree(winreg, prefix.rstrip("\\"))


@windows_only
def test_register_check_and_unregister(scratch):
    import winreg

    assert not fa.is_registered(PROGRAM, scratch)
    assert fa.register(PROGRAM, scratch)
    assert fa.is_registered(PROGRAM, scratch)
    assert not fa.is_registered(r"D:\otro\Lector-PDF.exe", scratch)  # the folder was moved

    # Another program's entry in a shared key must survive.
    shared = scratch + r"Software\Classes\.pdf\OpenWithProgids"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, shared, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "OtroPrograma.PDF", 0, winreg.REG_SZ, "")

    assert fa.unregister(scratch)
    assert not fa.is_registered(PROGRAM, scratch)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, shared) as key:
        assert winreg.QueryValueEx(key, "OtroPrograma.PDF")[0] == ""
        with pytest.raises(OSError):
            winreg.QueryValueEx(key, fa.PROG_ID)
    for own in fa.OWN_KEYS:
        with pytest.raises(OSError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, scratch + own)


@windows_only
def test_registering_twice_is_harmless(scratch):
    assert fa.register(PROGRAM, scratch)
    assert fa.register(PROGRAM, scratch)
    assert fa.is_registered(PROGRAM, scratch)
