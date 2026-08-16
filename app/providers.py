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
    runnable: bool
    version: str = ""
    detail: str = ""

    @property
    def ready(self) -> bool:
        return self.installed and self.runnable


@dataclass
class CodexClient:
    command: str
    model: str
    reasoning_effort: str
    timeout: float = 180.0

    def _executable(self) -> str | None:
        return shutil.which(self.command)

    def _command(self, exe: str, args: list[str]) -> list[str]:
        if os.name == "nt" and Path(exe).suffix.lower() in {".cmd", ".bat"}:
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            command_line = subprocess.list2cmdline([exe, *args])
            return [comspec, "/d", "/s", "/c", command_line]
        return [exe, *args]

    def _run(self, exe: str, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.run(self._command(exe, args), **kwargs)

    def status(self) -> CodexStatus:
        """Check only that Codex exists and launches.

        Authentication is intentionally not probed here. Some Windows Codex installs can
        stall on login-status checks. The real `codex exec` request is the authoritative
        authentication test and will return a clear sign-in error if needed.
        """
        exe = self._executable()
        if not exe:
            return CodexStatus(False, False, detail="Codex CLI was not found on PATH.")

        try:
            version_run = self._run(
                exe,
                ["--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=_creationflags(),
            )
            version = (version_run.stdout or version_run.stderr).strip()
            if version_run.returncode != 0:
                return CodexStatus(True, False, version=version, detail="Codex --version returned a non-zero exit code.")
            return CodexStatus(True, True, version=version)
        except subprocess.TimeoutExpired:
            return CodexStatus(True, False, detail="Codex --version timed out after 10 seconds.")
        except Exception as exc:
            return CodexStatus(True, False, detail=str(exc))

    def healthy(self) -> bool:
        return self.status().ready

    def chat_json(self, prompt: str, schema: dict) -> dict:
        exe = self._executable()
        if not exe:
            raise ProviderError(
                "Codex CLI is not installed or not on PATH. Install @openai/codex and sign in with ChatGPT."
            )

        with tempfile.TemporaryDirectory(prefix="bible-engine-codex-") as td:
            workdir = Path(td)
            schema_path = workdir / "answer.schema.json"
            output_path = workdir / "answer.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

            args = [
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
                run = self._run(
                    exe,
                    args,
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
                lower = detail.lower()
                if any(word in lower for word in ("login", "sign in", "signin", "unauthorized", "authentication", "401")):
                    raise ProviderError(
                        "Codex is not authenticated. Run `codex --login` once in a terminal, sign in with ChatGPT, then retry."
                    )
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
