from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .answering import answer_question
from .books import normalize_book
from .config import settings
from .db import init_db, library_stats, list_translations, session
from .esv import ESVClient, ESVError
from .intertext_graph import EDGE_TYPES, graph_for, graph_stats
from .local_settings import esv_key, masked_key, preferences, save_preferences, save_settings
from .original_languages import lab_stats, lemma_occurrences, search_words, verse_words
from .providers import CodexClient, ProviderError
from .retrieval import hydrate_canonical_esv, retrieve
from .studies import (
    add_item,
    append_consultation,
    build_context,
    create_project,
    delete_item,
    delete_project,
    export_json,
    export_markdown,
    list_projects,
    project_detail,
    update_project,
)

app = FastAPI(title="Bible Engine // Oracle", version="0.6.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    include_deuterocanon: bool | None = None
    include_reference: bool | None = None
    top_k_canonical: int | None = Field(default=None, ge=1, le=20)
    top_k_reference: int | None = Field(default=None, ge=0, le=40)
    project_id: str | None = Field(default=None, max_length=90)


class ESVKeyRequest(BaseModel):
    api_key: str = Field(default="", max_length=500)


class PreferenceRequest(BaseModel):
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    top_k_canonical: int = Field(default=8, ge=1, le=20)
    top_k_reference: int = Field(default=8, ge=0, le=40)
    include_deuterocanon: bool = True
    include_reference: bool = True
    study_context_chars: int = Field(default=6000, ge=1000, le=20000)
    motion: Literal["full", "reduced"] = "full"


class StudyCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    objective: str = Field(default="", max_length=4000)
    description: str = Field(default="", max_length=6000)


class StudyUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=140)
    objective: str | None = Field(default=None, max_length=4000)
    description: str | None = Field(default=None, max_length=6000)


class StudyItemRequest(BaseModel):
    kind: Literal["note", "finding", "question"]
    text: str = Field(min_length=1, max_length=8000)


def _codex_client(effort: str | None = None) -> CodexClient:
    chosen = effort or preferences(settings.local_settings_path)["reasoning_effort"]
    return CodexClient(settings.codex_command, settings.codex_model, chosen, settings.codex_timeout)


def _study_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, detail={"code": "study_not_found", "message": str(exc)})
    return HTTPException(400, detail={"code": "study_error", "message": str(exc)})


