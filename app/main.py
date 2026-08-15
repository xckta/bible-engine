from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .answering import answer_question
from .config import settings
from .db import init_db, list_translations, session
from .providers import OllamaClient
from .retrieval import retrieve

app = FastAPI(title="Bible Only Engine", version="0.1.0")
ollama = OllamaClient(settings.ollama_base_url, settings.ollama_chat_model, settings.ollama_embed_model) if settings.use_ollama else None

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    translations: list[str] = Field(default_factory=list)
    top_k: int = Field(default=settings.top_k, ge=1, le=50)
    context_radius: int = Field(default=settings.context_radius, ge=0, le=5)
    semantic: bool = True
    generate: bool = True

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
    return {
        "status": "ok",
        "database": str(settings.db_path),
        "translations": translations,
        "embedding_count": embedding_count,
        "ollama_enabled": bool(ollama),
        "ollama_reachable": bool(ollama and ollama.healthy()),
        "chat_model": settings.ollama_chat_model if ollama else None,
        "embed_model": settings.ollama_embed_model if ollama else None,
    }

@app.get("/api/translations")
def translations():
    with session(settings.db_path) as conn:
        return list_translations(conn)

@app.post("/api/ask")
def ask(req: AskRequest):
    with session(settings.db_path) as conn:
        available = {r["code"] for r in list_translations(conn)}
        selected = [c.upper() for c in req.translations] if req.translations else sorted(available)
        missing = [c for c in selected if c not in available]
        if missing:
            raise HTTPException(400, detail=f"Translations not loaded: {', '.join(missing)}")
        passages = retrieve(conn, req.question, selected, req.top_k, req.context_radius, req.semantic, ollama)
    result = answer_question(req.question, passages, ollama, generation_enabled=req.generate)
    return result.__dict__
