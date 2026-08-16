from __future__ import annotations

import sqlite3
from typing import Iterable

_WORD_TABLE = """
CREATE TABLE IF NOT EXISTS original_lab_words (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES original_lab_sources(id) ON DELETE CASCADE,
  book TEXT NOT NULL,
  book_order INTEGER NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  position INTEGER NOT NULL,
  source_word_id TEXT NOT NULL DEFAULT '',
  surface TEXT NOT NULL,
  surface_normalized TEXT NOT NULL DEFAULT '',
  lemma TEXT NOT NULL DEFAULT '',
  lemma_normalized TEXT NOT NULL DEFAULT '',
  alt_lemma TEXT NOT NULL DEFAULT '',
  strongs TEXT NOT NULL DEFAULT '',
  morph TEXT NOT NULL DEFAULT '',
  morph_expanded TEXT NOT NULL DEFAULT '',
  transliteration TEXT NOT NULL DEFAULT '',
  word_language TEXT NOT NULL DEFAULT '',
  source_book TEXT NOT NULL DEFAULT '',
  source_chapter INTEGER NOT NULL DEFAULT 0,
  source_verse INTEGER NOT NULL DEFAULT 0,
  verse_mapping_type TEXT NOT NULL DEFAULT 'same',
  UNIQUE(source_id,source_book,source_chapter,source_verse,position)
);
"""

_WORD_INDEXES = """
CREATE INDEX IF NOT EXISTS original_lab_words_ref_idx ON original_lab_words(source_id,book,chapter,verse,position);
CREATE INDEX IF NOT EXISTS original_lab_words_source_ref_idx ON original_lab_words(source_id,source_book,source_chapter,source_verse,position);
CREATE INDEX IF NOT EXISTS original_lab_words_lemma_idx ON original_lab_words(source_id,lemma_normalized);
CREATE INDEX IF NOT EXISTS original_lab_words_strongs_idx ON original_lab_words(source_id,strongs);
CREATE INDEX IF NOT EXISTS original_lab_words_surface_idx ON original_lab_words(source_id,surface_normalized);
CREATE INDEX IF NOT EXISTS original_lab_words_morph_idx ON original_lab_words(source_id,morph);
CREATE INDEX IF NOT EXISTS original_lab_words_language_idx ON original_lab_words(word_language,book,chapter,verse);
CREATE UNIQUE INDEX IF NOT EXISTS original_lab_words_source_word_id_idx
  ON original_lab_words(source_id,source_word_id) WHERE source_word_id<>'';
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS original_lab_sources (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  language TEXT NOT NULL,
  testament TEXT NOT NULL,
  license TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  attribution TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""" + _WORD_TABLE + _WORD_INDEXES + """
CREATE TABLE IF NOT EXISTS original_lab_verse_mappings (
  id INTEGER PRIMARY KEY,
  source_code TEXT NOT NULL,
  source_book TEXT NOT NULL,
  source_chapter INTEGER NOT NULL,
  source_verse INTEGER NOT NULL,
  source_segment TEXT NOT NULL DEFAULT '',
  target_book TEXT NOT NULL,
  target_chapter INTEGER NOT NULL,
  target_verse INTEGER NOT NULL,
  target_segment TEXT NOT NULL DEFAULT '',
  mapping_type TEXT NOT NULL,
  UNIQUE(source_code,source_book,source_chapter,source_verse,source_segment,target_book,target_chapter,target_verse,target_segment)
);
CREATE INDEX IF NOT EXISTS original_lab_verse_mappings_target_idx ON original_lab_verse_mappings(source_code,target_book,target_chapter,target_verse);
CREATE TABLE IF NOT EXISTS original_lab_lexicon (
  strongs TEXT PRIMARY KEY,
  language TEXT NOT NULL,
  headword TEXT NOT NULL DEFAULT '',
  definition TEXT NOT NULL DEFAULT '',
  source_label TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  license TEXT NOT NULL DEFAULT '',
  gloss TEXT NOT NULL DEFAULT '',
  pos TEXT NOT NULL DEFAULT '',
  transliteration TEXT NOT NULL DEFAULT '',
  bdb_ref TEXT NOT NULL DEFAULT '',
  twot_ref TEXT NOT NULL DEFAULT '',
  etymology TEXT NOT NULL DEFAULT '',
  semantic_range TEXT NOT NULL DEFAULT '',
  lexical_source_label TEXT NOT NULL DEFAULT '',
  lexical_source_url TEXT NOT NULL DEFAULT '',
  lexical_license TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS original_lab_lxx_lemma_occurrences (
  id INTEGER PRIMARY KEY,
  surface_key TEXT NOT NULL DEFAULT '',
  lemma TEXT NOT NULL,
  lemma_normalized TEXT NOT NULL,
  book TEXT NOT NULL,
  book_order INTEGER NOT NULL DEFAULT 0,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  position INTEGER NOT NULL,
  source_label TEXT NOT NULL DEFAULT 'Open Scriptures Septuagint Project — lemma index',
  source_url TEXT NOT NULL DEFAULT 'https://github.com/openscriptures/GreekResources',
  UNIQUE(book,chapter,verse,position,lemma_normalized)
);
CREATE INDEX IF NOT EXISTS lxx_lemma_idx ON original_lab_lxx_lemma_occurrences(lemma_normalized,book_order,chapter,verse,position);
CREATE INDEX IF NOT EXISTS lxx_key_idx ON original_lab_lxx_lemma_occurrences(surface_key);
"""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _unique_index_columns(conn: sqlite3.Connection, table: str) -> list[list[str]]:
    out: list[list[str]] = []
    for row in conn.execute(f"PRAGMA index_list({table})").fetchall():
        unique = row["unique"] if isinstance(row, sqlite3.Row) else row[2]
        if not unique:
            continue
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        cols = [r["name"] if isinstance(r, sqlite3.Row) else r[2] for r in conn.execute(f"PRAGMA index_info('{name}')").fetchall()]
        out.append(cols)
    return out


