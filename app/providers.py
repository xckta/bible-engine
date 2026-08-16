from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ProviderError(RuntimeError):
    """Raised when the required Codex CLI provider cannot complete a request."""


def _creationflags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0


def _resolve_windows_native_codex(shim: Path, machine: str | None = None) -> Path | None:
    if shim.suffix.lower() == ".exe" and shim.is_file():
        return shim

    machine_name = (machine or platform.machine()).lower()
    if machine_name in {"arm64", "aarch64"}:
        package = "codex-win32-arm64"
        triple = "aarch64-pc-windows-msvc"
    else:
        package = "codex-win32-x64"
        triple = "x86_64-pc-windows-msvc"

    npm_root = shim.parent
    openai_scope = npm_root / "node_modules" / "@openai"
    roots = [
        openai_scope / "codex" / "node_modules" / "@openai" / package,
        openai_scope / package,
        openai_scope / "codex",
    ]
    rels = [Path("vendor") / triple / "bin" / "codex.exe", Path("vendor") / triple / "codex" / "codex.exe"]
    for root in roots:
        for rel in rels:
            candidate = root / rel
            if candidate.is_file():
                return candidate
    if openai_scope.is_dir():
        for candidate in openai_scope.rglob("codex.exe"):
            if candidate.is_file() and triple in str(candidate).lower():
                return candidate
    return None


@dataclass(frozen=True)
class CodexStatus:
    installed: bool
    runnable: bool
    version: str = ""
    detail: str = ""
    executable: str = ""

    @property
    def ready(self) -> bool:
        return self.installed and self.runnable


@dataclass
class CodexClient:
    command: str
    model: str
    reasoning_effort: str
    timeout: float = 180.0

    def _shim(self) -> str | None:
        return shutil.which(self.command)

    def _executable(self) -> str | None:
        found = self._shim()
        if not found:
            return None
        if os.name != "nt":
            return found
        path = Path(found)
        if path.suffix.lower() == ".exe":
            return str(path)
        native = _resolve_windows_native_codex(path)
        return str(native) if native else None

    def _missing_message(self) -> str:
        shim = self._shim()
        if os.name == "nt" and shim:
            return (
                f"Codex launcher exists at {shim}, but Bible Engine could not locate its native codex.exe. "
                "Run `npm install -g @openai/codex@latest`, close Bible Engine, and reopen it."
            )
        return "Codex CLI is not installed or not on PATH. Install @openai/codex and sign in with ChatGPT."

    def status(self) -> CodexStatus:
        shim = self._shim()
        exe = self._executable()
        if not shim:
            return CodexStatus(False, False, detail="Codex CLI was not found on PATH.")
        if not exe:
            return CodexStatus(True, False, detail=self._missing_message())
        try:
            run = subprocess.run(
                [exe, "--version"], capture_output=True, timeout=10, creationflags=_creationflags()
            )
            stdout = run.stdout.decode("utf-8", errors="replace") if run.stdout else ""
            stderr = run.stderr.decode("utf-8", errors="replace") if run.stderr else ""
            version = (stdout or stderr).strip()
            if run.returncode != 0:
                return CodexStatus(True, False, version, "Codex --version returned a non-zero exit code.", exe)
            return CodexStatus(True, True, version=version, executable=exe)
        except subprocess.TimeoutExpired:
            return CodexStatus(True, False, detail="Codex --version timed out after 10 seconds.", executable=exe)
        except Exception as exc:
            return CodexStatus(True, False, detail=str(exc), executable=exe)

    def chat_json(self, prompt: str, schema: dict) -> dict:
        exe = self._executable()
        if not exe:
            raise ProviderError(self._missing_message())

        with tempfile.TemporaryDirectory(prefix="bible-engine-codex-") as td:
            workdir = Path(td)
            schema_path = workdir / "answer.schema.json"
            output_path = workdir / "answer.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            args = [
                "exec", "-",
                "--model", self.model,
                "--config", f'model_reasoning_effort="{self.reasoning_effort}"',
                "--config", 'web_search="disabled"',
                "--config", "features.shell_tool=false",
                "--config", "agents.enabled=false",
                "--ignore-user-config",
                "--ignore-rules",
                "--ephemeral",
                "--sandbox", "read-only",
                "--skip-git-repo-check",
                "--output-schema", str(schema_path),
                "--output-last-message", str(output_path),
            ]
            try:
                # Critical Windows rule: do not use text=True without an explicit encoding.
                # Codex requires UTF-8 on stdin. Passing bytes guarantees that smart quotes,
                # em dashes, Greek/Hebrew characters, etc. cannot be re-encoded as CP1252.
                run = subprocess.run(
                    [exe, *args],
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    cwd=workdir,
                    timeout=self.timeout,
                    creationflags=_creationflags(),
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderError(f"Codex timed out after {self.timeout:g} seconds while answering.") from exc
            except OSError as exc:
                raise ProviderError(f"Could not start Codex CLI: {exc}") from exc

            stdout = run.stdout.decode("utf-8", errors="replace") if run.stdout else ""
            stderr = run.stderr.decode("utf-8", errors="replace") if run.stderr else ""
            if run.returncode != 0:
                detail = (stderr or stdout or "Codex exited without an error message.").strip()[-3000:]
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
