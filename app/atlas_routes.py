from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .atlas_rich import atlas_books, atlas_countries, atlas_stats, atlas_types, distance_km, get_place, journey_catalog, journey_detail, nearby, query_places
from .config import settings
from .db import session

router=APIRouter();STATIC=Path(__file__).parent/'static';ROOT=Path(__file__).resolve().parents[1]
GEOMETRY_RE=re.compile(r'^geometry/[A-Za-z0-9_-]+\.geojson$')

@router.get('/research.js')
def enhanced_research_js():
    base=(STATIC/'research.js').read_text(encoding='utf-8')
    # The base Research Console owns tab state. Delegate its Atlas renderer to
    # the richer bundle instead of relying on a second click-handler contract.
    # This keeps R.activeTab correct and also upgrades programmatic/reopened
    # Atlas tabs, while failing loudly if the base bundle ever changes shape.
    needle='function renderAtlas(){'
    if needle not in base:
        raise HTTPException(500,detail={'code':'atlas_ui_contract_changed','message':'Research Atlas hook was not found; refusing to serve a silently downgraded Atlas.'})
    base=base.replace(needle,"function renderAtlas(){if(window.BibleEngineAtlas?.render)return window.BibleEngineAtlas.render();",1)
    loader="""
;(()=>{
  if(document.querySelector('script[data-bible-atlas-v2]'))return;
  const s=document.createElement('script');
  s.src='/atlas.js';s.defer=true;s.dataset.bibleAtlasV2='1';
  s.onload=()=>{const tab=document.querySelector('[data-research-tab="atlas"].active');if(tab)window.BibleEngineAtlas?.render?.()};
  document.head.appendChild(s);
})();
"""
    return Response(base+loader,media_type='application/javascript')

@router.get('/research.css')
def enhanced_research_css():
    return Response((STATIC/'research.css').read_text(encoding='utf-8')+'\n\n/* Atlas Explorer v2 */\n'+(STATIC/'atlas.css').read_text(encoding='utf-8'),media_type='text/css')

@router.get('/atlas.js')
def atlas_js():return Response((STATIC/'atlas.js').read_text(encoding='utf-8'),media_type='application/javascript')

@router.get('/api/atlas/explorer/status')
def status():
    with session(settings.db_path) as c:
        return {**atlas_stats(c),'types':atlas_types(c)[:80],'books':atlas_books(c),'countries':atlas_countries(c)[:120],'journeys':journey_catalog(c),
                'notice':'Geographic identifications are research data, not canonical evidence. Confidence and ambiguity remain visible; map segments between journey stops are schematic unless a source provides route geometry.'}

@router.get('/api/atlas/explorer/places')
def places(q:str=Query(default='',max_length=200),book:str=Query(default='',max_length=80),type:str=Query(default='',max_length=100),country:str=Query(default='',max_length=120),west:float|None=Query(default=None,ge=-180,le=180),south:float|None=Query(default=None,ge=-90,le=90),east:float|None=Query(default=None,ge=-180,le=180),north:float|None=Query(default=None,ge=-90,le=90),resolved_only:bool=True,limit:int=Query(default=300,ge=1,le=1000),offset:int=Query(default=0,ge=0)):
    if any(x is not None for x in (west,south,east,north)) and any(x is None for x in (west,south,east,north)):raise HTTPException(400,detail={'code':'atlas_bounds_error','message':'west, south, east, and north must be supplied together.'})
    if west is not None and east is not None and west>east:raise HTTPException(400,detail={'code':'atlas_bounds_error','message':'Dateline-crossing bounds are not supported in one query.'})
    with session(settings.db_path) as c:d=query_places(c,q=q,book=book,place_type=type,country=country,west=west,south=south,east=east,north=north,resolved_only=resolved_only,limit=limit,offset=offset)
    d['notice']='Map results reflect the installed OpenBible.info geographic dataset and its identification metadata.';return d

@router.get('/api/atlas/explorer/place/{place_id}')
def place(place_id:str,occurrence_limit:int=Query(default=250,ge=1,le=1000)):
    try:
        with session(settings.db_path) as c:
            p=get_place(c,place_id,occurrence_limit);p['nearby']=nearby(c,p['latitude'],p['longitude'],35,12,place_id) if p.get('resolved') else [];return p
    except KeyError as exc:raise HTTPException(404,detail={'code':'atlas_place_not_found','message':'Atlas place not found.'}) from exc

