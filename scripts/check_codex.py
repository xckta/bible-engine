from __future__ import annotations

from app.config import settings
from app.providers import CodexClient

client = CodexClient(
    command=settings.codex_command,
    model=settings.codex_model,
    reasoning_effort=settings.codex_reasoning_effort,
    timeout=settings.codex_timeout,
)

exe = client._executable()
status = client.status()
print(f"Codex native executable: {exe or 'NOT FOUND'}")
if status.version:
    print(f"Codex native version: {status.version}")
if not status.ready:
    raise SystemExit(status.detail or "Native Codex executable is not ready.")
