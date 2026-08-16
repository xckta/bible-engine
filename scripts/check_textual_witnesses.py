from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.db import init_db,session
from app.textual_witnesses import witness_stats

def main()->int:
    init_db(settings.db_path)
    with session(settings.db_path) as c:stats=witness_stats(c)
    print('Textual witnesses:',', '.join(f"{e['code']} {e['verse_count']:,}" for e in stats['editions']))
    return 0 if stats['ready'] and all(int(e['verse_count'])>7900 for e in stats['editions'][:2]) else 1
if __name__=='__main__':raise SystemExit(main())
