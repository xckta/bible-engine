from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("BIBLE_DB_PATH", "data/bible.db"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "gemma3:4b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma")
    use_ollama: bool = _bool("BIBLE_USE_OLLAMA", True)
    top_k: int = int(os.getenv("BIBLE_TOP_K", "12"))
    context_radius: int = int(os.getenv("BIBLE_CONTEXT_RADIUS", "1"))


settings = Settings()
