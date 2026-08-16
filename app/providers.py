from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ProviderError(RuntimeError):
    """Raised when the required Codex CLI provider cannot complete a request."""


def _creationflags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0


@dataclass(frozen=True)
class CodexStatus:
    installed: bool
    authenticated: bool
    chatgpt_auth: bool
    version: str = ""
    auth_detail: str = ""

    @property
    def ready(self) -> bool:
        return self.installed and self.authenticated and self.chatgpt_auth


@dataclass
class CodexClient:
    command: str
    model: str
    reasoning_effort: str
    timeout: float = 180.0

    def _executable(self) -> str | None:
        return shutil.which(self.command)

    def status(self) -> CodexStatus:
        exe = self._executable()
        if not exe:
            return CodexStatus(False, False, False)

        try:
            version_run = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=_creationflags(),
            )
            version = (version_run.stdout or version_run.stderr).strip()
        except Exception:
            version = ""

        try:
            auth_run = subprocess.run(
                [exe, "login", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=_creationflags(),
            )
            auth_detail = "\n".join(
                part.strip() for part in (auth_run.stdout, auth_run.stderr) if part and part.strip()
            )
            authenticated = auth_run.returncode == 0
            chatgpt_auth = authenticated and "chatgpt" in auth_detail.lower()
            return CodexStatus(True, authenticated, chatgpt_auth, version, auth_detail)
        except Exception as exc:
            return CodexStatus(True, False, False, version, str(exc))

    def healthy(self) -> bool:
        return self.status().ready

    def chat_json(self, prompt: str, schema: dict) -> dict:
        exe = self._executable()
        if not exe:
            raise ProviderError(
                "Codex CLI is not installed or not on PATH. Install @openai/codex and sign in with ChatGPT."
            )

        status = self.status()
        if not status.authenticated:
            raise ProviderError("Codex CLI is not signed in. Run `codex login` and sign in with ChatGPT.")
        if not status.chatgpt_auth:
            raise ProviderError(
                "Bible Engine requires Codex ChatGPT authentication, not API-key auth. "
                "Run `codex logout`, then `codex login`."
            )

        with tempfile.TemporaryDirectory(prefix="bible-engine-codex-") as td:
            workdir = Path(td)
            schema_path = workdir / "answer.schema.json"
            output_path = workdir / "answer.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

            cmd = [
                exe,
                "exec",
                "-",
                "--model",
                self.model,
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--config",
                'web_search="disabled"',
                "--config",
                "features.shell_tool=false",
                "--config",
                "agents.enabled=false",
                "--ignore-user-config",
                "--ignore-rules",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]

            try:
                run = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=workdir,
                    timeout=self.timeout,
                    creationflags=_creationflags(),
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderError(
                    f"Codex timed out after {self.timeout:g} seconds while answering."
                ) from exc
            except OSError as exc:
                raise ProviderError(f"Could not start Codex CLI: {exc}") from exc

            if run.returncode != 0:
                detail = (run.stderr or run.stdout or "Codex exited without an error message.").strip()
                detail = detail[-2000:]
                raise ProviderError(f"Codex failed: {detail}")
            if not output_path.exists():
                raise ProviderError("Codex completed without writing the required structured response.")

            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProviderError("Codex returned an unreadable structured response.") from exc
            if not isinstance(payload, dict):
                raise ProviderError("Codex returned a response that is not a JSON object.")
            return payload
