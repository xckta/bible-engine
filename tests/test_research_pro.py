from pathlib import Path

from fastapi.testclient import TestClient

from app.asset_routes import ASSET_VERSION, build_identity, versioned_root
from app.main import app
from app.research_pro_routes import _reference_work_name, _shared_terms, _vault_evidence


def test_professional_research_routes_are_registered():
    paths=set(app.openapi()['paths'])
    required={
        '/api/build',
        '/api/research-pro/witness/verse',
        '/api/research-pro/witness/chapter',
        '/api/research-pro/worldview',
        '/api/research-pro/traditions',
        '/api/research-pro/deep-dive',
        '/api/research-pro/vault/{source_id}',
    }
    assert required <= paths


def test_browser_receives_cache_proof_current_build():
    client=TestClient(app)
    root=client.get('/')
    assert root.status_code==200
    assert root.headers.get('cache-control','').startswith('no-store')
    assert f'/app.js?v={ASSET_VERSION}' in root.text
    assert f'/original.js?v={ASSET_VERSION}' in root.text

    research=client.get('/research.js')
    assert research.status_code==200
    assert research.headers.get('cache-control','').startswith('no-store')
    assert '/api/research-pro/worldview' in research.text
    assert '/api/research-pro/deep-dive' in research.text

    build=client.get('/api/build')
    assert build.status_code==200
    assert build.json()['version']=='2.0.0'


def test_root_builder_versions_core_assets():
    response=versioned_root()
    body=response.body.decode('utf-8')
    assert response.headers['cache-control'].startswith('no-store')
    assert f'/app.js?v={ASSET_VERSION}' in body
    assert f'/original.js?v={ASSET_VERSION}' in body
    assert build_identity()['version']=='2.0.0'


def test_research_console_uses_real_workbench_endpoints():
    js=(Path(__file__).resolve().parents[1]/'app'/'static'/'research.js').read_text(encoding='utf-8')
    assert '/api/research-pro/witness/chapter' in js
    assert '/api/research-pro/worldview' in js
    assert '/api/research-pro/traditions' in js
    assert '/api/research-pro/deep-dive' in js
    assert 'VERSE DOSSIER' in js
    assert 'SCAN CHAPTER' in js
    assert 'window.BibleEngineAtlas' in js
    assert 'Atlas / Temple / Cosmology Explorer' not in js


def test_shared_term_analysis_is_explicit_not_magic_similarity():
    rows=_shared_terms(['angels judgment prison prison'],['judgment watchers prison'])
    terms={r['term'] for r in rows}
    assert {'judgment','prison'} <= terms
    prison=next(r for r in rows if r['term']=='prison')
    assert prison['left_count']==2 and prison['right_count']==1


def test_reference_work_names_are_not_truncated():
    assert _reference_work_name('1 Enoch 6:1','fallback')=='1 Enoch'
    assert _reference_work_name('Assumption of Moses 10','fallback')=='Assumption of Moses'


def test_vault_rows_become_supplemental_evidence():
    e=_vault_evidence({'id':4,'ordinal':3,'title':'Monograph','text':'argument text','score':2.5,'author':'A. Scholar','source_class_label':'Modern scholarship'})
    assert e.tier=='vault'
    assert e.citation.startswith('A. Scholar Monograph')
