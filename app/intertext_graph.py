from __future__ import annotations

import re
import sqlite3
from collections import deque
from dataclasses import dataclass

from .books import CANONICAL_SET, DEUTEROCANON_SET
from .references import extract_references

GRAPH_SCHEMA = """
CREATE TABLE IF NOT EXISTS intertext_edges (
  id INTEGER PRIMARY KEY,
  source_ref TEXT NOT NULL,
  source_tier TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  target_tier TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  strength REAL NOT NULL DEFAULT 0.5,
  rationale TEXT NOT NULL DEFAULT '',
  provenance TEXT NOT NULL DEFAULT '',
  provenance_class TEXT NOT NULL DEFAULT 'curated',
  UNIQUE(source_ref,target_ref,edge_type,provenance)
);
CREATE INDEX IF NOT EXISTS graph_source_idx ON intertext_edges(source_ref);
CREATE INDEX IF NOT EXISTS graph_target_idx ON intertext_edges(target_ref);
CREATE INDEX IF NOT EXISTS graph_type_idx ON intertext_edges(edge_type);
"""

EDGE_TYPES = {
    "explicit_quotation": "Explicit quotation",
    "cross_reference": "Cross-reference",
    "canonical_parallel": "Canonical parallel",
    "strong_allusion": "Strong allusion",
    "thematic_parallel": "Thematic parallel",
    "ancient_context": "Ancient context",
    "study_link": "Study link",
    "suggested": "Suggested / unverified",
}


def ensure_graph_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(GRAPH_SCHEMA)


def tier_for_ref(ref: str) -> str:
    parsed = extract_references(ref)
    if parsed:
        work = parsed[0].work
        if work in CANONICAL_SET:
            return "canonical"
        if work in DEUTEROCANON_SET:
            return "deuterocanon"
        if parsed[0].kind == "reference":
            return "reference"
    low = ref.lower()
    if any(x in low for x in ("enoch", "jubilees", "moses", "patriarch", "baruch", "solomon", "aristeas", "sibylline", "adam and eve", "isaiah")):
        return "reference"
    return "unknown"


def canonicalize_ref(raw: str) -> str:
    raw = " ".join(raw.strip().split())
    refs = extract_references(raw)
    if not refs:
        return raw
    r = refs[0]
    if r.kind == "reference":
        if r.chapter:
            if r.chapter_end and r.chapter_end != r.chapter:
                return f"{r.work} {r.chapter}–{r.chapter_end}"
            if r.verse_start is not None:
                end = f"–{r.verse_end}" if r.verse_end and r.verse_end != r.verse_start else ""
                return f"{r.work} {r.chapter}:{r.verse_start}{end}"
            return f"{r.work} {r.chapter}"
        return r.work
    if r.verse_start is not None:
        end = f"–{r.verse_end}" if r.verse_end and r.verse_end != r.verse_start else ""
        return f"{r.work} {r.chapter}:{r.verse_start}{end}"
    return f"{r.work} {r.chapter}"


def add_edge(
    conn: sqlite3.Connection,
    source_ref: str,
    target_ref: str,
    edge_type: str,
    *,
    strength: float = 0.5,
    rationale: str = "",
    provenance: str = "",
    provenance_class: str = "curated",
    source_tier: str | None = None,
    target_tier: str | None = None,
) -> int:
    ensure_graph_schema(conn)
    s = canonicalize_ref(source_ref)
    t = canonicalize_ref(target_ref)
    if not s or not t or s == t:
        return 0
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unknown graph edge type: {edge_type}")
    conn.execute(
        "INSERT INTO intertext_edges(source_ref,source_tier,target_ref,target_tier,edge_type,strength,rationale,provenance,provenance_class) "
        "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_ref,target_ref,edge_type,provenance) DO UPDATE SET "
        "strength=excluded.strength,rationale=excluded.rationale,provenance_class=excluded.provenance_class",
        (
            s, source_tier or tier_for_ref(s), t, target_tier or tier_for_ref(t), edge_type,
            max(0.0, min(1.0, float(strength))), rationale.strip(), provenance.strip(), provenance_class,
        ),
    )
    return 1


