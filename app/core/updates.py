"""New versions: asking GitHub whether there is one, downloading it and installing it.

Nothing here runs unless the program asks for it, and the only place it talks
to is the project's page on GitHub (the list of published versions and their
files). No data about the user or the documents is sent: the requests carry
nothing but the name of the program.

Safety:
- a download is accepted only if it has the size and the fingerprint (SHA-256)
  that GitHub publishes for that file, and only from the project's own releases;
- the portable version is replaced file by file with a copy of the old one kept
  aside until the new one is in place; if anything fails the old one is put back.
"""

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.restart import relaunch_environment

REPOSITORY = "Lehendakari02/Lector-PDF"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
USER_AGENT = "Lector-PDF"
INSTALLER_SUFFIX = "-instalador.exe"
PORTABLE_SUFFIX = "-portatil.zip"
CHECKSUMS_NAME = "SHA256SUMS.txt"
EXE_NAME = "Lector-PDF.exe"
UPDATE_FOLDER = "actualizacion"  # inside the program's data folder
KEPT_ENTRIES = ("datos", "portable.txt")  # of the portable folder: never replaced
CHECK_SETTING = "avisar_de_versiones"  # True: look for new versions when starting
SKIPPED_SETTING = "version_omitida"  # a version the user does not want to hear about
NETWORK_SECONDS = 15
MAX_DOWNLOAD_BYTES = 600 * 1024 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024
EXIT_WAIT_SECONDS = 60
# While the program runs it holds this Windows "mutex" (a name that exists as
# long as its owner lives). The installer waits for it to disappear before it
# replaces the files. The same name is written in packaging/instalador.iss.
INSTANCE_MUTEX = "LectorPDF-6F6C2C0B-en-marcha"

Opener = Callable[[str, float], object]


class UpdateError(Exception):
    """Looking for, downloading or installing a version did not work."""


class UpdateCancelled(UpdateError):
    """The user stopped the download."""


@dataclass(frozen=True)
class Asset:
    """A file published with a version."""

    name: str
    url: str
    size: int
    sha256: str = ""  # empty if GitHub did not say


@dataclass(frozen=True)
class Release:
    """A published version."""

    version: str  # without the leading "v"
    page: str  # where its notes can be read
    assets: dict[str, Asset] = field(default_factory=dict)

    def asset(self, portable: bool) -> Asset | None:
        """The file that updates this kind of installation, if it was published."""
        suffix = PORTABLE_SUFFIX if portable else INSTALLER_SUFFIX
        return next((a for name, a in self.assets.items() if name.endswith(suffix)), None)

    def ready_for(self, portable: bool) -> bool:
        """True once the file for this kind of installation and its fingerprint exist.

        A version is published first and its files are attached some minutes
        later (or never, if building them fails): until then there is nothing
        to update with.
        """
        asset = self.asset(portable)
        return asset is not None and bool(asset.sha256 or CHECKSUMS_NAME in self.assets)


# ---- versions ----------------------------------------------------------------


def parse_version(text: str) -> tuple[int, ...] | None:
    """ "v1.2.3" or "1.2.3" as numbers; None for anything else (test or draft names)."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})", text.strip())
    if match is None:
        return None
    numbers = tuple(int(part) for part in match.group(1).split("."))
    return numbers + (0,) * (4 - len(numbers))


def is_newer(candidate: str, current: str) -> bool:
    """True if ``candidate`` is a later version than ``current``."""
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


def parse_release(data: object) -> Release | None:
    """Read GitHub's description of a release. None if it is not a normal version."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or parse_version(tag) is None:
        return None
    assets: dict[str, Asset] = {}
    for item in data.get("assets") or []:
        if not isinstance(item, dict):
            continue
        name, url, size = item.get("name"), item.get("browser_download_url"), item.get("size")
        if not (isinstance(name, str) and isinstance(url, str) and isinstance(size, int)):
            continue
        if not url.startswith(DOWNLOAD_PREFIX):
            continue  # only files of the project's own releases
        digest = item.get("digest")
        sha256 = ""
        if isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            sha256 = digest.split(":", 1)[1].lower()
        assets[name] = Asset(name, url, size, sha256)
    page = data.get("html_url")
    if not (isinstance(page, str) and page.startswith(f"https://github.com/{REPOSITORY}/")):
        page = RELEASES_PAGE
    return Release(tag.strip().lstrip("v"), page, assets)


