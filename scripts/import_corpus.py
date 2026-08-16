from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import init_db, replace_translation_verses, session, upsert_translation
from app.importers import parse_json_file, parse_usfm_files

p=argparse.ArgumentParser()
p.add_argument('--code', required=True);p.add_argument('--name', required=True);p.add_argument('--input', required=True)
p.add_argument('--license', default='');p.add_argument('--source-url', default='');p.add_argument('--db', default=str(settings.db_path))
a=p.parse_args(); source=Path(a.input); db=Path(a.db);init_db(db)
if source.is_dir():
    paths=list(source.rglob('*.usfm'))+list(source.rglob('*.sfm'))
    verses=parse_usfm_files(paths)
elif source.suffix.lower()=='.json': verses=parse_json_file(source)
else: raise SystemExit('Input must be a USFM directory or JSON file')
if not verses: raise SystemExit('No usable verses found')
with session(db) as conn:
    tid=upsert_translation(conn,a.code,a.name,a.license,a.source_url)
    count=replace_translation_verses(conn,tid,verses)
print(f'Imported {count} passages as {a.code.upper()} into {db}')
