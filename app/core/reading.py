"""The text of a page as a screen reader reads it.

A screen reader (NVDA, JAWS, Narrator) cannot read a picture: it needs the
words. Adobe Reader, Edge and Chrome hand it the text of the PDF in reading
order. Here, the text of each page is written as running text: the lines of a
paragraph joined, words split by a hyphen at the end of a line whole again,
every paragraph on its own line (the same text "Copiar" gives).

For every character of that text it is known which letter of the page it
comes from, so that moving through the text moves through the page: the page
scrolls to it, and what is selected while reading is selected on the page
(and can then be highlighted).
"""

from array import array
from bisect import bisect_right
from dataclasses import dataclass, field

from app.core.search import _LINE_END_HYPHENS, _SOFT_HYPHEN, PageText


@dataclass
class ReadingText:
    """A page as running text, and where each of its characters is on the page."""

    text: str = ""
    # For every character of ``text``, the letter of the page it stands for
    # (a space or a line break added between lines: the letter after it).
    letters: array = field(default_factory=lambda: array("I"))

    def letter_at(self, offset: int) -> int:
        """The letter of the page at a place of the text (the end: after the last)."""
        if not self.letters:
            return 0
        if offset >= len(self.letters):
            return self.letters[-1] + 1
        return self.letters[max(0, offset)]

    def offset_of(self, letter: int) -> int:
        """The place in the text of a letter of the page (or of the next one shown)."""
        if not self.letters:
            return 0
        place = bisect_right(self.letters, letter)
        if place > 0 and self.letters[place - 1] == letter:
            return place - 1  # the letter itself, not the line break before it
        return place


def reading_text(text: PageText) -> ReadingText:
    """The running text of a page, with where each character comes from."""
    chars, lines, blocks = text.chars, text.lines, text.line_blocks
    out: list[str] = []
    letters = array("I")
    joined = False  # the line before ended in a split word

    def put(char: str, letter: int) -> None:
        out.append(char)
        letters.append(letter)

    for letter in range(len(chars)):
        char = chars[letter]
        if letter > 0 and lines[letter] != lines[letter - 1]:
            same_paragraph = (
                lines[letter] < len(blocks) and blocks[lines[letter]] == blocks[lines[letter - 1]]
            )
            if not joined:
                while out and out[-1] == " ":
                    out.pop()
                    letters.pop()
                if out:
                    put(" " if same_paragraph else "\n", letter)
            joined = False
        if char == _SOFT_HYPHEN:
            continue
        if letter in text.split_hyphens and char in _LINE_END_HYPHENS:
            joined = True
            continue
        if char.isspace():
            if joined or not out or out[-1] in " \n":
                continue
            char = " "
        put(char, letter)
    while out and out[-1] in " \n":
        out.pop()
        letters.pop()
    return ReadingText("".join(out), letters)


# ---- the reading cursor (F7) ------------------------------------------------------

# On or off, as it was left (F7, like caret browsing in Edge and Chrome).
CURSOR_SETTING = "cursor_lectura"
# On by itself while a screen reader (NVDA, JAWS, Narrator) is running.
WITH_SCREEN_READER_SETTING = "cursor_lectura_con_lector"


def cursor_chosen(settings) -> bool:
    return bool(settings.get(CURSOR_SETTING, False))


def with_screen_reader(settings) -> bool:
    return bool(settings.get(WITH_SCREEN_READER_SETTING, True))


def cursor_wanted(settings, screen_reader: bool) -> bool:
    """Whether the page is read with the reading cursor now."""
    return cursor_chosen(settings) or (screen_reader and with_screen_reader(settings))
