from app.local_settings import preferences, save_preferences, save_settings


def test_preferences_roundtrip_and_preserve_esv_key(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(path, {"esv_api_key": "secret"})
    saved = save_preferences(path, {
        "reasoning_effort": "high",
        "top_k_canonical": 12,
        "top_k_reference": 30,
        "include_reference": False,
        "study_context_chars": 10000,
        "motion": "reduced",
    })
    assert saved["reasoning_effort"] == "high"
    assert saved["top_k_reference"] == 30
    assert saved["include_reference"] is False
    loaded = preferences(path)
    assert loaded["motion"] == "reduced"
    assert loaded["study_context_chars"] == 10000
    assert path.read_text(encoding="utf-8").find('"esv_api_key": "secret"') >= 0
