from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, session
from app.textual_witnesses import witness_stats

REQUIRED = {"SBLGNT": 7900, "RP2018": 7900}


def main() -> int:
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        stats = witness_stats(conn)
    by_code = {str(e["code"]): int(e["verse_count"]) for e in stats["editions"]}
    print("Textual witnesses:", ", ".join(f"{code} {by_code.get(code, 0):,}" for code in REQUIRED))
    missing = [code for code, minimum in REQUIRED.items() if by_code.get(code, 0) < minimum]
    if missing:
        print(
            "Textual Witness Lab missing/incomplete required editions: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    print("Textual Witness Lab is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
