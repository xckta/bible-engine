from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.books import CANONICAL_BOOKS
from app.config import settings
from app.db import init_db, session
from app.intertext_graph import add_edge, ensure_graph_schema, extract_usfm_crossrefs, graph_stats

BOOK_ORDER = {b: i + 1 for i, b in enumerate(CANONICAL_BOOKS)}
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

CURATED = [
    ("Jude 1:14–15", "1 Enoch 1:9", "explicit_quotation", 1.0,
     "Jude introduces this saying with an explicit quotation formula; the graph records the direct textual relationship.",
     "Bible Engine curated intertext layer"),
    ("Jude 1:6", "1 Enoch 6–16", "ancient_context", 0.88,
     "1 Enoch 6–16 is a major ancient Jewish elaboration of rebellious angel traditions relevant to Jude 6; it is context, not canonical proof.",
     "Bible Engine curated Second Temple context"),
    ("Genesis 6:1–4", "1 Enoch 6–16", "ancient_context", 0.86,
     "The Enochic Watchers narrative develops an ancient interpretation of Genesis 6:1–4.",
     "Bible Engine curated Second Temple context"),
    ("Jude 1:6", "2 Peter 2:4", "canonical_parallel", 0.94,
     "Both canonical passages describe sinful angels kept for judgment using closely parallel judgment imagery.",
     "Bible Engine curated canonical parallel"),
    ("Jude 1:7", "2 Peter 2:6", "canonical_parallel", 0.82,
     "Both contexts use Sodom and Gomorrah as an example of divine judgment.",
     "Bible Engine curated canonical parallel"),
    ("2 Peter 2:4", "1 Enoch 10", "ancient_context", 0.76,
     "Enochic judgment traditions concerning rebellious angels provide relevant ancient context for 2 Peter 2:4.",
     "Bible Engine curated Second Temple context"),
    ("Daniel 7:13–14", "1 Enoch 46:1–6", "ancient_context", 0.68,
     "The Enochic Son of Man material is useful comparative Second Temple context for Daniel 7 imagery.",
     "Bible Engine curated Second Temple context"),
    ("Deuteronomy 32:8", "Psalms 82:1", "thematic_parallel", 0.62,
     "Both passages participate in canonical language concerning divine/heavenly beings and the nations; this edge is thematic rather than a quotation claim.",
     "Bible Engine curated thematic parallel"),
]


def detect_book(path: Path) -> str | None:
    try:
        head = path.read_text(encoding="utf-8-sig", errors="replace")[:1000]
    except OSError:
        return None
    m = re.search(r"(?m)^\\id\s+([0-9A-Z]{3})", head)
    return USFM_CODES.get(m.group(1)) if m else None


def seed_web_crossrefs(conn) -> int:
    roots = [ROOT / "data" / "sources" / "web", ROOT / "data" / "sources" / "web_usfm"]
    root = next((r for r in roots if r.exists()), None)
    if not root:
        print("WEB USFM source directory not found; skipping source-file cross-reference import.")
        return 0
    count = 0
    files = sorted(list(root.rglob("*.usfm")) + list(root.rglob("*.sfm")))
    for path in files:
        book = detect_book(path)
        if not book or book not in BOOK_ORDER:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for source, target in extract_usfm_crossrefs(text, book=book):
            count += add_edge(
                conn, source, target, "cross_reference", strength=0.55,
                rationale="Cross-reference encoded in the installed WEB USFM source; presence does not by itself establish quotation or allusion.",
                provenance="WEB USFM cross-reference", provenance_class="source_cross_reference",
            )
    return count


def seed_curated(conn) -> int:
    count = 0
    for source, target, typ, strength, rationale, provenance in CURATED:
        count += add_edge(
            conn, source, target, typ, strength=strength, rationale=rationale,
            provenance=provenance, provenance_class="curated",
        )
    return count


def build_graph(conn, *, include_source_crossrefs: bool = True) -> dict:
    ensure_graph_schema(conn)
    conn.execute("DELETE FROM intertext_edges WHERE provenance_class IN ('source_cross_reference','curated')")
    xref_count = seed_web_crossrefs(conn) if include_source_crossrefs else 0
    curated_count = seed_curated(conn)
    stats = graph_stats(conn)
    return {**stats, "source_crossrefs": xref_count, "curated": curated_count}


def main() -> int:
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        stats = build_graph(conn)
    print(
        f"Intertext graph ready: {stats['edge_count']:,} edges "
        f"({stats['source_crossrefs']:,} source cross-references + {stats['curated']} curated edges)."
    )
    return 0 if stats["edge_count"] >= len(CURATED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
