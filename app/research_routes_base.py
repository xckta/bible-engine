from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader

from .answering import answer_question
from .argument_maps import add_edge as argument_add_edge, add_node as argument_add_node, create_map, delete_map, delete_node, get_map, list_maps
from .atlas import cosmology_model, place_catalog, temple_model
from .config import settings
from .db import session
from .deep_dive import build_plan, plan_dict
from .esv import ESVClient, ESVError
from .historical_worldview import period_catalog, worldview_search
from .local_settings import esv_key, preferences
from .providers import CodexClient, ProviderError
from .retrieval import Evidence, hydrate_canonical_esv, retrieve
from .studies import append_consultation, build_context
from .textual_witnesses import compare_verse, verse_readings, witness_stats
from .timeline import add_study_event, catalog as timeline_catalog, filter_events, study_events
from .traditions_matrix import build_matrix
from .vault import CLASSES, add_source, delete_source, list_sources, search_vault, vault_stats

router=APIRouter()
STATIC=Path(__file__).parent/'static'

@router.get('/research.js')
def research_js():return FileResponse(STATIC/'research.js',media_type='application/javascript')
@router.get('/research.css')
def research_css():return FileResponse(STATIC/'research.css',media_type='text/css')


def _esv()->ESVClient:
    key=esv_key(settings.local_settings_path)
    if not key:raise HTTPException(428,detail={'code':'esv_key_required','message':'This research tool displays canonical quotations in ESV. Add your ESV API key in Settings.'})
    return ESVClient(key,settings.esv_base_url)
def _codex()->CodexClient:
    p=preferences(settings.local_settings_path);return CodexClient(settings.codex_command,settings.codex_model,p['reasoning_effort'],settings.codex_timeout)
def _hydrate_rows(rows:list[dict])->list[dict]:
    if not rows:return rows
    try:passages=_esv().fetch_many([r['reference'] for r in rows])
    except ESVError as exc:raise HTTPException(502,detail={'code':'esv_error','message':str(exc)}) from exc
    out=[]
    for r,p in zip(rows,passages):out.append({**r,'text':p.text,'source':'ESV'})
    return out

@router.get('/api/research/status')
def research_status():
    with session(settings.db_path) as c:
        return {'witnesses':witness_stats(c),'vault':vault_stats(c),'periods':period_catalog(),'timeline_count':len(timeline_catalog())}

# --- Textual witnesses ---
@router.get('/api/witness/status')
def witness_status():
    with session(settings.db_path) as c:return witness_stats(c)
@router.get('/api/witness/verse')
def witness_verse(book:str,chapter:int=Query(ge=1,le=200),verse:int=Query(ge=1,le=200)):
    with session(settings.db_path) as c:return {'reference':f'{book} {chapter}:{verse}','readings':verse_readings(c,book,chapter,verse)}
@router.get('/api/witness/compare')
def witness_compare(book:str,chapter:int=Query(ge=1,le=200),verse:int=Query(ge=1,le=200),left:str='SBLGNT',right:str='RP2018'):
    try:
        with session(settings.db_path) as c:return compare_verse(c,book,chapter,verse,left,right)
    except KeyError as exc:raise HTTPException(404,detail={'code':'witness_reading_missing','message':str(exc)}) from exc

# --- Historical worldview ---
@router.get('/api/worldview/periods')
def worldview_periods():return {'periods':period_catalog()}
@router.get('/api/worldview/search')
def worldview_query(period:str,query:str=Query(min_length=2,max_length=500),limit:int=Query(default=12,ge=1,le=30)):
    try:
        with session(settings.db_path) as c:d=worldview_search(c,period,query,limit)
    except KeyError:raise HTTPException(404,detail={'code':'period_not_found','message':'Unknown worldview period.'})
    d['canonical']=_hydrate_rows(d['canonical']) if d['canonical'] else []
    return d

# --- Argument mapper ---
class ArgCreate(BaseModel):title:str=Field(min_length=1,max_length=180);thesis:str=Field(min_length=1,max_length=4000)
class ArgNode(BaseModel):node_type:Literal['thesis','position','claim','evidence','objection','assumption','question','conclusion'];text:str=Field(min_length=1,max_length=8000);authority:str='analysis';confidence:float|None=Field(default=None,ge=0,le=1);citations:list[str]=Field(default_factory=list,max_length=50)
class ArgEdge(BaseModel):source:str;target:str;edge_type:Literal['supports','challenges','depends_on','answers','qualifies','derived_from','competes_with']
@router.get('/api/studies/{project_id}/arguments')
def arg_list(project_id:str):
    try:return {'maps':list_maps(settings.studies_path,project_id)}
    except Exception as exc:raise HTTPException(400,detail={'code':'argument_error','message':str(exc)})
