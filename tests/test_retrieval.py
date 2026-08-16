from app.db import session
from app.retrieval import retrieve


def test_direct_reference_retrieval(db):
    with session(db) as conn:
        hits = retrieve(conn, "What does Jude 1:6 say?", ["WEB", "ASV"], 12, 0, False)
    assert len(hits) == 2
    assert {h.translation for h in hits} == {"WEB", "ASV"}
    assert all(h.book == "Jude" and h.verse == 6 for h in hits)


def test_lexical_retrieval(db):
    with session(db) as conn:
        hits = retrieve(conn, "angels darkness judgment", ["WEB"], 8, 0, False)
    assert hits
    assert any(h.book in {"Jude", "2 Peter"} for h in hits)
