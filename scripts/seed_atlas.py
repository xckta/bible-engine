from __future__ import annotations

import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.atlas_rich import atlas_stats,iter_openbible,replace_atlas
from app.config import settings
from app.db import init_db,session

URL='https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/main/data/ancient.jsonl'
SOURCE=Path(os.getenv('BIBLE_ATLAS_SOURCE',str(ROOT/'data'/'sources'/'atlas'/'openbible-ancient.jsonl')))

def download()->Path:
    if SOURCE.is_file() and SOURCE.stat().st_size>250_000:
        print(f'Atlas source already downloaded: {SOURCE}');return SOURCE
    SOURCE.parent.mkdir(parents=True,exist_ok=True);tmp=SOURCE.with_suffix(SOURCE.suffix+'.tmp');tmp.unlink(missing_ok=True)
    print('Downloading OpenBible.info Bible Geocoding Data...')
    req=urllib.request.Request(URL,headers={'User-Agent':'BibleEngine-Atlas/1.1'})
    with urllib.request.urlopen(req,timeout=180) as response,tmp.open('wb') as out:shutil.copyfileobj(response,out)
    if tmp.stat().st_size<250_000:tmp.unlink(missing_ok=True);raise RuntimeError('Atlas source download was unexpectedly small; refusing to replace the cache.')
    tmp.replace(SOURCE);return SOURCE

def main()->int:
    source=download();init_db(settings.db_path)
    with session(settings.db_path) as c:result=replace_atlas(c,iter_openbible(source));stats=atlas_stats(c)
    print(f"Biblical Atlas indexed {result['place_count']:,} places; {result['resolved_count']:,} resolved coordinates; {result['occurrence_count']:,} verse occurrences. Formats: {result['formats']}")
    if not stats['ready']:raise RuntimeError(f"Atlas source imported but did not meet readiness thresholds: places={stats['place_count']} resolved={stats['resolved_count']}. The upstream dataset shape may have changed.")
    print('Biblical Atlas gazetteer ready.');return 0
if __name__=='__main__':raise SystemExit(main())
