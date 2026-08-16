from __future__ import annotations

import json,re,uuid
from datetime import datetime,timezone
from pathlib import Path

# Organizational chronology only. Ranges are intentionally broad where dating is disputed.
BASE_EVENTS=[
{'id':'patriarchal-world','title':'Patriarchal narratives','start':-2000,'end':-1600,'type':'biblical_setting','label':'Broad 2nd-millennium setting','certainty':'model','refs':['Genesis 12–50']},
{'id':'exodus-wilderness','title':'Exodus / wilderness narratives','start':-1500,'end':-1200,'type':'biblical_setting','label':'Date debated; broad Late Bronze / early Iron framing','certainty':'contested','refs':['Exodus','Numbers','Deuteronomy']},
{'id':'judges-setting','title':'Judges / early settlement setting','start':-1200,'end':-1020,'type':'biblical_setting','label':'Early Iron Age framing','certainty':'approximate','refs':['Joshua','Judges']},
{'id':'united-monarchy','title':'United monarchy','start':-1020,'end':-930,'type':'political','label':'Saul–David–Solomon era, conventional chronology','certainty':'approximate','refs':['1 Samuel','2 Samuel','1 Kings 1–11']},
{'id':'divided-monarchy','title':'Divided monarchies','start':-930,'end':-722,'type':'political','label':'Israel and Judah before fall of Samaria','certainty':'approximate','refs':['1 Kings 12–22','2 Kings']},
{'id':'assyrian-crisis','title':'Assyrian imperial crisis','start':-745,'end':-701,'type':'empire','label':'8th-century BCE Assyrian expansion','certainty':'historical','refs':['2 Kings 15–19','Isaiah 1–39']},
{'id':'fall-samaria','title':'Fall of Samaria','start':-722,'end':-722,'type':'event','label':'722/721 BCE','certainty':'historical','refs':['2 Kings 17']},
{'id':'josiah-reform','title':'Josianic reform era','start':-640,'end':-609,'type':'political','label':'Late 7th century BCE','certainty':'historical','refs':['2 Kings 22–23']},
{'id':'babylonian-crisis','title':'Babylonian conquest / exile','start':-605,'end':-539,'type':'empire','label':'Early 6th century BCE','certainty':'historical','refs':['2 Kings 24–25','Jeremiah','Ezekiel']},
{'id':'jerusalem-destruction','title':'Destruction of First Temple','start':-586,'end':-586,'type':'event','label':'587/586 BCE','certainty':'historical','refs':['2 Kings 25','Lamentations']},
{'id':'persian-period','title':'Persian period / restoration','start':-539,'end':-332,'type':'empire','label':'539–332 BCE','certainty':'historical','refs':['Ezra','Nehemiah','Haggai','Zechariah']},
{'id':'second-temple-dedication','title':'Second Temple completed','start':-516,'end':-515,'type':'event','label':'516/515 BCE','certainty':'historical','refs':['Ezra 6']},
{'id':'hellenistic-period','title':'Hellenistic period','start':-332,'end':-167,'type':'empire','label':'Alexander through Seleucid crisis','certainty':'historical','refs':['Daniel','Letter of Aristeas']},
{'id':'enochic-literature','title':'Major Enochic composition strata','start':-300,'end':-50,'type':'literature','label':'Multiple strata; broad scholarly range','certainty':'contested','refs':['1 Enoch']},
{'id':'maccabean-crisis','title':'Maccabean revolt','start':-167,'end':-160,'type':'event','label':'167–160 BCE','certainty':'historical','refs':['1 Maccabees','2 Maccabees']},
{'id':'hasmonean','title':'Hasmonean era','start':-140,'end':-63,'type':'political','label':'2nd–1st centuries BCE','certainty':'historical','refs':['1 Maccabees']},
{'id':'roman-judea','title':'Roman domination of Judea','start':-63,'end':70,'type':'empire','label':'63 BCE onward; Second Temple destroyed 70 CE','certainty':'historical','refs':['Gospels','Acts']},
{'id':'herod-great','title':'Herod the Great','start':-37,'end':-4,'type':'ruler','label':'37–4 BCE','certainty':'historical','refs':['Matthew 2','Luke 1']},
{'id':'jesus-ministry','title':'Public ministry of Jesus','start':27,'end':33,'type':'biblical_setting','label':'Approx. late 20s–early 30s CE','certainty':'approximate','refs':['Matthew','Mark','Luke','John']},
{'id':'early-church','title':'Earliest Jerusalem church / apostolic mission','start':30,'end':50,'type':'biblical_setting','label':'30s–40s CE','certainty':'approximate','refs':['Acts 1–15']},
{'id':'pauline-missions','title':'Pauline mission and letters','start':46,'end':67,'type':'biblical_setting','label':'Mid-1st century CE','certainty':'approximate','refs':['Acts 13–28','Pauline Epistles']},
{'id':'jewish-war','title':'First Jewish–Roman War','start':66,'end':73,'type':'event','label':'66–73 CE','certainty':'historical','refs':[]},
{'id':'second-temple-destruction','title':'Destruction of Second Temple','start':70,'end':70,'type':'event','label':'70 CE','certainty':'historical','refs':[]},
{'id':'late-first-century','title':'Late first-century Christian/Jewish literary world','start':70,'end':100,'type':'literature','label':'Broad organizational window','certainty':'model','refs':['Revelation','Johannine literature']},
]
ID_RE=re.compile(r'^[a-z0-9][a-z0-9-]{5,80}$')
def catalog():return BASE_EVENTS
def filter_events(start:int=-2100,end:int=150,types:list[str]|None=None):return [e for e in BASE_EVENTS if e['end']>=start and e['start']<=end and (not types or e['type'] in types)]
def _path(root:Path,pid:str)->Path:
    if not ID_RE.fullmatch(pid):raise ValueError('Invalid study project ID.')
    p=root/pid
    if not p.exists():raise FileNotFoundError('Study not found.')
    return p/'timeline-events.json'
def study_events(root:Path,pid:str)->list[dict]:
    try:return json.loads(_path(root,pid).read_text(encoding='utf-8')).get('events',[])
    except FileNotFoundError:return []
def add_study_event(root:Path,pid:str,title:str,start:int,end:int|None=None,note:str='',citations:list[str]|None=None)->dict:
    p=_path(root,pid);events=study_events(root,pid);e={'id':uuid.uuid4().hex[:10],'title':title.strip(),'start':int(start),'end':int(end if end is not None else start),'type':'study','label':note.strip(),'certainty':'user','refs':citations or [],'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds')};events.append(e);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps({'events':events},indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(p);return e
