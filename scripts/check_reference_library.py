from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.db import init_db,session
CORE={'1ENOCH':40,'JUB':20,'ASMOS':6,'T12':12}
init_db(settings.db_path)
with session(settings.db_path) as conn:
    rows={r['code']:int(r['n']) for r in conn.execute("SELECT w.code,COUNT(p.id) n FROM reference_works w LEFT JOIN reference_passages p ON p.work_id=w.id GROUP BY w.id")}
missing=[f'{code}({rows.get(code,0)})' for code,min_n in CORE.items() if rows.get(code,0)<min_n]
if missing:
    print('Reference shelf incomplete: '+', '.join(missing));raise SystemExit(1)
print('Reference shelf ready: '+', '.join(f'{k}={rows[k]}' for k in CORE))
