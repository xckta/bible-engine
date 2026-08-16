from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, session
from app.intertext_graph import graph_stats


def main() -> int:
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        stats = graph_stats(conn)
    print(f"Intertext graph: {stats['edge_count']:,} edges")
    if stats["edge_count"] < 8:
        print("Intertext graph missing or incomplete.", file=sys.stderr)
        return 1
    print("Intertext graph is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
