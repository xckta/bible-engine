from __future__ import annotations

import re
from dataclasses import dataclass
from .books import ALL_BIBLICAL_WORKS, ALIASES, REFERENCE_WORKS, normalize_book


@dataclass(frozen=True)
class TextRef:
    work: str
    chapter: int
    verse_start: int | None = None
    verse_end: int | None = None
    kind: str = "biblical"


_NAMES = set(ALL_BIBLICAL_WORKS) | set(ALIASES.keys())
BOOK_PATTERN = "|".join(sorted((re.escape(b) for b in _NAMES), key=len, reverse=True))
REF_RE = re.compile(
    rf"(?<!\w)(?P<book>{BOOK_PATTERN})\.?(?!\w)\s+(?P<chapter>\d+)(?::(?P<v1>\d+)(?:\s*[-–]\s*(?P<v2>\d+))?)?",
    re.IGNORECASE,
)

REF_WORK_ALIASES = {
    "enoch": "1 Enoch", "1 enoch": "1 Enoch", "ethiopic enoch": "1 Enoch",
    "jubilees": "Jubilees", "book of jubilees": "Jubilees",
    "assumption of moses": "Assumption of Moses", "testament of moses": "Assumption of Moses",
    "2 baruch": "2 Baruch", "syriac baruch": "2 Baruch", "apocalypse of baruch": "2 Baruch",
    "psalms of solomon": "Psalms of Solomon", "psalter of solomon": "Psalms of Solomon",
    "testaments of the twelve patriarchs": "Testaments of the Twelve Patriarchs", "twelve patriarchs": "Testaments of the Twelve Patriarchs",
    "ascension of isaiah": "Ascension / Martyrdom of Isaiah", "martyrdom of isaiah": "Ascension / Martyrdom of Isaiah",
    "letter of aristeas": "Letter of Aristeas", "aristeas": "Letter of Aristeas",
    "apocalypse of moses": "Apocalypse of Moses",
    "slavonic life of adam and eve": "Slavonic Life of Adam and Eve",
    "books of adam and eve": "Books of Adam and Eve",
}
_REF_NAMES = set(REF_WORK_ALIASES) | {w.name.lower() for w in REFERENCE_WORKS}
REF_WORK_PATTERN = "|".join(sorted((re.escape(x) for x in _REF_NAMES), key=len, reverse=True))
REFERENCE_RE = re.compile(
    rf"(?<!\w)(?P<work>{REF_WORK_PATTERN})(?!\w)(?:\s+(?P<chapter>\d+)(?::(?P<v1>\d+)(?:\s*[-–]\s*(?P<v2>\d+))?)?)?",
    re.IGNORECASE,
)


def extract_references(text: str) -> list[TextRef]:
    refs: list[TextRef] = []
    spans: list[tuple[int, int]] = []
    for m in REF_RE.finditer(text):
        book = normalize_book(m.group("book"))
        if not book:
            continue
        v1 = int(m.group("v1")) if m.group("v1") else None
        v2 = int(m.group("v2")) if m.group("v2") else v1
        refs.append(TextRef(book, int(m.group("chapter")), v1, v2, "biblical"))
        spans.append(m.span())
    for m in REFERENCE_RE.finditer(text):
        if any(max(m.start(), a) < min(m.end(), b) for a, b in spans):
            continue
        raw = m.group("work").lower()
        work = REF_WORK_ALIASES.get(raw, next((w.name for w in REFERENCE_WORKS if w.name.lower() == raw), raw))
        chapter = int(m.group("chapter")) if m.group("chapter") else 0
        v1 = int(m.group("v1")) if m.group("v1") else None
        v2 = int(m.group("v2")) if m.group("v2") else v1
        refs.append(TextRef(work, chapter, v1, v2, "reference"))
    return refs