# ---- network -----------------------------------------------------------------


def _open(url: str, timeout: float):
    request = urllib.request.Request(  # noqa: S310 (https only, checked by the callers)
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def fetch_latest(opener: Opener = _open) -> Release | None:
    """Ask GitHub for the latest published version. None if there is none yet.

    Raises ``UpdateError`` when GitHub cannot be reached.
    """
    try:
        with opener(LATEST_URL, NETWORK_SECONDS) as answer:
            data = json.loads(answer.read(2_000_000).decode("utf-8"))
    except Exception as error:
        if getattr(error, "code", None) == 404:
            return None  # no version published yet (or the project is still private)
        raise UpdateError(f"cannot ask for the latest version: {error}") from error
    return parse_release(data)


def newer_release(
    current: str, opener: Opener = _open, portable: bool | None = None
) -> Release | None:
    """The latest version, if it is later than ``current``; otherwise None.

    With ``portable`` given (the kind of installation asking), a version whose
    files are not published yet does not count: see ``Release.ready_for``.
    """
    release = fetch_latest(opener)
    if release is None or not is_newer(release.version, current):
        return None
    if portable is not None and not release.ready_for(portable):
        return None
    return release


def _published_checksum(release: Release, asset: Asset, opener: Opener) -> str:
    """The fingerprint of ``asset``: from GitHub's own list, or from the sums file."""
    if asset.sha256:
        return asset.sha256
    sums = release.assets.get(CHECKSUMS_NAME)
    if sums is None or sums.size > 100_000:
        return ""
    try:
        with opener(sums.url, NETWORK_SECONDS) as answer:
            text = answer.read(100_000).decode("utf-8", "replace")
    except Exception:
        return ""
    for line in text.splitlines():
        parts = line.split()
        named = len(parts) == 2 and parts[1].lstrip("*") == asset.name
        if named and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return ""


def download(
    release: Release,
    asset: Asset,
    folder: Path,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    opener: Opener = _open,
) -> Path:
    """Download ``asset`` into ``folder`` and check it is the published file.

    ``progress`` receives bytes received and bytes in total. Raises
    ``UpdateCancelled`` or ``UpdateError``; nothing half-downloaded is left.
    """
    if not asset.url.startswith(DOWNLOAD_PREFIX) or not 0 < asset.size <= MAX_DOWNLOAD_BYTES:
        raise UpdateError("the file of the new version is not the expected one")
    wanted = _published_checksum(release, asset, opener)
    if not wanted:
        raise UpdateError("the new version does not say how to check its download")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / Path(asset.name).name
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    received = 0
    try:
        with opener(asset.url, NETWORK_SECONDS) as answer, partial.open("wb") as out:
            while True:
                if cancelled is not None and cancelled():
                    raise UpdateCancelled("cancelled")
                block = answer.read(256 * 1024)
                if not block:
                    break
                received += len(block)
                if received > asset.size:
                    raise UpdateError("the download is bigger than the published file")
                digest.update(block)
                out.write(block)
                if progress is not None:
                    progress(received, asset.size)
        if received != asset.size:
            raise UpdateError("the download is incomplete")
        if digest.hexdigest() != wanted:
            raise UpdateError("the download is not the published file")
        os.replace(partial, target)
    except UpdateError:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise
    except Exception as error:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise UpdateError(f"the download failed: {error}") from error
    return target


# ---- installing --------------------------------------------------------------


def hold_instance_mutex() -> object | None:
    """Tell Windows the program is running (see ``INSTANCE_MUTEX``). Keep the result."""
    if sys.platform != "win32":
        return None
    with contextlib.suppress(Exception):
        import ctypes

        return ctypes.windll.kernel32.CreateMutexW(None, False, INSTANCE_MUTEX) or None
    return None


def update_folder(data_folder: Path) -> Path:
    return data_folder / UPDATE_FOLDER


def clean_leftovers(data_folder: Path) -> None:
    """Remove what a past update left behind (downloads, the copy of the old version)."""
    shutil.rmtree(update_folder(data_folder), ignore_errors=True)


def installer_command(installer: Path) -> list[str]:
    """Run the installer by itself: it waits for the program to end, installs and starts it."""
    return [str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"]


def unpack_portable(archive: Path, folder: Path) -> Path:
    """Unpack the portable version into ``folder``. Returns the folder with the program."""
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    root = folder.resolve()
    try:
        with zipfile.ZipFile(archive) as packed:
            total = 0
            for item in packed.infolist():
                total += item.file_size
                destination = (root / item.filename).resolve()
                if not destination.is_relative_to(root) or total > MAX_UNPACKED_BYTES:
                    raise UpdateError("the new version is not packed as expected")
            packed.extractall(root)  # noqa: S202 (every path was checked just above)
    except (OSError, zipfile.BadZipFile) as error:
        shutil.rmtree(folder, ignore_errors=True)
        raise UpdateError(f"the new version cannot be unpacked: {error}") from error
    for candidate in (root, *sorted(p for p in root.iterdir() if p.is_dir())):
        if (candidate / EXE_NAME).is_file():
            return candidate
    shutil.rmtree(folder, ignore_errors=True)
    raise UpdateError("the new version does not contain the program")


def portable_update_command(new_program_folder: Path, target: Path, process_id: int) -> list[str]:
    """The new version, started from where it was unpacked, replaces the old one."""
    return [str(new_program_folder / EXE_NAME), APPLY_FLAG, str(target), str(process_id)]


APPLY_FLAG = "--apply-update"
NO_START_FLAG = "--no-start"  # only for the automatic builds


def wait_for_exit(process_id: int, seconds: float = EXIT_WAIT_SECONDS) -> bool:
    """Wait until the process has ended. True if it has (or never existed)."""
    if process_id <= 0:
        return True
    if sys.platform == "win32":
        import ctypes

        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, int(process_id))
        if not handle:
            return True  # it is gone already
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, int(seconds * 1000)) == 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return True
        except OSError:
            pass  # it exists but is not ours
        with contextlib.suppress(ChildProcessError, OSError):
            if os.waitpid(process_id, os.WNOHANG)[0] == process_id:
                return True
        time.sleep(0.1)
    return False


