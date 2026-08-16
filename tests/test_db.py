import sqlite3
from pathlib import Path
from app.db import init_db,session,upsert_translation,replace_translation_verses,upsert_reference_work,replace_reference_passages,library_stats

def test_migrates_old_verses_table(tmp_path:Path):
    db=tmp_path/'x.db';conn=sqlite3.connect(db)
    conn.executescript('CREATE TABLE translations(id INTEGER PRIMARY KEY,code TEXT UNIQUE,name TEXT,license TEXT DEFAULT "",source_url TEXT DEFAULT "");CREATE TABLE verses(id INTEGER PRIMARY KEY,translation_id INTEGER,book TEXT,book_order INTEGER,chapter INTEGER,verse INTEGER,text TEXT,UNIQUE(translation_id,book,chapter,verse));')
    conn.close();init_db(db)
    conn=sqlite3.connect(db);cols={r[1] for r in conn.execute('pragma table_info(verses)')};conn.close()
    assert 'corpus_tier' in cols

def test_library_stats_separate_tiers(tmp_path:Path):
    db=tmp_path/'x.db';init_db(db)
    with session(db) as c:
        tid=upsert_translation(c,'WEB','WEB')
        replace_translation_verses(c,tid,[
            {'book':'Genesis','book_order':1,'chapter':1,'verse':1,'text':'a','corpus_tier':'canonical'},
            {'book':'Tobit','book_order':67,'chapter':1,'verse':1,'text':'b','corpus_tier':'deuterocanon'},
        ])
        wid=upsert_reference_work(c,code='1ENOCH',name='1 Enoch',category='ref',relevance='high',source_label='x',source_url='u')
        replace_reference_passages(c,wid,[{'chapter':1,'verse_start':1,'verse_end':1,'text':'c'}])
        s=library_stats(c)
    assert s['canonical_verses']==1 and s['deuterocanon_verses']==1 and s['reference_passages']==1
