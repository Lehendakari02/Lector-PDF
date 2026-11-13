"""Tests for the notice of new versions and "Actualizar ahora" (no network used)."""

import hashlib
import io
import json
import urllib.error
import zipfile

import pytest

from app.core import updates
from app.core.settings import Settings
from app.core.updates import CHECK_SETTING, SKIPPED_SETTING
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.updater import UpdateBanner, Updater

PREFIX = updates.DOWNLOAD_PREFIX
INSTALLER = "Lector-PDF-0.2.0-instalador.exe"
PORTABLE = "Lector-PDF-0.2.0-portatil.zip"


def portable_zip() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("Lector-PDF/Lector-PDF.exe", b"new program")
        archive.writestr("Lector-PDF/portable.txt", b"")
    return data.getvalue()


class FakeGitHub:
    """Answers like GitHub: the latest version and its files."""

    def __init__(self, version="0.2.0", online=True, damaged=False):
        self.files = {INSTALLER: b"installer " * 50, PORTABLE: portable_zip()}
        self.online = online
        self.damaged = damaged
        self.asked = []
        assets = [
            {
                "name": name,
                "browser_download_url": f"{PREFIX}v{version}/{name}",
                "size": len(content),
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            }
            for name, content in self.files.items()
        ]
        self.latest = {
            "tag_name": f"v{version}",
            "html_url": f"{updates.RELEASES_PAGE}/tag/v{version}",
            "draft": False,
            "prerelease": False,
            "assets": assets,
        }

    def __call__(self, url, timeout):
        self.asked.append(url)
        if not self.online:
            raise urllib.error.URLError("no network")
        if url == updates.LATEST_URL:
            return io.BytesIO(json.dumps(self.latest).encode())
        content = self.files.get(url.rsplit("/", 1)[-1])
        if content is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return io.BytesIO(content[:-3] + b"bad" if self.damaged else content)


class Heard:
    """Remembers what an updater said."""

    def __init__(self, updater: Updater) -> None:
        self.found, self.nothing, self.ready, self.failed, self.progress = [], [], [], [], []
        updater.found.connect(self.found.append)
        updater.nothing_new.connect(self.nothing.append)
        updater.ready.connect(self.ready.append)
        updater.failed.connect(self.failed.append)
        updater.progress.connect(self.progress.append)


@pytest.fixture
def make_updater(qt_app, tmp_path):
    made = []

    def make(github=None, current="0.1.0", portable=False, packaged=True, settings=None):
        updater = Updater(
            settings or Settings(tmp_path / "ajustes-updater.json"),
            opener=github or FakeGitHub(),
            current_version=current,
            data_folder=tmp_path / "datos",
            portable=portable,
            packaged=packaged,
        )
        made.append(updater)
        return updater, Heard(updater)

    yield make
    for updater in made:
        updater.cancel()
        updater.wait()


def finish(updater: Updater, qt_app) -> None:
    updater.wait()
    qt_app.processEvents()


# ---- looking for a version ----


def test_a_newer_version_is_announced(make_updater, qt_app):
    updater, heard = make_updater()
    updater.check()
    finish(updater, qt_app)
    assert [release.version for release in heard.found] == ["0.2.0"]
    assert updater.release is heard.found[0]


def test_a_version_still_without_files_is_not_announced(make_updater, qt_app):
    github = FakeGitHub()
    github.latest["assets"] = []  # just published: the files are attached later
    updater, heard = make_updater(github)
    updater.check()
    finish(updater, qt_app)
    assert heard.found == []
    updater.check(by_hand=True)
    finish(updater, qt_app)
    assert heard.found == [] and heard.nothing == [True]


def test_nothing_is_said_when_starting_with_the_latest_version(make_updater, qt_app):
    updater, heard = make_updater(current="0.2.0")
    updater.check()
    finish(updater, qt_app)
    assert heard.found == [] and heard.nothing == []


