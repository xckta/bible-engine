from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass

from .references import BibleRef, extract_references


@dataclass(frozen=True)
class Passage:
    id: int
    translation: str
    book: str
    chapter: int
    verse: int
    text: str
    score: float

    @property
    def citation(self) -> str:
        return f"{self.translation} {self.book} {self.chapter}:{self.verse}"


def _translation_clause(codes: list[str]) -> tuple[str, list[str]]:
    if not codes:
        return "", []
    marks = ",".join("?" for _ in codes)
    return f" AND t.code IN ({marks})", [c.upper() for c in codes]


def fetch_ref(conn: sqlite3.Connection, ref: BibleRef, translations: list[str]) -> list[Passage]:
    clause, params = _translation_clause(translations)
    sql = (
        "SELECT v.id,t.code translation,v.book,v.chapter,v.verse,v.text FROM verses v "
        "JOIN translations t ON t.id=v.translation_id WHERE v.book=? AND v.chapter=?" + clause
    )
    args: list = [ref.book, ref.chapter] + params
    if ref.verse_start is not None:
        sql += " AND v.verse BETWEEN ? AND ?"
        args.extend([ref.verse_start, ref.verse_end or ref.verse_start])
    sql += " ORDER BY t.code,v.verse"
    return [Passage(**dict(r), score=1000.0) for r in conn.execute(sql, args).fetchall()]


STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "what", "does", "say", "says",
    "about", "into", "were", "was", "are", "who", "why", "how", "which", "where", "when",
    "bible", "scripture", "verse", "verses", "compare", "tell", "me", "can", "could", "would",
    "should",
}


def lexical_search(conn: sqlite3.Connection, query: str, translations: list[str], limit: int) -> list[Passage]:
    terms = [
        t for t in re.findall(r"[A-Za-z0-9']+", query.lower())
        if len(t) > 2 and t not in STOPWORDS
    ]
    if not terms:
        return []
    fts_query = " OR ".join(f'"{t}"' for t in terms[:24])
    clause, params = _translation_clause(translations)
    sql = (
        "SELECT v.id,t.code translation,v.book,v.chapter,v.verse,v.text,bm25(verses_fts) score "
        "FROM verses_fts JOIN verses v ON v.id=verses_fts.rowid JOIN translations t ON t.id=v.translation_id "
        "WHERE verses_fts MATCH ?" + clause + " ORDER BY score LIMIT ?"
    )
    rows = conn.execute(sql, [fts_query] + params + [limit]).fetchall()
    return [
        Passage(
            id=r["id"], translation=r["translation"], book=r["book"], chapter=r["chapter"],
            verse=r["verse"], text=r["text"], score=float(-r["score"])
        )
        for r in rows
    ]


def _hashed_embedding(text: str, dims: int = 384) -> list[float]:
    vec = [0.0] * dims
    for token in re.findall(r"[A-Za-z0-9']+", text.lower()):
        h = 2166136261
        for ch in token:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        idx = h % dims
        sign = -1.0 if (h >> 31) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return -1.0
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (da * db)


def semantic_search(conn: sqlite3.Connection, query: str, translations: list[str], limit: int) -> list[Passage]:
    qv = _hashed_embedding(query)
    model = "hash-384"
    clause, params = _translation_clause(translations)
    rows = conn.execute(
        "SELECT v.id,t.code translation,v.book,v.chapter,v.verse,v.text,e.vector_json,e.model "
        "FROM embeddings e JOIN verses v ON v.id=e.verse_id JOIN translations t ON t.id=v.translation_id "
        "WHERE e.model=?" + clause,
        [model] + params,
    ).fetchall()
    scored: list[Passage] = []
    for r in rows:
        vec = json.loads(r["vector_json"])
        score = cosine(qv, vec)
        if score > 0:
            scored.append(
                Passage(
                    id=r["id"], translation=r["translation"], book=r["book"], chapter=r["chapter"],
                    verse=r["verse"], text=r["text"], score=score
                )
            )
    return sorted(scored, key=lambda p: p.score, reverse=True)[:limit]


def expand_context(conn: sqlite3.Connection, passages: list[Passage], radius: int) -> list[Passage]:
    if radius <= 0:
        return passages
    out = {p.id: p for p in passages}
    for p in passages:
        rows = conn.execute(
            "SELECT v.id,t.code translation,v.book,v.chapter,v.verse,v.text FROM verses v "
            "JOIN translations t ON t.id=v.translation_id "
            "WHERE t.code=? AND v.book=? AND v.chapter=? AND v.verse BETWEEN ? AND ?",
            (p.translation, p.book, p.chapter, max(1, p.verse - radius), p.verse + radius),
        ).fetchall()
        for r in rows:
            q = Passage(**dict(r), score=p.score - 0.001)
            out.setdefault(q.id, q)
    return sorted(out.values(), key=lambda p: (-p.score, p.translation, p.book, p.chapter, p.verse))


def retrieve(
    conn: sqlite3.Connection,
    query: str,
    translations: list[str],
    top_k: int,
    radius: int,
    semantic: bool,
) -> list[Passage]:
    refs = extract_references(query)
    direct: list[Passage] = []
    for ref in refs:
        direct.extend(fetch_ref(conn, ref, translations))
    if direct:
        return expand_context(conn, direct, radius)

    lexical = lexical_search(conn, query, translations, top_k)
    semantic_hits = semantic_search(conn, query, translations, top_k) if semantic else []
    merged: dict[int, Passage] = {}
    for p in lexical + semantic_hits:
        prev = merged.get(p.id)
        if not prev or p.score > prev.score:
            merged[p.id] = p
    return expand_context(
        conn,
        sorted(merged.values(), key=lambda x: x.score, reverse=True)[:top_k],
        radius,
    )
