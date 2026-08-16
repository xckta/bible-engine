from __future__ import annotations

import difflib
import re
import sqlite3
import unicodedata

WITNESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS textual_editions (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  language TEXT NOT NULL,
  edition_class TEXT NOT NULL,
  date_label TEXT NOT NULL DEFAULT '',
  editor TEXT NOT NULL DEFAULT '',
  license TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS textual_verses (
  id INTEGER PRIMARY KEY,
  edition_code TEXT NOT NULL REFERENCES textual_editions(code) ON DELETE CASCADE,
  book TEXT NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  text TEXT NOT NULL,
  UNIQUE(edition_code,book,chapter,verse)
);
CREATE INDEX IF NOT EXISTS textual_ref_idx ON textual_verses(book,chapter,verse,edition_code);
"""


def ensure_witness_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(WITNESS_SCHEMA)


def upsert_edition(conn: sqlite3.Connection, **row) -> None:
    ensure_witness_schema(conn)
    conn.execute(
        "INSERT INTO textual_editions(code,name,language,edition_class,date_label,editor,license,source_url,notes) VALUES(?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name,language=excluded.language,edition_class=excluded.edition_class," 
        "date_label=excluded.date_label,editor=excluded.editor,license=excluded.license,source_url=excluded.source_url,notes=excluded.notes",
        (row["code"],row["name"],row["language"],row["edition_class"],row.get("date_label",""),row.get("editor",""),row.get("license",""),row.get("source_url",""),row.get("notes","")),
    )


def replace_edition_verses(conn: sqlite3.Connection, code: str, verses: list[dict]) -> int:
    ensure_witness_schema(conn)
    conn.execute("DELETE FROM textual_verses WHERE edition_code=?", (code,))
    rows=[(code,v["book"],int(v["chapter"]),int(v["verse"]),v["text"].strip()) for v in verses if v.get("text","").strip()]
    conn.executemany("INSERT INTO textual_verses(edition_code,book,chapter,verse,text) VALUES(?,?,?,?,?)",rows)
    return len(rows)


def witness_stats(conn: sqlite3.Connection) -> dict:
    ensure_witness_schema(conn)
    editions=[dict(r) for r in conn.execute(
        "SELECT e.*,COUNT(v.id) verse_count FROM textual_editions e LEFT JOIN textual_verses v ON v.edition_code=e.code GROUP BY e.code ORDER BY e.code"
    ).fetchall()]
    return {"ready": len(editions)>=2, "editions": editions, "edition_count": len(editions), "verse_rows": sum(int(e["verse_count"]) for e in editions)}


def verse_readings(conn: sqlite3.Connection, book: str, chapter: int, verse: int) -> list[dict]:
    ensure_witness_schema(conn)
    return [dict(r) for r in conn.execute(
        "SELECT e.code,e.name,e.language,e.edition_class,e.date_label,e.editor,e.license,e.source_url,e.notes,v.text "
        "FROM textual_editions e JOIN textual_verses v ON v.edition_code=e.code WHERE v.book=? AND v.chapter=? AND v.verse=? ORDER BY e.code",
        (book,chapter,verse),
    ).fetchall()]


def _norm_token(token: str) -> str:
    token="".join(ch for ch in unicodedata.normalize("NFD",token.lower()) if unicodedata.category(ch)!="Mn")
    return re.sub(r"[^\wἀ-῾α-ωא-ת]+","",token,flags=re.UNICODE)


def _tokens(text: str) -> list[tuple[str,str]]:
    raw=re.findall(r"[^\s]+",text)
    return [(t,_norm_token(t)) for t in raw if _norm_token(t)]


def collate_texts(a: str, b: str) -> dict:
    at=_tokens(a);bt=_tokens(b);an=[x[1] for x in at];bn=[x[1] for x in bt]
    matcher=difflib.SequenceMatcher(a=an,b=bn,autojunk=False)
    segments=[];changed=0
    for tag,i1,i2,j1,j2 in matcher.get_opcodes():
        left=" ".join(x[0] for x in at[i1:i2]);right=" ".join(x[0] for x in bt[j1:j2])
        if tag!="equal": changed+=max(i2-i1,j2-j1)
        segments.append({"op":tag,"left":left,"right":right})
    total=max(1,max(len(at),len(bt)))
    return {"segments":segments,"changed_tokens":changed,"similarity":round(1-(changed/total),4),"left_tokens":len(at),"right_tokens":len(bt)}


def compare_verse(conn: sqlite3.Connection, book: str, chapter: int, verse: int, left: str, right: str) -> dict:
    rows={r["code"]:r for r in verse_readings(conn,book,chapter,verse)}
    if left not in rows or right not in rows:
        missing=[x for x in (left,right) if x not in rows]
        raise KeyError("Missing reading for: "+", ".join(missing))
    return {
        "reference":f"{book} {chapter}:{verse}",
        "left":rows[left],"right":rows[right],
        "collation":collate_texts(rows[left]["text"],rows[right]["text"]),
        "notice":"Edition comparison is mechanical. A difference between editions is not by itself a claim about the earliest recoverable reading or manuscript support.",
    }


def parse_sblgnt_text(text: str, book: str) -> list[dict]:
    out=[]
    for line in text.splitlines():
        m=re.match(r"^[A-Za-z0-9 ]+\s+(\d+):(\d+)\t(.+)$",line.strip())
        if m:out.append({"book":book,"chapter":int(m.group(1)),"verse":int(m.group(2)),"text":m.group(3).strip()})
    return out
