from __future__ import annotations
import re,sqlite3

GROUPS={
'Torah':{'tier':'canonical','books':['Genesis','Exodus','Leviticus','Numbers','Deuteronomy']},
'Prophets':{'tier':'canonical','books':['Joshua','Judges','1 Samuel','2 Samuel','1 Kings','2 Kings','Isaiah','Jeremiah','Ezekiel','Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi']},
'Writings':{'tier':'canonical','books':['Ruth','1 Chronicles','2 Chronicles','Ezra','Nehemiah','Esther','Job','Psalms','Proverbs','Ecclesiastes','Song of Solomon','Lamentations','Daniel']},
'New Testament':{'tier':'canonical','books':['Matthew','Mark','Luke','John','Acts','Romans','1 Corinthians','2 Corinthians','Galatians','Ephesians','Philippians','Colossians','1 Thessalonians','2 Thessalonians','1 Timothy','2 Timothy','Titus','Philemon','Hebrews','James','1 Peter','2 Peter','1 John','2 John','3 John','Jude','Revelation']},
'Deuterocanon':{'tier':'deuterocanon','books':[]},
'Enochic / Jubilees':{'tier':'reference','works':['1 Enoch','Jubilees']},
'Other Second Temple':{'tier':'reference','works':['Assumption of Moses','Testaments of the Twelve Patriarchs','Letter of Aristeas','Psalms of Solomon','2 Baruch','Sibylline Oracles','Apocalypse of Moses','Ascension / Martyrdom of Isaiah']},
}
STOP={'the','and','for','that','this','with','from','what','does','about','into','were','was','are','who','why','how','which','where','when','compare','tradition','matrix','theme','concept','bible'}
def _fts(q):
    terms=[x for x in re.findall(r"[A-Za-z0-9']+",q.lower()) if len(x)>2 and x not in STOP][:18]
    return ' OR '.join(f'"{x}"' for x in terms)
def build_matrix(conn:sqlite3.Connection,query:str,per_group:int=5)->dict:
    fts=_fts(query);columns=[]
    for name,cfg in GROUPS.items():
        hits=[]
        if fts and cfg['tier'] in {'canonical','deuterocanon'}:
            params=[fts,cfg['tier']];sql="SELECT v.book,v.chapter,v.verse,v.text,bm25(verses_fts) rank FROM verses_fts JOIN verses v ON v.id=verses_fts.rowid JOIN translations t ON t.id=v.translation_id WHERE verses_fts MATCH ? AND t.code='WEB' AND v.corpus_tier=?"
            books=cfg.get('books',[])
            if books:sql+=' AND v.book IN ('+','.join('?' for _ in books)+')';params.extend(books)
            sql+=' ORDER BY rank LIMIT ?';params.append(per_group)
            for r in conn.execute(sql,params).fetchall():
                d=dict(r);hits.append({'tier':cfg['tier'],'reference':f"{d['book']} {d['chapter']}:{d['verse']}",'text':d['text'],'score':float(-d['rank'])})
        elif fts and cfg['tier']=='reference':
            works=cfg.get('works',[]);params=[fts];sql="SELECT w.name,p.chapter,p.verse_start,p.text,w.source_label,bm25(reference_fts) rank FROM reference_fts JOIN reference_passages p ON p.id=reference_fts.rowid JOIN reference_works w ON w.id=p.work_id WHERE reference_fts MATCH ?"
            if works:sql+=' AND w.name IN ('+','.join('?' for _ in works)+')';params.extend(works)
            sql+=' ORDER BY rank LIMIT ?';params.append(per_group)
            for r in conn.execute(sql,params).fetchall():
                d=dict(r);ref=d['name']+(f" {d['chapter']}" if d['chapter'] else '')+(f":{d['verse_start']}" if d['verse_start'] is not None else '');hits.append({'tier':'reference','reference':ref,'text':d['text'],'source_label':d['source_label'],'score':float(-d['rank'])})
        columns.append({'name':name,'tier':cfg['tier'],'hits':hits})
    return {'query':query,'columns':columns,'notice':'Columns organize textual parallels by corpus family. Similar vocabulary or theme does not by itself establish literary dependence or chronological development.'}
