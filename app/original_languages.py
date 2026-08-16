from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class OriginalWord:
    id: int
    language: str
    source: str
    book: str
    chapter: int
    verse: int
    position: int
    surface: str
    normalized: str
    lemma: str
    strongs: str
    morph: str
    transliteration: str


GREEK_MAP = {
    "α":"a","β":"b","γ":"g","δ":"d","ε":"e","ζ":"z","η":"ē","θ":"th","ι":"i","κ":"k","λ":"l","μ":"m",
    "ν":"n","ξ":"x","ο":"o","π":"p","ρ":"r","σ":"s","ς":"s","τ":"t","υ":"y","φ":"ph","χ":"ch","ψ":"ps","ω":"ō",
}
HEBREW_MAP = {
    "א":"ʾ","ב":"b","ג":"g","ד":"d","ה":"h","ו":"w","ז":"z","ח":"ḥ","ט":"ṭ","י":"y","כ":"k","ך":"k",
    "ל":"l","מ":"m","ם":"m","נ":"n","ן":"n","ס":"s","ע":"ʿ","פ":"p","ף":"p","צ":"ṣ","ץ":"ṣ","ק":"q","ר":"r","ש":"š","ת":"t",
}


def strip_marks(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def transliterate(text: str, language: str) -> str:
    bare = strip_marks(text).lower()
    mapping = GREEK_MAP if language == "greek" else HEBREW_MAP
    return "".join(mapping.get(ch, ch) for ch in bare)


def decode_greek_morph(code: str) -> str:
    # unfoldingWord morphology example: Gr,V,IAA3,,S or Gr,N,,,,,NMS,
    bits = [x.strip() for x in code.split(",")]
    if not bits or not code.startswith("Gr"):
        return code
    pos = {
        "N":"noun","V":"verb","AA":"adjective","AR":"adjective","EA":"article","RD":"demonstrative pronoun",
        "RI":"interrogative/indefinite pronoun","RP":"personal pronoun","RR":"relative pronoun","P":"preposition",
        "CC":"conjunction","D":"adverb","EN":"numeral","I":"interjection","PI":"preposition/idiom",
    }.get(bits[1] if len(bits) > 1 else "", bits[1] if len(bits) > 1 else "")
    details: list[str] = [pos] if pos else []
    compact = "".join(bits[2:])
    tense = {"P":"present","I":"imperfect","F":"future","A":"aorist","X":"perfect","Y":"pluperfect"}
    voice = {"A":"active","M":"middle","P":"passive"}
    mood = {"I":"indicative","D":"imperative","S":"subjunctive","O":"optative","N":"infinitive","P":"participle"}
    case = {"N":"nominative","G":"genitive","D":"dative","A":"accusative","V":"vocative"}
    number = {"S":"singular","P":"plural"}
    gender = {"M":"masculine","F":"feminine","N":"neuter"}
    if bits[1:2] == ["V"] and len(compact) >= 3:
        if compact[0] in tense: details.append(tense[compact[0]])
        if compact[1] in voice: details.append(voice[compact[1]])
        if compact[2] in mood: details.append(mood[compact[2]])
    tail = compact[-3:]
    if len(tail) == 3 and tail[0] in case and tail[1] in gender and tail[2] in number:
        details.extend([case[tail[0]], gender[tail[1]], number[tail[2]]])
    return ", ".join(dict.fromkeys(x for x in details if x)) or code


def decode_hebrew_morph(code: str) -> str:
    # Keep the raw code visible but decode the high-value POS prefix safely.
    if not code.startswith("He") and not code.startswith("Ar"):
        return code
    body = code.split(",", 1)[1] if "," in code else code[2:].lstrip("/")
    first = body.split("/")[-1] if "/" in body else body
    pos_code = first[:1]
    pos = {
        "N":"noun","V":"verb","A":"adjective","P":"pronoun","R":"preposition","C":"conjunction","D":"adverb",
        "T":"particle","S":"suffix","M":"numeral",
    }.get(pos_code, "")
    return f"{pos} · {code}" if pos else code


def morph_description(code: str, language: str) -> str:
    return decode_greek_morph(code) if language == "greek" else decode_hebrew_morph(code)


def language_for_book(book: str) -> str:
    return "greek" if book in {
        "Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians",
        "Philippians","Colossians","1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon",
        "Hebrews","James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
    } else "hebrew"


def verse_words(conn: sqlite3.Connection, book: str, chapter: int, verse: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id,language,source,book,chapter,verse,position,surface,normalized,lemma,strongs,morph,transliteration "
        "FROM original_words WHERE book=? AND chapter=? AND verse=? ORDER BY position",
        (book, chapter, verse),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["morph_description"] = morph_description(d["morph"], d["language"])
        out.append(d)
    return out


def lemma_occurrences(conn: sqlite3.Connection, lemma: str, language: str | None = None, limit: int = 100) -> dict:
    clause = " AND language=?" if language else ""
    params: list[object] = [lemma]
    if language:
        params.append(language)
    total = conn.execute("SELECT COUNT(*) n FROM original_words WHERE lemma=?" + clause, params).fetchone()["n"]
    rows = conn.execute(
        "SELECT id,language,source,book,chapter,verse,position,surface,normalized,lemma,strongs,morph,transliteration "
        "FROM original_words WHERE lemma=?" + clause + " ORDER BY book_order,chapter,verse,position LIMIT ?",
        params + [limit],
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r); d["morph_description"] = morph_description(d["morph"], d["language"]); items.append(d)
    return {"lemma": lemma, "total": int(total), "items": items}


def search_words(conn: sqlite3.Connection, query: str, language: str | None = None, limit: int = 80) -> list[dict]:
    q = query.strip()
    if not q:
        return []
    bare = strip_marks(q)
    like = f"%{q}%"; bare_like = f"%{bare}%"
    clause = " AND language=?" if language else ""
    params: list[object] = [like, like, bare_like, bare_like]
    if language:
        params.append(language)
    rows = conn.execute(
        "SELECT id,language,source,book,chapter,verse,position,surface,normalized,lemma,strongs,morph,transliteration "
        "FROM original_words WHERE (surface LIKE ? OR lemma LIKE ? OR normalized LIKE ? OR transliteration LIKE ?)" + clause +
        " ORDER BY book_order,chapter,verse,position LIMIT ?",
        params + [limit],
    ).fetchall()
    out=[]
    for r in rows:
        d=dict(r); d["morph_description"]=morph_description(d["morph"],d["language"]); out.append(d)
    return out


def lab_stats(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT language,source,COUNT(*) word_count,COUNT(DISTINCT lemma) lemma_count FROM original_words GROUP BY language,source ORDER BY language").fetchall()
    return {"ready": bool(rows), "sources": [dict(r) for r in rows], "total_words": sum(int(r["word_count"]) for r in rows)}


_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
_WORD_RE = re.compile(r'\\w\s+([^|\\]+)\|([^\\]*?)\\w\*')
_ALIGN_RE = re.compile(r'\\zaln-s\s*\|([^\\]*?)\\\*')


def parse_original_usfm(text: str, *, book: str, book_order: int, language: str, source: str) -> list[dict]:
    """Parse original-language USFM3 word/alignment attributes into normalized rows.

    Supports both direct ``\\w`` word fields and unfoldingWord ``\\zaln-s`` milestones.
    Duplicate alignment/word representations are removed by verse position + content.
    """
    chapter = 0
    verse = 0
    positions: dict[tuple[int, int], int] = {}
    seen: set[tuple] = set()
    out: list[dict] = []
    for line in text.splitlines():
        cm = re.match(r"^\\c\s+(\d+)", line)
        if cm:
            chapter = int(cm.group(1)); verse = 0
        vm = re.match(r"^\\v\s+(\d+)", line)
        if vm:
            verse = int(vm.group(1))
        if not chapter or not verse:
            continue
        candidates: list[tuple[str, dict[str, str]]] = []
        for m in _WORD_RE.finditer(line):
            attrs = dict(_ATTR_RE.findall(m.group(2)))
            candidates.append((m.group(1).strip(), attrs))
        for m in _ALIGN_RE.finditer(line):
            attrs = dict(_ATTR_RE.findall(m.group(1)))
            content = attrs.get("x-content", "").strip()
            if content:
                candidates.append((content, attrs))
        for surface, attrs in candidates:
            lemma = attrs.get("x-lemma") or attrs.get("lemma") or ""
            morph = attrs.get("x-morph") or attrs.get("morph") or ""
            strongs = attrs.get("x-strong") or attrs.get("strong") or ""
            key = (chapter, verse, surface, lemma, morph, strongs)
            if key in seen:
                continue
            seen.add(key)
            pv = (chapter, verse); positions[pv] = positions.get(pv, 0) + 1
            normalized = strip_marks(surface).lower()
            out.append({
                "language": language, "source": source, "book": book, "book_order": book_order,
                "chapter": chapter, "verse": verse, "position": positions[pv], "surface": surface,
                "normalized": normalized, "lemma": lemma, "strongs": strongs, "morph": morph,
                "transliteration": transliterate(surface, language),
            })
    return out