def _rebuild_word_table_for_source_identity(conn: sqlite3.Connection) -> None:
    """Migrate the first deep-lab schema away from target-verse identity.

    OSHB's official VerseMap moves/merges WLC material into English/KJV verse
    addresses. Display references therefore cannot be a stable unique key. The
    immutable source word / WLC source location is the identity; target refs are
    query/display metadata.
    """
    old_target_key = ["source_id", "book", "chapter", "verse", "position"]
    if old_target_key not in _unique_index_columns(conn, "original_lab_words"):
        return

    for name in (
        "original_lab_words_ref_idx", "original_lab_words_source_ref_idx", "original_lab_words_lemma_idx",
        "original_lab_words_strongs_idx", "original_lab_words_surface_idx", "original_lab_words_morph_idx",
        "original_lab_words_language_idx", "original_lab_words_source_word_id_idx",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {name}")

    conn.execute("ALTER TABLE original_lab_words RENAME TO original_lab_words_legacy")
    conn.executescript(_WORD_TABLE)
    cols = [
        "id", "source_id", "book", "book_order", "chapter", "verse", "position", "source_word_id", "surface",
        "surface_normalized", "lemma", "lemma_normalized", "alt_lemma", "strongs", "morph", "morph_expanded",
        "transliteration", "word_language", "source_book", "source_chapter", "source_verse", "verse_mapping_type",
    ]
    available = _columns(conn, "original_lab_words_legacy")
    copy_cols = [c for c in cols if c in available]
    if copy_cols:
        names = ",".join(copy_cols)
        conn.execute(f"INSERT OR IGNORE INTO original_lab_words({names}) SELECT {names} FROM original_lab_words_legacy")
    conn.execute("DROP TABLE original_lab_words_legacy")
    conn.executescript(_WORD_INDEXES)


def ensure_original_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    word_cols = _columns(conn, "original_lab_words")
    word_additions = {
        "word_language": "TEXT NOT NULL DEFAULT ''",
        "source_book": "TEXT NOT NULL DEFAULT ''",
        "source_chapter": "INTEGER NOT NULL DEFAULT 0",
        "source_verse": "INTEGER NOT NULL DEFAULT 0",
        "verse_mapping_type": "TEXT NOT NULL DEFAULT 'same'",
    }
    for name, ddl in word_additions.items():
        if name not in word_cols:
            conn.execute(f"ALTER TABLE original_lab_words ADD COLUMN {name} {ddl}")
    _rebuild_word_table_for_source_identity(conn)

    lex_cols = _columns(conn, "original_lab_lexicon")
    lex_additions = {
        "gloss": "TEXT NOT NULL DEFAULT ''",
        "pos": "TEXT NOT NULL DEFAULT ''",
        "transliteration": "TEXT NOT NULL DEFAULT ''",
        "bdb_ref": "TEXT NOT NULL DEFAULT ''",
        "twot_ref": "TEXT NOT NULL DEFAULT ''",
        "etymology": "TEXT NOT NULL DEFAULT ''",
        "semantic_range": "TEXT NOT NULL DEFAULT ''",
        "lexical_source_label": "TEXT NOT NULL DEFAULT ''",
        "lexical_source_url": "TEXT NOT NULL DEFAULT ''",
        "lexical_license": "TEXT NOT NULL DEFAULT ''",
    }
    for name, ddl in lex_additions.items():
        if name not in lex_cols:
            conn.execute(f"ALTER TABLE original_lab_lexicon ADD COLUMN {name} {ddl}")
    conn.executescript(_WORD_INDEXES)


def upsert_original_source(conn: sqlite3.Connection, *, code: str, name: str, language: str, testament: str,
                           license_text: str, source_url: str, attribution: str, version: str = "") -> int:
    ensure_original_schema(conn)
    conn.execute(
        "INSERT INTO original_lab_sources(code,name,language,testament,license,source_url,attribution,version) VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name,language=excluded.language,testament=excluded.testament,"
        "license=excluded.license,source_url=excluded.source_url,attribution=excluded.attribution,version=excluded.version,installed_at=CURRENT_TIMESTAMP",
        (code, name, language, testament, license_text, source_url, attribution, version),
    )
    return int(conn.execute("SELECT id FROM original_lab_sources WHERE code=?", (code,)).fetchone()["id"])


def _flush_word_batch(conn: sqlite3.Connection, sql: str, batch: list[tuple], total_before: int) -> None:
    conn.execute("SAVEPOINT original_word_batch")
    try:
        conn.executemany(sql, batch)
        conn.execute("RELEASE original_word_batch")
        return
    except sqlite3.DatabaseError as exc:
        conn.execute("ROLLBACK TO original_word_batch")
        conn.execute("RELEASE original_word_batch")
        for i, row in enumerate(batch):
            conn.execute("SAVEPOINT original_word_probe")
            try:
                conn.execute(sql, row)
            except sqlite3.DatabaseError as row_exc:
                conn.execute("ROLLBACK TO original_word_probe")
                conn.execute("RELEASE original_word_probe")
                target = f"{row[1]} {row[3]}:{row[4]} pos {row[5]}"
                source = f"{row[17]} {row[18]}:{row[19]} pos {row[5]}"
                wid = row[6] or "(no source id)"
                raise RuntimeError(
                    f"Original-language SQLite insert failed at row {total_before + i + 1}: "
                    f"target={target}; source={source}; source_word_id={wid}; error={row_exc}"
                ) from row_exc
            else:
                conn.execute("ROLLBACK TO original_word_probe")
                conn.execute("RELEASE original_word_probe")
        raise RuntimeError(f"Original-language batch insert failed: {exc}") from exc


def replace_original_words(conn: sqlite3.Connection, source_id: int, words: Iterable[dict], batch_size: int = 5000) -> int:
    ensure_original_schema(conn)
    conn.execute("DELETE FROM original_lab_words WHERE source_id=?", (source_id,))
    total = 0
    batch: list[tuple] = []
    sql = (
        "INSERT INTO original_lab_words(source_id,book,book_order,chapter,verse,position,source_word_id,surface,surface_normalized,"
        "lemma,lemma_normalized,alt_lemma,strongs,morph,morph_expanded,transliteration,word_language,source_book,source_chapter,source_verse,verse_mapping_type) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    for w in words:
        batch.append((
            source_id, w["book"], int(w["book_order"]), int(w["chapter"]), int(w["verse"]), int(w["position"]),
            w.get("source_word_id", "") or "", w["surface"], w.get("surface_normalized", "") or "", w.get("lemma", "") or "",
            w.get("lemma_normalized", "") or "", w.get("alt_lemma", "") or "", w.get("strongs", "") or "", w.get("morph", "") or "",
            w.get("morph_expanded", "") or "", w.get("transliteration", "") or "", w.get("word_language", "") or "",
            w.get("source_book", w["book"]) or w["book"], int(w.get("source_chapter", w["chapter"]) or w["chapter"]),
            int(w.get("source_verse", w["verse"]) or w["verse"]), w.get("verse_mapping_type", "same") or "same",
        ))
        if len(batch) >= batch_size:
            _flush_word_batch(conn, sql, batch, total)
            total += len(batch)
            batch.clear()
    if batch:
        _flush_word_batch(conn, sql, batch, total)
        total += len(batch)
    return total


def original_source_stats(conn: sqlite3.Connection) -> list[dict]:
    ensure_original_schema(conn)
    rows = conn.execute(
        "SELECT s.code,s.name,s.language,s.testament,s.license,s.source_url,s.attribution,s.version,s.installed_at,"
        "COUNT(w.id) word_count,COUNT(DISTINCT w.book||':'||w.chapter||':'||w.verse) verse_count "
        "FROM original_lab_sources s LEFT JOIN original_lab_words w ON w.source_id=s.id GROUP BY s.id ORDER BY s.id"
    ).fetchall()
    return [dict(r) for r in rows]


def replace_original_lexicon(conn: sqlite3.Connection, language: str, entries: Iterable[dict]) -> int:
    ensure_original_schema(conn)
    prefix = "H" if language.lower() == "hebrew" else "G"
    existing = {r["strongs"]: dict(r) for r in conn.execute("SELECT * FROM original_lab_lexicon WHERE strongs LIKE ?", (prefix + "%",)).fetchall()}
    conn.execute("DELETE FROM original_lab_lexicon WHERE strongs LIKE ?", (prefix + "%",))
    rows = []
    for e in entries:
        old = existing.get(e["strongs"], {})
        rows.append((
            e["strongs"], language, e.get("headword", ""), e.get("definition", ""), e.get("source_label", ""),
            e.get("source_url", ""), e.get("license", ""), old.get("gloss", ""), old.get("pos", ""), old.get("transliteration", ""),
            old.get("bdb_ref", ""), old.get("twot_ref", ""), old.get("etymology", ""), old.get("semantic_range", ""),
            old.get("lexical_source_label", ""), old.get("lexical_source_url", ""), old.get("lexical_license", ""),
        ))
    conn.executemany(
        "INSERT INTO original_lab_lexicon(strongs,language,headword,definition,source_label,source_url,license,gloss,pos,transliteration,"
        "bdb_ref,twot_ref,etymology,semantic_range,lexical_source_label,lexical_source_url,lexical_license) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def merge_original_lexicon_profiles(conn: sqlite3.Connection, entries: Iterable[dict]) -> int:
    ensure_original_schema(conn)
    count = 0
    for e in entries:
        strongs = str(e.get("strongs", "")).strip().upper()
        if not strongs:
            continue
        conn.execute(
            "INSERT INTO original_lab_lexicon(strongs,language,headword) VALUES(?,?,?) ON CONFLICT(strongs) DO NOTHING",
            (strongs, e.get("language", "Hebrew"), e.get("headword", "")),
        )
        conn.execute(
            "UPDATE original_lab_lexicon SET headword=CASE WHEN headword='' THEN ? ELSE headword END,"
            "gloss=?,pos=?,transliteration=?,bdb_ref=?,twot_ref=?,etymology=?,semantic_range=?,"
            "lexical_source_label=?,lexical_source_url=?,lexical_license=? WHERE strongs=?",
            (
                e.get("headword", ""), e.get("gloss", ""), e.get("pos", ""), e.get("transliteration", ""),
                e.get("bdb_ref", ""), e.get("twot_ref", ""), e.get("etymology", ""), e.get("semantic_range", ""),
                e.get("lexical_source_label", "Brown–Driver–Briggs / OpenScriptures Hebrew Lexicon"),
                e.get("lexical_source_url", "https://github.com/openscriptures/HebrewLexicon"),
                e.get("lexical_license", "BDB text public domain; OpenScriptures markup CC BY 4.0"), strongs,
            ),
        )
        count += 1
    return count


def replace_lxx_lemma_occurrences(conn: sqlite3.Connection, entries: Iterable[dict], batch_size: int = 10000) -> int:
    ensure_original_schema(conn)
    conn.execute("DELETE FROM original_lab_lxx_lemma_occurrences")
    sql = (
        "INSERT OR IGNORE INTO original_lab_lxx_lemma_occurrences(surface_key,lemma,lemma_normalized,book,book_order,chapter,verse,position,source_label,source_url) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)"
    )
    total = 0
    batch: list[tuple] = []
    for e in entries:
        batch.append((
            e.get("surface_key", ""), e.get("lemma", ""), e.get("lemma_normalized", ""), e.get("book", ""),
            int(e.get("book_order", 0)), int(e.get("chapter", 0)), int(e.get("verse", 0)), int(e.get("position", 0)),
            e.get("source_label", "Open Scriptures Septuagint Project — lemma index"), e.get("source_url", "https://github.com/openscriptures/GreekResources"),
        ))
        if len(batch) >= batch_size:
            conn.executemany(sql, batch); total += len(batch); batch.clear()
    if batch:
        conn.executemany(sql, batch); total += len(batch)
    return total


def replace_original_verse_mappings(conn: sqlite3.Connection, source_code: str, mappings: Iterable[dict]) -> int:
    ensure_original_schema(conn)
    conn.execute("DELETE FROM original_lab_verse_mappings WHERE source_code=?", (source_code,))
    rows = [
        (source_code, m["source_book"], int(m["source_chapter"]), int(m["source_verse"]), m.get("source_segment", ""),
         m["target_book"], int(m["target_chapter"]), int(m["target_verse"]), m.get("target_segment", ""), m.get("mapping_type", "full"))
        for m in mappings
    ]
    conn.executemany(
        "INSERT INTO original_lab_verse_mappings(source_code,source_book,source_chapter,source_verse,source_segment,target_book,target_chapter,target_verse,target_segment,mapping_type) VALUES(?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)
