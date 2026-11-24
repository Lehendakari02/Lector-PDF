"""«Comparar»: what text was added, taken out or changed between two versions
of a document (a law that has been modified, a contract sent back…).

The text of each version is read word by word, in reading order, with the
place of every word on its page. The two lists of words are then lined up
(Python's ``difflib``, the same idea as the "compare documents" of word
processors) and every stretch that is not the same is one change.

What does not count as a change: how the text is laid out (where lines and
pages break), a word split with a hyphen at the end of a line, the kind of
quotes or dashes («», “”, "…). Everything else counts: a letter, an accent,
a capital, a comma.
"""

import difflib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.core.search import read_page_text

ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"

# Two changes with only this many equal words between them are shown as one:
# "treinta días hábiles" → "cuarenta días naturales" reads better than two.
JOIN_GAP = 1
CONTEXT_WORDS = 6
# Longer changes are cut in the list (the marks on the pages show them whole).
SHOWN_WORDS = 40
# Parts with no word in common are lined up word by word only up to this
# size (words of one by words of the other): beyond it, it would take long.
SLOW_LIMIT = 4_000_000

Rect = tuple[float, float, float, float]

_SAME = str.maketrans(
    {
        "«": '"',
        "»": '"',
        "“": '"',
        "”": '"',
        "„": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "–": "-",
        "—": "-",
        "‐": "-",
        "‑": "-",
        "−": "-",
    }
)


@dataclass(frozen=True)
class Spot:
    """Where some words are on one page: one rectangle per line they touch."""

    page: int
    rects: tuple[Rect, ...]


@dataclass(frozen=True)
class Change:
    """One difference between the old version and the new one."""

    kind: str  # ADDED, REMOVED or CHANGED
    old_text: str  # "" when added
    new_text: str  # "" when removed
    before: str  # the words just before, to recognise the place
    after: str
    old_page: int  # where to look in each version (for an addition, the old
    new_page: int  # page is where the words would have been, and so on)
    old_spots: tuple[Spot, ...]
    new_spots: tuple[Spot, ...]


@dataclass
class Words:
    """The words of a document in reading order, with their places."""

    texts: list[str]
    pages: list[int]
    rects: list[tuple[Rect, ...]]  # one per line the word touches
    page_count: int = 0


def read_words(doc) -> Words:
    """Every word of the document, a word split at a line end taken as one."""
    words = Words([], [], [], doc.page_count)
    for number in range(doc.page_count):
        text = read_page_text(doc[number])
        chars, lines, hyphens = text.chars, text.lines, text.split_hyphens
        letters: list[str] = []
        rects: list[list[float]] = []
        line = -1

        joining = False  # the last letter was a hyphen that splits the word
        for index, char in enumerate(chars):
            if index in hyphens:
                joining = True
                continue
            if char.isspace() or char == "­":
                if not (joining and lines[index] == line):
                    # A space after the splitting hyphen, on its own line,
                    # does not end the word.
                    _finish(words, number, letters, rects)
                    joining = False
                continue
            if lines[index] != line and not joining:
                _finish(words, number, letters, rects)
            joining = False
            box = text.box(index)
            if lines[index] != line or not rects:
                rects.append(list(box))
            else:
                last = rects[-1]
                last[0], last[1] = min(last[0], box[0]), min(last[1], box[1])
                last[2], last[3] = max(last[2], box[2]), max(last[3], box[3])
            line = lines[index]
            letters.append(char)
        _finish(words, number, letters, rects)
    return words


def _finish(words: Words, page: int, letters: list[str], rects: list[list[float]]) -> None:
    """One word read: keep it, and start the next."""
    if letters:
        words.texts.append("".join(letters))
        words.pages.append(page)
        words.rects.append(tuple(tuple(r) for r in rects))
        letters.clear()
        rects.clear()


def _key(word: str) -> str:
    return unicodedata.normalize("NFC", word).translate(_SAME)


def _spots(words: Words, start: int, stop: int) -> tuple[Spot, ...]:
    spots: list[Spot] = []
    for index in range(start, stop):
        page = words.pages[index]
        if spots and spots[-1].page == page:
            spots[-1] = Spot(page, spots[-1].rects + words.rects[index])
        else:
            spots.append(Spot(page, words.rects[index]))
    return tuple(spots)


