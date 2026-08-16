from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .answering import answer_question
from .books import normalize_book
from .config import settings
from .db import session
from .deep_dive import build_plan, plan_dict
from .esv import ESVClient, ESVError
from .historical_worldview import PERIODS, worldview_search
from .local_settings import esv_key, preferences
from .providers import CodexClient, ProviderError
from .retrieval import Evidence, hydrate_canonical_esv, retrieve
from .studies import append_consultation, build_context
from .textual_witnesses import collate_texts, verse_readings, witness_stats
from .traditions_matrix import build_matrix
from .vault import CLASSES, ensure_vault_schema, search_vault

router = APIRouter(prefix="/api/research-pro", tags=["research-pro"])

_WORD_STOP = {
    "the", "and", "for", "that", "this", "with", "from", "into", "were", "was", "are", "who", "why", "how",
    "which", "where", "when", "have", "has", "had", "their", "there", "then", "than", "also", "they", "them",
    "his", "her", "its", "not", "but", "you", "your", "our", "out", "all", "any", "each", "one", "two",
    "what", "does", "about", "upon", "unto", "will", "shall", "would", "could", "should", "been", "being",
}


def _esv() -> ESVClient:
    key = esv_key(settings.local_settings_path)
    if not key:
        raise HTTPException(428, detail={"code": "esv_key_required", "message": "This analysis displays canonical quotations in ESV. Add your ESV API key in Settings."})
    return ESVClient(key, settings.esv_base_url)


def _codex() -> CodexClient:
    p = preferences(settings.local_settings_path)
    return CodexClient(settings.codex_command, settings.codex_model, p["reasoning_effort"], settings.codex_timeout)


def _terms(text: str) -> list[str]:
    return [x for x in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower()) if x not in _WORD_STOP]


def _term_profile(texts: list[str], limit: int = 24) -> list[dict]:
    c = Counter(x for text in texts for x in _terms(text))
    return [{"term": term, "count": count} for term, count in c.most_common(limit)]


def _shared_terms(left: list[str], right: list[str], limit: int = 20) -> list[dict]:
    a = Counter(x for text in left for x in _terms(text))
    b = Counter(x for text in right for x in _terms(text))
    rows = [(term, min(a[term], b[term]), a[term], b[term]) for term in (a.keys() & b.keys())]
    rows.sort(key=lambda x: (x[1], x[2] + x[3]), reverse=True)
    return [{"term": term, "shared_min": shared, "left_count": ac, "right_count": bc} for term, shared, ac, bc in rows[:limit]]


def _project_context(project_id: str | None) -> str:
    if not project_id:
        return ""
    p = preferences(settings.local_settings_path)
    try:
        return build_context(settings.studies_path, project_id, p["study_context_chars"])
    except Exception as exc:
        raise HTTPException(400, detail={"code": "study_error", "message": str(exc)}) from exc


def _worldview_evidence(data: dict, visible_limit: int) -> tuple[list[Evidence], dict]:
    evidence: list[Evidence] = []
    canonical = data.get("canonical", [])[:visible_limit]
    reference = data.get("reference", [])[:visible_limit]
    deuterocanon = data.get("deuterocanon", [])[:visible_limit]
    for i, row in enumerate(canonical):
        evidence.append(Evidence(f"WVC{i}", "canonical", "WEB", row["book"], row["chapter"], row["verse"], row["verse"], row["text"], float(-row.get("rank", 0))))
    for i, row in enumerate(deuterocanon):
        evidence.append(Evidence(f"WVD{i}", "deuterocanon", "WEB", row["book"], row["chapter"], row["verse"], row["verse"], row["text"], float(-row.get("rank", 0))))
    for i, row in enumerate(reference):
        evidence.append(Evidence(
            f"WVR{i}", "pseudepigrapha", row.get("source_label") or "Reference", row["name"], row.get("chapter"),
            row.get("verse_start"), row.get("verse_end"), row["text"], float(-row.get("rank", 0)), source_label=row.get("source_label") or "",
        ))
    analysis = {
        "canonical_distribution": [{"label": k, "count": v} for k, v in Counter(r["book"] for r in data.get("canonical", [])).most_common()],
        "reference_distribution": [{"label": k, "count": v} for k, v in Counter(r["name"] for r in data.get("reference", [])).most_common()],
        "canonical_terms": _term_profile([r["text"] for r in data.get("canonical", [])]),
        "reference_terms": _term_profile([r["text"] for r in data.get("reference", [])]),
        "shared_terms": _shared_terms([r["text"] for r in data.get("canonical", [])], [r["text"] for r in data.get("reference", [])]),
    }
    return evidence, analysis


