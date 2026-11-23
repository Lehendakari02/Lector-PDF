"""Sleeping tabs: documents out of sight for a while give back their memory.

Every open document has its own helper process (about 60 MB) and its drawn
pages. With 15 or 20 documents open, which is normal for studying, that is
more than 1 GB. Like the sleeping tabs of Edge, a document that has not been
looked at for a while stops its helper; the tab stays as it was, and when it
is looked at again it wakes up by itself on the same page, with its changes.

A document leaving the screen keeps only the pictures of the pages it showed,
at once: they are enough to show it again while the rest is drawn.

It can be turned off, and the time out of sight can be chosen.
"""

from app.core.settings import Settings

SLEEP_SETTING = "pestanas_dormir"
MINUTES_SETTING = "pestanas_dormir_minutos"
MINUTE_CHOICES = (5, 15, 30, 60, 120)
DEFAULT_MINUTES = 15


def sleep_wanted(settings: Settings) -> bool:
    return settings.get(SLEEP_SETTING, True) is not False


def sleep_minutes(settings: Settings) -> int:
    value = settings.get(MINUTES_SETTING, DEFAULT_MINUTES)
    return value if value in MINUTE_CHOICES else DEFAULT_MINUTES


def time_to_sleep(settings: Settings, unseen_seconds: float) -> bool:
    """Whether a document out of sight for this long goes to sleep."""
    return sleep_wanted(settings) and unseen_seconds >= sleep_minutes(settings) * 60
