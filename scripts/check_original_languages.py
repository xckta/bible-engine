from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, session
from app.original_languages import lab_stats


def main() -> int:
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        stats = lab_stats(conn)
    by_source = {row["source"]: int(row["word_count"]) for row in stats["sources"]}
    hebrew = by_source.get("UHB v2.1.32", 0)
    greek = by_source.get("UGNT v0.34", 0)
    print(f"Original languages: UHB {hebrew:,} words | UGNT {greek:,} words")
    if hebrew < 100000 or greek < 100000:
        print("Original-Language Lab corpus missing or incomplete.", file=sys.stderr)
        return 1
    print("Original-Language Lab corpus is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
