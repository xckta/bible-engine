from __future__ import annotations

import ast
import importlib
import pkgutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fail(errors: list[str]) -> int:
    if not errors:
        print("Runtime contract audit passed.")
        return 0
    print("Runtime contract audit failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


def audit_app_imports(errors: list[str]) -> None:
    import app
    for info in pkgutil.iter_modules(app.__path__):
        name = f"app.{info.name}"
        try:
            importlib.import_module(name)
        except Exception as exc:
            errors.append(f"cannot import {name}: {type(exc).__name__}: {exc}")


def audit_script_import_symbols(errors: list[str]) -> None:
    for path in sorted((ROOT / "scripts").glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append(f"cannot parse {path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.startswith("app"):
                try:
                    module = importlib.import_module(node.module)
                except Exception as exc:
                    errors.append(f"{path.name}: cannot import module {node.module}: {type(exc).__name__}: {exc}")
                    continue
                for alias in node.names:
                    if alias.name != "*" and not hasattr(module, alias.name):
                        errors.append(f"{path.name}: {node.module} has no exported symbol {alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app"):
                        try:
                            importlib.import_module(alias.name)
                        except Exception as exc:
                            errors.append(f"{path.name}: cannot import {alias.name}: {type(exc).__name__}: {exc}")


def audit_graph_seed(errors: list[str]) -> None:
    try:
        from app.db import init_db, session
        from app.intertext_graph import graph_stats
        from scripts import seed_intertext_graph as seed
        with tempfile.TemporaryDirectory(prefix="bible-engine-contract-") as tmp:
            db = Path(tmp) / "contracts.db"
            init_db(db)
            with session(db) as conn:
                stats = seed.build_graph(conn, include_source_crossrefs=False)
                observed = graph_stats(conn)
        if stats.get("curated") != len(seed.CURATED):
            errors.append(f"graph seeder inserted {stats.get('curated')} curated edges; expected {len(seed.CURATED)}")
        if observed.get("edge_count", 0) < len(seed.CURATED):
            errors.append("graph seeder runtime smoke produced an incomplete graph")
    except Exception as exc:
        errors.append(f"graph seeder runtime smoke failed: {type(exc).__name__}: {exc}")


def audit_textual_witness_storage(errors: list[str]) -> None:
    try:
        from app.db import init_db, session
        from app.textual_witnesses import compare_verse, replace_edition_verses, upsert_edition, witness_stats
        with tempfile.TemporaryDirectory(prefix="bible-engine-witness-") as tmp:
            db = Path(tmp) / "witness.db"
            init_db(db)
            with session(db) as conn:
                upsert_edition(conn, code="CONTRACT_A", name="Contract A", language="greek", edition_class="critical_edition")
                upsert_edition(conn, code="CONTRACT_B", name="Contract B", language="greek", edition_class="byzantine_edition")
                replace_edition_verses(conn, "CONTRACT_A", [{"book":"Jude","chapter":1,"verse":5,"text":"ὅτι Ἰησοῦς λαόν"}])
                replace_edition_verses(conn, "CONTRACT_B", [{"book":"Jude","chapter":1,"verse":5,"text":"ὅτι κύριος λαόν"}])
                stats = witness_stats(conn)
                comparison = compare_verse(conn, "Jude", 1, 5, "CONTRACT_A", "CONTRACT_B")
        if stats.get("edition_count") != 2:
            errors.append("textual-witness storage smoke did not retain both editions")
        if comparison.get("collation", {}).get("changed_tokens", 0) < 1:
            errors.append("textual-witness collation smoke did not detect the known variant")
    except Exception as exc:
        errors.append(f"textual-witness runtime smoke failed: {type(exc).__name__}: {exc}")


def audit_routes(errors: list[str]) -> None:
    try:
        from app.main import app
        paths = set(app.openapi().get("paths", {}))
        required = {
            "/", "/originals", "/api/health", "/api/ask", "/api/graph", "/api/graph/status",
            "/api/original/lab/status", "/api/research/status", "/api/witness/status",
            "/api/worldview/periods", "/api/traditions/matrix", "/api/timeline",
            "/api/atlas/places", "/api/deep-dive", "/api/vault",
        }
        missing = sorted(required - paths)
        if missing:
            errors.append("application OpenAPI contract missing: " + ", ".join(missing))
    except Exception as exc:
        errors.append(f"application route smoke failed: {type(exc).__name__}: {exc}")


def main() -> int:
    errors: list[str] = []
    audit_app_imports(errors)
    audit_script_import_symbols(errors)
    audit_graph_seed(errors)
    audit_textual_witness_storage(errors)
    audit_routes(errors)
    return _fail(errors)


if __name__ == "__main__":
    raise SystemExit(main())
