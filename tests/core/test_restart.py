"""Tests for starting the program again."""

import sys

from app.core import restart
from app.core.restart import (
    OWN_VARIABLES_MARK,
    relaunch,
    relaunch_command,
    relaunch_environment,
    set_own_variable,
)


def test_from_source_code_it_starts_the_same_python_again():
    assert relaunch_command() == [sys.executable, "-m", "app.main"]


def test_the_packaged_program_starts_itself(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert relaunch_command() == [sys.executable]


def test_the_new_copy_does_not_inherit_what_this_one_set_for_itself():
    environ = {"PATH": "x"}
    set_own_variable(environ, "QT_SCALE_FACTOR", "1.5")
    set_own_variable(environ, "OTRA", "1")
    fresh = relaunch_environment(environ)
    assert "QT_SCALE_FACTOR" not in fresh
    assert "OTRA" not in fresh
    assert OWN_VARIABLES_MARK not in fresh
    assert fresh["PATH"] == "x"
    assert environ["QT_SCALE_FACTOR"] == "1.5"  # this copy is not touched


def test_what_came_from_outside_is_passed_on():
    fresh = relaunch_environment({"QT_SCALE_FACTOR": "2"})
    assert fresh["QT_SCALE_FACTOR"] == "2"
    assert fresh["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_relaunch_starts_the_command(monkeypatch):
    started = []
    monkeypatch.setattr(
        restart.subprocess, "Popen", lambda command, **options: started.append((command, options))
    )
    assert relaunch() is True
    assert started[0][0] == relaunch_command()
    assert "env" in started[0][1]


def test_relaunch_says_when_it_cannot_start(monkeypatch):
    def fail(*_args, **_options):
        raise OSError("no")

    monkeypatch.setattr(restart.subprocess, "Popen", fail)
    assert relaunch() is False
