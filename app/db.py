from __future__ import annotations

import json
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
CREATE TABLE IF NOT EXISTS embeddings (
  verse_id INTEGER PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  vector_json TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: Path) -> None:
    with connect(path) as conn:
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
    row = conn.execute("SELECT id FROM translations WHERE code=?", (code.upper(),)).fetchone()
    return int(row["id"])


def replace_translation_verses(conn: sqlite3.Connection, translation_id: int, verses: Iterable[dict]) -> int:
    conn.execute("DELETE FROM verses WHERE translation_id=?", (translation_id,))
    rows = [
        (translation_id, v["book"], int(v["book_order"]), int(v["chapter"]), int(v["verse"]), v["text"].strip())
        for v in verses if v.get("text", "").strip()
    ]
    conn.executemany(
        "INSERT INTO verses(translation_id,book,book_order,chapter,verse,text) VALUES(?,?,?,?,?,?)", rows
    )
    return len(rows)


def list_translations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT t.code,t.name,t.license,t.source_url,COUNT(v.id) verse_count "
        "FROM translations t LEFT JOIN verses v ON v.translation_id=t.id GROUP BY t.id ORDER BY t.code"
    ).fetchall()
    return [dict(r) for r in rows]
