from __future__ import annotations

import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.books import CANONICAL_BOOKS
from app.config import settings
from app.db import init_db, replace_original_words, session
from app.original_languages import parse_original_usfm

# Legacy compatibility installer only. Normal startup now derives the compact
# drawer from the verified deep OSHB/Tischendorf corpus instead of downloading
# this second source set.
SOURCES = [
    {
        "source": "UHB v2.1.32",
        "language": "hebrew",
        "url": "https://git.door43.org/unfoldingWord/hbo_uhb/archive/v2.1.32.zip",
        "folder": "uhb-v2.1.32",
    },
    {
        "source": "UGNT v0.34",
        "language": "greek",
        "url": "https://git.door43.org/unfoldingWord/el-x-koine_ugnt/archive/v0.34.zip",
        "folder": "ugnt-v0.34",
    },
]

USFM_CODES = {
    "GEN":"Genesis","EXO":"Exodus","LEV":"Leviticus","NUM":"Numbers","DEU":"Deuteronomy","JOS":"Joshua","JDG":"Judges","RUT":"Ruth",
    "1SA":"1 Samuel","2SA":"2 Samuel","1KI":"1 Kings","2KI":"2 Kings","1CH":"1 Chronicles","2CH":"2 Chronicles","EZR":"Ezra","NEH":"Nehemiah",
    "EST":"Esther","JOB":"Job","PSA":"Psalms","PRO":"Proverbs","ECC":"Ecclesiastes","SNG":"Song of Solomon","ISA":"Isaiah","JER":"Jeremiah",
    "LAM":"Lamentations","EZK":"Ezekiel","DAN":"Daniel","HOS":"Hosea","JOL":"Joel","AMO":"Amos","OBA":"Obadiah","JON":"Jonah","MIC":"Micah",
    "NAM":"Nahum","HAB":"Habakkuk","ZEP":"Zephaniah","HAG":"Haggai","ZEC":"Zechariah","MAL":"Malachi","MAT":"Matthew","MRK":"Mark","LUK":"Luke",
    "JHN":"John","ACT":"Acts","ROM":"Romans","1CO":"1 Corinthians","2CO":"2 Corinthians","GAL":"Galatians","EPH":"Ephesians","PHP":"Philippians",
    "COL":"Colossians","1TH":"1 Thessalonians","2TH":"2 Thessalonians","1TI":"1 Timothy","2TI":"2 Timothy","TIT":"Titus","PHM":"Philemon","HEB":"Hebrews",
    "JAS":"James","1PE":"1 Peter","2PE":"2 Peter","1JN":"1 John","2JN":"2 John","3JN":"3 John","JUD":"Jude","REV":"Revelation",
}
BOOK_ORDER = {b: i + 1 for i, b in enumerate(CANONICAL_BOOKS)}


def _safe_extract(payload: bytes, tmp: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        base = tmp.resolve()
        for member in zf.infolist():
            dest = (tmp / member.filename).resolve()
            if dest != base and base not in dest.parents:
                raise RuntimeError(f"Unsafe archive path: {member.filename}")
        zf.extractall(tmp)


def download_extract(url: str, dest: Path) -> Path:
    if dest.exists() and (any(dest.rglob("*.usfm")) or any(dest.rglob("*.sfm"))):
        return dest
    print(f"Downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "BibleEngine-OriginalLanguageLab/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        payload = response.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / (dest.name + "-extract")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    _safe_extract(payload, tmp)
    roots = [p for p in tmp.iterdir() if p.is_dir()]
    source_root = roots[0] if len(roots) == 1 else tmp
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(source_root), str(dest))
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def book_for_file(path: Path) -> str | None:
    stem = path.stem.upper()
    for code, book in USFM_CODES.items():
        if stem.endswith(code) or f"-{code}" in stem or f"_{code}" in stem:
            return book
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:800]
    except OSError:
        return None
    import re
    m = re.search(r"(?m)^\\id\s+([0-9A-Z]{3})", head)
    return USFM_CODES.get(m.group(1)) if m else None


def seed_source(spec: dict) -> int:
    cache = ROOT / "data" / "sources" / "original" / spec["folder"]
    source_root = download_extract(spec["url"], cache)
    all_rows: list[dict] = []
    files = sorted(list(source_root.rglob("*.usfm")) + list(source_root.rglob("*.sfm")))
    for path in files:
        book = book_for_file(path)
        if not book or book not in BOOK_ORDER:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        rows = parse_original_usfm(
            text,
            book=book,
            book_order=BOOK_ORDER[book],
            language=spec["language"],
            source=spec["source"],
        )
        all_rows.extend(rows)
    if not all_rows:
        raise RuntimeError(f"No original-language words parsed from {spec['source']}. Source format may have changed.")
    with session(settings.db_path) as conn:
        count = replace_original_words(conn, spec["source"], all_rows)
    print(f"Indexed {count:,} words from {spec['source']}.")
    return count


def main() -> int:
    init_db(settings.db_path)
    counts = []
    for spec in SOURCES:
        counts.append(seed_source(spec))
    if any(n < 100000 for n in counts):
        print("Legacy original-language compatibility corpus looks incomplete.", file=sys.stderr)
        return 1
    print("Legacy Original-Language compatibility corpus ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
