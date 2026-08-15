from app.references import extract_references

def test_reference_parser():
    r=extract_references('Compare Jude 1:6-7 with 2 Peter 2:4')
    assert [(x.book,x.chapter,x.verse_start,x.verse_end) for x in r]==[('Jude',1,6,7),('2 Peter',2,4,4)]
