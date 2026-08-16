from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .answering import answer_question
from .config import settings
from .db import init_db, library_stats, list_translations, session
from .esv import ESVClient, ESVError
from .local_settings import esv_key, masked_key, save_settings
from .providers import CodexClient, ProviderError
from .retrieval import hydrate_canonical_esv, retrieve

app = FastAPI(title="Bible Engine // Oracle", version="0.3.0")
codex = CodexClient(settings.codex_command, settings.codex_model, settings.codex_reasoning_effort, settings.codex_timeout)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    include_deuterocanon: bool = True
    include_reference: bool = True
    top_k_canonical: int = Field(default=settings.top_k_canonical, ge=1, le=20)
    top_k_reference: int = Field(default=settings.top_k_reference, ge=0, le=20)


class ESVKeyRequest(BaseModel):
    api_key: str = Field(default="", max_length=500)


@app.on_event("startup")
def startup() -> None:
    init_db(settings.db_path)


@app.get("/")
def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(Path(__file__).parent / "static" / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def styles_css():
    return FileResponse(Path(__file__).parent / "static" / "styles.css", media_type="text/css")


@app.get("/api/health")
def health():
    status = codex.status()
    with session(settings.db_path) as conn:
        stats = library_stats(conn)
        translations = list_translations(conn)
    return {
        "status": "ok" if status.ready else "provider_required",
        "version": "0.3.0",
        "database": str(settings.db_path),
        "model": settings.codex_model,
        "reasoning_effort": settings.codex_reasoning_effort,
        "codex": {
            "installed": status.installed,
            "ready": status.ready,
            "version": status.version,
            "detail": status.detail,
            "executable": status.executable,
        },
        "esv": {"configured": bool(esv_key(settings.local_settings_path)), "masked_key": masked_key(settings.local_settings_path)},
        "library": stats,
        "translations": translations,
    }


@app.get("/api/library")
def library():
    with session(settings.db_path) as conn:
        return library_stats(conn)


@app.get("/api/settings")
def get_settings():
    return {
        "esv_configured": bool(esv_key(settings.local_settings_path)),
        "esv_masked_key": masked_key(settings.local_settings_path),
        "model": settings.codex_model,
        "reasoning_effort": settings.codex_reasoning_effort,
    }


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


@app.post("/api/ask")
def ask(req: AskRequest):
    status = codex.status()
    if not status.ready:
        raise HTTPException(503, detail={"code": "codex_unavailable", "message": status.detail or "Codex CLI is unavailable."})

    with session(settings.db_path) as conn:
        evidence = retrieve(
            conn,
            req.question,
            req.top_k_canonical,
            req.top_k_reference,
            req.include_deuterocanon,
            req.include_reference,
        )

    if any(e.tier == "canonical" for e in evidence):
        key = esv_key(settings.local_settings_path)
        if not key:
            raise HTTPException(428, detail={
                "code": "esv_key_required",
                "message": "Canonical Scripture is configured to display only ESV. Add your ESV API key in Oracle Settings.",
            })
        try:
            evidence = hydrate_canonical_esv(evidence, ESVClient(key, settings.esv_base_url))
        except ESVError as exc:
            raise HTTPException(502, detail={"code": "esv_error", "message": str(exc)}) from exc

    try:
        result = answer_question(req.question, evidence, codex)
    except ProviderError as exc:
        raise HTTPException(502, detail={"code": "codex_error", "message": str(exc)}) from exc
    return result.__dict__
