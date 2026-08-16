from pathlib import Path

from app.db import init_db, session
from app.textual_witnesses import (
    collate_texts,
    compare_verse,
    replace_edition_verses,
    upsert_edition,
    witness_stats,
)


def test_collation_detects_replacement_without_interpretive_claim():
    d = collate_texts("ὅτι κύριος λαόν", "ὅτι Ἰησοῦς λαόν")
    assert d["changed_tokens"] >= 1
    assert any(s["op"] == "replace" for s in d["segments"])


def test_two_editions_compare_and_remain_labeled_editions(tmp_path: Path):
    db = tmp_path / "w.db"
    init_db(db)
    with session(db) as c:
        upsert_edition(c, code="A", name="Critical A", language="greek", edition_class="critical_edition", notes="edition")
        upsert_edition(c, code="B", name="Byzantine B", language="greek", edition_class="byzantine_edition", notes="edition")
        replace_edition_verses(c, "A", [{"book":"Jude","chapter":1,"verse":5,"text":"ὅτι Ἰησοῦς λαόν"}])
        replace_edition_verses(c, "B", [{"book":"Jude","chapter":1,"verse":5,"text":"ὅτι κύριος λαόν"}])
        d = compare_verse(c, "Jude", 1, 5, "A", "B")
        stats = witness_stats(c)
    assert stats["edition_count"] == 2
    assert d["left"]["edition_class"] == "critical_edition"
    assert d["right"]["edition_class"] == "byzantine_edition"
    assert "not by itself" in d["notice"]
