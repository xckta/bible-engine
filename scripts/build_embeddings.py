from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import init_db, session

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


def hashed_embedding(text: str, dims: int = 384) -> list[float]:
    vec = [0.0] * dims
    for token in TOKEN_RE.findall(text.lower()):
        h = 2166136261
        for ch in token:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        idx = h % dims
        sign = -1.0 if (h >> 31) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


p = argparse.ArgumentParser()
p.add_argument("--db", default=str(settings.db_path))
p.add_argument("--batch-size", type=int, default=256)
a = p.parse_args()
db = Path(a.db)
init_db(db)

with session(db) as conn:
    rows = conn.execute("SELECT id,text FROM verses ORDER BY id").fetchall()
    for start in range(0, len(rows), a.batch_size):
        batch = rows[start:start + a.batch_size]
        vectors = [hashed_embedding(r["text"]) for r in batch]
        conn.executemany(
            "INSERT INTO embeddings(verse_id,model,vector_json) VALUES(?,?,?) "
            "ON CONFLICT(verse_id) DO UPDATE SET model=excluded.model,vector_json=excluded.vector_json",
            [
                (r["id"], "hash-384", json.dumps(v, separators=(",", ":")))
                for r, v in zip(batch, vectors)
            ],
        )
        print(f"{min(start + len(batch), len(rows))}/{len(rows)}")
print("Optional local similarity index complete")
