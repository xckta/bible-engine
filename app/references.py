from __future__ import annotations

import re
from dataclasses import dataclass
from .books import BOOKS, ALIASES, normalize_book

@dataclass(frozen=True)
class BibleRef:
    book: str
    chapter: int
    verse_start: int | None = None
    verse_end: int | None = None

# Only known canonical book names/aliases are eligible. This intentionally avoids
# treating ordinary prose such as "with 2" as a Bible reference.
_NAMES = set(BOOKS) | set(ALIASES.keys())
BOOK_PATTERN = "|".join(sorted((re.escape(b) for b in _NAMES), key=len, reverse=True))
REF_RE = re.compile(
    rf"(?<!\w)(?P<book>{BOOK_PATTERN})\.?(?!\w)\s+(?P<chapter>\d+)(?::(?P<v1>\d+)(?:\s*[-–]\s*(?P<v2>\d+))?)?",
    re.IGNORECASE,
)

def extract_references(text: str) -> list[BibleRef]:
    refs: list[BibleRef] = []
    for m in REF_RE.finditer(text):
        book = normalize_book(m.group("book"))
        if not book:
            continue
        v1 = int(m.group("v1")) if m.group("v1") else None
        v2 = int(m.group("v2")) if m.group("v2") else v1
        refs.append(BibleRef(book, int(m.group("chapter")), v1, v2))
    return refs
