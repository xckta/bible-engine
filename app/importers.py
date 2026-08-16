from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .books import ALL_BIBLICAL_WORKS, BOOK_ORDER, USFM_CODES, normalize_book, tier_for_book

INLINE_MARKER = re.compile(r"\\(?:add|bd|bdit|bk|dc|em|it|k|nd|ord|pn|qt|sig|sls|tl|wj|no|sc|sup|rb|pro|w)\*?")
NOTE_BLOCK = re.compile(r"\\(?:f|x)\s.*?\\(?:f|x)\*", re.DOTALL)
OTHER_MARKER = re.compile(r"\\[a-zA-Z0-9]+\*?(?:\s+)?")


def clean_usfm_text(text: str) -> str:
    text = NOTE_BLOCK.sub(" ", text)
    text = re.sub(r"\\w\s+([^|\\]+)\|[^\\]*?\\w\*", r"\1", text)
    text = INLINE_MARKER.sub("", text)
    text = OTHER_MARKER.sub(" ", text)
    return " ".join(text.replace("~", " ").split())


def _book_from_usfm(raw: str, fallback: str | None = None) -> str | None:
    raw = raw.strip()
    first = raw.split()[0].upper() if raw else ""
    if first in USFM_CODES:
        return USFM_CODES[first]
    normalized = normalize_book(raw)
    if normalized:
        return normalized
    return normalize_book(fallback) if fallback else None


def parse_usfm_files(paths: Iterable[Path]) -> list[dict]:
    verses: list[dict] = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        text = NOTE_BLOCK.sub(" ", text)
        id_match = re.search(r"(?m)^\\id\s+([^\r\n]+)", text)
        toc_match = re.search(r"(?m)^\\toc1\s+([^\r\n]+)", text)
        book = _book_from_usfm(id_match.group(1) if id_match else "", toc_match.group(1) if toc_match else path.stem)
        if not book or book not in BOOK_ORDER:
            continue
        chapter = 0
        current: dict | None = None
        for line in text.splitlines():
            cm = re.match(r"^\\c\s+(\d+)", line)
            if cm:
                chapter = int(cm.group(1))
                current = None
                continue
            vm = re.match(r"^\\v\s+(\d+)(?:[-–]\d+)?\s*(.*)", line)
            if vm and chapter:
                current = {
                    "book": book,
                    "book_order": BOOK_ORDER[book],
                    "chapter": chapter,
                    "verse": int(vm.group(1)),
                    "text": clean_usfm_text(vm.group(2)),
                    "corpus_tier": tier_for_book(book),
                }
                verses.append(current)
                continue
            if current and line:
                nonverse = (
                    "\\id", "\\ide", "\\usfm", "\\h", "\\toc", "\\mt", "\\mte", "\\s", "\\ms",
                    "\\mr", "\\r", "\\d", "\\sp", "\\qa", "\\cl", "\\cp", "\\rem", "\\sts",
                    "\\restore", "\\periph",
                )
                if not line.startswith(nonverse):
                    extra = clean_usfm_text(line)
                    if extra:
                        current["text"] = (current["text"] + " " + extra).strip()
    return verses


def parse_json_file(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["verses"] if isinstance(payload, dict) and "verses" in payload else payload
    if not isinstance(rows, list):
        raise ValueError("JSON corpus must be a list or an object with a 'verses' list")
    out = []
    for row in rows:
        book = normalize_book(str(row["book"]))
        if not book or book not in ALL_BIBLICAL_WORKS:
            raise ValueError(f"Unknown book: {row['book']}")
        out.append({
            "book": book,
            "book_order": BOOK_ORDER[book],
            "chapter": int(row["chapter"]),
            "verse": int(row["verse"]),
            "text": str(row["text"]).strip(),
            "corpus_tier": tier_for_book(book),
        })
    return out