def _page_at(words: Words, start: int, stop: int) -> int:
    """The page of these words; for none (an addition), of the word before."""
    if start < stop:
        return words.pages[start]
    if start > 0:
        return words.pages[start - 1]
    if words.pages:
        return words.pages[0]
    return 0


def _text(words: Words, start: int, stop: int) -> str:
    shown = words.texts[start : min(stop, start + SHOWN_WORDS)]
    return " ".join(shown) + (" …" if stop - start > SHOWN_WORDS else "")


def _longest_rising(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The longest run of ``pairs`` (sorted by their first number) whose second
    numbers go up too: the words that stay in the same order in both."""
    tails: list[int] = []  # index in pairs of the smallest end of each length
    links: list[int] = [-1] * len(pairs)
    for index, (_i, j) in enumerate(pairs):
        place = _bisect_tails(pairs, tails, j)
        if place > 0:
            links[index] = tails[place - 1]
        if place == len(tails):
            tails.append(index)
        else:
            tails[place] = index
    run: list[tuple[int, int]] = []
    index = tails[-1] if tails else -1
    while index >= 0:
        run.append(pairs[index])
        index = links[index]
    return run[::-1]


def _bisect_tails(pairs, tails, j) -> int:
    low, high = 0, len(tails)
    while low < high:
        middle = (low + high) // 2
        if pairs[tails[middle]][1] < j:
            low = middle + 1
        else:
            high = middle
    return low


def _same_words(a: list[str], b: list[str]) -> list[tuple[int, int, int]]:
    """Blocks of words that are the same in both, as (a start, b start, size).

    Like "patience diff" (git): words found once in each part are lined up
    first and split the work in small pieces; only the small pieces with no
    such word are lined up with ``difflib``, which is slow on long texts with
    words that repeat (a law says "artículo" thousands of times).
    """
    blocks: list[tuple[int, int, int]] = []
    work = [(0, len(a), 0, len(b))]
    while work:
        alo, ahi, blo, bhi = work.pop()
        while alo < ahi and blo < bhi and a[alo] == b[blo]:
            blocks.append((alo, blo, 1))
            alo, blo = alo + 1, blo + 1
        while alo < ahi and blo < bhi and a[ahi - 1] == b[bhi - 1]:
            ahi, bhi = ahi - 1, bhi - 1
            blocks.append((ahi, bhi, 1))
        if alo == ahi or blo == bhi:
            continue
        seen_a: dict[str, int] = {}
        for i in range(alo, ahi):
            seen_a[a[i]] = -1 if a[i] in seen_a else i
        seen_b: dict[str, int] = {}
        for j in range(blo, bhi):
            word = b[j]
            if word in seen_a and seen_a[word] >= 0:
                seen_b[word] = -1 if word in seen_b else j
        pairs = sorted((seen_a[w], j) for w, j in seen_b.items() if j >= 0)
        anchors = _longest_rising(pairs)
        if not anchors:
            if (ahi - alo) * (bhi - blo) <= SLOW_LIMIT:
                matcher = difflib.SequenceMatcher(None, a[alo:ahi], b[blo:bhi], autojunk=False)
                for i, j, size in matcher.get_matching_blocks():
                    if size:
                        blocks.append((alo + i, blo + j, size))
            continue  # too long with nothing in common: one big change
        previous_a, previous_b = alo, blo
        for i, j in anchors:
            blocks.append((i, j, 1))
            work.append((previous_a, i, previous_b, j))
            previous_a, previous_b = i + 1, j + 1
        work.append((previous_a, ahi, previous_b, bhi))
    blocks.sort()
    return blocks


def _opcodes(blocks, a_size: int, b_size: int):
    """What is not the same, as (a start, a stop, b start, b stop)."""
    i = j = 0
    for start_a, start_b, size in [*blocks, (a_size, b_size, 0)]:
        if start_a > i or start_b > j:
            yield i, start_a, j, start_b
        i, j = start_a + size, start_b + size


def _slid(opcodes, a: list[str], b: list[str]):
    """Words added or taken out can often be placed in several ways ("tres
    meses. Artículo 3." taken out of "… Artículo 2. … tres meses. Artículo 3."
    could also be "2. … meses. Artículo"). Move each one to start after the end
    of a sentence when it can, as a person would mark it."""
    result = []
    for index, (i1, i2, j1, j2) in enumerate(opcodes):
        if (i1 == i2) == (j1 == j2):  # a word changed, or nothing: stays
            result.append((i1, i2, j1, j2))
            continue
        seq, start, stop = (b, j1, j2) if i1 == i2 else (a, i1, i2)
        other_start = i1 if i1 == i2 else j1
        # How far it can move without touching the changes next to it.
        low = result[-1][1 if seq is a else 3] if result else 0
        following = opcodes[index + 1] if index + 1 < len(opcodes) else None
        high_limit = following[0 if seq is a else 2] if following else len(seq)
        left = 0
        while start - left - 1 >= low and seq[start - left - 1] == seq[stop - left - 1]:
            left += 1
        right = 0
        while stop + right < high_limit and seq[start + right] == seq[stop + right]:
            right += 1
        best = 0
        for shift in range(-left, right + 1):
            before = start + shift - 1
            if before < 0 or seq[before][-1:] in ".:;":
                best = shift
                break
        start, stop, other_start = start + best, stop + best, other_start + best
        if seq is b:
            result.append((other_start, other_start, start, stop))
        else:
            result.append((start, stop, other_start, other_start))
    return result


def compare_words(old: Words, new: Words) -> list[Change]:
    """The changes that turn ``old`` into ``new``, in the order of the text."""
    a = [_key(w) for w in old.texts]
    b = [_key(w) for w in new.texts]
    stretches: list[list[int]] = []  # [old start, old stop, new start, new stop]
    for i1, i2, j1, j2 in _slid(list(_opcodes(_same_words(a, b), len(a), len(b))), a, b):
        if stretches and i1 - stretches[-1][1] <= JOIN_GAP and j1 - stretches[-1][3] <= JOIN_GAP:
            stretches[-1][1], stretches[-1][3] = i2, j2
        else:
            stretches.append([i1, i2, j1, j2])
    changes = []
    for i1, i2, j1, j2 in stretches:
        if i1 == i2:
            kind = ADDED
        elif j1 == j2:
            kind = REMOVED
        else:
            kind = CHANGED
        # The words around, from the version where the change can be seen.
        around, start, stop = (old, i1, i2) if kind == REMOVED else (new, j1, j2)
        before = " ".join(around.texts[max(0, start - CONTEXT_WORDS) : start])
        after = " ".join(around.texts[stop : stop + CONTEXT_WORDS])
        changes.append(
            Change(
                kind,
                _text(old, i1, i2),
                _text(new, j1, j2),
                before,
                after,
                _page_at(old, i1, i2),
                _page_at(new, j1, j2),
                _spots(old, i1, i2),
                _spots(new, j1, j2),
            )
        )
    return changes


@dataclass(frozen=True)
class Comparison:
    changes: list[Change]
    old_pages: int
    new_pages: int
    old_words: int
    new_words: int

    @property
    def added(self) -> int:
        return sum(change.kind == ADDED for change in self.changes)

    @property
    def removed(self) -> int:
        return sum(change.kind == REMOVED for change in self.changes)

    @property
    def changed(self) -> int:
        return sum(change.kind == CHANGED for change in self.changes)


class NoText(Exception):
    """One of the versions has no text (scanned pages not recognised yet)."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"{path.name} has no text")
        self.path = path


def compare_files(old, new) -> Comparison:
    """Compare two documents, each a ``combine.Source`` (path and password).
    Raises ``combine.NeedsPassword``, ``combine.CombineError`` or ``NoText``."""
    from app.core.combine import _open

    documents = []
    try:
        for source in (old, new):
            documents.append(_open(source))
        words = []
        for source, doc in zip((old, new), documents, strict=True):
            read = read_words(doc)
            if not read.texts:
                raise NoText(source.path)
            words.append(read)
    finally:
        for doc in documents:
            doc.close()
    changes = compare_words(words[0], words[1])
    return Comparison(
        changes, words[0].page_count, words[1].page_count, len(words[0].texts), len(words[1].texts)
    )