def replace_program(new: Path, target: Path, backup: Path, tries: int = 20) -> None:
    """Replace the program in ``target`` with the one in ``new``.

    What is listed in ``KEPT_ENTRIES`` (the user's data) is never touched. The
    old files are moved to ``backup`` first; if anything fails they are put
    back, so the old version keeps working. Raises ``UpdateError`` then.
    """
    new, target, backup = new.resolve(), target.resolve(), backup.resolve()
    if not (new / EXE_NAME).is_file():
        raise UpdateError("the new version does not contain the program")
    if not target.is_dir():
        raise UpdateError("the folder of the program is not there")
    shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir(parents=True)
    moved: list[str] = []
    copied: list[str] = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name in KEPT_ENTRIES:
                continue
            _move_patiently(entry, backup / entry.name, tries)
            moved.append(entry.name)
        for entry in sorted(new.iterdir()):
            if entry.name in KEPT_ENTRIES:
                continue
            copied.append(entry.name)
            if entry.is_dir():
                shutil.copytree(entry, target / entry.name)
            else:
                shutil.copy2(entry, target / entry.name)
    except Exception as error:
        # Put everything back as it was.
        for name in copied:
            path = target / name
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)
        for name in moved:
            with contextlib.suppress(OSError):
                os.replace(backup / name, target / name)
        raise UpdateError(f"the new version could not be put in place: {error}") from error


def _move_patiently(source: Path, destination: Path, tries: int) -> None:
    """Move a file or folder; a file still in use for a moment is tried again."""
    for attempt in range(tries):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(0.25)


def apply_portable_update(new: Path, target: Path, process_id: int, start: bool = True) -> bool:
    """Run by the NEW version: replace the old one in ``target`` and start it.

    Whatever happens, a working program is started again: the new one if the
    replacement worked, the old one (put back) if it did not. Returns whether
    the new version is now in place.
    """
    wait_for_exit(process_id)
    backup = update_folder(target / "datos") / "anterior"
    try:
        replace_program(new, target, backup)
        updated = True
    except UpdateError:
        updated = False
    if start:
        with contextlib.suppress(OSError):
            subprocess.Popen(  # noqa: S603 (the program itself)
                [str(target / EXE_NAME)], env=relaunch_environment(os.environ), cwd=str(target)
            )
    return updated
