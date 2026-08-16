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
    """Resolve npm's Windows codex shim to the native codex.exe.

    The official Codex SDK invokes the platform-native executable directly. Doing the
    same here avoids cmd.exe/PowerShell re-parsing TOML --config values such as
    web_search="disabled" and model_reasoning_effort="medium".
    """
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
    rel_candidates = [
        Path("vendor") / triple / "bin" / "codex.exe",
        Path("vendor") / triple / "codex" / "codex.exe",
    ]

    for root in roots:
        for rel in rel_candidates:
            candidate = root / rel
            if candidate.is_file():
                return candidate

    # Package layouts can move between Codex releases. Limit fallback discovery to
    # the OpenAI npm scope and still require the expected platform triple.
    if openai_scope.is_dir():
        for candidate in openai_scope.rglob("codex.exe"):
            if candidate.is_file() and triple.lower() in str(candidate).lower():
                return candidate
    return None


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
                f"Codex launcher was found at {shim}, but Bible Engine could not locate "
                "the native codex.exe installed with @openai/codex. Run "
                "`npm install -g @openai/codex@latest` and restart Bible Engine."
            )
        return "Codex CLI is not installed or not on PATH. Install @openai/codex and sign in with ChatGPT."

    def status(self) -> CodexStatus:
        """Check only that the native Codex executable exists and launches.

        Authentication is intentionally not probed here. The real `codex exec` request
        is the authoritative authentication test and returns a sign-in error if needed.
        """
        shim = self._shim()
        exe = self._executable()
        if not shim:
            return CodexStatus(False, False, detail="Codex CLI was not found on PATH.")
        if not exe:
            return CodexStatus(True, False, detail=self._missing_message())

        try:
            version_run = subprocess.run(
                [exe, "--version"],
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
            raise ProviderError(self._missing_message())

        with tempfile.TemporaryDirectory(prefix="bible-engine-codex-") as td:
            workdir = Path(td)
            schema_path = workdir / "answer.schema.json"
            output_path = workdir / "answer.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

            # These match Codex's documented TOML config types. Because we invoke the
            # native executable directly, the quote characters arrive intact instead
            # of being escaped by an npm .cmd/.ps1 shim plus cmd.exe.
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
                run = subprocess.run(
                    [exe, *args],
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
