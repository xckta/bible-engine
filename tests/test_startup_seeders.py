from pathlib import Path

from app.db import init_db, session
from app.intertext_graph import graph_stats
from scripts import seed_intertext_graph as graph_seed
from scripts import seed_textual_witnesses as witness_seed


def test_graph_seeder_runs_against_empty_database(tmp_path: Path):
    db = tmp_path / "graph.db"
    init_db(db)
    with session(db) as conn:
        stats = graph_seed.build_graph(conn, include_source_crossrefs=False)
        observed = graph_stats(conn)
    assert stats["curated"] == len(graph_seed.CURATED)
    assert observed["edge_count"] >= len(graph_seed.CURATED)


def test_sblgnt_loader_matches_upstream_layout(tmp_path: Path):
    root = tmp_path / "sbl"
    target = root / "data" / "sblgnt" / "text"
    target.mkdir(parents=True)
    (target / "John.txt").write_text(
        "John 1:1\tἘν ἀρχῇ ἦν ὁ λόγος\nJohn 1:2\tοὗτος ἦν ἐν ἀρχῇ\n",
        encoding="utf-8",
    )
    rows = witness_seed.load_sbl(root)
    assert rows == [
        {"book": "John", "chapter": 1, "verse": 1, "text": "Ἐν ἀρχῇ ἦν ὁ λόγος"},
        {"book": "John", "chapter": 1, "verse": 2, "text": "οὗτος ἦν ἐν ἀρχῇ"},
    ]


def test_byzantine_loader_matches_upstream_layout(tmp_path: Path):
    root = tmp_path / "byz"
    target = root / "csv-unicode" / "ccat" / "no-variants"
    target.mkdir(parents=True)
    (target / "JOH.csv").write_text(
        "chapter,verse,text\n1,1,Ἐν ἀρχῇ ἦν ὁ λόγος\n1,2,οὗτος ἦν ἐν ἀρχῇ\n",
        encoding="utf-8",
    )
    rows = witness_seed.load_byz(root)
    assert rows == [
        {"book": "John", "chapter": 1, "verse": 1, "text": "Ἐν ἀρχῇ ἦν ὁ λόγος"},
        {"book": "John", "chapter": 1, "verse": 2, "text": "οὗτος ἦν ἐν ἀρχῇ"},
    ]


def test_archive_cache_requires_markers(tmp_path: Path):
    dest = tmp_path / "cache"
    dest.mkdir()
    (dest / "unrelated.txt").write_text("partial", encoding="utf-8")
    assert not witness_seed._markers_exist(dest, ("required/file.txt",))
    required = dest / "required" / "file.txt"
    required.parent.mkdir(parents=True)
    required.write_text("ok", encoding="utf-8")
    assert witness_seed._markers_exist(dest, ("required/file.txt",))
