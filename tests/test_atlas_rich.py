import json
from pathlib import Path

from app.atlas_rich import atlas_books,atlas_stats,get_place,journey_detail,parse_openbible_line,query_places,replace_atlas
from app.db import init_db,session

def rich(place_id='a1',name='Jerusalem',lon='35.235,31.778',verse='Matt.21.1'):
    return {'id':place_id,'friendly_id':name,'type':'settlement','translation_name_counts':{name:5},
            'identifications':[{'score':{'time_total':800},'resolutions':[{'lonlat':lon,'best_time_score':900,'description':name,'type':'settlement'}]}],
            'verses':[{'osis':verse,'readable':'Matthew 21:1','translations':['esv'],'instance_types':{'name':10}}]}

def test_parse_rich_openbible_record_with_verse_and_resolution():
    place,verses=parse_openbible_line(json.dumps(rich()));assert place['name']=='Jerusalem';assert round(place['latitude'],3)==31.778;assert place['confidence_label']=='higher';assert verses[0]['book']=='Matthew' and verses[0]['chapter']==21

def test_parse_feature_record_and_skip_reference_surface_code():
    feature={'type':'Feature','geometry':{'type':'Point','coordinates':[35.2,31.7]},'properties':{'id':'a2','name':'Bethany','alternate_names':['Beth Anya'],'detailed_type':'city_or_town','inside_modern_states':['Israel']}}
    place,verses=parse_openbible_line(json.dumps(feature));assert place['name']=='Bethany' and place['modern_states']==['Israel'] and not verses
    noise={'type':'Feature','geometry':{'type':'Point','coordinates':[35.2,31.7]},'properties':{'id':'z','name':'0RKFH','reference_ids':[],'alternate_names':[]}}
    assert parse_openbible_line(json.dumps(noise)) is None

def test_atlas_storage_search_detail_books(tmp_path:Path):
    db=tmp_path/'atlas.db';init_db(db);a=parse_openbible_line(json.dumps(rich('a1','Jerusalem','35.235,31.778','Matt.21.1')));b=parse_openbible_line(json.dumps(rich('a2','Bethany','35.261,31.771','John.11.18')))
    with session(db) as c:
        result=replace_atlas(c,[a,b]);stats=atlas_stats(c);hits=query_places(c,q='Jerusalem',resolved_only=True);detail=get_place(c,'a1');books=atlas_books(c)
    assert result['place_count']==2 and stats['occurrence_count']==2;assert hits['items'][0]['id']=='a1';assert detail['occurrences'][0]['reference']=='Matthew 21:1';assert {x['book'] for x in books}=={'Matthew','John'}

def test_journey_resolution_prefers_cited_occurrence(tmp_path:Path):
    db=tmp_path/'journey.db';init_db(db);records=[]
    for i,(name,ref,lon) in enumerate([('Nazareth','Luke.4.16','35.303,32.699'),('Cana','John.2.1','35.344,32.746'),('Capernaum','Matt.4.13','35.576,32.881'),('Sea of Galilee','Mark.1.16','35.58,32.82'),('Bethsaida','Mark.8.22','35.63,32.91'),('Caesarea Philippi','Matt.16.13','35.69,33.25'),('Bethany','John.11.18','35.26,31.77'),('Jerusalem','Matt.21.1','35.235,31.778')],1):
        r=rich(f'a{i}',name,lon,ref);r['verses'][0]['readable']=ref.replace('.', ' ',1).replace('.',':');records.append(parse_openbible_line(json.dumps(r)))
    with session(db) as c:replace_atlas(c,records);j=journey_detail(c,'jesus-galilee')
    assert len(j['stops'])==8 and not j['unresolved'] and j['straight_line_total_km']>0
