from __future__ import annotations

import csv
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.config import settings
from app.db import init_db,session
from app.textual_witnesses import replace_edition_verses,upsert_edition,witness_stats

SBL_MAP={
'Matt':'Matthew','Mark':'Mark','Luke':'Luke','John':'John','Acts':'Acts','Rom':'Romans','1Cor':'1 Corinthians','2Cor':'2 Corinthians','Gal':'Galatians','Eph':'Ephesians','Phil':'Philippians','Col':'Colossians','1Thess':'1 Thessalonians','2Thess':'2 Thessalonians','1Tim':'1 Timothy','2Tim':'2 Timothy','Titus':'Titus','Phlm':'Philemon','Heb':'Hebrews','Jas':'James','1Pet':'1 Peter','2Pet':'2 Peter','1John':'1 John','2John':'2 John','3John':'3 John','Jude':'Jude','Rev':'Revelation'}
BYZ_MAP={'MAT':'Matthew','MAR':'Mark','LUK':'Luke','JOH':'John','ACT':'Acts','ROM':'Romans','1CO':'1 Corinthians','2CO':'2 Corinthians','GAL':'Galatians','EPH':'Ephesians','PHP':'Philippians','COL':'Colossians','1TH':'1 Thessalonians','2TH':'2 Thessalonians','1TI':'1 Timothy','2TI':'2 Timothy','TIT':'Titus','PHM':'Philemon','HEB':'Hebrews','JAM':'James','1PE':'1 Peter','2PE':'2 Peter','1JO':'1 John','2JO':'2 John','3JO':'3 John','JUD':'Jude','REV':'Revelation'}


def archive(url:str,dest:Path)->Path:
    if dest.exists() and any(dest.rglob('*.*')):return dest
    print('Downloading',url)
    req=urllib.request.Request(url,headers={'User-Agent':'BibleEngine-TextualWitness/0.7'})
    with urllib.request.urlopen(req,timeout=120) as response:payload=response.read()
    tmp=dest.parent/(dest.name+'-extract');shutil.rmtree(tmp,ignore_errors=True);tmp.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as z: z.extractall(tmp)
    roots=[p for p in tmp.iterdir() if p.is_dir()];src=roots[0] if len(roots)==1 else tmp
    shutil.rmtree(dest,ignore_errors=True);dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(src),str(dest));shutil.rmtree(tmp,ignore_errors=True)
    return dest


def load_sbl(root:Path)->list[dict]:
    rows=[]
    for stem,book in SBL_MAP.items():
        p=root/'data'/'sblgnt'/'text'/f'{stem}.txt'
        if not p.exists():continue
        for line in p.read_text(encoding='utf-8-sig',errors='replace').splitlines():
            if '\t' not in line:continue
            ref,text=line.split('\t',1)
            import re
            m=re.search(r'(\d+):(\d+)$',ref.strip())
            if m:rows.append({'book':book,'chapter':int(m.group(1)),'verse':int(m.group(2)),'text':text.strip()})
    return rows


def load_byz(root:Path)->list[dict]:
    rows=[];base=root/'csv-unicode'/'ccat'/'no-variants'
    for stem,book in BYZ_MAP.items():
        p=base/f'{stem}.csv'
        if not p.exists():continue
        with p.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                if r.get('chapter') and r.get('verse') and r.get('text'):
                    rows.append({'book':book,'chapter':int(r['chapter']),'verse':int(r['verse']),'text':r['text'].strip()})
    return rows


def main()->int:
    init_db(settings.db_path)
    base=ROOT/'data'/'sources'/'witnesses'
    sbl=archive('https://github.com/Faithlife/SBLGNT/archive/refs/heads/master.zip',base/'sblgnt')
    byz=archive('https://github.com/byztxt/byzantine-majority-text/archive/refs/heads/master.zip',base/'rp2018')
    sbl_rows=load_sbl(sbl);byz_rows=load_byz(byz)
    if len(sbl_rows)<7900 or len(byz_rows)<7900:raise RuntimeError(f'Witness source incomplete: SBLGNT={len(sbl_rows)} RP2018={len(byz_rows)}')
    with session(settings.db_path) as c:
        upsert_edition(c,code='SBLGNT',name='SBL Greek New Testament',language='greek',edition_class='critical_edition',date_label='2010 / public source v1.2',editor='Michael W. Holmes',license='CC BY 4.0',source_url='https://github.com/Faithlife/SBLGNT',notes='Modern critically edited Greek New Testament. Edition data, not a manuscript.')
        upsert_edition(c,code='RP2018',name='Robinson–Pierpont Byzantine Textform',language='greek',edition_class='byzantine_edition',date_label='2018',editor='Maurice A. Robinson / William G. Pierpont',license='Public Domain / Unlicense repository',source_url='https://github.com/byztxt/byzantine-majority-text',notes='Byzantine-priority Greek edition. Edition data, not a manuscript.')
        a=replace_edition_verses(c,'SBLGNT',sbl_rows);b=replace_edition_verses(c,'RP2018',byz_rows);stats=witness_stats(c)
    print(f'Textual Witness Lab ready: SBLGNT {a:,} verses | RP2018 {b:,} verses | {stats["edition_count"]} editions')
    return 0

if __name__=='__main__':raise SystemExit(main())
