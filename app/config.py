from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_REASONING = {"minimal", "low", "medium", "high", "xhigh"}


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("BIBLE_DB_PATH", "data/bible.db"))
    local_settings_path: Path = Path(os.getenv("BIBLE_LOCAL_SETTINGS_PATH", "data/local_settings.json"))
    codex_command: str = os.getenv("BIBLE_CODEX_COMMAND", "codex")
    codex_model: str = os.getenv("BIBLE_CODEX_MODEL", "gpt-5.6-luna")
    codex_reasoning_effort: str = os.getenv("BIBLE_CODEX_REASONING_EFFORT", "medium").lower()
    codex_timeout: float = float(os.getenv("BIBLE_CODEX_TIMEOUT", "180"))
    top_k_canonical: int = int(os.getenv("BIBLE_TOP_K_CANONICAL", "8"))
    top_k_reference: int = int(os.getenv("BIBLE_TOP_K_REFERENCE", "8"))
    context_radius: int = int(os.getenv("BIBLE_CONTEXT_RADIUS", "1"))
    esv_base_url: str = os.getenv("BIBLE_ESV_BASE_URL", "https://api.esv.org/v3/passage/text/")

    def __post_init__(self) -> None:
        if self.codex_reasoning_effort not in _ALLOWED_REASONING:
            raise ValueError("BIBLE_CODEX_REASONING_EFFORT must be one of: " + ", ".join(sorted(_ALLOWED_REASONING)))


settings = Settings()
