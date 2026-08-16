from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator

from .books import BOOK_ORDER, normalize_book

OPENBIBLE_URL = "https://github.com/openbibleinfo/Bible-Geocoding-Data"
OPENBIBLE_LICENSE = "CC BY 4.0"

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS atlas_places (
  id TEXT PRIMARY KEY,
  friendly_id TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  preceding_article TEXT NOT NULL DEFAULT '',
  place_type TEXT NOT NULL DEFAULT '',
  detailed_type TEXT NOT NULL DEFAULT '',
  aliases_json TEXT NOT NULL DEFAULT '[]',
  latitude REAL,
  longitude REAL,
  geometry_json TEXT NOT NULL DEFAULT '',
  modern_states_json TEXT NOT NULL DEFAULT '[]',
  confidence REAL,
  confidence_label TEXT NOT NULL DEFAULT '',
  identification_summary_json TEXT NOT NULL DEFAULT '[]',
  linked_data_json TEXT NOT NULL DEFAULT '{}',
  comment TEXT NOT NULL DEFAULT '',
  source_format TEXT NOT NULL DEFAULT '',
  source_label TEXT NOT NULL DEFAULT 'OpenBible.info Bible Geocoding Data',
  source_url TEXT NOT NULL DEFAULT 'https://github.com/openbibleinfo/Bible-Geocoding-Data',
  license TEXT NOT NULL DEFAULT 'CC BY 4.0',
  verse_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS atlas_places_name_idx ON atlas_places(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS atlas_places_type_idx ON atlas_places(place_type,detailed_type);
CREATE INDEX IF NOT EXISTS atlas_places_coords_idx ON atlas_places(latitude,longitude);
CREATE VIRTUAL TABLE IF NOT EXISTS atlas_places_fts USING fts5(
  place_id UNINDEXED, name, friendly_id, aliases, tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS atlas_occurrences (
  id INTEGER PRIMARY KEY,
  place_id TEXT NOT NULL REFERENCES atlas_places(id) ON DELETE CASCADE,
  book TEXT NOT NULL,
  book_order INTEGER NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  reference TEXT NOT NULL,
  osis TEXT NOT NULL DEFAULT '',
  translations_json TEXT NOT NULL DEFAULT '[]',
  instance_types_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(place_id,book,chapter,verse)
);
CREATE INDEX IF NOT EXISTS atlas_occ_ref_idx ON atlas_occurrences(book,chapter,verse);
CREATE INDEX IF NOT EXISTS atlas_occ_place_idx ON atlas_occurrences(place_id,book_order,chapter,verse);
'''


def ensure_atlas_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _clean_markup(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(text))).strip()


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lonlat(value) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    if isinstance(value, str):
        parts = value.split(",")
        if len(parts) >= 2:
            lon, lat = _float(parts[0]), _float(parts[1])
            return lat, lon
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        lon, lat = _float(value[0]), _float(value[1])
        return lat, lon
    return None, None


def _geometry_center(geometry: dict | None) -> tuple[float | None, float | None]:
    if not isinstance(geometry, dict):
        return None, None
    coords = geometry.get("coordinates")
    if geometry.get("type") == "Point":
        return _lonlat(coords)
    points: list[tuple[float, float]] = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
                points.append((float(node[0]), float(node[1])))
            else:
                for item in node:
                    walk(item)
    walk(coords)
    if not points:
        return None, None
    west = min(x for x, _ in points); east = max(x for x, _ in points)
    south = min(y for _, y in points); north = max(y for _, y in points)
    return (south + north) / 2, (west + east) / 2


def _normalize_confidence(raw) -> float | None:
    value = _float(raw)
    if value is None:
        return None
    if value > 1:
        value = value / 1000.0 if value <= 1000 else value / 10000.0
    return max(0.0, min(1.0, value))


def _confidence_label(value: float | None) -> str:
    if value is None: return "source-reported"
    if value >= .65: return "higher"
    if value >= .30: return "moderate"
    return "lower"


def _verse_row(place_id: str, verse: dict) -> dict | None:
    readable = str(verse.get("readable") or verse.get("reference") or "").strip()
    osis = str(verse.get("osis") or verse.get("usx") or "").strip()
    book = chapter = number = None
    if osis:
        m = re.match(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$", osis.replace(" ", ""))
        if m:
            book = normalize_book(m.group(1)); chapter, number = int(m.group(2)), int(m.group(3))
    if not book and readable:
        m = re.match(r"^(.+?)\s+(\d+):(\d+)", readable)
        if m:
            book = normalize_book(m.group(1)); chapter, number = int(m.group(2)), int(m.group(3))
    if not book or chapter is None or number is None or book not in BOOK_ORDER:
        return None
    return {"place_id":place_id,"book":book,"book_order":BOOK_ORDER[book],"chapter":chapter,"verse":number,
            "reference":readable or f"{book} {chapter}:{number}","osis":osis,
            "translations":verse.get("translations") or [],"instance_types":verse.get("instance_types") or {}}


def _rich_record(obj: dict) -> tuple[dict, list[dict]] | None:
    place_id = str(obj.get("id") or "").strip(); name = str(obj.get("friendly_id") or obj.get("name") or "").strip()
    if not place_id or not name: return None
    aliases = []
    counts = obj.get("translation_name_counts") or {}
    if isinstance(counts, dict): aliases.extend(str(x) for x in counts if x)
    for item in obj.get("names") or []:
        if isinstance(item, dict) and item.get("name"): aliases.append(str(item["name"]))
        elif isinstance(item, str): aliases.append(item)
    aliases = list(dict.fromkeys(x for x in aliases if x and x.casefold()!=name.casefold()))
    candidates=[]
    for i, ident in enumerate(obj.get("identifications") or []):
        if not isinstance(ident, dict): continue
        score=ident.get("score"); ident_score=(score.get("time_total") or score.get("total") or score.get("score")) if isinstance(score,dict) else score
        for j,res in enumerate(ident.get("resolutions") or []):
            if not isinstance(res,dict): continue
            lat,lon=_lonlat(res.get("lonlat"))
            if lat is None: lat,lon=_geometry_center(res.get("geometry"))
            if lat is None or lon is None: continue
            time_score=_float(res.get("best_time_score")); path_score=_float(res.get("best_path_score")); raw_score=_float(ident_score)
            rank=raw_score*(time_score/1000.0) if raw_score is not None and time_score is not None else (raw_score if raw_score is not None else (time_score or path_score or 0.0))
            candidates.append({"identification_index":i,"resolution_index":j,"lat":lat,"lon":lon,"rank":rank,
                               "type":res.get("type") or ident.get("type") or "","description":_clean_markup(res.get("description") or ident.get("description") or ""),
                               "modern_basis_id":res.get("modern_basis_id") or ""})
    candidates.sort(key=lambda x:x["rank"],reverse=True); best=candidates[0] if candidates else None
    lat=_float(obj.get("latitude")); lon=_float(obj.get("longitude"))
    if lat is None or lon is None:
        dlat,dlon=_lonlat(obj.get("lonlat")); lat=lat if lat is not None else dlat; lon=lon if lon is not None else dlon
    if (lat is None or lon is None) and best: lat,lon=best["lat"],best["lon"]
    geometry=obj.get("geometry") if isinstance(obj.get("geometry"),dict) else None
    confidence=_normalize_confidence(best.get("rank") if best else None)
    verses=[x for x in (_verse_row(place_id,v) for v in obj.get("verses") or []) if x]
    return ({"id":place_id,"friendly_id":str(obj.get("friendly_id") or name),"name":name,"preceding_article":str(obj.get("preceding_article") or ""),
             "place_type":str(obj.get("type") or ""),"detailed_type":str(obj.get("class") or ""),"aliases":aliases,"latitude":lat,"longitude":lon,
             "geometry":geometry,"modern_states":[],"confidence":confidence,"confidence_label":_confidence_label(confidence),"identification_summary":candidates[:8],
             "linked_data":obj.get("linked_data") or {},"comment":_clean_markup(obj.get("comment") or ""),"source_format":"openbible-rich","verse_count":len(verses)},verses)


def _feature_record(obj: dict) -> tuple[dict, list[dict]] | None:
    props=obj.get("properties") if isinstance(obj.get("properties"),dict) else {}
    place_id=str(props.get("id") or obj.get("id") or "").strip(); name=str(props.get("friendly_id") or props.get("name") or "").strip()
    if not place_id or not name:return None
    refs=props.get("ancient_reference_ids") or props.get("reference_ids") or []; aliases=props.get("alternate_names") or []
    if not refs and not aliases and re.fullmatch(r"[0-9A-Z]{4,}",name):return None
    geometry=obj.get("geometry") if isinstance(obj.get("geometry"),dict) else None; lat,lon=_geometry_center(geometry)
    aliases=[x.get("name") if isinstance(x,dict) else str(x) for x in aliases]
    return ({"id":place_id,"friendly_id":str(props.get("friendly_id") or name),"name":name,"preceding_article":str(props.get("preceding_article") or ""),
             "place_type":str(props.get("type") or props.get("class") or ""),"detailed_type":str(props.get("detailed_type") or ""),"aliases":[x for x in aliases if x],
             "latitude":lat,"longitude":lon,"geometry":geometry,"modern_states":props.get("inside_modern_states") or [],"confidence":None,
             "confidence_label":"source-reported","identification_summary":[],"linked_data":{},"comment":_clean_markup(props.get("comment") or ""),
             "source_format":"openbible-feature","verse_count":0},[])


def parse_openbible_line(line: str) -> tuple[dict, list[dict]] | None:
    obj=json.loads(line)
    return _feature_record(obj) if obj.get("type")=="Feature" and isinstance(obj.get("properties"),dict) else _rich_record(obj)


def iter_openbible(path: Path) -> Iterator[tuple[dict, list[dict]]]:
    with path.open(encoding="utf-8-sig") as handle:
        for line_no,line in enumerate(handle,1):
            if not line.strip():continue
            try:parsed=parse_openbible_line(line)
            except Exception as exc:raise ValueError(f"Atlas source parse failed at line {line_no}: {exc}") from exc
            if parsed:yield parsed


def replace_atlas(conn: sqlite3.Connection, records: Iterable[tuple[dict, list[dict]]]) -> dict:
    ensure_atlas_schema(conn);conn.execute("DELETE FROM atlas_occurrences");conn.execute("DELETE FROM atlas_places_fts");conn.execute("DELETE FROM atlas_places")
    place_sql=("INSERT INTO atlas_places(id,friendly_id,name,preceding_article,place_type,detailed_type,aliases_json,latitude,longitude,geometry_json,modern_states_json,"
               "confidence,confidence_label,identification_summary_json,linked_data_json,comment,source_format,source_label,source_url,license,verse_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    occ_sql=("INSERT OR IGNORE INTO atlas_occurrences(place_id,book,book_order,chapter,verse,reference,osis,translations_json,instance_types_json) VALUES(?,?,?,?,?,?,?,?,?)")
    places=occurrences=resolved=0;formats={}
    for place,verses in records:
        conn.execute(place_sql,(place["id"],place.get("friendly_id",""),place["name"],place.get("preceding_article",""),place.get("place_type",""),place.get("detailed_type",""),
            _json(place.get("aliases",[])),place.get("latitude"),place.get("longitude"),_json(place.get("geometry")) if place.get("geometry") else "",_json(place.get("modern_states",[])),
            place.get("confidence"),place.get("confidence_label",""),_json(place.get("identification_summary",[])),_json(place.get("linked_data",{})),place.get("comment",""),
            place.get("source_format",""),"OpenBible.info Bible Geocoding Data",OPENBIBLE_URL,OPENBIBLE_LICENSE,int(place.get("verse_count",len(verses)))))
        conn.execute("INSERT INTO atlas_places_fts(place_id,name,friendly_id,aliases) VALUES(?,?,?,?)",(place["id"],place["name"],place.get("friendly_id",""),_json(place.get("aliases",[]))))
        places+=1;resolved+=int(place.get("latitude") is not None and place.get("longitude") is not None);formats[place.get("source_format","unknown")]=formats.get(place.get("source_format","unknown"),0)+1
        for row in verses:
            conn.execute(occ_sql,(row["place_id"],row["book"],row["book_order"],row["chapter"],row["verse"],row["reference"],row["osis"],_json(row.get("translations",[])),_json(row.get("instance_types",{}))));occurrences+=1
    return {"place_count":places,"resolved_count":resolved,"occurrence_count":occurrences,"formats":formats}


def atlas_stats(conn: sqlite3.Connection) -> dict:
    ensure_atlas_schema(conn);row=conn.execute("SELECT COUNT(*) place_count,SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END) resolved_count,SUM(verse_count) source_verse_count FROM atlas_places").fetchone()
    occurrence_count=int(conn.execute("SELECT COUNT(*) n FROM atlas_occurrences").fetchone()["n"]);type_count=int(conn.execute("SELECT COUNT(DISTINCT COALESCE(NULLIF(detailed_type,''),place_type)) n FROM atlas_places").fetchone()["n"])
    return {"ready":int(row["place_count"] or 0)>=250 and int(row["resolved_count"] or 0)>=150,"place_count":int(row["place_count"] or 0),"resolved_count":int(row["resolved_count"] or 0),
            "occurrence_count":occurrence_count,"source_verse_count":int(row["source_verse_count"] or 0),"type_count":type_count,"country_count":len(atlas_countries(conn)),
            "source":"OpenBible.info Bible Geocoding Data","license":OPENBIBLE_LICENSE,"source_url":OPENBIBLE_URL}


def _decode_place(row: sqlite3.Row,include_geometry: bool=False) -> dict:
    d=dict(row)
    for field,default in (("aliases_json",[]),("modern_states_json",[]),("identification_summary_json",[]),("linked_data_json",{})):
        raw=d.pop(field,"")
        try:d[field.removesuffix("_json")]=json.loads(raw) if raw else default
        except json.JSONDecodeError:d[field.removesuffix("_json")]=default
    raw=d.pop("geometry_json","")
    if include_geometry:
        try:d["geometry"]=json.loads(raw) if raw else None
        except json.JSONDecodeError:d["geometry"]=None
    d["resolved"]=d.get("latitude") is not None and d.get("longitude") is not None
    return d


def _search_term(q:str)->str:
    tokens=re.findall(r"[\w'’-]+",q,flags=re.UNICODE)
    return " ".join(f'"{token.replace(chr(34),"")}"' for token in tokens if token)[:300]


def query_places(conn: sqlite3.Connection,*,q:str="",book:str="",place_type:str="",country:str="",west:float|None=None,south:float|None=None,east:float|None=None,north:float|None=None,resolved_only:bool=True,limit:int=250,offset:int=0)->dict:
    ensure_atlas_schema(conn);clauses=[];args=[];join=""
    if q.strip():
        term=_search_term(q)
        if term:join+=" JOIN atlas_places_fts f ON f.place_id=p.id ";clauses.append("f.atlas_places_fts MATCH ?");args.append(term)
    if book:
        normalized=normalize_book(book)
        if normalized:join+=" JOIN atlas_occurrences o ON o.place_id=p.id ";clauses.append("o.book=?");args.append(normalized)
    if place_type:clauses.append("(lower(p.place_type)=lower(?) OR lower(p.detailed_type)=lower(?))");args.extend([place_type,place_type])
    if country:clauses.append("lower(p.modern_states_json) LIKE ?");args.append(f'%"{country.lower()}"%')
    if resolved_only:clauses.append("p.latitude IS NOT NULL AND p.longitude IS NOT NULL")
    if None not in (west,south,east,north):clauses.extend(["p.longitude BETWEEN ? AND ?","p.latitude BETWEEN ? AND ?"]);args.extend([west,east,south,north])
    where=" WHERE "+" AND ".join(clauses) if clauses else "";total=int(conn.execute("SELECT COUNT(DISTINCT p.id) n FROM atlas_places p"+join+where,args).fetchone()["n"])
    rows=conn.execute("SELECT DISTINCT p.* FROM atlas_places p"+join+where+" ORDER BY CASE WHEN p.verse_count>0 THEN 0 ELSE 1 END,p.verse_count DESC,p.name COLLATE NOCASE LIMIT ? OFFSET ?",args+[max(1,min(limit,1000)),max(0,offset)]).fetchall()
    return {"items":[_decode_place(r) for r in rows],"total":total,"limit":limit,"offset":offset}


def get_place(conn: sqlite3.Connection,place_id:str,occurrence_limit:int=250)->dict:
    ensure_atlas_schema(conn);row=conn.execute("SELECT * FROM atlas_places WHERE id=?",(place_id,)).fetchone()
    if not row:raise KeyError(place_id)
    place=_decode_place(row,True);occ=[dict(r) for r in conn.execute("SELECT book,chapter,verse,reference,osis,translations_json,instance_types_json FROM atlas_occurrences WHERE place_id=? ORDER BY book_order,chapter,verse LIMIT ?",(place_id,occurrence_limit)).fetchall()]
    for item in occ:
        for field in ("translations_json","instance_types_json"):
            raw=item.pop(field,"")
            try:item[field.removesuffix("_json")]=json.loads(raw) if raw else ([] if field.startswith("translations") else {})
            except json.JSONDecodeError:item[field.removesuffix("_json")]=[] if field.startswith("translations") else {}
    place["occurrences"]=occ;place["books"]=[dict(r) for r in conn.execute("SELECT book,COUNT(*) count FROM atlas_occurrences WHERE place_id=? GROUP BY book ORDER BY MIN(book_order)",(place_id,)).fetchall()]
    return place


def atlas_types(conn:sqlite3.Connection)->list[dict]:
    ensure_atlas_schema(conn);return [dict(r) for r in conn.execute("SELECT COALESCE(NULLIF(detailed_type,''),NULLIF(place_type,''),'other') type,COUNT(*) count FROM atlas_places GROUP BY type ORDER BY count DESC,type").fetchall()]

def atlas_books(conn:sqlite3.Connection)->list[dict]:
    ensure_atlas_schema(conn);return [dict(r) for r in conn.execute("SELECT book,COUNT(DISTINCT place_id) places,COUNT(*) occurrences FROM atlas_occurrences GROUP BY book ORDER BY MIN(book_order)").fetchall()]

def atlas_countries(conn:sqlite3.Connection)->list[dict]:
    ensure_atlas_schema(conn);counts={}
    for row in conn.execute("SELECT modern_states_json FROM atlas_places WHERE modern_states_json<>'[]'").fetchall():
        try:values=json.loads(row["modern_states_json"])
        except json.JSONDecodeError:continue
        for value in values:
            value=str(value).strip()
            if value:counts[value]=counts.get(value,0)+1
    return [{"country":k,"count":v} for k,v in sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))]


def distance_km(lat1:float,lon1:float,lat2:float,lon2:float)->float:
    r=6371.0088;p1,p2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dlambda=math.radians(lon2-lon1);a=math.sin(dphi/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dlambda/2)**2
    return r*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

def nearby(conn:sqlite3.Connection,lat:float,lon:float,radius_km:float=50,limit:int=30,exclude_id:str="")->list[dict]:
    ensure_atlas_schema(conn);lat_delta=radius_km/111.0;lon_delta=radius_km/max(20.0,111.0*math.cos(math.radians(lat)));rows=conn.execute("SELECT * FROM atlas_places WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? AND id<>?",(lat-lat_delta,lat+lat_delta,lon-lon_delta,lon+lon_delta,exclude_id)).fetchall();items=[]
    for row in rows:
        d=_decode_place(row);d["distance_km"]=round(distance_km(lat,lon,d["latitude"],d["longitude"]),2)
        if d["distance_km"]<=radius_km:items.append(d)
    return sorted(items,key=lambda x:x["distance_km"])[:max(1,min(limit,100))]

JOURNEYS=[
{"id":"abraham","name":"Abraham: Ur to Canaan","category":"patriarchs","notice":"Stop-sequence visualization based on the cited Genesis narrative; straight map segments are not reconstructed roads.","stops":[("Ur","Genesis 11:31"),("Haran","Genesis 11:31"),("Shechem","Genesis 12:6"),("Bethel","Genesis 12:8"),("Hebron","Genesis 13:18"),("Beersheba","Genesis 21:33")]},
{"id":"exodus","name":"Exodus: Egypt to Sinai","category":"exodus","notice":"Several Exodus locations remain debated. Unresolved or ambiguous stops are surfaced rather than silently assigned coordinates.","stops":[("Rameses","Exodus 12:37"),("Succoth","Exodus 12:37"),("Etham","Exodus 13:20"),("Pi-hahiroth","Exodus 14:2"),("Marah","Exodus 15:23"),("Elim","Exodus 15:27"),("Rephidim","Exodus 17:1"),("Sinai","Exodus 19:1")]},
{"id":"jesus-galilee","name":"Jesus: Galilee to Jerusalem","category":"gospels","notice":"Selected narrative locations, not a claim that the Gospels present one continuous itinerary in this exact sequence.","stops":[("Nazareth","Luke 4:16"),("Cana","John 2:1"),("Capernaum","Matthew 4:13"),("Sea of Galilee","Mark 1:16"),("Bethsaida","Mark 8:22"),("Caesarea Philippi","Matthew 16:13"),("Bethany","John 11:18"),("Jerusalem","Matthew 21:1")]},
{"id":"paul-1","name":"Paul: First Missionary Journey","category":"acts","notice":"Ordered Acts stops. Map segments connect stops for orientation; they are not reconstructed ancient road or sea tracks.","stops":[("Antioch","Acts 13:1"),("Seleucia","Acts 13:4"),("Salamis","Acts 13:5"),("Paphos","Acts 13:6"),("Perga","Acts 13:13"),("Pisidian Antioch","Acts 13:14"),("Iconium","Acts 13:51"),("Lystra","Acts 14:6"),("Derbe","Acts 14:6"),("Attalia","Acts 14:25")]},
{"id":"paul-2","name":"Paul: Second Missionary Journey","category":"acts","notice":"Ordered Acts stops; straight segments are schematic connections between sourced locations.","stops":[("Antioch","Acts 15:35"),("Lystra","Acts 16:1"),("Troas","Acts 16:8"),("Philippi","Acts 16:12"),("Thessalonica","Acts 17:1"),("Berea","Acts 17:10"),("Athens","Acts 17:15"),("Corinth","Acts 18:1"),("Ephesus","Acts 18:19"),("Caesarea","Acts 18:22")]},
{"id":"rome","name":"Paul: Voyage to Rome","category":"acts","notice":"Acts 27–28 stop sequence. Sea segments indicate narrative progression only, not a reconstructed sailing track.","stops":[("Caesarea","Acts 27:1"),("Sidon","Acts 27:3"),("Myra","Acts 27:5"),("Cnidus","Acts 27:7"),("Fair Havens","Acts 27:8"),("Malta","Acts 28:1"),("Syracuse","Acts 28:12"),("Rhegium","Acts 28:13"),("Puteoli","Acts 28:13"),("Rome","Acts 28:16")]}
]

def _resolve_stop(conn:sqlite3.Connection,name:str,reference:str)->dict|None:
    m=re.match(r"^(.+?)\s+(\d+):(\d+)",reference)
    if m:
        book=normalize_book(m.group(1));chapter=int(m.group(2));verse=int(m.group(3))
        if book:
            row=conn.execute("SELECT p.* FROM atlas_places p JOIN atlas_occurrences o ON o.place_id=p.id WHERE o.book=? AND o.chapter=? AND o.verse=? AND (lower(p.name)=lower(?) OR lower(p.friendly_id)=lower(?) OR lower(p.aliases_json) LIKE ?) AND p.latitude IS NOT NULL ORDER BY p.confidence DESC NULLS LAST LIMIT 1",(book,chapter,verse,name,name,f'%"{name.lower()}"%')).fetchone()
            if row:return _decode_place(row)
    rows=conn.execute("SELECT * FROM atlas_places WHERE (lower(name)=lower(?) OR lower(friendly_id)=lower(?) OR lower(aliases_json) LIKE ?) AND latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY verse_count DESC,confidence DESC NULLS LAST LIMIT 5",(name,name,f'%"{name.lower()}"%')).fetchall()
    return _decode_place(rows[0]) if rows else None

def journey_catalog(conn:sqlite3.Connection)->list[dict]:
    out=[]
    for journey in JOURNEYS:
        resolved=sum(1 for name,ref in journey["stops"] if _resolve_stop(conn,name,ref));out.append({**{k:v for k,v in journey.items() if k!="stops"},"stop_count":len(journey["stops"]),"resolved_count":resolved})
    return out

def journey_detail(conn:sqlite3.Connection,journey_id:str)->dict:
    journey=next((x for x in JOURNEYS if x["id"]==journey_id),None)
    if not journey:raise KeyError(journey_id)
    stops=[];unresolved=[];total=0.0;previous=None
    for ordinal,(name,reference) in enumerate(journey["stops"],1):
        place=_resolve_stop(conn,name,reference)
        if not place:unresolved.append({"ordinal":ordinal,"name":name,"reference":reference});continue
        stop={"ordinal":ordinal,"name":name,"reference":reference,"place_id":place["id"],"resolved_name":place["name"],"latitude":place["latitude"],"longitude":place["longitude"],"confidence":place.get("confidence"),"confidence_label":place.get("confidence_label")}
        if previous:
            segment=distance_km(previous["latitude"],previous["longitude"],stop["latitude"],stop["longitude"]);stop["straight_line_from_previous_km"]=round(segment,1);total+=segment
        stops.append(stop);previous=stop
    return {**{k:v for k,v in journey.items() if k!="stops"},"stops":stops,"unresolved":unresolved,"straight_line_total_km":round(total,1)}
