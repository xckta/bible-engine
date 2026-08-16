from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, replace

from .books import CANONICAL_SET, DEUTEROCANON_SET, tier_for_book
from .esv import ESVClient
from .references import TextRef, extract_references

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "what", "does", "say", "says", "about", "into",
    "were", "was", "are", "who", "why", "how", "which", "where", "when", "bible", "scripture", "verse", "verses",
    "compare", "tell", "me", "can", "could", "would", "should", "meaning", "means", "explain",
}


@dataclass(frozen=True)
class Evidence:
    source_id: str
    tier: str
    source: str
    work: str
    chapter: int | None
    verse_start: int | None
    verse_end: int | None
    text: str
    score: float
    source_url: str = ""
    source_label: str = ""

    @property
    def citation(self) -> str:
        if self.chapter:
            if self.verse_start is not None:
                suffix = f":{self.verse_start}"
                if self.verse_end and self.verse_end != self.verse_start:
                    suffix += f"–{self.verse_end}"
                return f"{self.source} {self.work} {self.chapter}{suffix}"
            return f"{self.source} {self.work} {self.chapter}"
        return f"{self.source} {self.work}"

    @property
    def reference(self) -> str:
        if self.chapter and self.verse_start is not None:
            return f"{self.work} {self.chapter}:{self.verse_start}"
        if self.chapter:
            return f"{self.work} {self.chapter}"
        return self.work


def _terms(query: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9']+", query.lower()) if len(t) > 2 and t not in STOPWORDS][:24]


def _fetch_biblical_ref(conn: sqlite3.Connection, ref: TextRef, translation: str = "WEB") -> list[Evidence]:
    tier = tier_for_book(ref.work)
    sql = (
        "SELECT v.id,v.book,v.chapter,v.verse,v.text FROM verses v JOIN translations t ON t.id=v.translation_id "
        "WHERE t.code=? AND v.book=? AND v.chapter=?"
    )
    args: list[object] = [translation, ref.work, ref.chapter]
    if ref.verse_start is not None:
        sql += " AND v.verse BETWEEN ? AND ?"
        args.extend([ref.verse_start, ref.verse_end or ref.verse_start])
    sql += " ORDER BY v.verse"
    return [
        Evidence(f"B{r['id']}", tier, translation, r["book"], r["chapter"], r["verse"], r["verse"], r["text"], 1000.0)
        for r in conn.execute(sql, args).fetchall()
    ]


def _lexical_biblical(conn: sqlite3.Connection, query: str, tier: str, limit: int) -> list[Evidence]:
    terms = _terms(query)
    if not terms:
        return []
    fts = " OR ".join(f'"{t}"' for t in terms)
    rows = conn.execute(
        "SELECT v.id,v.book,v.chapter,v.verse,v.text,bm25(verses_fts) rank "
        "FROM verses_fts JOIN verses v ON v.id=verses_fts.rowid JOIN translations t ON t.id=v.translation_id "
        "WHERE verses_fts MATCH ? AND t.code='WEB' AND v.corpus_tier=? ORDER BY rank LIMIT ?",
        (fts, tier, limit),
    ).fetchall()
    return [
        Evidence(f"B{r['id']}", tier, "WEB", r["book"], r["chapter"], r["verse"], r["verse"], r["text"], float(-r["rank"]))
        for r in rows
    ]


def _reference_direct(conn: sqlite3.Connection, ref: TextRef, limit: int) -> list[Evidence]:
    sql = (
        "SELECT p.id,w.name,w.source_label,w.source_url,p.chapter,p.verse_start,p.verse_end,p.text,p.ordinal "
        "FROM reference_passages p JOIN reference_works w ON w.id=p.work_id WHERE lower(w.name)=lower(?)"
    )
    args: list[object] = [ref.work]
    if ref.chapter:
        sql += " AND p.chapter=?"
        args.append(ref.chapter)
    if ref.verse_start is not None:
        sql += " AND (p.verse_start IS NULL OR p.verse_end IS NULL OR (? BETWEEN p.verse_start AND p.verse_end))"
        args.append(ref.verse_start)
    sql += " ORDER BY p.ordinal LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [
        Evidence(
            f"R{r['id']}", "pseudepigrapha", r["source_label"] or "Reference", r["name"], r["chapter"],
            r["verse_start"], r["verse_end"], r["text"], 1000.0, r["source_url"], r["source_label"],
        ) for r in rows
    ]


def _reference_lexical(conn: sqlite3.Connection, query: str, limit: int) -> list[Evidence]:
    terms = _terms(query)
    if not terms:
        return []
    fts = " OR ".join(f'"{t}"' for t in terms)
    rows = conn.execute(
        "SELECT p.id,w.name,w.source_label,w.source_url,p.chapter,p.verse_start,p.verse_end,p.text,bm25(reference_fts) rank "
        "FROM reference_fts JOIN reference_passages p ON p.id=reference_fts.rowid "
        "JOIN reference_works w ON w.id=p.work_id WHERE reference_fts MATCH ? ORDER BY rank LIMIT ?",
        (fts, limit),
    ).fetchall()
    return [
        Evidence(
            f"R{r['id']}", "pseudepigrapha", r["source_label"] or "Reference", r["name"], r["chapter"],
            r["verse_start"], r["verse_end"], r["text"], float(-r["rank"]), r["source_url"], r["source_label"],
        ) for r in rows
    ]


def _dedupe(rows: list[Evidence], limit: int) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for e in sorted(rows, key=lambda x: x.score, reverse=True):
        key = (e.tier, e.work, e.chapter, e.verse_start, e.text[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= limit:
            break
    return out


def retrieve(conn: sqlite3.Connection, query: str, top_k_canonical: int, top_k_reference: int,
             include_deuterocanon: bool = True, include_pseudepigrapha: bool = True) -> list[Evidence]:
    refs = extract_references(query)
    canonical: list[Evidence] = []
    deuterocanon: list[Evidence] = []
    reference: list[Evidence] = []

    for ref in refs:
        if ref.kind == "biblical":
            hits = _fetch_biblical_ref(conn, ref)
            if ref.work in CANONICAL_SET:
                canonical.extend(hits)
            elif include_deuterocanon and ref.work in DEUTEROCANON_SET:
                deuterocanon.extend(hits)
        elif include_pseudepigrapha:
            reference.extend(_reference_direct(conn, ref, top_k_reference))

    if not canonical:
        canonical = _lexical_biblical(conn, query, "canonical", top_k_canonical)
    if include_deuterocanon and not deuterocanon:
        deuterocanon = _lexical_biblical(conn, query, "deuterocanon", max(3, top_k_reference // 2))
    if include_pseudepigrapha and not reference:
        reference = _reference_lexical(conn, query, top_k_reference)

    return _dedupe(canonical, top_k_canonical) + _dedupe(deuterocanon, max(4, top_k_reference // 2)) + _dedupe(reference, top_k_reference)


def hydrate_canonical_esv(evidence: list[Evidence], esv: ESVClient) -> list[Evidence]:
    canonical_indices = [i for i, e in enumerate(evidence) if e.tier == "canonical"]
    if not canonical_indices:
        return evidence
    refs = [evidence[i].reference for i in canonical_indices]
    passages = esv.fetch_many(refs)
    if len(passages) != len(canonical_indices):
        raise RuntimeError("ESV API returned a different number of passages than requested.")
    out = list(evidence)
    for idx, passage in zip(canonical_indices, passages):
        e = out[idx]
        out[idx] = replace(e, source="ESV", text=passage.text, source_label="English Standard Version")
    return out
