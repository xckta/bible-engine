from pathlib import Path

from app.db import init_db, replace_original_words, session
from app.original_languages import (
    lab_stats,
    lemma_occurrences,
    parse_original_usfm,
    search_words,
    transliterate,
    verse_words,
)


def test_parses_direct_greek_word_tokens():
    text = r'''\c 1
\v 6 \w ἀγγέλους|x-strong="G00320" x-lemma="ἄγγελος" x-morph="Gr,N,,,,,AMP,"\w* \w τοὺς|x-strong="G35880" x-lemma="ὁ" x-morph="Gr,RD,,,,AMP,"\w*
'''
    rows = parse_original_usfm(text, book="Jude", book_order=65, language="greek", source="UGNT v0.34")
    assert len(rows) == 2
    assert rows[0]["surface"] == "ἀγγέλους"
    assert rows[0]["lemma"] == "ἄγγελος"
    assert rows[0]["strongs"] == "G00320"
    assert rows[0]["position"] == 1


def test_parses_alignment_milestones_without_duplicates():
    text = r'''\c 1
\v 1 \zaln-s |x-strong="H0430" x-lemma="אֱלֹהִים" x-morph="He,Ncmpa" x-content="אֱלֹהִים"\*\w אֱלֹהִים|x-strong="H0430" x-lemma="אֱלֹהִים" x-morph="He,Ncmpa"\w*\zaln-e\*
'''
    rows = parse_original_usfm(text, book="Genesis", book_order=1, language="hebrew", source="UHB v2.1.32")
    assert len(rows) == 1
    assert rows[0]["surface"] == "אֱלֹהִים"
    assert rows[0]["lemma"] == "אֱלֹהִים"


def test_transliteration_is_unicode_safe():
    assert transliterate("λόγος", "greek").startswith("logos")
    assert "ʾ" in transliterate("אֱלֹהִים", "hebrew")


def test_original_word_queries(tmp_path: Path):
    db = tmp_path / "x.db"
    init_db(db)
    rows = [
        {"language":"greek","source":"UGNT v0.34","book":"John","book_order":43,"chapter":1,"verse":1,"position":1,"surface":"Ἐν","normalized":"εν","lemma":"ἐν","strongs":"G17220","morph":"Gr,P,,,,,D,,,","transliteration":"en"},
        {"language":"greek","source":"UGNT v0.34","book":"John","book_order":43,"chapter":1,"verse":1,"position":2,"surface":"ἀρχῇ","normalized":"αρχη","lemma":"ἀρχή","strongs":"G07460","morph":"Gr,N,,,,,DFS,","transliteration":"archē"},
        {"language":"greek","source":"UGNT v0.34","book":"John","book_order":43,"chapter":1,"verse":2,"position":1,"surface":"ἀρχῇ","normalized":"αρχη","lemma":"ἀρχή","strongs":"G07460","morph":"Gr,N,,,,,DFS,","transliteration":"archē"},
    ]
    with session(db) as conn:
        replace_original_words(conn, "UGNT v0.34", rows)
        assert len(verse_words(conn, "John", 1, 1)) == 2
        occ = lemma_occurrences(conn, "ἀρχή", "greek", 20)
        assert occ["total"] == 2
        assert len(search_words(conn, "arch", "greek", 20)) == 2
        stats = lab_stats(conn)
        assert stats["total_words"] == 3
