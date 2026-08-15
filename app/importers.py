from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .books import BOOKS, normalize_book

INLINE_MARKER = re.compile(r"\\(?:add|bd|bdit|bk|dc|em|it|k|nd|ord|pn|qt|sig|sls|tl|wj|no|sc|sup|rb|pro|w)\*?")
NOTE_BLOCK = re.compile(r"\\(?:f|x)\s.*?\\(?:f|x)\*", re.DOTALL)
OTHER_MARKER = re.compile(r"\\[a-zA-Z0-9]+\*?(?:\s+)?")


def clean_usfm_text(text: str) -> str:
    text = NOTE_BLOCK.sub(" ", text)
    text = INLINE_MARKER.sub("", text)
    text = re.sub(r"\\w\s+([^|\\]+)\|[^\\]*?\\w\*", r"\1", text)
    text = OTHER_MARKER.sub(" ", text)
    return " ".join(text.replace("~", " ").split())


def _book_from_usfm(raw: str, fallback: str | None = None) -> str | None:
    raw = raw.strip()
    normalized = normalize_book(raw)
    if normalized:
        return normalized
    codes = {
        "GEN":"Genesis","EXO":"Exodus","LEV":"Leviticus","NUM":"Numbers","DEU":"Deuteronomy","JOS":"Joshua",
        "JDG":"Judges","RUT":"Ruth","1SA":"1 Samuel","2SA":"2 Samuel","1KI":"1 Kings","2KI":"2 Kings",
        "1CH":"1 Chronicles","2CH":"2 Chronicles","EZR":"Ezra","NEH":"Nehemiah","EST":"Esther","JOB":"Job",
        "PSA":"Psalms","PRO":"Proverbs","ECC":"Ecclesiastes","SNG":"Song of Solomon","ISA":"Isaiah","JER":"Jeremiah",
        "LAM":"Lamentations","EZK":"Ezekiel","DAN":"Daniel","HOS":"Hosea","JOL":"Joel","AMO":"Amos","OBA":"Obadiah",
        "JON":"Jonah","MIC":"Micah","NAM":"Nahum","HAB":"Habakkuk","ZEP":"Zephaniah","HAG":"Haggai","ZEC":"Zechariah",
        "MAL":"Malachi","MAT":"Matthew","MRK":"Mark","LUK":"Luke","JHN":"John","ACT":"Acts","ROM":"Romans",
        "1CO":"1 Corinthians","2CO":"2 Corinthians","GAL":"Galatians","EPH":"Ephesians","PHP":"Philippians","COL":"Colossians",
        "1TH":"1 Thessalonians","2TH":"2 Thessalonians","1TI":"1 Timothy","2TI":"2 Timothy","TIT":"Titus","PHM":"Philemon",
        "HEB":"Hebrews","JAS":"James","1PE":"1 Peter","2PE":"2 Peter","1JN":"1 John","2JN":"2 John","3JN":"3 John",
        "JUD":"Jude","REV":"Revelation",
    }
    first = raw.split()[0].upper()
    return codes.get(first) or (normalize_book(fallback) if fallback else None)


def parse_usfm_files(paths: Iterable[Path]) -> list[dict]:
    verses: list[dict] = []
    book_order = {b: i + 1 for i, b in enumerate(BOOKS)}
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        # Remove note/cross-reference blocks before line parsing so multiline notes cannot leak into verse text.
        text = NOTE_BLOCK.sub(" ", text)
        id_match = re.search(r"(?m)^\\id\s+([^\r\n]+)", text)
        toc_match = re.search(r"(?m)^\\toc1\s+([^\r\n]+)", text)
        book = _book_from_usfm(id_match.group(1) if id_match else "", toc_match.group(1) if toc_match else path.stem)
        if not book or book not in book_order:
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
                    "book_order": book_order[book],
                    "chapter": chapter,
                    "verse": int(vm.group(1)),
                    "text": clean_usfm_text(vm.group(2)),
                }
                verses.append(current)
                continue
            if current and line:
                # Poetry/paragraph markers may contain continuation text belonging to the current verse.
                # Headings and book metadata must never be appended to a verse.
                nonverse = ("\\id", "\\ide", "\\usfm", "\\h", "\\toc", "\\mt", "\\mte",
                            "\\s", "\\ms", "\\mr", "\\r", "\\d", "\\sp", "\\qa",
                            "\\cl", "\\cp", "\\rem", "\\sts", "\\restore", "\\periph")
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
    book_order = {b: i + 1 for i, b in enumerate(BOOKS)}
    out = []
    for row in rows:
        book = normalize_book(str(row["book"]))
        if not book:
            raise ValueError(f"Unknown book: {row['book']}")
        out.append({
            "book": book,
            "book_order": book_order[book],
            "chapter": int(row["chapter"]),
            "verse": int(row["verse"]),
            "text": str(row["text"]).strip(),
        })
    return out
