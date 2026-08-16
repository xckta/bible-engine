from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{5,80}$")
ITEM_KINDS = {"note", "finding", "question"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_id(project_id: str) -> str:
    project_id = project_id.strip().lower()
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("Invalid study project ID.")
    return project_id


def _project_dir(root: Path, project_id: str) -> Path:
    return root / _safe_id(project_id)


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _new_item(text: str) -> dict:
    return {"id": uuid.uuid4().hex[:12], "text": text.strip(), "created_at": _now()}


def _context_markdown(project: dict) -> str:
    def section(title: str, rows: list[dict]) -> list[str]:
        if not rows:
            return []
        return [f"## {title}", *[f"- {row['text']}" for row in rows], ""]

    lines = [
        f"# {project['title']} — Curated Study Context",
        "",
        "> This file is continuity context, not evidence. Bible Engine requires fresh corpus citations for substantive claims.",
        "",
    ]
    if project.get("objective"):
        lines += ["## Objective", project["objective"].strip(), ""]
    if project.get("description"):
        lines += ["## Scope / Description", project["description"].strip(), ""]
    lines += section("Pinned Findings", project.get("findings", []))
    lines += section("Context Notes", project.get("notes", []))
    lines += section("Open Research Questions", project.get("questions", []))
    return "\n".join(lines).strip() + "\n"


def _sync_context(root: Path, project: dict) -> None:
    folder = _project_dir(root, project["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "context.md").write_text(_context_markdown(project), encoding="utf-8")


def create_project(root: Path, title: str, objective: str = "", description: str = "") -> dict:
    title = title.strip()
    if not title:
        raise ValueError("Study title is required.")
    root.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "study"
    project_id = f"{slug}-{uuid.uuid4().hex[:8]}"
    now = _now()
    project = {
        "id": project_id,
        "title": title,
        "objective": objective.strip(),
        "description": description.strip(),
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "findings": [],
        "questions": [],
    }
    folder = _project_dir(root, project_id)
    folder.mkdir(parents=True, exist_ok=False)
    _atomic_json(folder / "project.json", project)
    (folder / "research-log.jsonl").touch()
    _sync_context(root, project)
    return project_summary(root, project)


def load_project(root: Path, project_id: str) -> dict:
    folder = _project_dir(root, project_id)
    project = _load_json(folder / "project.json", None)
    if not isinstance(project, dict):
        raise FileNotFoundError(f"Study project not found: {project_id}")
    project.setdefault("notes", [])
    project.setdefault("findings", [])
    project.setdefault("questions", [])
    return project


def list_projects(root: Path) -> list[dict]:
    if not root.exists():
        return []
    rows: list[dict] = []
    for path in root.iterdir():
        if not path.is_dir() or not PROJECT_ID_RE.fullmatch(path.name):
            continue
        project = _load_json(path / "project.json", None)
        if isinstance(project, dict):
            rows.append(project_summary(root, project))
    return sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True)


def research_log(root: Path, project_id: str, limit: int = 100) -> list[dict]:
    path = _project_dir(root, project_id) / "research-log.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    rows: list[dict] = []
    for line in lines[-max(1, limit):]:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def project_summary(root: Path, project: dict) -> dict:
    context = _context_markdown(project)
    folder = _project_dir(root, project["id"])
    log_count = 0
    try:
        with (folder / "research-log.jsonl").open("r", encoding="utf-8") as handle:
            log_count = sum(1 for line in handle if line.strip())
    except FileNotFoundError:
        pass
    return {
        **project,
        "context_chars": len(context),
        "log_count": log_count,
        "context_file": str(folder / "context.md"),
    }


def project_detail(root: Path, project_id: str, log_limit: int = 100) -> dict:
    project = load_project(root, project_id)
    return {**project_summary(root, project), "log": research_log(root, project_id, log_limit)}


def update_project(root: Path, project_id: str, updates: dict) -> dict:
    project = load_project(root, project_id)
    for key in ("title", "objective", "description"):
        if key in updates and updates[key] is not None:
            value = str(updates[key]).strip()
            if key == "title" and not value:
                raise ValueError("Study title cannot be empty.")
            project[key] = value
    project["updated_at"] = _now()
    folder = _project_dir(root, project_id)
    _atomic_json(folder / "project.json", project)
    _sync_context(root, project)
    return project_summary(root, project)


def add_item(root: Path, project_id: str, kind: str, text: str) -> dict:
    if kind not in ITEM_KINDS:
        raise ValueError("Study item kind must be note, finding, or question.")
    text = text.strip()
    if not text:
        raise ValueError("Study item text is required.")
    project = load_project(root, project_id)
    key = {"note": "notes", "finding": "findings", "question": "questions"}[kind]
    item = _new_item(text)
    project[key].append(item)
    project["updated_at"] = _now()
    folder = _project_dir(root, project_id)
    _atomic_json(folder / "project.json", project)
    _sync_context(root, project)
    return item


def delete_item(root: Path, project_id: str, kind: str, item_id: str) -> bool:
    if kind not in ITEM_KINDS:
        raise ValueError("Invalid study item kind.")
    project = load_project(root, project_id)
    key = {"note": "notes", "finding": "findings", "question": "questions"}[kind]
    before = len(project[key])
    project[key] = [row for row in project[key] if row.get("id") != item_id]
    if len(project[key]) == before:
        return False
    project["updated_at"] = _now()
    folder = _project_dir(root, project_id)
    _atomic_json(folder / "project.json", project)
    _sync_context(root, project)
    return True


def build_context(root: Path, project_id: str, max_chars: int = 6000) -> str:
    project = load_project(root, project_id)
    text = _context_markdown(project)
    max_chars = max(1000, min(int(max_chars), 20000))
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-(max_chars // 2):]
    return head.rstrip() + "\n\n[… curated context truncated to budget …]\n\n" + tail.lstrip()


def _sanitize_result_for_log(result: dict) -> dict:
    evidence = []
    for row in result.get("evidence", []) or []:
        cleaned = dict(row)
        if str(cleaned.get("source", "")).upper() == "ESV":
            cleaned.pop("text", None)
            cleaned["text_persisted"] = False
        else:
            cleaned["text_persisted"] = True
        evidence.append(cleaned)
    return {
        "answer": result.get("answer", ""),
        "claims": result.get("claims", []),
        "evidence": evidence,
        "mode": result.get("mode", ""),
        "insufficient_evidence": bool(result.get("insufficient_evidence", False)),
    }


def append_consultation(root: Path, project_id: str, question: str, result: dict) -> dict:
    project = load_project(root, project_id)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "type": "consultation",
        "created_at": _now(),
        "question": question.strip(),
        "result": _sanitize_result_for_log(result),
    }
    folder = _project_dir(root, project_id)
    with (folder / "research-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    project["updated_at"] = entry["created_at"]
    _atomic_json(folder / "project.json", project)
    _sync_context(root, project)
    return entry


def delete_project(root: Path, project_id: str) -> None:
    folder = _project_dir(root, project_id)
    if not folder.exists():
        raise FileNotFoundError(project_id)
    for child in folder.iterdir():
        if child.is_file():
            child.unlink()
    folder.rmdir()


def export_markdown(root: Path, project_id: str) -> str:
    detail = project_detail(root, project_id, 10000)
    lines = [f"# {detail['title']}", "", "_Exported from Bible Engine // Oracle_", ""]
    if detail.get("objective"):
        lines += ["## Objective", detail["objective"], ""]
    if detail.get("description"):
        lines += ["## Scope", detail["description"], ""]
    for heading, key in (("Pinned Findings", "findings"), ("Context Notes", "notes"), ("Open Questions", "questions")):
        rows = detail.get(key, [])
        if rows:
            lines += [f"## {heading}", *[f"- {r['text']}" for r in rows], ""]
    lines += ["## Research Log", ""]
    for entry in detail.get("log", []):
        if entry.get("type") != "consultation":
            continue
        lines += [f"### {entry.get('question', 'Consultation')}", "", entry.get("result", {}).get("answer", ""), ""]
        claims = entry.get("result", {}).get("claims", [])
        if claims:
            lines += ["**Claims**", ""]
            for claim in claims:
                cites = "; ".join(claim.get("citations", []))
                lines.append(f"- **{claim.get('authority','')} / {claim.get('classification','')}** — {claim.get('text','')}" + (f" — {cites}" if cites else ""))
            lines.append("")
        evidence = entry.get("result", {}).get("evidence", [])
        if evidence:
            lines += ["**Evidence ledger**", ""]
            for row in evidence:
                text = row.get("text") if row.get("text_persisted") else "[ESV text intentionally not persisted; citation retained.]"
                lines.append(f"- {row.get('citation','')} — {text or ''}")
            lines.append("")
    lines += ["---", "Canonical ESV text is not accumulated in the persistent study log. Canonical citations are retained and ESV text is fetched on demand."]
    return "\n".join(lines).strip() + "\n"


def export_json(root: Path, project_id: str) -> str:
    return json.dumps(project_detail(root, project_id, 10000), indent=2, ensure_ascii=False)
