from pathlib import Path

from app.db import init_db, session
from app.intertext_graph import add_edge, extract_usfm_crossrefs, graph_for, graph_stats


def test_graph_preserves_edge_semantics_and_tiers(tmp_path: Path):
    db = tmp_path / "x.db"
    init_db(db)
    with session(db) as conn:
        add_edge(conn, "Jude 1:6", "2 Peter 2:4", "canonical_parallel", strength=.94, provenance="test")
        add_edge(conn, "Jude 1:6", "1 Enoch 6–16", "ancient_context", strength=.88, provenance="test")
        graph = graph_for(conn, "Jude 1:6", depth=1)
        stats = graph_stats(conn)
    assert stats["edge_count"] == 2
    assert {e["type"] for e in graph["edges"]} == {"canonical_parallel", "ancient_context"}
    tiers = {n["id"]: n["tier"] for n in graph["nodes"]}
    assert tiers["Jude 1:6"] == "canonical"
    assert tiers["2 Peter 2:4"] == "canonical"
    assert tiers["1 Enoch 6–16"] == "reference"


def test_graph_depth_expands_without_retyping_edges(tmp_path: Path):
    db = tmp_path / "x.db"
    init_db(db)
    with session(db) as conn:
        add_edge(conn, "Jude 1:6", "2 Peter 2:4", "canonical_parallel", provenance="test")
        add_edge(conn, "2 Peter 2:4", "1 Enoch 10", "ancient_context", provenance="test")
        one = graph_for(conn, "Jude 1:6", depth=1)
        two = graph_for(conn, "Jude 1:6", depth=2)
    assert len(one["edges"]) == 1
    assert len(two["edges"]) == 2


def test_usfm_crossrefs_are_only_cross_reference_candidates():
    text = r'''\c 1
\v 6 Angels are discussed. \x + \xo 1:6 \xt 2 Peter 2:4; Genesis 6:1\x*
'''
    rows = extract_usfm_crossrefs(text, book="Jude")
    assert ("Jude 1:6", "2 Peter 2:4") in rows
    assert ("Jude 1:6", "Genesis 6:1") in rows
