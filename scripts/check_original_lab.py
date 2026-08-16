from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.db import init_db, session
from app.original_queries import original_status

init_db(settings.db_path)
with session(settings.db_path) as conn:
    status = original_status(conn)
for src in status['sources']:
    print(f"{src['code']}: {int(src['word_count']):,} words / {int(src['verse_count']):,} verses")
print(f"Hebrew words: {int(status.get('hebrew_words', 0)):,}")
print(f"Biblical Aramaic words: {int(status.get('aramaic_words', 0)):,}")
print(f"Greek NT words: {int(status.get('greek_words', 0)):,}")
print(f"Historical lexicon entries: {int(status.get('lexicon_entries', 0)):,}")
print(f"BDB/OpenScriptures lexical profiles: {int(status.get('lexical_profiles', 0)):,}")
print(f"LXX lemma witnesses: {int(status.get('lxx_lemma_occurrences', 0)):,}")
print(f"OSHB versification map: {int(status.get('verse_mappings', 0)):,} mappings ({int(status.get('partial_verse_mappings', 0)):,} partial boundaries)")
if not status['ready']:
    print('Original-language corpus missing or incomplete.')
    raise SystemExit(1)
print('Original Language Lab corpus ready.')
