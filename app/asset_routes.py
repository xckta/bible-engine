from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response

from .version import ASSET_VERSION, BUILD_ID, VERSION

router = APIRouter()
STATIC = Path(__file__).parent / "static"
NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"}


def _asset(name: str, media_type: str):
    return FileResponse(STATIC / name, media_type=media_type, headers=NO_STORE)


@router.get("/")
def versioned_root():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    replacements = {
        'href="/styles.css"': f'href="/styles.css?v={ASSET_VERSION}"',
        'href="/original.css"': f'href="/original.css?v={ASSET_VERSION}"',
        'src="/app.js"': f'src="/app.js?v={ASSET_VERSION}"',
        'src="/original.js"': f'src="/original.js?v={ASSET_VERSION}"',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    html = html.replace("</body>", f'<div id="buildStamp" data-build="{BUILD_ID}" hidden></div></body>')
    return HTMLResponse(html, headers=NO_STORE)


@router.get("/app.js")
def app_js_v2(): return _asset("app.js", "application/javascript")


@router.get("/styles.css")
def styles_css_v2(): return _asset("styles.css", "text/css")


@router.get("/original.js")
def original_js_v2(): return _asset("original.js", "application/javascript")


@router.get("/original.css")
def original_css_v2(): return _asset("original.css", "text/css")


@router.get("/graph.js")
def graph_js_v2(): return _asset("graph.js", "application/javascript")


@router.get("/graph.css")
def graph_css_v2(): return _asset("graph.css", "text/css")


@router.get("/research.js")
def research_js_v2():
    base = (STATIC / "research.js").read_text(encoding="utf-8")
    loader = f"""
;(()=>{{
  if(document.querySelector('script[data-bible-atlas-v2]'))return;
  const s=document.createElement('script');
  s.src='/atlas.js?v={ASSET_VERSION}';s.dataset.bibleAtlasV2='1';
  document.head.appendChild(s);
}})();
"""
    return Response(base + loader, media_type="application/javascript", headers=NO_STORE)


@router.get("/research.css")
def research_css_v2():
    body = (STATIC / "research.css").read_text(encoding="utf-8") + "\n\n" + (STATIC / "atlas.css").read_text(encoding="utf-8")
    return Response(body, media_type="text/css", headers=NO_STORE)


@router.get("/atlas.js")
def atlas_js_v2(): return _asset("atlas.js", "application/javascript")


@router.get("/api/build")
def build_identity():
    return {"version": VERSION, "build_id": BUILD_ID, "asset_version": ASSET_VERSION}