def test_asking_by_hand_always_gets_an_answer(make_updater, qt_app):
    updater, heard = make_updater(current="0.2.0")
    updater.check(by_hand=True)
    finish(updater, qt_app)
    assert heard.nothing == [True]

    offline, heard_offline = make_updater(FakeGitHub(online=False))
    offline.check(by_hand=True)
    finish(offline, qt_app)
    assert heard_offline.nothing == [False]


def test_no_network_when_starting_is_not_worth_a_word(make_updater, qt_app):
    updater, heard = make_updater(FakeGitHub(online=False))
    updater.check()
    finish(updater, qt_app)
    assert heard.found == [] and heard.nothing == [] and heard.failed == []


def test_nothing_is_asked_when_the_notice_is_turned_off(make_updater, qt_app, settings):
    github = FakeGitHub()
    settings.set(CHECK_SETTING, False)
    updater, heard = make_updater(github, settings=settings)
    assert not updater.check_wanted
    updater.check()
    finish(updater, qt_app)
    assert github.asked == [] and heard.found == []
    updater.check(by_hand=True)  # asking by hand still works
    finish(updater, qt_app)
    assert len(heard.found) == 1


def test_a_skipped_version_is_not_mentioned_again_when_starting(make_updater, qt_app, settings):
    updater, heard = make_updater(settings=settings)
    updater.check()
    finish(updater, qt_app)
    updater.skip(heard.found[0])
    assert settings.get(SKIPPED_SETTING) == "0.2.0"

    again, heard_again = make_updater(settings=settings)
    again.check()
    finish(again, qt_app)
    assert heard_again.found == []
    again.check(by_hand=True)
    finish(again, qt_app)
    assert len(heard_again.found) == 1

    newer, heard_newer = make_updater(FakeGitHub("0.3.0"), settings=settings)
    newer.check()
    finish(newer, qt_app)
    assert [release.version for release in heard_newer.found] == ["0.3.0"]


# ---- downloading it ----


def _found(make_updater, qt_app, **options):
    updater, heard = make_updater(**options)
    updater.check()
    finish(updater, qt_app)
    return updater, heard


def test_the_installer_is_downloaded_and_made_ready(make_updater, qt_app, tmp_path):
    updater, heard = _found(make_updater, qt_app)
    assert updater.start_update(updater.release)
    finish(updater, qt_app)
    assert heard.failed == []
    (command,) = heard.ready
    installer = tmp_path / "datos" / updates.UPDATE_FOLDER / INSTALLER
    assert command[0] == str(installer) and installer.is_file()
    assert "/SILENT" in command and "/RELAUNCH=1" in command
    assert heard.progress[-1] == 100


def test_the_portable_version_is_unpacked_and_made_ready(make_updater, qt_app, tmp_path):
    updater, heard = _found(make_updater, qt_app, portable=True)
    assert updater.start_update(updater.release)
    finish(updater, qt_app)
    (command,) = heard.ready
    new_program = tmp_path / "datos" / updates.UPDATE_FOLDER / "nueva" / "Lector-PDF"
    assert command[0] == str(new_program / updates.EXE_NAME)
    assert (new_program / updates.EXE_NAME).read_bytes() == b"new program"
    assert updates.APPLY_FLAG in command


def test_a_damaged_download_is_never_installed(make_updater, qt_app, tmp_path):
    updater, heard = _found(make_updater, qt_app, github=FakeGitHub(damaged=True))
    assert updater.start_update(updater.release)
    finish(updater, qt_app)
    assert heard.ready == [] and heard.failed == [False]
    assert not (tmp_path / "datos" / updates.UPDATE_FOLDER / INSTALLER).exists()


def test_the_download_can_be_cancelled(make_updater, qt_app):
    updater, heard = _found(make_updater, qt_app)
    updater._cancel.set()
    updater._prepare(updater.release, updater.release.asset(False))
    qt_app.processEvents()
    assert heard.ready == [] and heard.failed == [True]


def test_the_program_run_from_its_code_does_not_replace_itself(make_updater, qt_app):
    updater, heard = _found(make_updater, qt_app, packaged=False)
    assert not updater.can_install
    assert not updater.start_update(updater.release)
    assert not updater.busy