def graph_stats(conn: sqlite3.Connection) -> dict:
    ensure_graph_schema(conn)
    total = conn.execute("SELECT COUNT(*) n FROM intertext_edges").fetchone()["n"]
    types = [dict(r) for r in conn.execute(
        "SELECT edge_type,COUNT(*) count FROM intertext_edges GROUP BY edge_type ORDER BY count DESC"
    ).fetchall()]
    classes = [dict(r) for r in conn.execute(
        "SELECT provenance_class,COUNT(*) count FROM intertext_edges GROUP BY provenance_class ORDER BY count DESC"
    ).fetchall()]
    return {"edge_count": int(total), "types": types, "provenance_classes": classes}


def _node(ref: str, tier: str, root: str) -> dict:
    return {"id": ref, "label": ref, "tier": tier or tier_for_ref(ref), "root": ref == root}


def graph_for(
    conn: sqlite3.Connection,
    reference: str,
    *,
    depth: int = 1,
    edge_types: list[str] | None = None,
    limit: int = 120,
) -> dict:
    ensure_graph_schema(conn)
    root = canonicalize_ref(reference)
    if not root:
        return {"root": reference, "nodes": [], "edges": []}
    allowed = [x for x in (edge_types or []) if x in EDGE_TYPES]
    visited = {root}
    queue: deque[tuple[str, int]] = deque([(root, 0)])
    edges: dict[int, dict] = {}
    node_tiers: dict[str, str] = {root: tier_for_ref(root)}
    while queue and len(edges) < limit:
        current, level = queue.popleft()
        if level >= max(1, min(depth, 3)):
            continue
        sql = "SELECT * FROM intertext_edges WHERE (source_ref=? OR target_ref=?)"
        params: list[object] = [current, current]
        if allowed:
            sql += " AND edge_type IN (" + ",".join("?" for _ in allowed) + ")"
            params.extend(allowed)
        sql += " ORDER BY strength DESC,id LIMIT ?"
        params.append(limit)
        for row in conn.execute(sql, params).fetchall():
            d = dict(row)
            edges[d["id"]] = {
                "id": d["id"], "source": d["source_ref"], "target": d["target_ref"],
                "source_tier": d["source_tier"], "target_tier": d["target_tier"],
                "type": d["edge_type"], "type_label": EDGE_TYPES.get(d["edge_type"], d["edge_type"]),
                "strength": float(d["strength"]), "rationale": d["rationale"],
                "provenance": d["provenance"], "provenance_class": d["provenance_class"],
            }
            node_tiers[d["source_ref"]] = d["source_tier"]
            node_tiers[d["target_ref"]] = d["target_tier"]
            other = d["target_ref"] if d["source_ref"] == current else d["source_ref"]
            if other not in visited and len(visited) < limit:
                visited.add(other)
                queue.append((other, level + 1))
    nodes = [_node(ref, node_tiers.get(ref, "unknown"), root) for ref in visited]
    nodes.sort(key=lambda n: (not n["root"], n["tier"], n["label"]))
    return {"root": root, "nodes": nodes, "edges": list(edges.values()), "edge_types": EDGE_TYPES}


_XREF_BLOCK_RE = re.compile(r"\\x\s+.*?\\x\*", re.DOTALL)
_XT_RE = re.compile(r"\\xt\s+([^\\]+)")


def extract_usfm_crossrefs(text: str, *, book: str) -> list[tuple[str, str]]:
    """Extract explicit source-file cross-reference links from a USFM book.

    These are labelled `cross_reference`; no stronger quotation/allusion claim is
    inferred from their presence.
    """
    chapter = 0
    verse = 0
    out: set[tuple[str, str]] = set()
    for line in text.splitlines():
        cm = re.match(r"^\\c\s+(\d+)", line)
        if cm:
            chapter = int(cm.group(1)); verse = 0
        vm = re.match(r"^\\v\s+(\d+)", line)
        if vm:
            verse = int(vm.group(1))
        if not chapter or not verse or "\\x" not in line:
            continue
        source = f"{book} {chapter}:{verse}"
        for block in _XREF_BLOCK_RE.findall(line):
            for target_text in _XT_RE.findall(block):
                for ref in extract_references(target_text):
                    if ref.kind != "biblical":
                        continue
                    if ref.verse_start is not None:
                        target = f"{ref.work} {ref.chapter}:{ref.verse_start}"
                    else:
                        target = f"{ref.work} {ref.chapter}"
                    if source != target:
                        out.add((source, target))
    return sorted(out)
