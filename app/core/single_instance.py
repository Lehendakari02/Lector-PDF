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
import time
from collections.abc import Callable
from multiprocessing.connection import Client, Connection, Listener
from pathlib import Path

from app.core.paths import data_dir

KEY_FILE_NAME = "instancia.clave"
ANSWER_SECONDS = 5.0
KEY_READ_TRIES = 50
MAX_FAILED_ACCEPTS = 200  # in a row: the listener itself is broken
TAKE_OVER_SECONDS = 3.0  # how long a copy insists on handing over its files
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
    """The secret shared by the copies of the program; created the first time.

    Several copies may start at the same instant the very first time: only one
    of them creates the file, and the others read what it wrote.
    """
    folder = folder if folder is not None else data_dir()
    file = folder / KEY_FILE_NAME
    key = secrets.token_bytes(32)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handle = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another copy may be writing it right now: give it a moment.
        for _ in range(KEY_READ_TRIES):
            stored = _stored_key(file)
            if stored:
                return stored
            time.sleep(0.02)
        with contextlib.suppress(OSError):  # a damaged file: start again
            file.write_bytes(key)
    except OSError:
        pass  # a folder that cannot be written: this copy works alone
    else:
        with os.fdopen(handle, "wb") as out:
            out.write(key)
    return _stored_key(file) or key


def _stored_key(file: Path) -> bytes:
    with contextlib.suppress(OSError):
        key = file.read_bytes()
        if len(key) >= 16:
            return key
    return b""


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


@contextlib.contextmanager
def _decision_lock(address: str):
    """Only one copy at a time decides whether a socket file is abandoned."""
    import fcntl

    with open(address + ".lock", "w") as lock:  # noqa: PTH123 (a plain lock file)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _somebody_listens(address: str) -> bool:
    """True if a program accepts connections on the socket file ``address``."""
    import socket

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        try:
            probe.connect(address)
        except OSError:
            return False
    return True


def become_main_copy(
    server: "InstanceServer",
    files: list[str],
    seconds: float = TAKE_OVER_SECONDS,
    pause: float = 0.15,
) -> bool:
    """Decide whether this copy is the main one. False: another one took the files.

    Meant to be called before anything slow (building the window): the first
    copy starts to listen at once, so the ones started in the same instant find
    it. A copy that cannot listen because another one already does hands over
    its files, trying for a moment because the other may still be starting. If
    nobody takes them, this copy carries on as the main one, without listening.
    """
    if send_to_running_copy(files, server.address, server.key):
        return False
    deadline = time.monotonic() + seconds
    while True:
        if server.start():
            return True
        if send_to_running_copy(files, server.address, server.key):
            return False
        if time.monotonic() >= deadline:
            return True
        time.sleep(pause)


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
        self._stopping = False

    @property
    def key(self) -> bytes:
        return self._key

    @property
    def listening(self) -> bool:
        return self._thread is not None

    def start(self) -> bool:
        """Begin to listen. False if it was not possible (the program works anyway)."""
        try:
            self._listener = self._listen()
        except OSError:
            return False
        self._start_serving()
        return True

    def _start_serving(self) -> None:
        self._stopping = False
        self._thread = threading.Thread(target=self._serve, name="single-instance", daemon=True)
        self._thread.start()

    def _listen(self) -> Listener:
        if sys.platform == "win32":
            # A named pipe has one owner: a second listener is refused by Windows.
            return Listener(self.address, authkey=self._key)
        # A socket file can be left behind by a copy that ended badly. It is only
        # removed when nobody answers there, and one copy at a time decides that.
        with _decision_lock(self.address):
            try:
                return Listener(self.address, authkey=self._key)
            except OSError:
                if not os.path.exists(self.address) or _somebody_listens(self.address):
                    raise
            os.unlink(self.address)
            return Listener(self.address, authkey=self._key)

    def _serve(self) -> None:
        listener = self._listener
        failures = 0
        while listener is not None:
            try:
                connection = listener.accept()
            except Exception:
                # A stranger without the secret, or one that hung up at once, must
                # not stop the listening; a closed or broken listener does.
                failures += 1
                if self._stopping or failures > MAX_FAILED_ACCEPTS:
                    break
                time.sleep(0.01)
                continue
            failures = 0
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
            self._stopping = True
            with contextlib.suppress(Exception):
                if self._listener is not None:
                    self._listener.close()
        thread.join(ANSWER_SECONDS)
        self._listener = None
