"""Tests for running a single copy of the program."""

import os
import threading

import pytest

from app.core.single_instance import (
    InstanceServer,
    become_main_copy,
    default_address,
    load_key,
    send_to_running_copy,
)


@pytest.fixture
def channel(tmp_path):
    return default_address(tmp_path), load_key(tmp_path)


@pytest.fixture
def server(channel):
    received = []
    arrived = threading.Event()

    def on_files(files):
        received.append(files)
        arrived.set()

    made = InstanceServer(on_files, *channel)
    assert made.start()
    made.received = received
    made.arrived = arrived
    yield made
    made.close()


def test_without_a_running_copy_nothing_is_sent(channel):
    assert send_to_running_copy(["a.pdf"], *channel) is False


def test_files_reach_the_running_copy_with_their_whole_path(server, channel):
    assert send_to_running_copy(["tema.pdf", "ley.pdf"], *channel) is True
    assert server.arrived.wait(5)
    assert server.received == [[os.path.abspath("tema.pdf"), os.path.abspath("ley.pdf")]]


def test_starting_again_without_files_also_tells_the_running_copy(server, channel):
    assert send_to_running_copy([], *channel) is True
    assert server.received == [[]]


def test_several_copies_one_after_another(server, channel):
    for name in ("1.pdf", "2.pdf", "3.pdf"):
        assert send_to_running_copy([name], *channel)
    assert [os.path.basename(files[0]) for files in server.received] == ["1.pdf", "2.pdf", "3.pdf"]


def test_a_stranger_without_the_secret_is_ignored(server, channel):
    address, _key = channel
    assert send_to_running_copy(["x.pdf"], address, b"another secret, not ours") is False
    assert server.received == []
    assert send_to_running_copy(["y.pdf"], *channel) is True  # still listening


def test_after_closing_a_new_copy_becomes_the_main_one(channel):
    first = InstanceServer(lambda files: None, *channel)
    assert first.start()
    first.close()
    assert send_to_running_copy(["a.pdf"], *channel) is False
    second = InstanceServer(lambda files: None, *channel)
    assert second.start()
    second.close()


def test_a_second_listener_cannot_take_the_place_of_the_first(server, channel):
    other = InstanceServer(lambda files: None, *channel)
    assert other.start() is False
    assert send_to_running_copy(["a.pdf"], *channel) is True
    assert server.arrived.wait(5)


@pytest.mark.skipif(os.name == "nt", reason="socket files are not used on Windows")
def test_a_socket_file_left_behind_is_taken_over(channel):
    import socket

    address, _key = channel
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as abandoned:
        abandoned.bind(address)  # bound but never listening, like after a crash
    assert os.path.exists(address)
    server = InstanceServer(lambda files: None, *channel)
    assert server.start()
    try:
        assert send_to_running_copy([], *channel) is True
    finally:
        server.close()


def test_somebody_who_connects_and_hangs_up_does_not_stop_the_listening(server, channel):
    from multiprocessing.connection import Client

    address, _key = channel
    for _ in range(3):
        with pytest.raises(Exception):  # noqa: B017, PT011 (any refusal will do)
            Client(address, authkey=b"wrong").close()
    assert send_to_running_copy(["a.pdf"], *channel) is True


def test_the_first_copy_becomes_the_main_one(channel):
    server = InstanceServer(lambda files: None, *channel)
    try:
        assert become_main_copy(server, ["a.pdf"]) is True
        assert server.listening
    finally:
        server.close()


def test_a_later_copy_hands_over_its_files_and_ends(server, channel):
    later = InstanceServer(lambda files: None, *channel)
    assert become_main_copy(later, ["a.pdf"]) is False
    assert not later.listening
    assert server.received == [[os.path.abspath("a.pdf")]]


