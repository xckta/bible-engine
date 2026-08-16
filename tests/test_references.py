from app.references import extract_references

def test_parses_canon_deut_and_reference():
    refs=extract_references('Compare Jude 1:6, Tobit 1:3, and 1 Enoch 6:1-2')
    assert [(r.work,r.kind) for r in refs]==[('Jude','biblical'),('Tobit','biblical'),('1 Enoch','reference')]
