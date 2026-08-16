from __future__ import annotations

import json,re,uuid
from datetime import datetime,timezone
from pathlib import Path

ID_RE=re.compile(r'^[a-z0-9][a-z0-9-]{5,80}$')
NODE_TYPES={'thesis','position','claim','evidence','objection','assumption','question','conclusion'}
EDGE_TYPES={'supports','challenges','depends_on','answers','qualifies','derived_from','competes_with'}

def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _p(root:Path,pid:str)->Path:
    if not ID_RE.fullmatch(pid):raise ValueError('Invalid study project ID.')
    p=root/pid
    if not p.exists():raise FileNotFoundError(f'Study not found: {pid}')
    return p/'argument-maps.json'
def _load(path:Path)->dict:
    try:return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return {'maps':[]}
def _save(path:Path,d:dict):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
def list_maps(root:Path,pid:str)->list[dict]:return _load(_p(root,pid))['maps']
def get_map(root:Path,pid:str,map_id:str)->dict:
    for m in list_maps(root,pid):
        if m['id']==map_id:return m
    raise FileNotFoundError(f'Argument map not found: {map_id}')
def create_map(root:Path,pid:str,title:str,thesis:str)->dict:
    path=_p(root,pid);d=_load(path);mid=uuid.uuid4().hex[:10];nid=uuid.uuid4().hex[:10];now=_now()
    m={'id':mid,'title':title.strip() or 'Untitled argument','created_at':now,'updated_at':now,'nodes':[{'id':nid,'type':'thesis','text':thesis.strip(),'authority':'analysis','confidence':None,'citations':[]}],'edges':[]}
    d['maps'].append(m);_save(path,d);return m
def add_node(root:Path,pid:str,map_id:str,node_type:str,text:str,authority:str='analysis',confidence:float|None=None,citations:list[str]|None=None)->dict:
    if node_type not in NODE_TYPES:raise ValueError('Invalid argument node type.')
    path=_p(root,pid);d=_load(path);m=next((x for x in d['maps'] if x['id']==map_id),None)
    if not m:raise FileNotFoundError('Argument map not found.')
    n={'id':uuid.uuid4().hex[:10],'type':node_type,'text':text.strip(),'authority':authority,'confidence':None if confidence is None else max(0,min(1,float(confidence))),'citations':citations or []}
    m['nodes'].append(n);m['updated_at']=_now();_save(path,d);return n
def add_edge(root:Path,pid:str,map_id:str,source:str,target:str,edge_type:str)->dict:
    if edge_type not in EDGE_TYPES:raise ValueError('Invalid argument edge type.')
    path=_p(root,pid);d=_load(path);m=next((x for x in d['maps'] if x['id']==map_id),None)
    if not m:raise FileNotFoundError('Argument map not found.')
    ids={n['id'] for n in m['nodes']}
    if source not in ids or target not in ids:raise ValueError('Argument edge references an unknown node.')
    e={'id':uuid.uuid4().hex[:10],'source':source,'target':target,'type':edge_type};m['edges'].append(e);m['updated_at']=_now();_save(path,d);return e
def delete_node(root:Path,pid:str,map_id:str,node_id:str)->bool:
    path=_p(root,pid);d=_load(path);m=next((x for x in d['maps'] if x['id']==map_id),None)
    if not m:return False
    before=len(m['nodes']);m['nodes']=[n for n in m['nodes'] if n['id']!=node_id];m['edges']=[e for e in m['edges'] if e['source']!=node_id and e['target']!=node_id];m['updated_at']=_now();_save(path,d);return len(m['nodes'])<before
def delete_map(root:Path,pid:str,map_id:str)->bool:
    path=_p(root,pid);d=_load(path);before=len(d['maps']);d['maps']=[m for m in d['maps'] if m['id']!=map_id];_save(path,d);return len(d['maps'])<before
