from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import init_db, list_translations, session

MIN_VERSES = 30000
REQUIRED = {"WEB", "ASV"}

init_db(settings.db_path)
with session(settings.db_path) as conn:
    rows = {row["code"]: int(row["verse_count"]) for row in list_translations(conn)}

missing = [code for code in sorted(REQUIRED) if rows.get(code, 0) < MIN_VERSES]
if missing:
    print("Full corpus missing or incomplete: " + ", ".join(missing))
    raise SystemExit(1)

print("Full WEB + ASV corpus is ready.")
