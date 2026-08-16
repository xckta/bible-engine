from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace
from app.providers import CodexClient, CodexStatus, ProviderError


def test_codex_stdin_is_utf8_bytes(monkeypatch):
    c=CodexClient('codex','gpt-5.6-luna','medium',30)
    monkeypatch.setattr(c,'_executable',lambda:'/fake/codex')
    captured={}
    def fake_run(cmd,**kwargs):
        captured.update(cmd=cmd,kwargs=kwargs)
        out=Path(cmd[cmd.index('--output-last-message')+1])
        out.write_text(json.dumps({'answer':'ok','claims':[],'insufficient_evidence':False}),encoding='utf-8')
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
    monkeypatch.setattr('app.providers.subprocess.run',fake_run)
    prompt='λόγος — “faith” אֱלֹהִים'
    result=c.chat_json(prompt,{'type':'object'})
    assert result['answer']=='ok'
    assert isinstance(captured['kwargs']['input'],bytes)
    assert captured['kwargs']['input'].decode('utf-8')==prompt
    cmd=captured['cmd']
    assert 'web_search="disabled"' in cmd
    assert 'model_reasoning_effort="medium"' in cmd
    assert 'features.shell_tool=false' in cmd
    assert 'agents.enabled=false' in cmd


def test_status_reports_native_executable(monkeypatch):
    c=CodexClient('codex','gpt-5.6-luna','medium')
    monkeypatch.setattr(c,'_shim',lambda:'/fake/codex')
    monkeypatch.setattr(c,'_executable',lambda:'/fake/codex')
    monkeypatch.setattr('app.providers.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'codex-cli 0.147.0\n',stderr=b''))
    s=c.status();assert s.ready;assert s.executable=='/fake/codex';assert '0.147.0' in s.version

def test_windows_npm_native_layout_resolves(tmp_path):
    from app.providers import _resolve_windows_native_codex
    shim=tmp_path/'npm'/'codex.ps1';shim.parent.mkdir(parents=True);shim.write_text('shim')
    exe=shim.parent/'node_modules'/'@openai'/'codex'/'node_modules'/'@openai'/'codex-win32-x64'/'vendor'/'x86_64-pc-windows-msvc'/'bin'/'codex.exe'
    exe.parent.mkdir(parents=True);exe.write_bytes(b'MZ')
    assert _resolve_windows_native_codex(shim,'AMD64')==exe


def test_structured_codex_error_does_not_dump_evidence(monkeypatch):
    import pytest
    c=CodexClient('codex','gpt-5.6-luna','medium',30)
    monkeypatch.setattr(c,'_executable',lambda:'/fake/codex')
    stderr=(
        'E13 | REFERENCE | Sibylline Oracles 11:90 | irrelevant evidence\n'
        'E14 | REFERENCE | 1 Enoch 6:1 | evidence\n'
        'ERROR: {"type":"error","error":{"code":"invalid_json_schema","message":"Invalid schema: Missing evidence_ids."}}\n'
    ).encode('utf-8')
    monkeypatch.setattr('app.providers.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'',stderr=stderr))
    with pytest.raises(ProviderError) as exc:
        c.chat_json('prompt',{'type':'object'})
    msg=str(exc.value)
    assert 'invalid_json_schema' in msg and 'Missing evidence_ids' in msg
    assert 'E13' not in msg and 'Sibylline Oracles' not in msg
