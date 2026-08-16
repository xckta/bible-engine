from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .answering import answer_question
from .config import settings
from .db import init_db, list_translations, session
from .providers import CodexClient, ProviderError
from .retrieval import retrieve

app = FastAPI(title="Bible Only Engine", version="0.2.0")
codex = CodexClient(
    command=settings.codex_command,
    model=settings.codex_model,
    reasoning_effort=settings.codex_reasoning_effort,
    timeout=settings.codex_timeout,
)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    translations: list[str] = Field(default_factory=list)
    top_k: int = Field(default=settings.top_k, ge=1, le=50)
    context_radius: int = Field(default=settings.context_radius, ge=0, le=5)
    semantic: bool = False


@app.on_event("startup")
def startup() -> None:
    init_db(settings.db_path)


@app.get("/")
def root():
    index = Path(__file__).parent / "static" / "index.html"
    return FileResponse(index)


@app.get("/api/health")
def health():
    with session(settings.db_path) as conn:
        translations = list_translations(conn)
        embedding_count = int(conn.execute("SELECT COUNT(*) n FROM embeddings").fetchone()["n"])
    status = codex.status()
    return {
        "status": "ok" if status.ready else "provider_required",
        "database": str(settings.db_path),
        "translations": translations,
        "embedding_count": embedding_count,
        "codex_installed": status.installed,
        "codex_authenticated": status.authenticated,
        "codex_chatgpt_auth": status.chatgpt_auth,
        "codex_ready": status.ready,
        "codex_version": status.version,
        "codex_auth_detail": status.auth_detail,
        "model": settings.codex_model,
        "reasoning_effort": settings.codex_reasoning_effort,
    }


@app.get("/api/translations")
def translations():
    with session(settings.db_path) as conn:
        return list_translations(conn)


@app.post("/api/ask")
def ask(req: AskRequest):
    status = codex.status()
    if not status.ready:
        if not status.installed:
            detail = "Codex CLI is required. Close the app and run START_BIBLE_ENGINE.bat to install/configure it."
        elif not status.authenticated:
            detail = "Codex CLI is not signed in. Run `codex login` and choose ChatGPT sign-in."
        else:
            detail = "Bible Engine requires ChatGPT-authenticated Codex, not API-key authentication. Run `codex logout`, then `codex login`."
        raise HTTPException(503, detail=detail)

    with session(settings.db_path) as conn:
        available = {r["code"] for r in list_translations(conn)}
        selected = [c.upper() for c in req.translations] if req.translations else sorted(available)
        missing = [c for c in selected if c not in available]
        if missing:
            raise HTTPException(400, detail=f"Translations not loaded: {', '.join(missing)}")
        passages = retrieve(
            conn,
            req.question,
            selected,
            req.top_k,
            req.context_radius,
            req.semantic,
        )

    try:
        result = answer_question(req.question, passages, codex)
    except ProviderError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return result.__dict__
