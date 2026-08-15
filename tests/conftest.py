from __future__ import annotations
import os
from pathlib import Path
import pytest
from app.db import init_db, session, upsert_translation, replace_translation_verses
from app.importers import parse_json_file

@pytest.fixture
def db(tmp_path: Path):
    p=tmp_path/'test.db'; init_db(p)
    root=Path(__file__).parents[1]
    with session(p) as conn:
        for code,file in [('WEB','web_demo.json'),('ASV','asv_demo.json')]:
            tid=upsert_translation(conn,code,code,'Public Domain','')
            replace_translation_verses(conn,tid,parse_json_file(root/'data'/'demo'/file))
    return p
