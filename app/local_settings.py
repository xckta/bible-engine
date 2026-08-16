from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PREFERENCES = {
    "reasoning_effort": "medium",
    "top_k_canonical": 8,
    "top_k_reference": 8,
    "include_deuterocanon": True,
    "include_reference": True,
    "study_context_chars": 6000,
    "motion": "full",
    "original_show_transliteration": True,
    "original_morphology": "both",
    "hebrew_display": "pointed",
    "original_occurrence_limit": 60,
}
_ALLOWED_REASONING = {"low", "medium", "high", "xhigh"}
_ALLOWED_MOTION = {"full", "reduced"}
_ALLOWED_ORIGINAL_MORPH = {"both", "expanded", "raw"}
_ALLOWED_HEBREW_DISPLAY = {"pointed", "no_cantillation", "unpointed"}


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


def preferences(path: Path) -> dict:
    raw = load_settings(path).get("preferences", {})
    raw = raw if isinstance(raw, dict) else {}
    out = {**DEFAULT_PREFERENCES, **raw}
    effort = str(out.get("reasoning_effort", "medium")).lower()
    out["reasoning_effort"] = effort if effort in _ALLOWED_REASONING else "medium"
    try:
        out["top_k_canonical"] = max(1, min(int(out["top_k_canonical"]), 20))
    except (TypeError, ValueError):
        out["top_k_canonical"] = 8
    try:
        out["top_k_reference"] = max(0, min(int(out["top_k_reference"]), 40))
    except (TypeError, ValueError):
        out["top_k_reference"] = 8
    try:
        out["study_context_chars"] = max(1000, min(int(out["study_context_chars"]), 20000))
    except (TypeError, ValueError):
        out["study_context_chars"] = 6000
    out["include_deuterocanon"] = bool(out.get("include_deuterocanon", True))
    out["include_reference"] = bool(out.get("include_reference", True))
    motion = str(out.get("motion", "full")).lower()
    out["motion"] = motion if motion in _ALLOWED_MOTION else "full"
    out["original_show_transliteration"] = bool(out.get("original_show_transliteration", True))
    morph = str(out.get("original_morphology", "both")).lower()
    out["original_morphology"] = morph if morph in _ALLOWED_ORIGINAL_MORPH else "both"
    hebrew = str(out.get("hebrew_display", "pointed")).lower()
    out["hebrew_display"] = hebrew if hebrew in _ALLOWED_HEBREW_DISPLAY else "pointed"
    try:
        out["original_occurrence_limit"] = max(10, min(int(out["original_occurrence_limit"]), 200))
    except (TypeError, ValueError):
        out["original_occurrence_limit"] = 60
    return out


def save_preferences(path: Path, updates: dict) -> dict:
    current = preferences(path)
    current.update({k: v for k, v in updates.items() if k in DEFAULT_PREFERENCES})
    data = load_settings(path)
    data["preferences"] = current
    save_settings(path, data)
    return preferences(path)
