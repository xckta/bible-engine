from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.providers import CodexClient


def test_codex_exec_is_locked_to_requested_model_and_no_tools(monkeypatch):
    client = CodexClient("codex", "gpt-5.6-luna", "medium", timeout=30)
    monkeypatch.setattr("app.providers.shutil.which", lambda command: "/fake/codex")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        captured["cwd"] = kwargs.get("cwd")
        output_path = Path(cmd[cmd.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps({"claims": [], "insufficient_evidence": True}), encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.providers.subprocess.run", fake_run)
    payload = client.chat_json("PROMPT", {"type": "object"})

    cmd = captured["cmd"]
    assert payload["insufficient_evidence"] is True
    assert cmd[cmd.index("--model") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="medium"' in cmd
    assert 'web_search="disabled"' in cmd
    assert "features.shell_tool=false" in cmd
    assert "agents.enabled=false" in cmd
    assert "--ignore-user-config" in cmd
    assert "--ignore-rules" in cmd
    assert "--ephemeral" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert captured["input"] == "PROMPT"
    assert Path(captured["cwd"]).name.startswith("bible-engine-codex-")


def test_status_only_checks_that_codex_launches(monkeypatch):
    client = CodexClient("codex", "gpt-5.6-luna", "medium")
    monkeypatch.setattr("app.providers.shutil.which", lambda command: "/fake/codex")
    monkeypatch.setattr(
        "app.providers.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="codex-cli 1.0", stderr=""),
    )
    status = client.status()
    assert status.installed is True
    assert status.runnable is True
    assert status.ready is True
    assert status.version == "codex-cli 1.0"
