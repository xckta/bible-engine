from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.providers import CodexClient
c=CodexClient(settings.codex_command,settings.codex_model,settings.codex_reasoning_effort,settings.codex_timeout)
s=c.status()
print('Codex shim/native status:')
print('  ready:',s.ready)
print('  version:',s.version or '(unknown)')
print('  executable:',s.executable or '(not resolved)')
if not s.ready:
    print('  detail:',s.detail);raise SystemExit(1)
