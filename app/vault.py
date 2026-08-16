from __future__ import annotations

import re,sqlite3,uuid
from datetime import datetime,timezone

VAULT_SCHEMA="""
CREATE TABLE IF NOT EXISTS vault_sources(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,filename TEXT NOT NULL DEFAULT '',source_class TEXT NOT NULL,
author TEXT NOT NULL DEFAULT '',citation TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vault_chunks(
 id INTEGER PRIMARY KEY,source_id TEXT NOT NULL REFERENCES vault_sources(id) ON DELETE CASCADE,ordinal INTEGER NOT NULL,text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(text,content='vault_chunks',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS vault_ai AFTER INSERT ON vault_chunks BEGIN INSERT INTO vault_fts(rowid,text) VALUES(new.id,new.text); END;
CREATE TRIGGER IF NOT EXISTS vault_ad AFTER DELETE ON vault_chunks BEGIN INSERT INTO vault_fts(vault_fts,rowid,text) VALUES('delete',old.id,old.text); END;
"""
CLASSES={'primary_ancient':'Primary / ancient source','lexicon':'Lexicon / language reference','scholarship':'Modern scholarship','personal_notes':'Personal notes','other':'Other noncanonical source'}

def ensure_vault_schema(conn:sqlite3.Connection):conn.executescript(VAULT_SCHEMA)
def _chunks(text:str,max_chars:int=1800)->list[str]:
    text=text.replace('\r\n','\n').strip();paras=[p.strip() for p in re.split(r'\n\s*\n',text) if p.strip()];out=[];buf=''
    for p in paras:
        if len(p)>max_chars:
            parts=re.split(r'(?<=[.!?])\s+',p)
        else:parts=[p]
        for part in parts:
            if len(buf)+len(part)+2>max_chars and buf:out.append(buf.strip());buf=''
            if len(part)>max_chars:
                for i in range(0,len(part),max_chars):
                    if buf:out.append(buf.strip());buf=''
                    out.append(part[i:i+max_chars].strip())
            else:buf=(buf+'\n\n'+part).strip()
    if buf:out.append(buf.strip())
    return [x for x in out if x]
def add_source(conn:sqlite3.Connection,*,title:str,filename:str,source_class:str,text:str,author:str='',citation:str='',notes:str='')->dict:
    ensure_vault_schema(conn)
    if source_class not in CLASSES:raise ValueError('Invalid Vault source class.')
    chunks=_chunks(text)
    if not chunks:raise ValueError('No readable text found in source.')
    sid=uuid.uuid4().hex[:16];created=datetime.now(timezone.utc).isoformat(timespec='seconds')
    conn.execute('INSERT INTO vault_sources(id,title,filename,source_class,author,citation,notes,created_at) VALUES(?,?,?,?,?,?,?,?)',(sid,title.strip() or filename,filename,source_class,author.strip(),citation.strip(),notes.strip(),created))
    conn.executemany('INSERT INTO vault_chunks(source_id,ordinal,text) VALUES(?,?,?)',[(sid,i+1,t) for i,t in enumerate(chunks)])
    return {'id':sid,'title':title.strip() or filename,'filename':filename,'source_class':source_class,'source_class_label':CLASSES[source_class],'author':author,'citation':citation,'notes':notes,'created_at':created,'chunk_count':len(chunks)}
def list_sources(conn:sqlite3.Connection)->list[dict]:
    ensure_vault_schema(conn);rows=conn.execute('SELECT s.*,COUNT(c.id) chunk_count FROM vault_sources s LEFT JOIN vault_chunks c ON c.source_id=s.id GROUP BY s.id ORDER BY s.created_at DESC').fetchall();return [{**dict(r),'source_class_label':CLASSES.get(r['source_class'],r['source_class'])} for r in rows]
def delete_source(conn:sqlite3.Connection,sid:str)->bool:
    ensure_vault_schema(conn);cur=conn.execute('DELETE FROM vault_sources WHERE id=?',(sid,));return cur.rowcount>0
def search_vault(conn:sqlite3.Connection,query:str,limit:int=20,classes:list[str]|None=None)->list[dict]:
    ensure_vault_schema(conn);terms=[x for x in re.findall(r"[A-Za-z0-9']+",query.lower()) if len(x)>2][:20]
    if not terms:return []
    fts=' OR '.join(f'"{t}"' for t in terms);sql='SELECT c.id,c.ordinal,c.text,s.id source_id,s.title,s.source_class,s.author,s.citation,bm25(vault_fts) rank FROM vault_fts JOIN vault_chunks c ON c.id=vault_fts.rowid JOIN vault_sources s ON s.id=c.source_id WHERE vault_fts MATCH ?';params:[object]=[fts]
    valid=[c for c in (classes or []) if c in CLASSES]
    if valid:sql+=' AND s.source_class IN ('+','.join('?' for _ in valid)+')';params.extend(valid)
    sql+=' ORDER BY rank LIMIT ?';params.append(limit)
    return [{**dict(r),'source_class_label':CLASSES.get(r['source_class'],r['source_class']),'score':float(-r['rank'])} for r in conn.execute(sql,params).fetchall()]
def vault_stats(conn:sqlite3.Connection)->dict:
    ensure_vault_schema(conn);s=conn.execute('SELECT COUNT(*) n FROM vault_sources').fetchone()['n'];c=conn.execute('SELECT COUNT(*) n FROM vault_chunks').fetchone()['n'];return {'source_count':int(s),'chunk_count':int(c),'classes':CLASSES}
