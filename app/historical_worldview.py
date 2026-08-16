from __future__ import annotations

import re
import sqlite3

PERIODS={
"ancient_israel":{"name":"Ancient Israel / Torah World","range":"2nd millennium–early Iron Age setting","note":"Broad literary-historical lens; dates and composition questions are not resolved by this label.","books":["Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges","Ruth"],"reference_works":[]},
"monarchy":{"name":"Monarchy / First Temple World","range":"Iron Age monarchy","note":"Lens for royal, temple, prophetic, and wisdom settings before the Babylonian exile.","books":["1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah","Hosea","Amos","Micah","Nahum","Habakkuk","Zephaniah"],"reference_works":[]},
"exilic_postexilic":{"name":"Exilic + Persian Period","range":"Babylonian exile through Persian period","note":"Lens for exile, restoration, rebuilt-temple, and postexilic community texts.","books":["Jeremiah","Lamentations","Ezekiel","Daniel","Ezra","Nehemiah","Esther","Haggai","Zechariah","Malachi"],"reference_works":[]},
"second_temple":{"name":"Second Temple Jewish World","range":"Persian/Hellenistic/Roman Second Temple era","note":"Primary-context shelf intentionally includes Deuterocanon and installed Jewish pseudepigrapha without treating them as canonical Scripture.","books":["Daniel","Ezra","Nehemiah","Esther","Haggai","Zechariah","Malachi"],"reference_works":["1 Enoch","Jubilees","Assumption of Moses","Testaments of the Twelve Patriarchs","Letter of Aristeas","Psalms of Solomon","2 Baruch","Sibylline Oracles"]},
"first_century":{"name":"First-Century Jewish + Greco-Roman World","range":"1st century BCE–1st century CE focus","note":"Uses installed NT and late Second Temple sources. The Vault can later add Josephus, Philo, inscriptions, and specialist corpora.","books":["Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians","Colossians","1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation"],"reference_works":["1 Enoch","Jubilees","Assumption of Moses","Psalms of Solomon","2 Baruch","Sibylline Oracles"]},
}
STOP={"the","and","for","that","this","with","from","what","does","about","into","were","was","are","who","why","how","which","where","when","bible","scripture","worldview","context","period","tell","show"}

def period_catalog()->list[dict]:return [{"id":k,**v} for k,v in PERIODS.items()]

def _fts(query:str)->str:
    terms=[x for x in re.findall(r"[A-Za-z0-9']+",query.lower()) if len(x)>2 and x not in STOP][:20]
    return " OR ".join(f'"{x}"' for x in terms)

def worldview_search(conn:sqlite3.Connection,period_id:str,query:str,limit:int=20)->dict:
    if period_id not in PERIODS:raise KeyError(period_id)
    p=PERIODS[period_id];fts=_fts(query);canonical=[];reference=[];deut=[]
    if fts:
        books=p["books"]
        if books:
            marks=','.join('?' for _ in books)
            rows=conn.execute(
                f"SELECT v.book,v.chapter,v.verse,v.text,bm25(verses_fts) rank FROM verses_fts JOIN verses v ON v.id=verses_fts.rowid JOIN translations t ON t.id=v.translation_id WHERE verses_fts MATCH ? AND t.code='WEB' AND v.book IN ({marks}) ORDER BY rank LIMIT ?",
                [fts,*books,limit],).fetchall()
            for r in rows:
                d=dict(r);d['reference']=f"{d['book']} {d['chapter']}:{d['verse']}";(deut if d['book'] not in p['books'] else canonical).append(d)
        works=p["reference_works"]
        if works:
            marks=','.join('?' for _ in works)
            rows=conn.execute(
                f"SELECT w.name,p.chapter,p.verse_start,p.verse_end,p.text,bm25(reference_fts) rank,w.source_label FROM reference_fts JOIN reference_passages p ON p.id=reference_fts.rowid JOIN reference_works w ON w.id=p.work_id WHERE reference_fts MATCH ? AND w.name IN ({marks}) ORDER BY rank LIMIT ?",
                [fts,*works,limit],).fetchall()
            for r in rows:
                d=dict(r);suffix=f" {d['chapter']}" if d['chapter'] else '';suffix+=f":{d['verse_start']}" if d['verse_start'] is not None else '';d['reference']=d['name']+suffix;reference.append(d)
    return {"period":{"id":period_id,**p},"query":query,"canonical":canonical,"deuterocanon":deut,"reference":reference,"notice":"This tool surfaces primary-text material associated with a historical lens. Period labels and approximate ranges are organizing metadata, not evidence for a disputed dating claim."}
