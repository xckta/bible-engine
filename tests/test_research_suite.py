from pathlib import Path
from types import SimpleNamespace

from app.argument_maps import add_edge, add_node, create_map, get_map
from app.atlas import cosmology_model, place_catalog, temple_model
from app.db import init_db, replace_reference_passages, replace_translation_verses, session, upsert_reference_work, upsert_translation
from app.deep_dive import build_plan
from app.historical_worldview import PERIODS, period_catalog
from app.timeline import add_study_event, catalog as timeline_catalog, study_events
from app.traditions_matrix import GROUPS
from app.vault import add_source, list_sources, search_vault, vault_stats


def make_study(root: Path) -> str:
    pid = "study-abc123"
    p = root / pid
    p.mkdir(parents=True)
    (p / "project.json").write_text('{"id":"study-abc123","title":"X"}', encoding="utf-8")
    return pid


def test_argument_map_persists_reasoning_graph(tmp_path: Path):
    pid = make_study(tmp_path)
    m = create_map(tmp_path, pid, "Genesis 6", "The sons of God are heavenly beings")
    evidence = add_node(tmp_path, pid, m["id"], "evidence", "Genesis 6:2 calls them sons of God", "canonical", .8, ["Genesis 6:2"])
    objection = add_node(tmp_path, pid, m["id"], "objection", "Alternative human-line interpretation", "analysis")
    thesis = m["nodes"][0]["id"]
    add_edge(tmp_path, pid, m["id"], evidence["id"], thesis, "supports")
    add_edge(tmp_path, pid, m["id"], objection["id"], thesis, "challenges")
    got = get_map(tmp_path, pid, m["id"])
    assert len(got["nodes"]) == 3 and len(got["edges"]) == 2


def test_vault_sources_stay_noncanonical_and_are_searchable(tmp_path: Path):
    db = tmp_path / "v.db"
    init_db(db)
    with session(db) as c:
        s = add_source(c, title="My Paper", filename="paper.md", source_class="scholarship", text="The watchers tradition appears in this research note.")
        hits = search_vault(c, "watchers tradition", 10)
        stats = vault_stats(c)
        sources = list_sources(c)
    assert s["source_class"] == "scholarship"
    assert hits[0]["source_class"] == "scholarship"
    assert stats["source_count"] == 1 and sources[0]["source_class_label"] == "Modern scholarship"


def test_timeline_and_atlas_expose_model_certainty(tmp_path: Path):
    events = timeline_catalog()
    assert any(e["certainty"] == "contested" for e in events)
    assert any(e["certainty"] == "historical" for e in events)
    assert len(place_catalog()) >= 10
    assert "model" in temple_model()["notice"].lower() or "schematic" in temple_model()["notice"].lower()
    assert "not a claim" in cosmology_model()["notice"].lower()
    pid = make_study(tmp_path)
    add_study_event(tmp_path, pid, "My checkpoint", -100, note="research marker")
    assert study_events(tmp_path, pid)[0]["certainty"] == "user"


def test_worldview_and_matrix_keep_corpus_families_explicit():
    ids = {p["id"] for p in period_catalog()}
    assert {"second_temple", "first_century"} <= ids
    assert "1 Enoch" in PERIODS["second_temple"]["reference_works"]
    assert GROUPS["Deuterocanon"]["tier"] == "deuterocanon"
    assert GROUPS["Other Second Temple"]["tier"] == "reference"


def test_deep_dive_plan_is_bounded_and_structured(monkeypatch):
    class Fake:
        def chat_json(self, prompt, schema):
            assert "planning searches only" in prompt
            return {
                "title":"Jude research plan",
                "questions":[
                    {"question":"What does Jude explicitly say?","purpose":"Establish canonical text","shelf_focus":"canonical"},
                    {"question":"What canonical parallels exist?","purpose":"Compare canonical material","shelf_focus":"canonical_parallel"},
                    {"question":"What does 1 Enoch add as context?","purpose":"Ancient context","shelf_focus":"reference"},
                ],
                "caution":"Do not conflate reference literature with canon",
            }
    plan = build_plan(Fake(), "Explain Jude 6")
    assert len(plan.questions) == 3
    assert plan.questions[-1].shelf_focus == "reference"
