from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS translations (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  license TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS verses (
  id INTEGER PRIMARY KEY,
  translation_id INTEGER NOT NULL REFERENCES translations(id) ON DELETE CASCADE,
  book TEXT NOT NULL,
  book_order INTEGER NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  text TEXT NOT NULL,
  corpus_tier TEXT NOT NULL DEFAULT 'canonical',
  UNIQUE(translation_id, book, chapter, verse)
);
CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
  text, book, content='verses', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS verses_ai AFTER INSERT ON verses BEGIN
  INSERT INTO verses_fts(rowid,text,book) VALUES(new.id,new.text,new.book);
END;
CREATE TRIGGER IF NOT EXISTS verses_ad AFTER DELETE ON verses BEGIN
  INSERT INTO verses_fts(verses_fts,rowid,text,book) VALUES('delete',old.id,old.text,old.book);
END;
CREATE TRIGGER IF NOT EXISTS verses_au AFTER UPDATE ON verses BEGIN
  INSERT INTO verses_fts(verses_fts,rowid,text,book) VALUES('delete',old.id,old.text,old.book);
  INSERT INTO verses_fts(rowid,text,book) VALUES(new.id,new.text,new.book);
END;
CREATE TABLE IF NOT EXISTS reference_works (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  relevance TEXT NOT NULL DEFAULT '',
  source_label TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  license TEXT NOT NULL DEFAULT 'Public Domain'
);
CREATE TABLE IF NOT EXISTS reference_passages (
  id INTEGER PRIMARY KEY,
  work_id INTEGER NOT NULL REFERENCES reference_works(id) ON DELETE CASCADE,
  chapter INTEGER,
  verse_start INTEGER,
  verse_end INTEGER,
  section TEXT NOT NULL DEFAULT '',
  ordinal INTEGER NOT NULL DEFAULT 0,
  text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS reference_fts USING fts5(
  text, section, content='reference_passages', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS ref_ai AFTER INSERT ON reference_passages BEGIN
  INSERT INTO reference_fts(rowid,text,section) VALUES(new.id,new.text,new.section);
END;
CREATE TRIGGER IF NOT EXISTS ref_ad AFTER DELETE ON reference_passages BEGIN
  INSERT INTO reference_fts(reference_fts,rowid,text,section) VALUES('delete',old.id,old.text,old.section);
END;
CREATE TRIGGER IF NOT EXISTS ref_au AFTER UPDATE ON reference_passages BEGIN
  INSERT INTO reference_fts(reference_fts,rowid,text,section) VALUES('delete',old.id,old.text,old.section);
  INSERT INTO reference_fts(rowid,text,section) VALUES(new.id,new.text,new.section);
END;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db(path: Path) -> None:
    with connect(path) as conn:
        # Existing v0.2 databases do not have corpus_tier. Add it before creating triggers
        # that expect the modern schema.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS translations (
          id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          license TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS verses (
          id INTEGER PRIMARY KEY,
          translation_id INTEGER NOT NULL REFERENCES translations(id) ON DELETE CASCADE,
          book TEXT NOT NULL, book_order INTEGER NOT NULL, chapter INTEGER NOT NULL,
          verse INTEGER NOT NULL, text TEXT NOT NULL,
          UNIQUE(translation_id, book, chapter, verse)
        );
        """)
        if "corpus_tier" not in _columns(conn, "verses"):
            conn.execute("ALTER TABLE verses ADD COLUMN corpus_tier TEXT NOT NULL DEFAULT 'canonical'")
        conn.executescript(SCHEMA)


@contextmanager
def session(path: Path):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_translation(conn: sqlite3.Connection, code: str, name: str, license_text: str = "", source_url: str = "") -> int:
    conn.execute(
        "INSERT INTO translations(code,name,license,source_url) VALUES(?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name,license=excluded.license,source_url=excluded.source_url",
        (code.upper(), name, license_text, source_url),
    )
    return int(conn.execute("SELECT id FROM translations WHERE code=?", (code.upper(),)).fetchone()["id"])


def replace_translation_verses(conn: sqlite3.Connection, translation_id: int, verses: Iterable[dict]) -> int:
    conn.execute("DELETE FROM verses WHERE translation_id=?", (translation_id,))
    rows = [
        (
            translation_id, v["book"], int(v["book_order"]), int(v["chapter"]), int(v["verse"]),
            v["text"].strip(), v.get("corpus_tier", "canonical"),
        )
        for v in verses if v.get("text", "").strip()
    ]
    conn.executemany(
        "INSERT INTO verses(translation_id,book,book_order,chapter,verse,text,corpus_tier) VALUES(?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def list_translations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT t.code,t.name,t.license,t.source_url,COUNT(v.id) verse_count "
        "FROM translations t LEFT JOIN verses v ON v.translation_id=t.id GROUP BY t.id ORDER BY t.code"
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_reference_work(conn: sqlite3.Connection, *, code: str, name: str, category: str, relevance: str,
                          source_label: str, source_url: str, license_text: str = "Public Domain") -> int:
    conn.execute(
        "INSERT INTO reference_works(code,name,category,relevance,source_label,source_url,license) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name,category=excluded.category,relevance=excluded.relevance," 
        "source_label=excluded.source_label,source_url=excluded.source_url,license=excluded.license",
        (code, name, category, relevance, source_label, source_url, license_text),
    )
    return int(conn.execute("SELECT id FROM reference_works WHERE code=?", (code,)).fetchone()["id"])


def replace_reference_passages(conn: sqlite3.Connection, work_id: int, passages: Iterable[dict]) -> int:
    conn.execute("DELETE FROM reference_passages WHERE work_id=?", (work_id,))
    rows = [
        (
            work_id, p.get("chapter"), p.get("verse_start"), p.get("verse_end"), p.get("section", ""),
            int(p.get("ordinal", i + 1)), p["text"].strip(),
        )
        for i, p in enumerate(passages) if p.get("text", "").strip()
    ]
    conn.executemany(
        "INSERT INTO reference_passages(work_id,chapter,verse_start,verse_end,section,ordinal,text) VALUES(?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def library_stats(conn: sqlite3.Connection) -> dict:
    canonical = conn.execute("SELECT COUNT(*) n FROM verses WHERE corpus_tier='canonical' AND translation_id=(SELECT id FROM translations WHERE code='WEB')").fetchone()["n"]
    deuterocanon = conn.execute("SELECT COUNT(*) n FROM verses WHERE corpus_tier='deuterocanon' AND translation_id=(SELECT id FROM translations WHERE code='WEB')").fetchone()["n"]
    references = conn.execute("SELECT COUNT(*) n FROM reference_passages").fetchone()["n"]
    works = [dict(r) for r in conn.execute(
        "SELECT w.code,w.name,w.category,w.relevance,w.source_label,w.source_url,w.license,COUNT(p.id) passage_count "
        "FROM reference_works w LEFT JOIN reference_passages p ON p.work_id=w.id GROUP BY w.id ORDER BY w.name"
    ).fetchall()]
    return {"canonical_verses": int(canonical), "deuterocanon_verses": int(deuterocanon), "reference_passages": int(references), "reference_works": works}
