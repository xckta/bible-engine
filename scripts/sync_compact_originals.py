from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, session
from app.original_storage import ensure_original_schema

LEGACY_SOURCES = {
    "OSHB": "UHB v2.1.32",
    "TISCH": "UGNT v0.34",
}


def sync_source(conn, source_code: str, legacy_source: str) -> int:
    """Derive the compact drawer cache directly inside SQLite.

    The deep OSHB/Tischendorf tables are authoritative. The compact drawer is only
    a compatibility projection. ROW_NUMBER() creates a unique sequential position
    inside each displayed English verse, including OSHB remapped verse segments and
    Tischendorf records that share a source slot.
    """
    conn.execute("DELETE FROM original_words WHERE source=?", (legacy_source,))
    before = conn.total_changes
    conn.execute(
        """
        INSERT INTO original_words(
          language,source,book,book_order,chapter,verse,position,
          surface,normalized,lemma,strongs,morph,transliteration
        )
        SELECT
          CASE lower(COALESCE(NULLIF(w.word_language,''),s.language))
            WHEN 'aramaic' THEN 'aramaic'
            WHEN 'greek' THEN 'greek'
            ELSE 'hebrew'
          END,
          ?,w.book,w.book_order,w.chapter,w.verse,
          ROW_NUMBER() OVER (
            PARTITION BY w.book,w.chapter,w.verse
            ORDER BY w.position,w.id
          ),
          w.surface,COALESCE(w.surface_normalized,''),COALESCE(w.lemma,''),
          COALESCE(w.strongs,''),COALESCE(w.morph,''),COALESCE(w.transliteration,'')
        FROM original_lab_words w
        JOIN original_lab_sources s ON s.id=w.source_id
        WHERE s.code=? AND trim(w.surface)<>''
        ORDER BY w.book_order,w.chapter,w.verse,w.position,w.id
        """,
        (legacy_source, source_code),
    )
    return conn.total_changes - before


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
            count = sync_source(conn, code, legacy_source)
            print(f"Compact cache: {legacy_source} <- {code}: {count:,} words")

        # Validate the exact cache just written before returning success.
        compact_counts = {
            row["source"]: int(row["n"])
            for row in conn.execute(
                "SELECT source,COUNT(*) n FROM original_words "
                "WHERE source IN ('UHB v2.1.32','UGNT v0.34') GROUP BY source"
            ).fetchall()
        }
        if compact_counts.get("UHB v2.1.32", 0) < 100000 or compact_counts.get("UGNT v0.34", 0) < 100000:
            print(
                "Compact cache synchronization completed but validation counts are incomplete.",
                file=sys.stderr,
            )
            return 1

    print("Compact Languages drawer cache synchronized from the deep corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
