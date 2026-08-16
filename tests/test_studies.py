from pathlib import Path

from app.studies import add_item, append_consultation, build_context, create_project, export_markdown, project_detail


def test_study_context_is_curated_and_log_is_separate(tmp_path: Path):
    root = tmp_path / "studies"
    project = create_project(root, "Jude Deep Dive", "Understand Jude in Second Temple context", "Keep authority tiers distinct")
    add_item(root, project["id"], "finding", "Jude explicitly cites supplied canonical evidence.")
    add_item(root, project["id"], "note", "Track Watchers terminology carefully.")
    add_item(root, project["id"], "question", "How does 1 Enoch 6–16 compare?")
    result = {
        "answer": "A synthesis",
        "claims": [{"text": "x", "citations": ["ESV Jude 1:6"]}],
        "evidence": [
            {"source": "ESV", "citation": "ESV Jude 1:6", "text": "copyrighted verse"},
            {"source": "Charles", "citation": "1 Enoch 6:1", "text": "reference text"},
        ],
        "mode": "codex_closed_corpus",
        "insufficient_evidence": False,
    }
    append_consultation(root, project["id"], "Compare Jude and Enoch", result)
    context = build_context(root, project["id"], 6000)
    assert "Jude explicitly cites" in context
    assert "Track Watchers" in context
    assert "How does 1 Enoch" in context
    assert "A synthesis" not in context
    assert "copyrighted verse" not in context
    detail = project_detail(root, project["id"])
    evidence = detail["log"][0]["result"]["evidence"]
    assert "text" not in evidence[0] and evidence[0]["text_persisted"] is False
    assert evidence[1]["text"] == "reference text"
    assert (root / project["id"] / "context.md").exists()
    markdown = export_markdown(root, project["id"])
    assert "ESV text intentionally not persisted" in markdown


def test_context_budget_is_bounded(tmp_path: Path):
    project = create_project(tmp_path, "Long Study", "x" * 5000, "")
    add_item(tmp_path, project["id"], "note", "y" * 5000)
    context = build_context(tmp_path, project["id"], 2000)
    assert len(context) < 2200
    assert "truncated to budget" in context
