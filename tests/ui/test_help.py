"""Tests for the built-in help (F1), the "F1" of the finder and the tip of the day."""

import datetime

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core import shortcuts
from app.ui import help_topics
from app.ui.command_palette import CommandPalette
from app.ui.features import FEATURES, Mode


def ids(query: str) -> list[str]:
    return [topic.id for topic in help_topics.search_topics(query)]


def test_every_function_has_its_page_and_ids_are_unique():
    topic_ids = [topic.id for topic in help_topics.TOPICS]
    assert len(topic_ids) == len(set(topic_ids))
    for feature in FEATURES:
        assert help_topics.topic(feature.id) is not None, feature.id
    for topic in help_topics.TOPICS:
        assert topic.section in help_topics.SECTIONS
        assert topic.title and topic.summary


def test_every_function_that_works_says_how(window):
    """A new function must bring its page of help: steps, at least."""
    for feature_id in window.feature_handlers:
        assert help_topics.topic(feature_id).steps, f"{feature_id} has no steps in help_topics"


def test_pages_without_a_button_run_a_command_that_exists(window):
    for topic in help_topics.TOPICS:
        if topic.command is not None:
            assert topic.command in window.key_commands, topic.id


def test_every_tip_has_a_page():
    for _text, topic_id in help_topics.TIPS:
        assert help_topics.topic(topic_id) is not None, topic_id


def test_search_finds_what_people_want_to_do():
    assert ids("foto")[0] == "photo_to_pdf"
    assert "photo_to_pdf" in ids("escanear movil")
    assert "merge" in ids("juntar")
    assert "recover_crash" in ids("apagon")
    assert "versions" in ids("volver atras")
    assert "sign_certificate" in ids("DNIe")
    assert ids("firmar")[0] in {"sign_drawn", "sign_certificate"}
    assert ids("xyzxyz") == []
    assert len(ids("")) == len(help_topics.TOPICS)


def test_search_ignores_accents_but_not_the_enye():
    assert "go_to_article" in ids("ARTICULO")
    assert "password" in ids("contraseña")
    assert "password" not in ids("contrasena")


def test_f1_opens_the_help_and_its_search(window):
    window.help_action.trigger()
    help_window = window.help_window
    assert help_window.isVisible()
    QTest.keyClicks(help_window.query, "unir pdf")
    assert help_window.current.id == "merge"
    assert help_window.run_button.text() == "Hazlo ahora"
    assert help_window.run_button.isVisibleTo(help_window)
    assert "Unir" in help_window.page.toPlainText()
    assert "merge" in help_window.visible_topics()
    assert "highlight" not in help_window.visible_topics()


def test_f1_is_a_key_that_can_be_changed():
    assert shortcuts.defaults_of("help") == ("F1",)


def test_the_page_says_the_key_of_the_function(window):
    window.open_help("save")
    assert "Ctrl+S" in window.help_window.page.toPlainText()


def test_do_it_now_goes_to_the_function(window, monkeypatch):
    ran = []
    monkeypatch.setitem(window.feature_handlers, "annotations", lambda: ran.append(True))
    window.open_help("annotations")
    window.help_window.run_button.click()
    assert not window.help_window.isVisible()
    assert window._mode is Mode.STUDY
    assert ran == [True]


def test_functions_not_built_yet_say_so(window):
    missing = [feature.id for feature in FEATURES if feature.id not in window.feature_handlers]
    if not missing:
        return
    window.open_help(missing[0])
    assert "Todavía no está disponible" in window.help_window.page.toPlainText()
    assert not window.help_window.run_button.isVisibleTo(window.help_window)


def test_f1_in_the_finder_tells_how_the_function_is_used(window):
    palette = CommandPalette(window)
    palette.show()
    QTest.keyClicks(palette.query, "unir")
    QTest.keyClick(palette.query, Qt.Key.Key_F1)
    assert palette.help_wanted.id == "merge"
    assert palette.chosen is None


def test_the_finder_offers_the_help_when_it_finds_nothing(window):
    palette = CommandPalette(window)
    palette.show()
    palette.query.setText("apagón")
    assert palette.ask_help.isVisible()
    palette.ask_help.click()
    assert palette.help_query == "apagón"
    window.open_help(query=palette.help_query)
    assert window.help_window.current.id == "recover_crash"


def test_one_tip_a_day_each_a_different_one(settings):
    today = datetime.date(2026, 11, 24)
    first = help_topics.tip_for_today(settings, today)
    assert first == help_topics.TIPS[0]
    assert help_topics.tip_for_today(settings, today) is None
    second = help_topics.tip_for_today(settings, today + datetime.timedelta(days=1))
    assert second == help_topics.TIPS[1]


def test_tips_can_be_turned_off(window):
    window.offer_tip()
    banner = window.tip_banner
    assert banner.isVisible()
    shown = banner.message.text()
    banner.another_button.click()
    assert banner.message.text() != shown
    banner.never_button.click()
    assert not banner.isVisible()
    assert not help_topics.tips_wanted(window.settings)
    assert help_topics.tip_for_today(window.settings, datetime.date(2030, 1, 1)) is None


def test_the_tip_opens_its_page(window):
    window.offer_tip()
    window.tip_banner.how_button.click()
    assert not window.tip_banner.isVisible()
    assert window.help_window.current.id == help_topics.TIPS[0][1]
