from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.atlas_rich import atlas_stats
from app.config import settings
from app.db import init_db,session
init_db(settings.db_path)
with session(settings.db_path) as c:stats=atlas_stats(c)
print(f"Atlas places: {stats['place_count']:,} | resolved: {stats['resolved_count']:,} | verse occurrences: {stats['occurrence_count']:,} | types: {stats['type_count']:,}")
if not stats['ready']:
    print('Biblical Atlas gazetteer missing or incomplete.');raise SystemExit(1)
print('Biblical Atlas gazetteer ready.')
