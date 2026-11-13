"""Tests for looking for, downloading and installing new versions (no network used)."""

import hashlib
import io
import json
import subprocess
import sys
import urllib.error
import zipfile

import pytest

from app.core import updates
from app.core.updates import (
    Asset,
    Release,
    UpdateCancelled,
    UpdateError,
    apply_portable_update,
    clean_leftovers,
    download,
    fetch_latest,
    installer_command,
    is_newer,
    newer_release,
    parse_release,
    parse_version,
    portable_update_command,
    replace_program,
    unpack_portable,
    wait_for_exit,
)

PREFIX = updates.DOWNLOAD_PREFIX


def github_release(tag="v0.2.0", assets=None, **more):
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/{updates.REPOSITORY}/releases/tag/{tag}",
        "draft": False,
        "prerelease": False,
        "assets": assets if assets is not None else [],
        **more,
    }


def github_asset(name, content=b"x" * 10, digest=True, url=None):
    item = {
        "name": name,
        "browser_download_url": url or f"{PREFIX}v0.2.0/{name}",
        "size": len(content),
    }
    if digest:
        item["digest"] = "sha256:" + hashlib.sha256(content).hexdigest()
    return item


class FakeGitHub:
    """Answers the addresses it was given, like ``urlopen``; remembers what was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def __call__(self, url, timeout):
        self.asked.append(url)
        answer = self.answers.get(url)
        if answer is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)


# ---- versions ----


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("v0.1.0", (0, 1, 0, 0)),
        ("1.2", (1, 2, 0, 0)),
        (" v2.0.1 ", (2, 0, 1, 0)),
        ("3", (3, 0, 0, 0)),
    ],
)
def test_version_numbers(text, numbers):
    assert parse_version(text) == numbers


@pytest.mark.parametrize("text", ["", "prueba", "v1.2-beta", "1.2.3.4.5", "v", "1..2"])
def test_names_that_are_not_versions(text):
    assert parse_version(text) is None


def test_which_version_is_newer():
    assert is_newer("0.2.0", "0.1.0")
    assert is_newer("v0.10.0", "0.9.9")  # as numbers, not as text
    assert is_newer("1.0", "0.99.99")
    assert not is_newer("0.1.0", "0.1.0")
    assert not is_newer("0.1", "0.1.0")
    assert not is_newer("0.0.9", "0.1.0")
    assert not is_newer("beta", "0.1.0")


# ---- what GitHub says ----


def test_a_release_is_read_with_its_files():
    release = parse_release(
        github_release(
            assets=[
                github_asset("Lector-PDF-0.2.0-instalador.exe"),
                github_asset("Lector-PDF-0.2.0-portatil.zip", digest=False),
            ]
        )
    )
    assert release.version == "0.2.0"
    assert release.page.endswith("/releases/tag/v0.2.0")
    assert release.asset(portable=False).name == "Lector-PDF-0.2.0-instalador.exe"
    assert len(release.asset(portable=False).sha256) == 64
    assert release.asset(portable=True).sha256 == ""


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        github_release(draft=True),
        github_release(prerelease=True),
        github_release(tag="pruebas"),
        {"assets": []},
    ],
)
def test_drafts_tests_and_nonsense_are_not_versions(data):
    assert parse_release(data) is None


def test_files_from_somewhere_else_are_ignored():
    release = parse_release(
        github_release(
            assets=[
                github_asset("Lector-PDF-0.2.0-instalador.exe", url="https://malo.example/x.exe"),
                {"name": "sin-datos"},
                "texto",
            ]
        )
    )
    assert release.assets == {}
    assert release.asset(portable=False) is None


def test_asking_github_for_the_latest_version():
    github = FakeGitHub({updates.LATEST_URL: json.dumps(github_release()).encode()})
    assert fetch_latest(github).version == "0.2.0"
    assert github.asked == [updates.LATEST_URL]  # nothing else is contacted
    assert newer_release("0.1.0", github).version == "0.2.0"
    assert newer_release("0.2.0", github) is None
    assert newer_release("0.3.0", github) is None


def test_no_published_version_yet_is_not_an_error():
    assert fetch_latest(FakeGitHub({})) is None  # 404: none yet, or the project is private


def test_no_connection_is_reported():
    github = FakeGitHub({updates.LATEST_URL: OSError("no network")})
    with pytest.raises(UpdateError):
        fetch_latest(github)
    github = FakeGitHub({updates.LATEST_URL: b"<html>not json"})
    with pytest.raises(UpdateError):
        fetch_latest(github)


def test_requests_say_only_the_name_of_the_program(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["headers"] = dict(request.header_items())
        seen["url"] = request.full_url
        seen["data"] = request.data
        return io.BytesIO(json.dumps(github_release()).encode())

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    fetch_latest()
    assert seen["url"] == updates.LATEST_URL
    assert seen["data"] is None
    assert seen["headers"]["User-agent"] == "Lector-PDF"
    assert set(seen["headers"]) == {"User-agent", "Accept"}


# ---- downloading ----


def published(content, name="Lector-PDF-0.2.0-instalador.exe", digest=True):
    release = parse_release(github_release(assets=[github_asset(name, content, digest)]))
    return release, release.assets[name]


def test_a_download_that_matches_is_kept(tmp_path):
    content = bytes(range(256)) * 4000
    release, asset = published(content)
    steps = []
    file = download(
        release,
        asset,
        tmp_path / "d",
        lambda got, total: steps.append((got, total)),
        opener=FakeGitHub({asset.url: content}),
    )
    assert file.read_bytes() == content
    assert steps[-1] == (len(content), len(content))
    assert [p.name for p in (tmp_path / "d").iterdir()] == [asset.name]


@pytest.mark.parametrize(
    "received",
    [b"x" * 9, b"x" * 11, b"y" * 10],
    ids=["cut short", "too long", "another file"],
)
def test_a_download_that_does_not_match_is_thrown_away(tmp_path, received):
    release, asset = published(b"x" * 10)
    with pytest.raises(UpdateError):
        download(release, asset, tmp_path, opener=FakeGitHub({asset.url: received}))
    assert list(tmp_path.iterdir()) == []


def test_a_broken_connection_leaves_nothing_behind(tmp_path):
    release, asset = published(b"x" * 10)
    with pytest.raises(UpdateError):
        download(release, asset, tmp_path, opener=FakeGitHub({asset.url: OSError("cut")}))
    assert list(tmp_path.iterdir()) == []


def test_a_download_can_be_cancelled(tmp_path):
    content = b"z" * (1024 * 1024)
    release, asset = published(content)
    with pytest.raises(UpdateCancelled):
        download(
            release,
            asset,
            tmp_path,
            cancelled=lambda: True,
            opener=FakeGitHub({asset.url: content}),
        )
    assert list(tmp_path.iterdir()) == []


def test_without_a_published_fingerprint_nothing_is_installed(tmp_path):
    release, asset = published(b"x" * 10, digest=False)
    github = FakeGitHub({asset.url: b"x" * 10})
    with pytest.raises(UpdateError):
        download(release, asset, tmp_path, opener=github)
    assert asset.url not in github.asked  # not even downloaded


def test_the_sums_file_also_serves_as_fingerprint(tmp_path):
    content = b"programa nuevo"
    name = "Lector-PDF-0.2.0-portatil.zip"
    sums = f"{'0' * 64}  otro.exe\n{hashlib.sha256(content).hexdigest()}  {name}\n".encode()
    release = parse_release(
        github_release(
            assets=[github_asset(name, content, digest=False), github_asset("SHA256SUMS.txt", sums)]
        )
    )
    asset = release.asset(portable=True)
    github = FakeGitHub({asset.url: content, release.assets["SHA256SUMS.txt"].url: sums})
    assert download(release, asset, tmp_path, opener=github).read_bytes() == content


def test_only_files_of_the_project_are_downloaded(tmp_path):
    release = Release("0.2.0", "", {})
    stranger = Asset("x-instalador.exe", "https://malo.example/x-instalador.exe", 10, "0" * 64)
    with pytest.raises(UpdateError):
        download(release, stranger, tmp_path, opener=FakeGitHub({stranger.url: b"x" * 10}))


# ---- installing ----


def make_program(folder, mark, extra=()):
    (folder / "_internal").mkdir(parents=True)
    (folder / updates.EXE_NAME).write_text(f"programa {mark}")
    (folder / "_internal" / "base.dll").write_text(f"pieza {mark}")
    for name in extra:
        (folder / name).write_text(mark)
    return folder


def test_the_installer_runs_by_itself_and_starts_the_program_again(tmp_path):
    command = installer_command(tmp_path / "i.exe")
    assert command[0] == str(tmp_path / "i.exe")
    assert "/SILENT" in command and "/RELAUNCH=1" in command


def test_the_installer_script_waits_for_the_program_and_starts_it_again():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[2] / "packaging" / "instalador.iss").read_text(
        encoding="utf-8"
    )
    assert "RELAUNCH" in script.upper()
    assert updates.INSTANCE_MUTEX in script


def test_unpacking_the_portable_version(tmp_path):
    archive = tmp_path / "p.zip"
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr("Lector-PDF/Lector-PDF.exe", "nuevo")
        packed.writestr("Lector-PDF/_internal/base.dll", "pieza")
        packed.writestr("Lector-PDF/portable.txt", "")
    program = unpack_portable(archive, tmp_path / "nueva")
    assert program.name == "Lector-PDF"
    assert (program / "_internal" / "base.dll").read_text() == "pieza"


def test_a_pack_that_writes_outside_its_folder_is_refused(tmp_path):
    archive = tmp_path / "p.zip"
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr("../fuera.txt", "malo")
        packed.writestr("Lector-PDF/Lector-PDF.exe", "nuevo")
    with pytest.raises(UpdateError):
        unpack_portable(archive, tmp_path / "nueva")
    assert not (tmp_path / "fuera.txt").exists()


@pytest.mark.parametrize("content", [b"no es un zip", None])
def test_a_pack_without_the_program_is_refused(tmp_path, content):
    archive = tmp_path / "p.zip"
    if content is None:
        with zipfile.ZipFile(archive, "w") as packed:
            packed.writestr("LEEME.txt", "nada")
    else:
        archive.write_bytes(content)
    with pytest.raises(UpdateError):
        unpack_portable(archive, tmp_path / "nueva")
    assert not (tmp_path / "nueva").exists()


def test_the_new_version_takes_the_place_of_the_old_and_the_data_stay(tmp_path):
    target = make_program(tmp_path / "Lector-PDF", "viejo", extra=["sobra.dll", "portable.txt"])
    (target / "datos").mkdir()
    (target / "datos" / "ajustes.json").write_text("mis ajustes")
    new = make_program(tmp_path / "nueva", "nuevo", extra=["portable.txt"])
    (new / "novedad.dll").write_text("nuevo")

    replace_program(new, target, target / "datos" / "actualizacion" / "anterior")

    assert (target / updates.EXE_NAME).read_text() == "programa nuevo"
    assert (target / "_internal" / "base.dll").read_text() == "pieza nuevo"
    assert (target / "novedad.dll").exists()
    assert not (target / "sobra.dll").exists()  # files of the old version do not linger
    assert (target / "datos" / "ajustes.json").read_text() == "mis ajustes"
    assert (target / "portable.txt").read_text() == "viejo"  # the user's own, untouched
    assert (new / updates.EXE_NAME).exists()  # the new one is copied, it is running from there


def test_if_putting_it_in_place_fails_the_old_version_comes_back(tmp_path, monkeypatch):
    target = make_program(tmp_path / "Lector-PDF", "viejo")
    (target / "datos").mkdir()
    new = make_program(tmp_path / "nueva", "nuevo")
    real_copy = updates.shutil.copy2

    def failing_copy(source, destination):
        real_copy(source, destination)
        raise OSError("disk full")

    monkeypatch.setattr(updates.shutil, "copy2", failing_copy)
    with pytest.raises(UpdateError):
        replace_program(new, target, target / "datos" / "actualizacion" / "anterior")
    assert (target / updates.EXE_NAME).read_text() == "programa viejo"
    assert (target / "_internal" / "base.dll").read_text() == "pieza viejo"


def test_a_new_version_without_the_program_changes_nothing(tmp_path):
    target = make_program(tmp_path / "Lector-PDF", "viejo")
    (tmp_path / "nueva").mkdir()
    with pytest.raises(UpdateError):
        replace_program(tmp_path / "nueva", target, tmp_path / "copia")
    assert (target / updates.EXE_NAME).read_text() == "programa viejo"


def test_applying_an_update_waits_replaces_and_starts(tmp_path, monkeypatch):
    target = make_program(tmp_path / "Lector-PDF", "viejo")
    new = make_program(target / "datos" / "actualizacion" / "nueva" / "Lector-PDF", "nuevo")
    old_program = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.4)"])
    started = []
    monkeypatch.setattr(
        updates.subprocess, "Popen", lambda command, **options: started.append((command, options))
    )
    try:
        assert apply_portable_update(new, target, old_program.pid) is True
        assert old_program.poll() is not None, "it must wait for the old program to end"
    finally:
        old_program.kill()
        old_program.wait()
    assert (target / updates.EXE_NAME).read_text() == "programa nuevo"
    assert started[0][0] == [str(target / updates.EXE_NAME)]
    assert started[0][1]["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_a_failed_update_still_starts_the_old_program(tmp_path, monkeypatch):
    target = make_program(tmp_path / "Lector-PDF", "viejo")
    (tmp_path / "vacia").mkdir()
    started = []
    monkeypatch.setattr(updates.subprocess, "Popen", lambda command, **o: started.append(command))
    assert apply_portable_update(tmp_path / "vacia", target, 0) is False
    assert (target / updates.EXE_NAME).read_text() == "programa viejo"
    assert started == [[str(target / updates.EXE_NAME)]]


def test_the_command_that_hands_over_to_the_new_version(tmp_path):
    command = portable_update_command(tmp_path / "nueva", tmp_path / "Lector-PDF", 1234)
    assert command == [
        str(tmp_path / "nueva" / updates.EXE_NAME),
        updates.APPLY_FLAG,
        str(tmp_path / "Lector-PDF"),
        "1234",
    ]


def test_waiting_for_a_program_that_is_gone_returns_at_once():
    finished = subprocess.Popen([sys.executable, "-c", "pass"])
    finished.wait()
    assert wait_for_exit(finished.pid, 5) is True
    assert wait_for_exit(0) is True


def test_waiting_gives_up_on_a_program_that_stays(tmp_path):
    staying = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert wait_for_exit(staying.pid, 0.3) is False
    finally:
        staying.kill()
        staying.wait()


def test_leftovers_of_an_update_are_removed(tmp_path):
    (tmp_path / "actualizacion" / "anterior").mkdir(parents=True)
    (tmp_path / "actualizacion" / "x.zip").write_text("x")
    (tmp_path / "ajustes.json").write_text("{}")
    clean_leftovers(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["ajustes.json"]
    clean_leftovers(tmp_path)  # nothing there: no error
