import sqlite3
from pathlib import Path

from app.db import init_db, session, upsert_translation, replace_translation_verses
from app.original_core import strongs_from_oshb_lemma
from app.original_parsers import parse_hebrew_lexicon, parse_lxx_lemma_file, parse_oshb_xml, parse_tischendorf_file
from app.original_queries import lemma_report, search_words, translation_parallels, verse_words
from app.original_storage import ensure_original_schema, replace_lxx_lemma_occurrences, replace_original_words, upsert_original_source
from scripts.sync_compact_originals import sync_source


def test_oshb_aramaic_and_augmented_strongs(tmp_path: Path):
    xml='''<?xml version="1.0"?><osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText><verse osisID="Dan.2.4"><w lemma="560" morph="AVqp3mp" id="ar1">אֲמַר</w></verse></osisText></osis>'''
    p=tmp_path/'Dan.xml';p.write_text(xml,encoding='utf-8')
    rows=parse_oshb_xml(p)
    assert rows[0]['word_language']=='Aramaic'
    assert strongs_from_oshb_lemma('122 a')=='H122A'


def test_tischendorf_duplicate_slots_get_unique_record_identity(tmp_path: Path):
    p=tmp_path/'JOH.TUP'
    p.write_text(
        'JOH 1:1.1 Ἐν PREP 1722 ἐν ! ἐν\n'
        'JOH 1:1.1 Ἐν PREP 1722 ἐν ! ἐν\n'
        'JOH 1:1.1 Ἐν2 PREP 1722 ἐν ! ἐν\n'
        'JOH 1:1.2 ἀρχῇ N-DSF 746 ἀρχή ! ἀρχή\n',
        encoding='utf-8',
    )
    rows=parse_tischendorf_file(p)
    assert len(rows)==3
    assert [r['position'] for r in rows]==[1,2,3]
    assert len({r['source_word_id'] for r in rows})==3
    assert rows[0]['source_word_id'].startswith('JOH.TUP:L1:1:1.1')
    assert rows[1]['source_word_id'].startswith('JOH.TUP:L3:1:1.1')

    db=tmp_path/'tisch.db';init_db(db)
    with session(db) as c:
        sid=upsert_original_source(c,code='TISCH',name='T',language='Greek',testament='New Testament',license_text='x',source_url='u',attribution='a')
        assert replace_original_words(c,sid,rows)==3


def test_deep_lab_queries_and_aramaic_filter(tmp_path: Path):
    db=tmp_path/'x.db';init_db(db)
    with session(db) as c:
        sid=upsert_original_source(c,code='OSHB',name='OSHB',language='Hebrew',testament='Old Testament',license_text='x',source_url='u',attribution='a')
        replace_original_words(c,sid,[{'book':'Daniel','book_order':27,'chapter':2,'verse':4,'position':1,'surface':'אֲמַר','surface_normalized':'אמר','lemma':'560','lemma_normalized':'560','strongs':'H560','morph':'AVqp3mp','morph_expanded':'Aramaic, verb','transliteration':'amar','word_language':'Aramaic'}])
        hits=search_words(c,'H560','aramaic','strongs',20)
        payload=verse_words(c,'Daniel 2:4')
    assert len(hits)==1 and hits[0]['word_language']=='Aramaic'
    assert payload['language']=='Aramaic'


def test_compact_cache_projects_deep_rows_and_renumbers_positions(tmp_path: Path):
    db=tmp_path/'compact.db';init_db(db)
    with session(db) as c:
        sid=upsert_original_source(c,code='OSHB',name='OSHB',language='Hebrew',testament='Old Testament',license_text='x',source_url='u',attribution='a')
        replace_original_words(c,sid,[
            {'book':'Psalms','book_order':19,'chapter':3,'verse':1,'position':1,'source_word_id':'a1','surface':'א','surface_normalized':'א','source_book':'Psalms','source_chapter':3,'source_verse':1,'word_language':'Hebrew'},
            {'book':'Psalms','book_order':19,'chapter':3,'verse':1,'position':1,'source_word_id':'a2','surface':'ב','surface_normalized':'ב','source_book':'Psalms','source_chapter':3,'source_verse':2,'word_language':'Aramaic'},
        ])
        assert sync_source(c,'OSHB','UHB v2.1.32')==2
        rows=c.execute("SELECT language,source,book,chapter,verse,position,surface FROM original_words ORDER BY position").fetchall()
    assert [r['position'] for r in rows]==[1,2]
    assert [r['language'] for r in rows]==['hebrew','aramaic']
    assert all(r['source']=='UHB v2.1.32' for r in rows)


def test_bdb_profile_and_augindex(tmp_path: Path):
    index=tmp_path/'LexicalIndex.xml';bdb=tmp_path/'BrownDriverBriggs.xml';aug=tmp_path/'AugIndex.xml'
    index.write_text('<index><entry id="afc"><w xlit="adom">אָדֹם</w><pos>A</pos><def>red</def><xref bdb="a.bd.ac" strong="122" aug="a"/></entry></index>',encoding='utf-8')
    bdb.write_text('<lexicon><entry id="a.bd.ac"><sense><def>red</def></sense><sense><def>ruddy</def></sense></entry></lexicon>',encoding='utf-8')
    aug.write_text('<index><w aug="122a">afc</w></index>',encoding='utf-8')
    rows=parse_hebrew_lexicon(index,bdb,aug)
    row=next(x for x in rows if x['strongs']=='H122A')
    assert row['gloss']=='red' and 'ruddy' in row['semantic_range']


