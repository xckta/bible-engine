from pathlib import Path

from app.db import init_db, session
from app.original_storage import replace_original_words as replace_deep_words, upsert_original_source
from scripts.sync_compact_originals import rows_for_source


def test_compact_cache_projection_renumbers_and_preserves_language(tmp_path: Path):
    db = tmp_path / "x.db"
    init_db(db)
    with session(db) as conn:
        sid = upsert_original_source(
            conn,
            code="OSHB",
            name="OSHB",
            language="Hebrew",
            testament="Old Testament",
            license_text="x",
            source_url="u",
            attribution="a",
        )
        replace_deep_words(
            conn,
            sid,
            [
                {
                    "book": "Daniel",
                    "book_order": 27,
                    "chapter": 2,
                    "verse": 4,
                    "position": 1,
                    "surface": "אֲמַר",
                    "surface_normalized": "אמר",
                    "lemma": "560",
                    "lemma_normalized": "560",
                    "strongs": "H560",
                    "morph": "AVqp3mp",
                    "morph_expanded": "Aramaic, verb",
                    "transliteration": "amar",
                    "word_language": "Aramaic",
                },
                {
                    "book": "Daniel",
                    "book_order": 27,
                    "chapter": 2,
                    "verse": 4,
                    "position": 2,
                    "surface": "מַלְכָּא",
                    "surface_normalized": "מלכא",
                    "lemma": "4430",
                    "lemma_normalized": "4430",
                    "strongs": "H4430",
                    "morph": "ANcmsd",
                    "morph_expanded": "Aramaic, noun",
                    "transliteration": "malka",
                    "word_language": "Aramaic",
                },
            ],
        )
        projected = list(rows_for_source(conn, "OSHB"))

    assert [r["position"] for r in projected] == [1, 2]
    assert all(r["language"] == "aramaic" for r in projected)
    assert all(r["source"] == "UHB v2.1.32" for r in projected)
