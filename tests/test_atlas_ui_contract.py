from __future__ import annotations

from app.atlas_routes import enhanced_research_js


def test_research_bundle_delegates_live_atlas_tab_to_rich_workspace():
    response = enhanced_research_js()
    body = response.body.decode("utf-8")

    assert "function renderAtlas(){if(window.BibleEngineAtlas?.render)return window.BibleEngineAtlas.render();" in body
    assert "s.src='/atlas.js'" in body
    assert "[data-research-tab=\"atlas\"].active" in body
    assert "window.BibleEngineAtlas?.render?.()" in body
