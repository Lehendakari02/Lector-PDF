"""Tests for running a single copy of the program."""

import os
import threading

import pytest

from app.core.single_instance import (
    InstanceServer,
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
    if os.name == "nt":
        assert other.start() is False
    assert send_to_running_copy(["a.pdf"], *channel) is True


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


def test_installed_and_portable_copies_do_not_mix(tmp_path):
    assert default_address(tmp_path / "a") != default_address(tmp_path / "b")
    assert default_address(tmp_path / "a") == default_address(tmp_path / "a")
