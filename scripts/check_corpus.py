from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.db import init_db,session
init_db(settings.db_path)
with session(settings.db_path) as conn:
    web_can=int(conn.execute("SELECT COUNT(*) n FROM verses v JOIN translations t ON t.id=v.translation_id WHERE t.code='WEB' AND v.corpus_tier='canonical'").fetchone()['n'])
    web_deut=int(conn.execute("SELECT COUNT(*) n FROM verses v JOIN translations t ON t.id=v.translation_id WHERE t.code='WEB' AND v.corpus_tier='deuterocanon'").fetchone()['n'])
    asv=int(conn.execute("SELECT COUNT(*) n FROM verses v JOIN translations t ON t.id=v.translation_id WHERE t.code='ASV' AND v.corpus_tier='canonical'").fetchone()['n'])
if web_can < 30000 or asv < 30000 or web_deut < 3000:
    print(f'Corpus incomplete: WEB canon={web_can}, WEB deuterocanon={web_deut}, ASV canon={asv}')
    raise SystemExit(1)
print(f'Corpus ready: WEB canon={web_can}, WEB deuterocanon={web_deut}, ASV canon={asv}')
