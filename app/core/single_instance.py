"""Only one copy of the program runs at a time.

When the program is started while it is already open (a double click on a
second PDF, for example), the new copy hands its files to the one that is
running and ends. The running copy opens them in new tabs. With a single copy,
nothing else writes the settings or the remembered tabs behind its back.

The two copies talk through a private local channel of this computer and this
user (a named pipe on Windows); nothing goes through the network. A secret kept
in the program's data folder makes sure the other end is really this program.
"""

import contextlib
import getpass
import hashlib
import json
import os
import secrets
import sys
import tempfile
import threading
from collections.abc import Callable
from multiprocessing.connection import Client, Connection, Listener
from pathlib import Path

from app.core.paths import data_dir

KEY_FILE_NAME = "instancia.clave"
ANSWER_SECONDS = 5.0
_STOP = "stop"
_OPEN = "open"


def default_address(folder: Path | None = None) -> str:
    """The channel of this user and this data folder (installed and portable differ)."""
    folder = folder if folder is not None else data_dir()
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = ""
    mark = hashlib.sha256(f"{user}|{os.path.normcase(str(folder))}".encode()).hexdigest()[:16]
    if sys.platform == "win32":
        return rf"\\.\pipe\lector-pdf-{mark}"
    return str(Path(tempfile.gettempdir()) / f"lector-pdf-{mark}.sock")


def load_key(folder: Path | None = None) -> bytes:
    """The secret shared by the copies of the program; created the first time."""
    folder = folder if folder is not None else data_dir()
    file = folder / KEY_FILE_NAME
    with contextlib.suppress(OSError):
        key = file.read_bytes()
        if len(key) >= 16:
            return key
    key = secrets.token_bytes(32)
    with contextlib.suppress(OSError):
        folder.mkdir(parents=True, exist_ok=True)
        file.write_bytes(key)
        with contextlib.suppress(OSError):
            file.chmod(0o600)
    # If the file could not be written, read back whatever another copy wrote.
    with contextlib.suppress(OSError):
        stored = file.read_bytes()
        if len(stored) >= 16:
            return stored
    return key


def _allow_to_come_forward(process_id: int) -> None:
    """Windows only lets a window come to the front if the program in use allows it."""
    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(int(process_id))


def _send(connection: Connection, message: dict) -> None:
    connection.send_bytes(json.dumps(message).encode("utf-8"))


def _receive(connection: Connection, seconds: float = ANSWER_SECONDS) -> dict:
    if not connection.poll(seconds):
        raise TimeoutError
    message = json.loads(connection.recv_bytes(1_000_000).decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("unexpected message")
    return message


def send_to_running_copy(
    files: list[str], address: str | None = None, key: bytes | None = None
) -> bool:
    """Hand ``files`` to the copy that is already open. False if there is none.

    With no files the running copy just comes to the front.
    """
    address = address if address is not None else default_address()
    key = key if key is not None else load_key()
    paths = [os.path.abspath(file) for file in files]
    try:
        with Client(address, authkey=key) as connection:
            hello = _receive(connection)
            _allow_to_come_forward(hello.get("pid", 0))
            _send(connection, {"what": _OPEN, "files": paths})
            return _receive(connection).get("done") is True
    except Exception:  # nobody there, or it is not our program: start normally
        return False


class InstanceServer:
    """Listens for other copies of the program and passes on their files.

    ``on_files`` is called from a background thread with the list of files
    (possibly empty) every time another copy starts.
    """

    def __init__(
        self,
        on_files: Callable[[list[str]], None],
        address: str | None = None,
        key: bytes | None = None,
    ) -> None:
        self.address = address if address is not None else default_address()
        self._key = key if key is not None else load_key()
        self._on_files = on_files
        self._listener: Listener | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Begin to listen. False if it was not possible (the program works anyway)."""
        try:
            self._listener = self._listen()
        except OSError:
            return False
        self._thread = threading.Thread(target=self._serve, name="single-instance", daemon=True)
        self._thread.start()
        return True

    def _listen(self) -> Listener:
        try:
            return Listener(self.address, authkey=self._key)
        except OSError:
            if sys.platform == "win32" or not os.path.exists(self.address):
                raise
        # A socket file left behind by a copy that ended badly: nobody answers there.
        os.unlink(self.address)
        return Listener(self.address, authkey=self._key)

    def _serve(self) -> None:
        listener = self._listener
        while listener is not None:
            try:
                connection = listener.accept()
            except OSError:
                break  # the listener was closed
            except Exception:  # noqa: S112 (a stranger without the secret)
                continue
            with connection:
                try:
                    _send(connection, {"pid": os.getpid()})
                    message = _receive(connection)
                    if message.get("what") == _STOP:
                        break
                    files = [f for f in message.get("files", []) if isinstance(f, str)]
                    self._on_files(files)
                    _send(connection, {"done": True})
                except Exception:  # noqa: S112 (a broken conversation must not stop the listening)
                    continue
        with contextlib.suppress(Exception):
            if listener is not None:
                listener.close()

    def close(self) -> None:
        """Stop listening, so that a copy started from now on becomes the main one."""
        thread, self._thread = self._thread, None
        if thread is None:
            return
        try:
            with Client(self.address, authkey=self._key) as connection:
                _receive(connection)
                _send(connection, {"what": _STOP})
        except Exception:
            with contextlib.suppress(Exception):
                if self._listener is not None:
                    self._listener.close()
        thread.join(ANSWER_SECONDS)
        self._listener = None
