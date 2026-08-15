from pathlib import Path
from app.importers import parse_usfm_files

def test_usfm_parser(tmp_path: Path):
    f=tmp_path/'JUD.usfm'
    f.write_text('\\id JUD\n\\toc1 Jude\n\\c 1\n\\v 5 First verse.\n\\v 6 Angels that kept not their own.\n',encoding='utf8')
    rows=parse_usfm_files([f])
    assert len(rows)==2
    assert rows[1]['book']=='Jude' and rows[1]['chapter']==1 and rows[1]['verse']==6

def test_usfm_poetry_continuation_but_not_heading(tmp_path: Path):
    f=tmp_path/'PSA.usfm'
    f.write_text('\\id PSA\n\\toc1 Psalms\n\\c 23\n\\s1 A Psalm of David\n\\v 1 Jehovah is my shepherd;\n\\q1 I shall not want.\n\\s1 Another heading\n\\v 2 He maketh me to lie down.\n',encoding='utf8')
    rows=parse_usfm_files([f])
    assert rows[0]['text']=='Jehovah is my shepherd; I shall not want.'
    assert 'heading' not in rows[0]['text'].lower()
