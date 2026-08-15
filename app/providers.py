from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
import httpx

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")

class ProviderError(RuntimeError):
    """Raised when a configured local model provider cannot complete a request."""


def hashed_embedding(text: str, dims: int = 384) -> list[float]:
    vec = [0.0] * dims
    for token in TOKEN_RE.findall(text.lower()):
        h = 2166136261
        for ch in token:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        idx = h % dims
        sign = -1.0 if (h >> 31) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@dataclass
class OllamaClient:
    base_url: str
    chat_model: str
    embed_model: str
    timeout: float = 60.0

    def healthy(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            r = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.embed_model, "input": texts},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["embeddings"]
        except Exception as exc:
            raise ProviderError(f"Ollama embedding failed: {exc}") from exc

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        try:
            r = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "format": schema,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            return json.loads(r.json()["message"]["content"])
        except Exception as exc:
            raise ProviderError(f"Ollama chat failed: {exc}") from exc
