from pathlib import Path
from app.db import init_db,session,upsert_translation,replace_translation_verses,upsert_reference_work,replace_reference_passages
from app.retrieval import retrieve,hydrate_canonical_esv
from app.esv import ESVPassage

def make_db(tmp_path:Path):
    db=tmp_path/'x.db';init_db(db)
    with session(db) as c:
        tid=upsert_translation(c,'WEB','WEB')
        replace_translation_verses(c,tid,[
            {'book':'Jude','book_order':65,'chapter':1,'verse':6,'text':'angels darkness','corpus_tier':'canonical'},
            {'book':'Tobit','book_order':67,'chapter':1,'verse':3,'text':'mercy charity','corpus_tier':'deuterocanon'},])
        wid=upsert_reference_work(c,code='1ENOCH',name='1 Enoch',category='ref',relevance='high',source_label='Charles',source_url='u')
        replace_reference_passages(c,wid,[{'chapter':6,'verse_start':1,'verse_end':1,'text':'watchers angels darkness'}])
    return db

def test_retrieves_three_tiers(tmp_path):
    db=make_db(tmp_path)
    with session(db) as c:r=retrieve(c,'angels darkness',8,8,True,True)
    assert {e.tier for e in r}>={'canonical','pseudepigrapha'}

def test_hydrates_only_canon_to_esv(tmp_path):
    db=make_db(tmp_path)
    with session(db) as c:r=retrieve(c,'Jude 1:6 and 1 Enoch 6:1',8,8,True,True)
    class E:
        def fetch_many(self,refs):return [ESVPassage(refs[0],'ESV canonical (ESV)')]
    out=hydrate_canonical_esv(r,E())
    can=[e for e in out if e.tier=='canonical'][0];ref=[e for e in out if e.tier=='pseudepigrapha'][0]
    assert can.source=='ESV' and can.text=='ESV canonical (ESV)';assert ref.source!='ESV'


def test_explicit_reference_range_stays_on_named_work(tmp_path):
    db=tmp_path/'range.db';init_db(db)
    with session(db) as c:
        tid=upsert_translation(c,'WEB','WEB')
        replace_translation_verses(c,tid,[
            {'book':'Jude','book_order':65,'chapter':1,'verse':6,'text':'angels darkness','corpus_tier':'canonical'}])
        wid=upsert_reference_work(c,code='1ENOCH',name='1 Enoch',category='ref',relevance='high',source_label='Charles',source_url='u')
        replace_reference_passages(c,wid,[
            {'chapter':6,'verse_start':1,'verse_end':1,'text':'watchers descend'},
            {'chapter':7,'verse_start':1,'verse_end':1,'text':'watchers offspring'},
            {'chapter':16,'verse_start':1,'verse_end':1,'text':'spirits judgment'},
            *[{'chapter':8,'verse_start':i,'verse_end':i,'text':f'watcher detail {i}'} for i in range(1,10)],])
        other=upsert_reference_work(c,code='SIB',name='Sibylline Oracles',category='ref',relevance='x',source_label='Terry',source_url='u')
        replace_reference_passages(c,other,[{'chapter':1,'verse_start':1,'verse_end':1,'text':'watchers angels judgment'}])
    with session(db) as c:
        rows=retrieve(c,'Compare Jude 1:6 with 1 Enoch 6–16',8,8,True,True)
    ref=[e for e in rows if e.tier=='pseudepigrapha']
    assert ref
    assert {e.work for e in ref}=={'1 Enoch'}
    assert {6,7,16} <= {e.chapter for e in ref}
    assert len(ref)>8
    assert not any(e.tier=='deuterocanon' for e in rows)