@app.on_event("startup")
def startup() -> None:
    init_db(settings.db_path)
    settings.studies_path.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(Path(__file__).parent / "static" / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def styles_css():
    return FileResponse(Path(__file__).parent / "static" / "styles.css", media_type="text/css")


@app.get("/original.js")
def original_js():
    return FileResponse(Path(__file__).parent / "static" / "original.js", media_type="application/javascript")


@app.get("/original.css")
def original_css():
    return FileResponse(Path(__file__).parent / "static" / "original.css", media_type="text/css")


@app.get("/graph.js")
def graph_js():
    return FileResponse(Path(__file__).parent / "static" / "graph.js", media_type="application/javascript")


@app.get("/graph.css")
def graph_css():
    return FileResponse(Path(__file__).parent / "static" / "graph.css", media_type="text/css")


@app.get("/api/health")
def health():
    prefs = preferences(settings.local_settings_path)
    status = _codex_client(prefs["reasoning_effort"]).status()
    with session(settings.db_path) as conn:
        stats = library_stats(conn)
        translations = list_translations(conn)
        original = lab_stats(conn)
        graph = graph_stats(conn)
    return {
        "status": "ok" if status.ready else "provider_required",
        "version": "0.6.0",
        "database": str(settings.db_path),
        "model": settings.codex_model,
        "reasoning_effort": prefs["reasoning_effort"],
        "codex": {"installed": status.installed,"ready": status.ready,"version": status.version,"detail": status.detail,"executable": status.executable},
        "esv": {"configured": bool(esv_key(settings.local_settings_path)), "masked_key": masked_key(settings.local_settings_path)},
        "preferences": prefs,
        "library": stats,
        "original_languages": original,
        "graph": graph,
        "translations": translations,
        "studies": {"count": len(list_projects(settings.studies_path))},
    }


@app.get("/api/library")
def library():
    with session(settings.db_path) as conn:
        return library_stats(conn)


@app.get("/api/graph/status")
def graph_status():
    with session(settings.db_path) as conn:
        stats = graph_stats(conn)
    return {**stats, "edge_types": EDGE_TYPES}


@app.get("/api/graph")
def graph_get(
    reference: str = Query(min_length=2, max_length=180),
    depth: int = Query(default=1, ge=1, le=3),
    types: str = Query(default="", max_length=500),
    limit: int = Query(default=120, ge=10, le=300),
):
    selected = [x.strip() for x in types.split(",") if x.strip()]
    with session(settings.db_path) as conn:
        return graph_for(conn, reference, depth=depth, edge_types=selected, limit=limit)


@app.get("/api/original/status")
def original_status():
    with session(settings.db_path) as conn:
        stats = lab_stats(conn)
    return {
        **stats,
        "provenance": [
            {"source":"UHB v2.1.32","language":"Biblical Hebrew / Aramaic","publisher":"unfoldingWord","license":"CC BY-SA 4.0; based on Open Scriptures Hebrew Bible / WLC","url":"https://git.door43.org/unfoldingWord/hbo_uhb"},
            {"source":"UGNT v0.34","language":"Koine Greek","publisher":"unfoldingWord","license":"CC BY-SA 4.0","url":"https://git.door43.org/unfoldingWord/el-x-koine_ugnt"},
        ],
    }


@app.get("/api/original/verse")
def original_verse(book: str, chapter: int = Query(ge=1, le=200), verse: int = Query(ge=1, le=200)):
    normalized = normalize_book(book)
    if not normalized:
        raise HTTPException(400, detail={"code": "unknown_book", "message": f"Unknown biblical book: {book}"})
    with session(settings.db_path) as conn:
        words = verse_words(conn, normalized, chapter, verse)
    if not words:
        raise HTTPException(404, detail={"code": "original_verse_not_found", "message": "Original-language data for that verse is not installed or was not found."})
    return {"reference": f"{normalized} {chapter}:{verse}","language": words[0]["language"],"source": words[0]["source"],"words": words}


@app.get("/api/original/lemma")
def original_lemma(lemma: str = Query(min_length=1, max_length=120),language: Literal["hebrew", "aramaic", "greek"] | None = None,limit: int = Query(default=100, ge=1, le=500)):
    with session(settings.db_path) as conn:
        return lemma_occurrences(conn, lemma, language, limit)


@app.get("/api/original/search")
def original_search(q: str = Query(min_length=1, max_length=120),language: Literal["hebrew", "aramaic", "greek"] | None = None,limit: int = Query(default=80, ge=1, le=300)):
    with session(settings.db_path) as conn:
        return {"query": q, "items": search_words(conn, q, language, limit)}


@app.get("/api/settings")
def get_settings():
    prefs = preferences(settings.local_settings_path)
    return {"esv_configured": bool(esv_key(settings.local_settings_path)),"esv_masked_key": masked_key(settings.local_settings_path),"model": settings.codex_model,"preferences": prefs}


@app.post("/api/settings/esv")
def set_esv_key(req: ESVKeyRequest):
    key = req.api_key.strip()
    if not key:
        save_settings(settings.local_settings_path, {"esv_api_key": ""})
        return {"ok": True, "configured": False, "masked_key": None}
    try:
        ESVClient(key, settings.esv_base_url).fetch("John 1:1")
    except ESVError as exc:
        raise HTTPException(400, detail={"code": "invalid_esv_key", "message": str(exc)}) from exc
    save_settings(settings.local_settings_path, {"esv_api_key": key})
    return {"ok": True, "configured": True, "masked_key": masked_key(settings.local_settings_path)}


@app.post("/api/settings/preferences")
def set_preferences(req: PreferenceRequest):
    prefs = save_preferences(settings.local_settings_path, req.model_dump())
    return {"ok": True, "preferences": prefs, "model": settings.codex_model}


@app.get("/api/studies")
def studies_index():
    return {"projects": list_projects(settings.studies_path)}


@app.post("/api/studies")
def studies_create(req: StudyCreateRequest):
    try:
        return create_project(settings.studies_path, req.title, req.objective, req.description)
    except (ValueError, OSError) as exc:
        raise _study_error(exc) from exc


@app.get("/api/studies/{project_id}")
def studies_get(project_id: str):
    try:
        return project_detail(settings.studies_path, project_id)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.patch("/api/studies/{project_id}")
def studies_update(project_id: str, req: StudyUpdateRequest):
    try:
        return update_project(settings.studies_path, project_id, req.model_dump(exclude_none=True))
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.delete("/api/studies/{project_id}")
def studies_delete(project_id: str):
    try:
        delete_project(settings.studies_path, project_id)
        return {"ok": True}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.post("/api/studies/{project_id}/items")
def studies_add_item(project_id: str, req: StudyItemRequest):
    try:
        return add_item(settings.studies_path, project_id, req.kind, req.text)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.delete("/api/studies/{project_id}/items/{kind}/{item_id}")
def studies_delete_item(project_id: str, kind: str, item_id: str):
    try:
        deleted = delete_item(settings.studies_path, project_id, kind, item_id)
        if not deleted:
            raise HTTPException(404, detail={"code": "study_item_not_found", "message": "Study item not found."})
        return {"ok": True}
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.get("/api/studies/{project_id}/export")
def studies_export(project_id: str, format: Literal["markdown", "json"] = "markdown"):
    try:
        if format == "json":
            body = export_json(settings.studies_path, project_id);media = "application/json";ext = "json"
        else:
            body = export_markdown(settings.studies_path, project_id);media = "text/markdown; charset=utf-8";ext = "md"
        filename = f"bible-engine-study-{project_id}.{ext}"
        return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise _study_error(exc) from exc


@app.post("/api/ask")
def ask(req: AskRequest):
    prefs = preferences(settings.local_settings_path)
    codex = _codex_client(prefs["reasoning_effort"])
    status = codex.status()
    if not status.ready:
        raise HTTPException(503, detail={"code": "codex_unavailable", "message": status.detail or "Codex CLI is unavailable."})
    include_deuterocanon = prefs["include_deuterocanon"] if req.include_deuterocanon is None else req.include_deuterocanon
    include_reference = prefs["include_reference"] if req.include_reference is None else req.include_reference
    top_k_canonical = req.top_k_canonical or prefs["top_k_canonical"]
    top_k_reference = prefs["top_k_reference"] if req.top_k_reference is None else req.top_k_reference
    with session(settings.db_path) as conn:
        evidence = retrieve(conn,req.question,top_k_canonical,top_k_reference,include_deuterocanon,include_reference)
    if any(e.tier == "canonical" for e in evidence):
        key = esv_key(settings.local_settings_path)
        if not key:
            raise HTTPException(428, detail={"code":"esv_key_required","message":"Canonical Scripture is configured to display only ESV. Add your ESV API key in Oracle Settings."})
        try:
            evidence = hydrate_canonical_esv(evidence, ESVClient(key, settings.esv_base_url))
        except ESVError as exc:
            raise HTTPException(502, detail={"code": "esv_error", "message": str(exc)}) from exc
    project_context = ""
    if req.project_id:
        try:
            project_context = build_context(settings.studies_path, req.project_id, prefs["study_context_chars"])
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise _study_error(exc) from exc
    try:
        result = answer_question(req.question, evidence, codex, project_context=project_context)
    except ProviderError as exc:
        raise HTTPException(502, detail={"code": "codex_error", "message": str(exc)}) from exc
    payload = result.__dict__
    if req.project_id and result.mode == "codex_closed_corpus":
        try:
            entry = append_consultation(settings.studies_path, req.project_id, req.question, payload)
            payload = {**payload, "study": {"project_id": req.project_id, "log_entry_id": entry["id"], "context_chars": len(project_context)}}
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise _study_error(exc) from exc
    return payload