@router.post('/api/studies/{project_id}/arguments')
def arg_create(project_id:str,req:ArgCreate):
    try:return create_map(settings.studies_path,project_id,req.title,req.thesis)
    except Exception as exc:raise HTTPException(400,detail={'code':'argument_error','message':str(exc)})
@router.get('/api/studies/{project_id}/arguments/{map_id}')
def arg_get(project_id:str,map_id:str):
    try:return get_map(settings.studies_path,project_id,map_id)
    except Exception as exc:raise HTTPException(404,detail={'code':'argument_error','message':str(exc)})
@router.post('/api/studies/{project_id}/arguments/{map_id}/nodes')
def arg_node(project_id:str,map_id:str,req:ArgNode):
    try:return argument_add_node(settings.studies_path,project_id,map_id,req.node_type,req.text,req.authority,req.confidence,req.citations)
    except Exception as exc:raise HTTPException(400,detail={'code':'argument_error','message':str(exc)})
@router.post('/api/studies/{project_id}/arguments/{map_id}/edges')
def arg_edge(project_id:str,map_id:str,req:ArgEdge):
    try:return argument_add_edge(settings.studies_path,project_id,map_id,req.source,req.target,req.edge_type)
    except Exception as exc:raise HTTPException(400,detail={'code':'argument_error','message':str(exc)})
@router.delete('/api/studies/{project_id}/arguments/{map_id}/nodes/{node_id}')
def arg_node_delete(project_id:str,map_id:str,node_id:str):return {'ok':delete_node(settings.studies_path,project_id,map_id,node_id)}
@router.delete('/api/studies/{project_id}/arguments/{map_id}')
def arg_map_delete(project_id:str,map_id:str):return {'ok':delete_map(settings.studies_path,project_id,map_id)}

# --- Traditions matrix ---
@router.get('/api/traditions/matrix')
def traditions_matrix(query:str=Query(min_length=2,max_length=500),per_group:int=Query(default=4,ge=1,le=10)):
    with session(settings.db_path) as c:d=build_matrix(c,query,per_group)
    canonical=[h for col in d['columns'] for h in col['hits'] if h['tier']=='canonical']
    if canonical:
        hydrated=_hydrate_rows(canonical);lookup={h['reference']:h['text'] for h in hydrated}
        for col in d['columns']:
            for h in col['hits']:
                if h['tier']=='canonical':h['text']=lookup.get(h['reference'],h['text']);h['source']='ESV'
    return d

# --- Timeline ---
class TimelineEvent(BaseModel):title:str=Field(min_length=1,max_length=180);start:int=Field(ge=-5000,le=3000);end:int|None=Field(default=None,ge=-5000,le=3000);note:str=Field(default='',max_length=2000);citations:list[str]=Field(default_factory=list,max_length=50)
@router.get('/api/timeline')
def timeline(start:int=-2100,end:int=150,types:str='',project_id:str|None=None):
    selected=[x for x in types.split(',') if x];events=filter_events(start,end,selected or None)
    if project_id:
        try:events=events+study_events(settings.studies_path,project_id)
        except Exception:pass
    return {'events':sorted(events,key=lambda x:(x['start'],x['end'])),'notice':'Timeline dates are organizational research metadata. Entries marked contested/model/approximate are not claims established by the biblical corpus.'}
@router.post('/api/studies/{project_id}/timeline')
def timeline_add(project_id:str,req:TimelineEvent):
    try:return add_study_event(settings.studies_path,project_id,req.title,req.start,req.end,req.note,req.citations)
    except Exception as exc:raise HTTPException(400,detail={'code':'timeline_error','message':str(exc)})

# --- Atlas / temple / cosmology ---
@router.get('/api/atlas/places')
def atlas_places():return {'places':place_catalog(),'notice':'Coordinates are approximate research markers, not archaeological boundary claims.'}
@router.get('/api/atlas/temple')
def atlas_temple():return temple_model()
@router.get('/api/atlas/cosmology')
def atlas_cosmology():return cosmology_model()

