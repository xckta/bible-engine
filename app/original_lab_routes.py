from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .config import settings
from .db import session
from .esv import ESVClient, ESVError
from .local_settings import esv_key, preferences, save_preferences
from .original_core import strip_hebrew_cantillation, strip_hebrew_points
from .original_queries import lemma_report, morphology_summary, original_status, search_words, translation_parallels, verse_words

router = APIRouter()
STATIC = Path(__file__).parent / "static"


class OriginalLabPreferenceRequest(BaseModel):
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] | None = None
    top_k_canonical: int | None = Field(default=None, ge=1, le=20)
    top_k_reference: int | None = Field(default=None, ge=0, le=40)
    include_deuterocanon: bool | None = None
    include_reference: bool | None = None
    study_context_chars: int | None = Field(default=None, ge=1000, le=20000)
    motion: Literal["full", "reduced"] | None = None
    original_show_transliteration: bool | None = None
    original_morphology: Literal["both", "expanded", "raw"] | None = None
    hebrew_display: Literal["pointed", "no_cantillation", "unpointed"] | None = None
    original_occurrence_limit: int | None = Field(default=None, ge=10, le=200)


@router.get("/originals")
def originals_page():
    return FileResponse(STATIC / "originals.html")


@router.get("/originals.js")
def originals_js():
    return FileResponse(STATIC / "originals.js", media_type="application/javascript")


@router.get("/originals.css")
def originals_css():
    return FileResponse(STATIC / "originals.css", media_type="text/css")


@router.get("/original.js")
def enhanced_original_js():
    """Serve the existing compact drawer unchanged plus one discoverability link."""
    base = (STATIC / "original.js").read_text(encoding="utf-8")
    enhancement = r'''
;(()=>{
  const add=()=>{
    const bar=document.querySelector('.top-actions');
    if(!bar||document.querySelector('#deepOriginalLabLink'))return;
    const a=document.createElement('a');a.id='deepOriginalLabLink';a.href='/originals';a.className='ghost';
    a.textContent='ORIGINAL LAB';a.style.textDecoration='none';a.title='Open the full Hebrew / Aramaic / Greek research workspace';
    const language=document.querySelector('#languageBtn');bar.insertBefore(a,language||bar.firstChild);
  };
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',add):add();
})();
'''
    return Response(base + enhancement, media_type="application/javascript")


@router.post("/api/settings/preferences")
def enriched_preferences(req: OriginalLabPreferenceRequest):
    """Backward-compatible superset of the normal Oracle preference endpoint."""
    prefs = save_preferences(settings.local_settings_path, req.model_dump(exclude_none=True))
    return {"ok": True, "preferences": prefs, "model": settings.codex_model}


def _display_payload(payload: dict, prefs: dict) -> dict:
    if payload.get("source_code") != "OSHB":
        return payload
    mode = prefs.get("hebrew_display", "pointed")
    for verse in payload.get("verses", []):
        shown_words = []
        for word in verse.get("words", []):
            raw = word.get("surface", "")
            if mode == "unpointed":
                shown = strip_hebrew_points(raw)
            elif mode == "no_cantillation":
                shown = strip_hebrew_cantillation(raw)
            else:
                shown = raw
            word["surface_display"] = shown.replace("/", "")
            shown_words.append(shown)
        verse["original_text_display"] = " ".join(shown_words)
    return payload


@router.get("/api/original/lab/status")
def lab_status():
    with session(settings.db_path) as conn:
        return original_status(conn)


@router.get("/api/original/lab/verse")
def lab_verse(reference: str = Query(min_length=3, max_length=180)):
    prefs = preferences(settings.local_settings_path)
    try:
        with session(settings.db_path) as conn:
            payload = verse_words(conn, reference)
            payload["translations"] = translation_parallels(conn, payload["reference"])
    except (ValueError, LookupError) as exc:
        status = 400 if isinstance(exc, ValueError) else 404
        raise HTTPException(status, detail={"code": "original_reference_error", "message": str(exc)}) from exc
    payload = _display_payload(payload, prefs)
    key = esv_key(settings.local_settings_path)
    payload["esv"] = None
    payload["esv_configured"] = bool(key)
    if key:
        try:
            passage = ESVClient(key, settings.esv_base_url).fetch(payload["reference"])
            payload["esv"] = {"reference": passage.canonical, "text": passage.text}
        except ESVError as exc:
            payload["esv_error"] = str(exc)
    return payload


@router.get("/api/original/lab/lemma/{word_id}")
def lab_lemma(word_id: int, limit: int | None = None, offset: int = Query(default=0, ge=0)):
    prefs = preferences(settings.local_settings_path)
    chosen = max(10, min(limit or prefs["original_occurrence_limit"], 200))
    try:
        with session(settings.db_path) as conn:
            return lemma_report(conn, word_id, chosen, offset)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "original_word_not_found", "message": str(exc)}) from exc


@router.get("/api/original/lab/search")
def lab_search(
    q: str = Query(min_length=1, max_length=180),
    language: Literal["all", "hebrew", "aramaic", "greek"] = "all",
    field: Literal["all", "lemma", "surface", "strongs", "morph"] = "all",
    limit: int = Query(default=60, ge=1, le=200),
):
    with session(settings.db_path) as conn:
        return {"query": q, "language": language, "field": field, "results": search_words(conn, q, language, field, limit)}


@router.get("/api/original/lab/morphology")
def lab_morphology(language: Literal["hebrew", "aramaic", "greek"], limit: int = Query(default=100, ge=1, le=300)):
    with session(settings.db_path) as conn:
        return {"language": language, "patterns": morphology_summary(conn, language, limit)}