def test_a_copy_keeps_trying_while_the_main_one_is_busy(server, channel, monkeypatch):
    """The main copy may be attending another one: the hand-over is tried again."""
    from app.core import single_instance

    real = single_instance.send_to_running_copy
    tries = []

    def busy_at_first(*args, **kwargs):
        tries.append(1)
        return False if len(tries) < 3 else real(*args, **kwargs)

    monkeypatch.setattr(single_instance, "send_to_running_copy", busy_at_first)
    later = InstanceServer(lambda files: None, *channel)
    assert become_main_copy(later, ["b.pdf"], pause=0.01) is False
    assert server.received == [[os.path.abspath("b.pdf")]]


def test_if_nobody_ever_takes_the_files_the_copy_carries_on_alone(server, channel, monkeypatch):
    from app.core import single_instance

    monkeypatch.setattr(single_instance, "send_to_running_copy", lambda *a, **k: False)
    later = InstanceServer(lambda files: None, *channel)
    assert become_main_copy(later, [], seconds=0.2, pause=0.01) is True
    assert not later.listening


def test_three_copies_started_at_once_end_in_one_window(tmp_path):
    """Opening three PDFs together: one program stays, with the three documents."""
    import json
    import subprocess
    import sys
    import time
    from pathlib import Path

    examples = Path(__file__).resolve().parents[1] / "ejemplos"
    names = ["boe.pdf", "formulario.pdf", "texto-dificil.pdf"]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env["LOCALAPPDATA"] = env["XDG_DATA_HOME"] = str(tmp_path)
    copies = [
        subprocess.Popen([sys.executable, "-m", "app.main", str(examples / name)], env=env)
        for name in names
    ]
    settings = tmp_path / "Lector-PDF" / "ajustes.json"
    try:
        deadline = time.monotonic() + 90
        remembered = ""
        while time.monotonic() < deadline:
            ended = [copy for copy in copies if copy.poll() is not None]
            if settings.is_file():
                remembered = json.dumps(json.loads(settings.read_text(encoding="utf-8")))
            if len(ended) == 2 and all(name in remembered for name in names):
                break
            assert len(ended) <= 2, "no copy stayed open"
            time.sleep(0.2)
        assert [copy.returncode for copy in copies].count(0) == 2
        assert sum(copy.poll() is None for copy in copies) == 1
        assert all(name in remembered for name in names)
    finally:
        for copy in copies:
            if copy.poll() is None:
                copy.terminate()
            copy.wait(30)


def test_a_problem_in_the_window_does_not_stop_the_listening(channel):
    calls = []

    def on_files(files):
        calls.append(files)
        if len(calls) == 1:
            raise RuntimeError("boom")

    server = InstanceServer(on_files, *channel)
    assert server.start()
    try:
        assert send_to_running_copy(["a.pdf"], *channel) is False
        assert send_to_running_copy(["b.pdf"], *channel) is True
    finally:
        server.close()


def test_the_secret_is_created_once_and_kept(tmp_path):
    key = load_key(tmp_path)
    assert len(key) >= 16
    assert load_key(tmp_path) == key


def test_copies_starting_together_for_the_first_time_share_one_secret(tmp_path):
    keys = []
    together = threading.Barrier(8)

    def start():
        together.wait()
        keys.append(load_key(tmp_path))

    threads = [threading.Thread(target=start) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(keys)) == 1 and len(keys) == 8


def test_a_damaged_secret_is_made_again(tmp_path, monkeypatch):
    from app.core import single_instance

    monkeypatch.setattr(single_instance, "KEY_READ_TRIES", 2)
    (tmp_path / single_instance.KEY_FILE_NAME).write_bytes(b"short")
    key = load_key(tmp_path)
    assert len(key) >= 16 and load_key(tmp_path) == key


def test_installed_and_portable_copies_do_not_mix(tmp_path):
    assert default_address(tmp_path / "a") != default_address(tmp_path / "b")
    assert default_address(tmp_path / "a") == default_address(tmp_path / "a")
