"""How a signature with a certificate looks, and whether it has a timestamp.

Nobody has to touch anything: by default the signature is visible (a box with
the name, the date and the handwritten signature, if one is saved) and has no
timestamp, so nothing leaves the computer. Signing is then choosing where and
typing the PIN.

Whatever is stored is read with care: a value that is not one of the choices
counts as the default.
"""

from app.core.batch_signing import BOTTOM_RIGHT, CORNERS, LAST, PAGES
from app.core.settings import Settings
from app.core.signing import DEFAULT_TIMESTAMP_SERVER

# Visible (a box on the page) or invisible (only in the signature panel of
# the reader).
VISIBLE_SETTING = "firma/visible"
# Whether the visible box shows the handwritten signature saved in the program.
HANDWRITTEN_SETTING = "firma/manuscrita"
# Whether to ask a timestamping server for the time (it goes on the internet;
# only a fingerprint of the document is sent).
TIMESTAMP_SETTING = "firma/sello_tiempo"
TIMESTAMP_SERVER_SETTING = "firma/servidor_sello"
# Signing several documents at once: the page and the corner used last time.
BATCH_PAGE_SETTING = "firma/varios_pagina"
BATCH_CORNER_SETTING = "firma/varios_esquina"


def visible_wanted(settings: Settings) -> bool:
    return settings.get(VISIBLE_SETTING, True) is not False


def handwritten_wanted(settings: Settings) -> bool:
    return settings.get(HANDWRITTEN_SETTING, True) is not False


def timestamp_wanted(settings: Settings) -> bool:
    return settings.get(TIMESTAMP_SETTING, False) is True


def timestamp_server(settings: Settings) -> str:
    value = settings.get(TIMESTAMP_SERVER_SETTING, "")
    if isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
        return value.strip()
    return DEFAULT_TIMESTAMP_SERVER


def batch_page(settings: Settings) -> str:
    value = settings.get(BATCH_PAGE_SETTING, LAST)
    return value if value in PAGES else LAST


def batch_corner(settings: Settings) -> str:
    value = settings.get(BATCH_CORNER_SETTING, BOTTOM_RIGHT)
    return value if value in CORNERS else BOTTOM_RIGHT