# ---- the notice ----


def _shown(banner: UpdateBanner) -> set[str]:
    names = ("update_button", "news_button", "later_button", "skip_button", "cancel_button", "bar")
    return {name for name in names if not getattr(banner, name).isHidden()}


def test_the_notice_is_hidden_until_there_is_a_version(window):
    assert window.update_banner.isHidden()


def test_the_notice_offers_the_new_version(make_updater, qt_app):
    updater, _heard = _found(make_updater, qt_app)
    banner = UpdateBanner()
    banner.offer(updater.release, True)
    assert not banner.isHidden()
    assert "0.2.0" in banner.message.text()
    assert banner.update_button.text() == "Actualizar ahora"
    assert _shown(banner) == {"update_button", "news_button", "later_button", "skip_button"}
    assert banner.page.endswith("v0.2.0")

    banner.downloading(40)
    assert _shown(banner) == {"cancel_button", "bar"}
    assert banner.bar.value() == 40 and "40" in banner.message.text()

    banner.installing()
    assert _shown(banner) == set()

    banner.problem("No se ha podido")
    assert _shown(banner) == {"update_button", "news_button", "later_button"}

    banner.offer(updater.release, False)
    assert banner.update_button.text() == "Ir a la descarga"


def test_later_hides_the_notice_and_skip_also_remembers(make_updater, qt_app):
    updater, _heard = _found(make_updater, qt_app)
    banner = UpdateBanner()
    skipped = []
    banner.skip_wanted.connect(lambda: skipped.append(True))
    banner.offer(updater.release, True)
    banner.later_button.click()
    assert banner.isHidden() and skipped == []
    banner.offer(updater.release, True)
    banner.skip_button.click()
    assert banner.isHidden() and skipped == [True]


def test_every_button_of_the_notice_has_a_name(qt_app):
    banner = UpdateBanner()
    for name in ("update_button", "news_button", "later_button", "skip_button", "cancel_button"):
        assert getattr(banner, name).text()
    assert banner.bar.accessibleName()


# ---- in the window ----


@pytest.fixture
def updating_window(qt_app, settings, tmp_path):
    """A window whose updater talks to a fake GitHub, as the installed program."""
    main_window = MainWindow(settings)
    updater = main_window.updater
    updater._opener = FakeGitHub()
    updater.current_version = "0.1.0"
    updater._data_folder = tmp_path / "datos"
    updater.portable = False
    updater.packaged = True
    main_window.show()
    qt_app.processEvents()
    yield main_window
    updater.cancel()
    updater.wait()
    main_window.close()
    main_window.deleteLater()


def test_the_window_shows_the_notice_when_a_version_is_found(updating_window, qt_app):
    window = updating_window
    window.updater.check()
    finish(window.updater, qt_app)
    assert not window.update_banner.isHidden()
    assert "0.2.0" in window.update_banner.message.text()


def test_looking_by_hand_says_when_there_is_nothing_new(updating_window, qt_app):
    window = updating_window
    window.updater.current_version = "0.2.0"
    window.check_updates_action.trigger()
    finish(window.updater, qt_app)
    assert window.update_banner.isHidden()
    assert "0.2.0" in window.statusBar().currentMessage()

    window.updater._opener = FakeGitHub(online=False)
    window.check_updates_action.trigger()
    finish(window.updater, qt_app)
    assert "conexión" in window.statusBar().currentMessage()


def test_update_now_downloads_closes_and_leaves_the_installation_ready(
    updating_window, qt_app, tmp_path
):
    window = updating_window
    window.updater.check()
    finish(window.updater, qt_app)
    window.update_banner.update_button.click()
    finish(window.updater, qt_app)
    installer = tmp_path / "datos" / updates.UPDATE_FOLDER / INSTALLER
    assert window.after_exit_command is not None
    assert window.after_exit_command[0] == str(installer)
    assert not window.isVisible()  # closed: the installation runs after the program


