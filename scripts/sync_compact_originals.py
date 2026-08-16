from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, replace_original_words, session
from app.original_storage import ensure_original_schema

LEGACY_SOURCES = {
    "OSHB": "UHB v2.1.32",
    "TISCH": "UGNT v0.34",
}


def rows_for_source(conn, source_code: str):
    """Project the verified deep-lab corpus into the compact drawer schema.

    The compact drawer is a compatibility cache only. The deep Original Language
    Lab remains the authoritative local original-language dataset.
    """
    ensure_original_schema(conn)
    rows = conn.execute(
        "SELECT w.book,w.book_order,w.chapter,w.verse,w.position,w.surface,"
        "w.surface_normalized,w.lemma,w.strongs,w.morph,w.transliteration,"
        "COALESCE(NULLIF(w.word_language,''),s.language) word_language "
        "FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id "
        "WHERE s.code=? ORDER BY w.book_order,w.chapter,w.verse,w.position,w.id",
        (source_code,),
    ).fetchall()

    # Deep-lab versification safeguards can map more than one source segment into
    # the same English verse. Renumber positions per target verse so the legacy
    # compact table's UNIQUE(source,book,chapter,verse,position) constraint remains valid.
    positions: dict[tuple[str, int, int], int] = defaultdict(int)
    for row in rows:
        key = (row["book"], int(row["chapter"]), int(row["verse"]))
        positions[key] += 1
        language = str(row["word_language"] or "").strip().lower()
        if language not in {"hebrew", "aramaic", "greek"}:
            language = "greek" if source_code == "TISCH" else "hebrew"
        yield {
            "language": language,
            "source": LEGACY_SOURCES[source_code],
            "book": row["book"],
            "book_order": int(row["book_order"]),
            "chapter": int(row["chapter"]),
            "verse": int(row["verse"]),
            "position": positions[key],
            "surface": row["surface"],
            "normalized": row["surface_normalized"] or "",
            "lemma": row["lemma"] or "",
            "strongs": row["strongs"] or "",
            "morph": row["morph"] or "",
            "transliteration": row["transliteration"] or "",
        }


def main() -> int:
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        ensure_original_schema(conn)
        counts = {
            row["code"]: int(row["n"])
            for row in conn.execute(
                "SELECT s.code,COUNT(w.id) n FROM original_lab_sources s "
                "LEFT JOIN original_lab_words w ON w.source_id=s.id "
                "WHERE s.code IN ('OSHB','TISCH') GROUP BY s.code"
            ).fetchall()
        }
        if counts.get("OSHB", 0) < 100000 or counts.get("TISCH", 0) < 100000:
            print(
                "Deep original-language corpus is not complete enough to build the compact drawer cache.",
                file=sys.stderr,
            )
            return 1

        for code, legacy_source in LEGACY_SOURCES.items():
            payload = list(rows_for_source(conn, code))
            count = replace_original_words(conn, legacy_source, payload)
            print(f"Compact cache: {legacy_source} <- {code}: {count:,} words")

    print("Compact Languages drawer cache synchronized from the deep corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
