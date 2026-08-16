from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.db import init_db,replace_reference_passages,session,upsert_reference_work
from app.reference_library import REFERENCE_SPECS,download_spec

CORE={'1ENOCH','JUB','ASMOS','T12'}
failures=[];installed={}
init_db(settings.db_path)
with session(settings.db_path) as conn:
    for spec in REFERENCE_SPECS:
        w=spec.work
        wid=upsert_reference_work(conn,code=w.code,name=w.name,category=w.category,relevance=w.relevance,source_label=w.source_label,source_url=w.source_url,license_text='Public Domain')
        try:
            print(f'Indexing {w.name} ...',flush=True)
            passages=download_spec(spec)
            count=replace_reference_passages(conn,wid,passages)
            installed[w.code]=count
            print(f'  {count} passages',flush=True)
        except Exception as exc:
            failures.append((w.code,w.name,str(exc)))
            print(f'  WARNING: {exc}',flush=True)

missing=sorted(CORE-set(k for k,v in installed.items() if v>0))
print('\nReference library summary:')
for code,count in installed.items(): print(f'  {code}: {count}')
if failures:
    print('Sources unavailable this run:')
    for _,name,msg in failures: print(f'  {name}: {msg}')
if missing:
    print('WARNING: core reference works still missing: '+', '.join(missing))
    print('Bible Engine will still start; run this installer again later to retry unavailable sources.')
else:
    print('Core reference shelf ready.')
