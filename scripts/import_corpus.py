from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from app.books import BOOKS
from app.config import settings
from app.db import init_db, session, upsert_translation, replace_translation_verses
from app.importers import parse_json_file, parse_usfm_files

p=argparse.ArgumentParser(description="Import a Bible translation from JSON or a USFM directory.")
p.add_argument("--code", required=True)
p.add_argument("--name", required=True)
p.add_argument("--input", required=True)
p.add_argument("--license", default="")
p.add_argument("--source-url", default="")
p.add_argument("--db", default=str(settings.db_path))
a=p.parse_args()
path=Path(a.input)
if path.is_dir():
    files=[p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".usfm", ".sfm"}]
    verses=parse_usfm_files(files)
elif path.suffix.lower()==".json":
    verses=parse_json_file(path)
else:
    raise SystemExit("Input must be a .json file or directory containing .usfm/.sfm files")
if not verses:
    raise SystemExit("No canonical Bible verses were parsed")
init_db(Path(a.db))
with session(Path(a.db)) as conn:
    tid=upsert_translation(conn,a.code,a.name,a.license,a.source_url)
    count=replace_translation_verses(conn,tid,verses)
print(f"Imported {count} verses as {a.code.upper()} into {a.db}")
