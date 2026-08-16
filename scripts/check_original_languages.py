from __future__ import annotations

import sys
from collections import defaultdict
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

    # lab_stats is grouped by language + source, so OSHB-derived Hebrew and
    # Aramaic appear as separate rows. Sum by source instead of allowing one
    # language row to overwrite another in a dict comprehension.
    by_source: dict[str, int] = defaultdict(int)
    for row in stats["sources"]:
        by_source[str(row["source"])] += int(row["word_count"])

    hebrew_aramaic = by_source.get("UHB v2.1.32", 0)
    greek = by_source.get("UGNT v0.34", 0)
    print(f"Compact Languages drawer: Hebrew/Aramaic {hebrew_aramaic:,} words | Greek {greek:,} words")
    if hebrew_aramaic < 100000 or greek < 100000:
        print(
            "Compact Languages drawer cache is missing or incomplete; regenerate it from the verified deep corpus.",
            file=sys.stderr,
        )
        return 1
    print("Compact Languages drawer cache is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