def test_lxx_lemma_witness_without_text(tmp_path: Path):
    p=tmp_path/'Gen.js';p.write_text('{"Gen.1.1":[{"key":"εν","lemma":"ἐν"}],"Gen.1.2":[{"key":"εν","lemma":"ἐν"}]}',encoding='utf-8')
    lxx=parse_lxx_lemma_file(p);db=tmp_path/'lxx.db';init_db(db)
    with session(db) as c:
        sid=upsert_original_source(c,code='TISCH',name='T',language='Greek',testament='New Testament',license_text='x',source_url='u',attribution='a')
        replace_original_words(c,sid,[{'book':'John','book_order':43,'chapter':1,'verse':1,'position':1,'surface':'ἐν','surface_normalized':'εν','lemma':'ἐν','lemma_normalized':'εν','strongs':'G1722','morph':'PREP','morph_expanded':'preposition','transliteration':'en','word_language':'Greek'}])
        replace_lxx_lemma_occurrences(c,lxx)
        wid=verse_words(c,'John 1:1')['verses'][0]['words'][0]['id'];report=lemma_report(c,wid)
    assert report['lxx']['occurrence_count']==2
    assert 'does not bundle' in report['lxx']['note']


def test_translation_parallels(tmp_path: Path):
    db=tmp_path/'translations.db';init_db(db)
    with session(db) as c:
        web=upsert_translation(c,'WEB','World English Bible');asv=upsert_translation(c,'ASV','American Standard Version')
        row={'book':'John','book_order':43,'chapter':1,'verse':1,'text':'In the beginning was the Word.','corpus_tier':'canonical'}
        replace_translation_verses(c,web,[row]);r2=dict(row);r2['text']='In the beginning was the Word;';replace_translation_verses(c,asv,[r2])
        rows=translation_parallels(c,'John 1:1')
    assert [x['translation'] for x in rows]==['WEB','ASV']


def test_word_identity_allows_remapped_target_position_overlap(tmp_path: Path):
    db=tmp_path/'identity.db';init_db(db)
    with session(db) as c:
        sid=upsert_original_source(c,code='OSHB',name='OSHB',language='Hebrew',testament='Old Testament',license_text='x',source_url='u',attribution='a')
        rows=[
            {'book':'Psalms','book_order':19,'chapter':3,'verse':1,'position':1,'source_word_id':'a1','surface':'א','source_book':'Psalms','source_chapter':3,'source_verse':1,'word_language':'Hebrew'},
            {'book':'Psalms','book_order':19,'chapter':3,'verse':1,'position':1,'source_word_id':'a2','surface':'ב','source_book':'Psalms','source_chapter':3,'source_verse':2,'word_language':'Hebrew'},
        ]
        assert replace_original_words(c,sid,rows)==2
        count=c.execute("SELECT COUNT(*) n FROM original_lab_words WHERE source_id=? AND book='Psalms' AND chapter=3 AND verse=1",(sid,)).fetchone()['n']
    assert count==2


def test_legacy_target_unique_schema_migrates_to_source_identity(tmp_path: Path):
    db=tmp_path/'legacy.db';init_db(db)
    with sqlite3.connect(db) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS original_lab_sources(
          id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,language TEXT NOT NULL,testament TEXT NOT NULL,
          license TEXT NOT NULL DEFAULT '',source_url TEXT NOT NULL DEFAULT '',attribution TEXT NOT NULL DEFAULT '',version TEXT NOT NULL DEFAULT '',installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS original_lab_words(
          id INTEGER PRIMARY KEY,source_id INTEGER NOT NULL,book TEXT NOT NULL,book_order INTEGER NOT NULL,chapter INTEGER NOT NULL,verse INTEGER NOT NULL,position INTEGER NOT NULL,
          source_word_id TEXT NOT NULL DEFAULT '',surface TEXT NOT NULL,surface_normalized TEXT NOT NULL DEFAULT '',lemma TEXT NOT NULL DEFAULT '',lemma_normalized TEXT NOT NULL DEFAULT '',
          alt_lemma TEXT NOT NULL DEFAULT '',strongs TEXT NOT NULL DEFAULT '',morph TEXT NOT NULL DEFAULT '',morph_expanded TEXT NOT NULL DEFAULT '',transliteration TEXT NOT NULL DEFAULT '',
          word_language TEXT NOT NULL DEFAULT '',source_book TEXT NOT NULL DEFAULT '',source_chapter INTEGER NOT NULL DEFAULT 0,source_verse INTEGER NOT NULL DEFAULT 0,verse_mapping_type TEXT NOT NULL DEFAULT 'same',
          UNIQUE(source_id,book,chapter,verse,position)
        );
        ''')
    with session(db) as c:
        ensure_original_schema(c)
        unique_sets=[]
        for idx in c.execute('PRAGMA index_list(original_lab_words)').fetchall():
            if not idx['unique']: continue
            unique_sets.append([r['name'] for r in c.execute(f"PRAGMA index_info('{idx['name']}')").fetchall()])
    assert ['source_id','book','chapter','verse','position'] not in unique_sets
    assert ['source_id','source_book','source_chapter','source_verse','position'] in unique_sets