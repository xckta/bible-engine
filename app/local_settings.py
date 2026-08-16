from __future__ import annotations

import json
import os
from pathlib import Path


def load_settings(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(path: Path, updates: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_settings(path)
    data.update(updates)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    return data


def esv_key(path: Path) -> str:
    env = os.getenv("ESV_API_KEY", "").strip()
    if env:
        return env
    return str(load_settings(path).get("esv_api_key", "")).strip()


def masked_key(path: Path) -> str | None:
    key = esv_key(path)
    if not key:
        return None
    if len(key) <= 8:
        return "••••••••"
    return key[:4] + "••••••••" + key[-4:]
