from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse, json
from app.config import settings
from app.db import init_db, session
from app.providers import OllamaClient, hashed_embedding

p=argparse.ArgumentParser()
p.add_argument('--db', default=str(settings.db_path));p.add_argument('--provider', choices=['ollama','hash'], default='ollama');p.add_argument('--batch-size', type=int, default=64)
a=p.parse_args(); db=Path(a.db); init_db(db)
client=OllamaClient(settings.ollama_base_url,settings.ollama_chat_model,settings.ollama_embed_model)
with session(db) as conn:
    rows=conn.execute('SELECT id,text FROM verses ORDER BY id').fetchall()
    for start in range(0,len(rows),a.batch_size):
        batch=rows[start:start+a.batch_size]; texts=[r['text'] for r in batch]
        if a.provider=='ollama':
            vectors=client.embed(texts); model=settings.ollama_embed_model
        else:
            vectors=[hashed_embedding(t) for t in texts]; model='hash-384'
        conn.executemany('INSERT INTO embeddings(verse_id,model,vector_json) VALUES(?,?,?) ON CONFLICT(verse_id) DO UPDATE SET model=excluded.model,vector_json=excluded.vector_json',[(r['id'],model,json.dumps(v,separators=(',',':'))) for r,v in zip(batch,vectors)])
        print(f'{min(start+len(batch),len(rows))}/{len(rows)}')
print('Embedding index complete')