# --- Automated Deep Dive ---
class DeepDiveRequest(BaseModel):question:str=Field(min_length=5,max_length=4000);project_id:str|None=None;max_evidence:int=Field(default=60,ge=15,le=100)
@router.post('/api/deep-dive')
def deep_dive(req:DeepDiveRequest):
    codex=_codex();status=codex.status()
    if not status.ready:raise HTTPException(503,detail={'code':'codex_unavailable','message':status.detail or 'Codex unavailable.'})
    try:plan=build_plan(codex,req.question)
    except ProviderError as exc:raise HTTPException(502,detail={'code':'deep_dive_plan_error','message':str(exc)}) from exc
    prefs=preferences(settings.local_settings_path);packets=[];merged:dict[tuple,Evidence]={}
    with session(settings.db_path) as c:
        for item in plan.questions:
            rows=retrieve(c,item.question,min(12,prefs['top_k_canonical']+4),min(16,prefs['top_k_reference']+8),True,True)
            packets.append({'question':item.question,'purpose':item.purpose,'shelf_focus':item.shelf_focus,'retrieved':[r.citation for r in rows]})
            for e in rows:merged[(e.tier,e.citation,e.text[:120])]=e
    evidence=list(merged.values())[:req.max_evidence]
    if any(e.tier=='canonical' for e in evidence):
        try:evidence=hydrate_canonical_esv(evidence,_esv())
        except ESVError as exc:raise HTTPException(502,detail={'code':'esv_error','message':str(exc)}) from exc
    context='DEEP DIVE PLAN (research organization only; not evidence):\n'+json.dumps(plan_dict(plan),ensure_ascii=False,indent=2)
    if req.project_id:
        try:context+='\n\nACTIVE STUDY CONTEXT:\n'+build_context(settings.studies_path,req.project_id,prefs['study_context_chars'])
        except Exception as exc:raise HTTPException(400,detail={'code':'study_error','message':str(exc)})
    try:result=answer_question(req.question,evidence,codex,project_context=context)
    except ProviderError as exc:raise HTTPException(502,detail={'code':'deep_dive_synthesis_error','message':str(exc)}) from exc
    payload={'plan':plan_dict(plan),'packets':packets,'result':result.__dict__,'evidence_count':len(evidence)}
    if req.project_id and result.mode=='codex_closed_corpus':
        try:append_consultation(settings.studies_path,req.project_id,'DEEP DIVE: '+req.question,result.__dict__)
        except Exception:pass
    return payload

# --- Custom Corpus Vault ---
@router.get('/api/vault')
def vault_list():
    with session(settings.db_path) as c:return {'sources':list_sources(c),'stats':vault_stats(c)}
@router.get('/api/vault/search')
def vault_search(query:str=Query(min_length=2,max_length=500),classes:str='',limit:int=Query(default=20,ge=1,le=100)):
    with session(settings.db_path) as c:return {'query':query,'hits':search_vault(c,query,limit,[x for x in classes.split(',') if x])}
@router.delete('/api/vault/{source_id}')
def vault_delete(source_id:str):
    with session(settings.db_path) as c:return {'ok':delete_source(c,source_id)}
@router.post('/api/vault/upload')
async def vault_upload(file:UploadFile=File(...),source_class:str=Form('scholarship'),title:str=Form(''),author:str=Form(''),citation:str=Form(''),notes:str=Form('')):
    if source_class not in CLASSES:raise HTTPException(400,detail={'code':'vault_class','message':'Invalid Vault source class.'})
    raw=await file.read();name=file.filename or 'uploaded-source';ext=Path(name).suffix.lower()
    try:
        if ext=='.pdf':
            import io
            reader=PdfReader(io.BytesIO(raw));text='\n\n'.join((p.extract_text() or '') for p in reader.pages)
        elif ext in {'.txt','.md','.markdown','.json','.csv','.xml','.html','.htm'}:text=raw.decode('utf-8',errors='replace')
        else:raise HTTPException(400,detail={'code':'vault_type','message':'Supported Vault files: PDF, TXT, Markdown, JSON, CSV, XML, HTML.'})
        with session(settings.db_path) as c:return add_source(c,title=title or Path(name).stem,filename=name,source_class=source_class,text=text,author=author,citation=citation,notes=notes)
    except HTTPException:raise
    except Exception as exc:raise HTTPException(400,detail={'code':'vault_ingest','message':str(exc)}) from exc