def test_a_failed_download_keeps_the_program_as_it_was(updating_window, qt_app):
    window = updating_window
    window.updater._opener = FakeGitHub(damaged=True)
    window.updater.check()
    finish(window.updater, qt_app)
    window.update_now()
    finish(window.updater, qt_app)
    assert window.after_exit_command is None
    assert window.isVisible()
    assert "No se ha podido" in window.update_banner.message.text()
    assert not window.update_banner.update_button.isHidden()  # it can be tried again


def test_skipping_from_the_window_is_remembered(updating_window, qt_app, settings):
    window = updating_window
    window.updater.check()
    finish(window.updater, qt_app)
    window.update_banner.skip_button.click()
    assert settings.get(SKIPPED_SETTING) == "0.2.0"
    assert window.update_banner.isHidden()


def test_from_the_code_the_button_only_opens_the_download_page(
    updating_window, qt_app, monkeypatch
):
    window = updating_window
    window.updater.packaged = False
    opened = []
    monkeypatch.setattr(window.update_banner, "open_page", lambda: opened.append(True))
    window.updater.check()
    finish(window.updater, qt_app)
    assert window.update_banner.update_button.text() == "Ir a la descarga"
    window.update_now()
    assert opened == [True] and window.after_exit_command is None


# ---- settings ----


def test_the_notice_can_be_turned_off_in_the_settings(window, settings):
    dialog = SettingsDialog(window)
    assert dialog.updates_box.isChecked()  # on unless the user says otherwise
    dialog.updates_box.setChecked(False)
    assert settings.get(CHECK_SETTING) is False
    assert not window.updater.check_wanted
    dialog.updates_box.setChecked(True)
    assert window.updater.check_wanted
    dialog.close()


# ---- the entry point ----


def test_the_installation_runs_after_the_program_has_closed(monkeypatch):
    import app.main as program

    class WindowWithAnUpdateReady(program.MainWindow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.after_exit_command = ["instalador.exe", "/SILENT"]
            self.restart_wanted = True  # the installation wins: it restarts by itself

    ran, restarted = [], []
    monkeypatch.setattr(program, "MainWindow", WindowWithAnUpdateReady)
    monkeypatch.setattr(program, "relaunch", lambda: restarted.append(True))
    monkeypatch.setattr(
        program.subprocess, "Popen", lambda command, **options: ran.append((command, options))
    )
    assert program.main(["lector-pdf", program.AUTOCLOSE_FLAG]) == 0
    ((command, options),) = ran
    assert command == ["instalador.exe", "/SILENT"]
    assert options["env"].get("PYINSTALLER_RESET_ENVIRONMENT") == "1"
    assert restarted == []


def test_no_version_is_looked_for_in_the_automatic_checks(monkeypatch):
    import app.main as program

    asked = []
    monkeypatch.setattr(updates, "newer_release", lambda *a, **k: asked.append(True))
    assert program.main(["lector-pdf", program.AUTOCLOSE_FLAG]) == 0
    assert asked == []


def test_the_new_version_takes_the_place_of_the_old_one(monkeypatch, tmp_path):
    import app.main as program

    done = []

    def fake_apply(new, target, process_id, start=True):
        done.append((new, target, process_id, start))
        return True

    monkeypatch.setattr(program, "apply_portable_update", fake_apply)
    target = tmp_path / "Lector-PDF"
    start = ["lector-pdf", program.APPLY_FLAG]
    assert program.main([*start, str(target), "1234"]) == 0
    assert program.main([*start, str(target), "1234", program.NO_START_FLAG]) == 0
    assert done == [
        (program.program_dir(), target, 1234, True),
        (program.program_dir(), target, 1234, False),
    ]
    assert program.main([*start, str(target)]) == program.EXIT_UPDATE_FAILED
    assert program.main([*start, str(target), "abc"]) == program.EXIT_UPDATE_FAILED
    monkeypatch.setattr(program, "apply_portable_update", lambda *a, **k: False)
    assert program.main([*start, str(target), "1234"]) == program.EXIT_UPDATE_FAILED