@router.get('/api/atlas/explorer/place/{place_id}/geometry')
def place_geometry(place_id:str):
    try:
        with session(settings.db_path) as c:p=get_place(c,place_id,1)
    except KeyError as exc:raise HTTPException(404,detail={'code':'atlas_place_not_found','message':'Atlas place not found.'}) from exc
    if p.get('geometry'):
        return p['geometry']
    rel=str(p.get('geometry_path') or '').strip()
    if not rel:
        raise HTTPException(404,detail={'code':'atlas_geometry_missing','message':'No source geometry is published for this place.'})
    if not GEOMETRY_RE.fullmatch(rel):
        raise HTTPException(502,detail={'code':'atlas_geometry_path_invalid','message':'The source geometry path is not in the expected OpenBible format.'})
    cache=ROOT/'data'/'sources'/'atlas'/'geometry'/Path(rel).name
    cache.parent.mkdir(parents=True,exist_ok=True)
    if not cache.is_file() or cache.stat().st_size<20:
        url='https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/main/'+rel
        req=urllib.request.Request(url,headers={'User-Agent':'BibleEngine-Atlas/1.1'})
        try:
            with urllib.request.urlopen(req,timeout=45) as response:
                raw=response.read(8_000_001)
        except Exception as exc:
            raise HTTPException(502,detail={'code':'atlas_geometry_download_failed','message':f'Source geometry could not be downloaded: {exc}'}) from exc
        if len(raw)>8_000_000:
            raise HTTPException(502,detail={'code':'atlas_geometry_too_large','message':'Source geometry exceeded the Atlas safety limit.'})
        try:payload=json.loads(raw.decode('utf-8-sig'))
        except Exception as exc:raise HTTPException(502,detail={'code':'atlas_geometry_invalid','message':'Source geometry was not valid GeoJSON.'}) from exc
        if not isinstance(payload,dict) or payload.get('type') not in {'Feature','FeatureCollection','Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon','GeometryCollection'}:
            raise HTTPException(502,detail={'code':'atlas_geometry_invalid','message':'Source geometry was not a supported GeoJSON object.'})
        tmp=cache.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(cache)
    try:payload=json.loads(cache.read_text(encoding='utf-8'))
    except Exception as exc:
        cache.unlink(missing_ok=True);raise HTTPException(502,detail={'code':'atlas_geometry_cache_invalid','message':'Cached source geometry was invalid and has been discarded.'}) from exc
    return payload

@router.get('/api/atlas/explorer/nearby')
def nearby_places(lat:float=Query(ge=-90,le=90),lon:float=Query(ge=-180,le=180),radius_km:float=Query(default=50,gt=0,le=500),limit:int=Query(default=30,ge=1,le=100)):
    with session(settings.db_path) as c:return {'items':nearby(c,lat,lon,radius_km,limit),'radius_km':radius_km}

@router.get('/api/atlas/explorer/filters')
def filters():
    with session(settings.db_path) as c:return {'types':atlas_types(c),'books':atlas_books(c),'countries':atlas_countries(c)}

@router.get('/api/atlas/explorer/journeys')
def journeys():
    with session(settings.db_path) as c:return {'journeys':journey_catalog(c)}

@router.get('/api/atlas/explorer/journeys/{journey_id}')
def journey(journey_id:str):
    try:
        with session(settings.db_path) as c:return journey_detail(c,journey_id)
    except KeyError as exc:raise HTTPException(404,detail={'code':'atlas_journey_not_found','message':'Unknown Atlas journey.'}) from exc

class AtlasDistanceRequest(BaseModel):
    lat1:float=Field(ge=-90,le=90);lon1:float=Field(ge=-180,le=180);lat2:float=Field(ge=-90,le=90);lon2:float=Field(ge=-180,le=180)

@router.post('/api/atlas/explorer/distance')
def distance(req:AtlasDistanceRequest):
    km=distance_km(req.lat1,req.lon1,req.lat2,req.lon2)
    return {'kilometers':round(km,2),'miles':round(km*0.621371,2),'notice':'Great-circle straight-line distance between the selected coordinates; not an ancient road, walking, or sailing distance.'}
