from pathlib import Path
from app.importers import parse_usfm_files

def test_canonical_and_deuterocanon_tiers(tmp_path:Path):
    gen=tmp_path/'01GEN.usfm';gen.write_text('\\id GEN\n\\c 1\n\\v 1 In the beginning.\n',encoding='utf-8')
    tob=tmp_path/'67TOB.usfm';tob.write_text('\\id TOB\n\\c 1\n\\v 1 This is Tobit.\n',encoding='utf-8')
    rows=parse_usfm_files([gen,tob])
    by={r['book']:r for r in rows}
    assert by['Genesis']['corpus_tier']=='canonical'
    assert by['Tobit']['corpus_tier']=='deuterocanon'