@router.get("/witness/verse")
def witness_verse_dossier(
    book: str,
    chapter: int = Query(ge=1, le=200),
    verse: int = Query(ge=1, le=200),
    base: str = "",
):
    normalized = normalize_book(book) or book.strip()
    with session(settings.db_path) as conn:
        readings = verse_readings(conn, normalized, chapter, verse)
        stats = witness_stats(conn)
    if not readings:
        raise HTTPException(404, detail={"code": "witness_reading_missing", "message": "No installed witness edition contains that verse."})
    codes = [r["code"] for r in readings]
    chosen = base if base in codes else codes[0]
    base_row = next(r for r in readings if r["code"] == chosen)
    comparisons = []
    for row in readings:
        if row["code"] == chosen:
            continue
        comparisons.append({"code": row["code"], "name": row["name"], **collate_texts(base_row["text"], row["text"])})
    pairwise = []
    for i, left in enumerate(readings):
        for right in readings[i + 1:]:
            d = collate_texts(left["text"], right["text"])
            pairwise.append({"left": left["code"], "right": right["code"], "similarity": d["similarity"], "changed_tokens": d["changed_tokens"]})
    return {
        "reference": f"{normalized} {chapter}:{verse}", "base": chosen, "readings": readings, "comparisons": comparisons,
        "pairwise": pairwise, "editions": stats["editions"],
        "notice": "This is edition-level mechanical collation. It does not substitute for manuscript-level apparatus evidence, dating, or textual-critical judgment.",
    }


@router.get("/witness/chapter")
def witness_chapter_scan(
    book: str,
    chapter: int = Query(ge=1, le=200),
    left: str = Query(min_length=1, max_length=40),
    right: str = Query(min_length=1, max_length=40),
    include_equal: bool = False,
):
    normalized = normalize_book(book) or book.strip()
    with session(settings.db_path) as conn:
        lrows = {int(r["verse"]): r["text"] for r in conn.execute("SELECT verse,text FROM textual_verses WHERE edition_code=? AND book=? AND chapter=? ORDER BY verse", (left, normalized, chapter)).fetchall()}
        rrows = {int(r["verse"]): r["text"] for r in conn.execute("SELECT verse,text FROM textual_verses WHERE edition_code=? AND book=? AND chapter=? ORDER BY verse", (right, normalized, chapter)).fetchall()}
    if not lrows and not rrows:
        raise HTTPException(404, detail={"code": "witness_chapter_missing", "message": "Neither selected edition contains that chapter."})
    rows = []
    identical = variants = missing = 0
    for v in sorted(set(lrows) | set(rrows)):
        lt, rt = lrows.get(v), rrows.get(v)
        if lt is None or rt is None:
            missing += 1
            row = {"verse": v, "reference": f"{normalized} {chapter}:{v}", "status": "missing", "left": lt or "", "right": rt or "", "similarity": 0.0, "changed_tokens": None, "segments": []}
        else:
            d = collate_texts(lt, rt)
            same = d["changed_tokens"] == 0
            identical += int(same); variants += int(not same)
            row = {"verse": v, "reference": f"{normalized} {chapter}:{v}", "status": "equal" if same else "variant", "left": lt, "right": rt, **d}
        if include_equal or row["status"] != "equal":
            rows.append(row)
    return {"book": normalized, "chapter": chapter, "left": left, "right": right, "stats": {"verse_union": len(set(lrows) | set(rrows)), "identical": identical, "variants": variants, "missing": missing}, "rows": rows,
            "notice": "Variant counts are token-level edition differences, not manuscript support counts."}


class WorldviewRequest(BaseModel):
    period: str
    query: str = Field(min_length=2, max_length=1200)
    limit: int = Field(default=14, ge=4, le=30)
    synthesize: bool = True
    project_id: str | None = None


@router.post("/worldview")
def worldview_dossier(req: WorldviewRequest):
    if req.period not in PERIODS:
        raise HTTPException(404, detail={"code": "period_not_found", "message": "Unknown worldview period."})
    with session(settings.db_path) as conn:
        data = worldview_search(conn, req.period, req.query, max(30, min(90, req.limit * 4)))
    evidence, analysis = _worldview_evidence(data, req.limit)
    if any(e.tier == "canonical" for e in evidence):
        try:
            evidence = hydrate_canonical_esv(evidence, _esv())
        except ESVError as exc:
            raise HTTPException(502, detail={"code": "esv_error", "message": str(exc)}) from exc
    synthesis = None; synthesis_error = ""
    if req.synthesize and evidence:
        try:
            context = f"HISTORICAL LENS (organizing metadata, not evidence): {data['period']['name']} // {data['period']['range']} // {data['period']['note']}"
            project = _project_context(req.project_id)
            if project:
                context += "\n\nACTIVE STUDY CONTEXT:\n" + project
            synthesis = answer_question(
                f"Within this research lens, identify what the supplied texts establish about: {req.query}. Distinguish canonical claims from ancient reference parallels and do not infer literary dependence from thematic similarity alone.",
                evidence, _codex(), project_context=context,
            ).__dict__
        except ProviderError as exc:
            synthesis_error = str(exc)
    return {"period": data["period"], "query": req.query, "analysis": analysis, "evidence": [e.__dict__ | {"citation": e.citation} for e in evidence], "synthesis": synthesis, "synthesis_error": synthesis_error,
            "method": "Searches a bounded period-specific primary-text shelf, reports distributions and shared vocabulary, then optionally runs citation-validated closed-corpus synthesis. Period labels remain organizational metadata."}


class TraditionsRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1200)
    per_group: int = Field(default=8, ge=2, le=15)
    synthesize: bool = True
    project_id: str | None = None


def _parse_biblical_reference(ref: str) -> tuple[str, int | None, int | None]:
    m = re.match(r"^(.+?)\s+(\d+):(\d+)$", ref.strip())
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else (ref.strip(), None, None)


@router.post("/traditions")
def traditions_dossier(req: TraditionsRequest):
    with session(settings.db_path) as conn:
        matrix = build_matrix(conn, req.query, req.per_group)
    canonical_hits = [h for col in matrix["columns"] for h in col["hits"] if h["tier"] == "canonical"]
    if canonical_hits:
        try:
            passages = _esv().fetch_many([h["reference"] for h in canonical_hits])
        except ESVError as exc:
            raise HTTPException(502, detail={"code": "esv_error", "message": str(exc)}) from exc
        for hit, passage in zip(canonical_hits, passages):
            hit["text"] = passage.text; hit["source"] = "ESV"
    evidence: list[Evidence] = []
    group_text: dict[str, list[str]] = {}
    for col in matrix["columns"]:
        group_text[col["name"]] = [h["text"] for h in col["hits"]]
        for i, hit in enumerate(col["hits"]):
            if hit["tier"] in {"canonical", "deuterocanon"}:
                work, chapter, verse = _parse_biblical_reference(hit["reference"])
                evidence.append(Evidence(f"TM-{len(evidence)}", hit["tier"], hit.get("source") or "WEB", work, chapter, verse, verse, hit["text"], float(hit.get("score", 0))))
            else:
                work = hit["reference"].split(" ")[0] if hit["reference"] else col["name"]
                evidence.append(Evidence(f"TM-{len(evidence)}", "pseudepigrapha", hit.get("source_label") or "Reference", work, None, None, None, hit["text"], float(hit.get("score", 0)), source_label=hit.get("source_label") or ""))
    overlaps = []
    names = list(group_text)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ta = set(_terms(" ".join(group_text[a]))); tb = set(_terms(" ".join(group_text[b]))
            if not ta or not tb:
                score = 0.0; shared = []
            else:
                shared = sorted(ta & tb); score = len(ta & tb) / len(ta | tb)
            overlaps.append({"left": a, "right": b, "jaccard": round(score, 4), "shared_terms": shared[:16]})
    synthesis = None; synthesis_error = ""
    if req.synthesize and evidence:
        try:
            context = "CORPUS FAMILY LABELS (organizing metadata, not evidence): " + ", ".join(names)
            project = _project_context(req.project_id)
            if project: context += "\n\nACTIVE STUDY CONTEXT:\n" + project
            synthesis = answer_question(
                f"Compare the supplied textual evidence for this theme: {req.query}. State what is explicit in canonical Scripture, what appears in deuterocanonical/reference literature, and where similarity is only thematic rather than evidence of dependence.",
                evidence[:80], _codex(), project_context=context,
            ).__dict__
        except ProviderError as exc:
            synthesis_error = str(exc)
    return {"matrix": matrix, "overlaps": sorted(overlaps, key=lambda x: x["jaccard"], reverse=True), "synthesis": synthesis, "synthesis_error": synthesis_error,
            "method": "Retrieval is separated by corpus family; overlap is lexical-set similarity only and is never presented as proof of literary dependence."}


@router.get("/vault/{source_id}")
def vault_source(source_id: str, offset: int = Query(default=0, ge=0), limit: int = Query(default=80, ge=1, le=300)):
    with session(settings.db_path) as conn:
        ensure_vault_schema(conn)
        source = conn.execute("SELECT * FROM vault_sources WHERE id=?", (source_id,)).fetchone()
        if not source:
            raise HTTPException(404, detail={"code": "vault_source_not_found", "message": "Vault source not found."})
        total = int(conn.execute("SELECT COUNT(*) n FROM vault_chunks WHERE source_id=?", (source_id,)).fetchone()["n"])
        chunks = [dict(r) for r in conn.execute("SELECT id,ordinal,text FROM vault_chunks WHERE source_id=? ORDER BY ordinal LIMIT ? OFFSET ?", (source_id, limit, offset)).fetchall()]
    row = dict(source); row["source_class_label"] = CLASSES.get(row["source_class"], row["source_class"])
    return {"source": row, "chunks": chunks, "total_chunks": total, "offset": offset, "limit": limit}


class VaultUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    author: str | None = Field(default=None, max_length=300)
    citation: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    source_class: Literal["primary_ancient", "lexicon", "scholarship", "personal_notes", "other"] | None = None


@router.patch("/vault/{source_id}")
def vault_update(source_id: str, req: VaultUpdateRequest):
    updates = req.model_dump(exclude_none=True)
    if not updates:
        return vault_source(source_id)
    with session(settings.db_path) as conn:
        ensure_vault_schema(conn)
        if not conn.execute("SELECT 1 FROM vault_sources WHERE id=?", (source_id,)).fetchone():
            raise HTTPException(404, detail={"code": "vault_source_not_found", "message": "Vault source not found."})
        cols = ",".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE vault_sources SET {cols} WHERE id=?", [*updates.values(), source_id])
    return vault_source(source_id)


class ProDeepDiveRequest(BaseModel):
    question: str = Field(min_length=5, max_length=4000)
    project_id: str | None = None
    max_evidence: int = Field(default=70, ge=20, le=120)
    include_vault: bool = True
    vault_classes: list[Literal["primary_ancient", "lexicon", "scholarship", "personal_notes", "other"]] = Field(default_factory=list)


def _vault_evidence(hit: dict) -> Evidence:
    label = hit.get("author") or hit.get("source_class_label") or "Vault"
    work = f"{hit['title']} §{hit['ordinal']}"
    return Evidence(f"V{hit['id']}", "vault", label, work, None, None, None, hit["text"], float(hit.get("score", 0)), source_label=hit.get("source_class_label") or "User Vault")


@router.post("/deep-dive")
def pro_deep_dive(req: ProDeepDiveRequest):
    codex = _codex(); status = codex.status()
    if not status.ready:
        raise HTTPException(503, detail={"code": "codex_unavailable", "message": status.detail or "Codex unavailable."})
    try:
        plan = build_plan(codex, req.question)
    except ProviderError as exc:
        raise HTTPException(502, detail={"code": "deep_dive_plan_error", "message": str(exc)}) from exc
    prefs = preferences(settings.local_settings_path)
    packets = []; merged: dict[tuple, Evidence] = {}
    with session(settings.db_path) as conn:
        for item in plan.questions:
            rows = retrieve(conn, item.question, min(14, prefs["top_k_canonical"] + 6), min(18, prefs["top_k_reference"] + 10), True, True)
            vault_rows = search_vault(conn, item.question, 6, req.vault_classes) if req.include_vault else []
            all_rows = rows + [_vault_evidence(h) for h in vault_rows]
            packets.append({
                "question": item.question, "purpose": item.purpose, "shelf_focus": item.shelf_focus,
                "counts": dict(Counter(r.tier for r in all_rows)), "citations": [r.citation for r in all_rows],
            })
            for e in all_rows:
                merged[(e.tier, e.citation, e.text[:140])] = e
        if req.include_vault:
            for hit in search_vault(conn, req.question, 10, req.vault_classes):
                e = _vault_evidence(hit); merged[(e.tier, e.citation, e.text[:140])] = e
    priority = {"canonical": 0, "deuterocanon": 1, "pseudepigrapha": 2, "vault": 3}
    evidence = sorted(merged.values(), key=lambda e: (priority.get(e.tier, 9), -e.score))[:req.max_evidence]
    if any(e.tier == "canonical" for e in evidence):
        try:
            evidence = hydrate_canonical_esv(evidence, _esv())
        except ESVError as exc:
            raise HTTPException(502, detail={"code": "esv_error", "message": str(exc)}) from exc
    context = "DEEP DIVE PLAN (research organization only; not evidence):\n" + str(plan_dict(plan))
    if req.project_id:
        project = _project_context(req.project_id)
        if project: context += "\n\nACTIVE STUDY CONTEXT:\n" + project
    try:
        result = answer_question(req.question, evidence, codex, project_context=context)
    except ProviderError as exc:
        raise HTTPException(502, detail={"code": "deep_dive_synthesis_error", "message": str(exc)}) from exc
    payload = {"plan": plan_dict(plan), "packets": packets, "result": result.__dict__, "evidence_count": len(evidence), "tier_counts": dict(Counter(e.tier for e in evidence)), "vault_included": req.include_vault,
               "method": "Each planner subquestion performs fresh closed-corpus retrieval. User Vault hits are a separate supplemental tier and cannot establish canonical claims."}
    if req.project_id and result.mode == "codex_closed_corpus":
        try: append_consultation(settings.studies_path, req.project_id, "DEEP DIVE PRO: " + req.question, result.__dict__)
        except Exception: pass
    return payload
