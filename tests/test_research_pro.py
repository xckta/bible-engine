from pathlib import Path

from app.asset_routes import ASSET_VERSION, build_identity, versioned_root
from app.main import app
from app.research_pro_routes import _shared_terms, _vault_evidence


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


def test_root_is_cache_proof_and_versions_core_assets():
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


def test_vault_rows_become_supplemental_evidence():
    e=_vault_evidence({'id':4,'ordinal':3,'title':'Monograph','text':'argument text','score':2.5,'author':'A. Scholar','source_class_label':'Modern scholarship'})
    assert e.tier=='vault'
    assert e.citation.startswith('A. Scholar Monograph')
