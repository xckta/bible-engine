from __future__ import annotations

import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .books import BOOK_ORDER, CANONICAL_BOOKS
from .references import extract_references

OT_BOOKS = set(CANONICAL_BOOKS[:39])
NT_BOOKS = set(CANONICAL_BOOKS[39:])

OSIS_BOOKS = {
    "Gen":"Genesis","Exod":"Exodus","Lev":"Leviticus","Num":"Numbers","Deut":"Deuteronomy",
    "Josh":"Joshua","Judg":"Judges","Ruth":"Ruth","1Sam":"1 Samuel","2Sam":"2 Samuel",
    "1Kgs":"1 Kings","2Kgs":"2 Kings","1Chr":"1 Chronicles","2Chr":"2 Chronicles","Ezra":"Ezra",
    "Neh":"Nehemiah","Esth":"Esther","Job":"Job","Ps":"Psalms","Prov":"Proverbs","Eccl":"Ecclesiastes",
    "Song":"Song of Solomon","Isa":"Isaiah","Jer":"Jeremiah","Lam":"Lamentations","Ezek":"Ezekiel",
    "Dan":"Daniel","Hos":"Hosea","Joel":"Joel","Amos":"Amos","Obad":"Obadiah","Jonah":"Jonah",
    "Mic":"Micah","Nah":"Nahum","Hab":"Habakkuk","Zeph":"Zephaniah","Hag":"Haggai","Zech":"Zechariah","Mal":"Malachi",
}

TISCH_BOOKS = {
    "MT":"Matthew","MR":"Mark","LU":"Luke","JOH":"John","AC":"Acts","RO":"Romans",
    "1CO":"1 Corinthians","2CO":"2 Corinthians","GA":"Galatians","EPH":"Ephesians","PHP":"Philippians",
    "COL":"Colossians","1TH":"1 Thessalonians","2TH":"2 Thessalonians","1TI":"1 Timothy","2TI":"2 Timothy",
    "TIT":"Titus","PHM":"Philemon","HEB":"Hebrews","JAS":"James","1PE":"1 Peter","2PE":"2 Peter",
    "1JO":"1 John","2JO":"2 John","3JO":"3 John","JUDE":"Jude","RE":"Revelation",
}

HEBREW_LETTERS = {
    "א":"ʾ","ב":"b","ג":"g","ד":"d","ה":"h","ו":"w","ז":"z","ח":"ḥ","ט":"ṭ","י":"y",
    "כ":"k","ך":"k","ל":"l","מ":"m","ם":"m","נ":"n","ן":"n","ס":"s","ע":"ʿ","פ":"p",
    "ף":"p","צ":"ṣ","ץ":"ṣ","ק":"q","ר":"r","ש":"š","ת":"t",
}
HEBREW_VOWELS = {
    "\u05b0":"ə","\u05b1":"ĕ","\u05b2":"ă","\u05b3":"ŏ","\u05b4":"i","\u05b5":"ē","\u05b6":"e",
    "\u05b7":"a","\u05b8":"ā","\u05b9":"ō","\u05ba":"ō","\u05bb":"u","\u05c7":"o",
}
CANTILLATION = set(chr(c) for c in range(0x0591, 0x05B0))

GREEK_MAP = {
    "α":"a","β":"b","γ":"g","δ":"d","ε":"e","ζ":"z","η":"ē","θ":"th","ι":"i","κ":"k","λ":"l",
    "μ":"m","ν":"n","ξ":"x","ο":"o","π":"p","ρ":"r","σ":"s","ς":"s","τ":"t","υ":"y","φ":"ph",
    "χ":"ch","ψ":"ps","ω":"ō",
}


def strip_combining(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def normalize_word(text: str) -> str:
    base = strip_combining(text).casefold()
    return "".join(ch for ch in base if ch.isalnum() or ("\u0590" <= ch <= "\u05ff") or ("\u0370" <= ch <= "\u03ff"))


def strip_hebrew_cantillation(text: str) -> str:
    return "".join(ch for ch in text if ch not in CANTILLATION)


def strip_hebrew_points(text: str) -> str:
    return "".join(ch for ch in text if not (0x0591 <= ord(ch) <= 0x05C7 and unicodedata.category(ch) == "Mn"))


def transliterate_hebrew(text: str) -> str:
    text = strip_hebrew_cantillation(text)
    out: list[str] = []
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch == "ש":
            following = "".join(chars[i + 1:i + 4])
            out.append("s" if "\u05c2" in following else "š")
        elif ch in HEBREW_LETTERS:
            out.append(HEBREW_LETTERS[ch])
        elif ch in HEBREW_VOWELS:
            out.append(HEBREW_VOWELS[ch])
        elif ch in {"\u05bc", "\u05c1", "\u05c2", "\u05bd", "\u05bf"}:
            continue
        elif ch.isspace() or unicodedata.category(ch).startswith("P"):
            out.append(ch)
    return "".join(out).strip()


def transliterate_greek(text: str) -> str:
    base = strip_combining(text).lower()
    return "".join(GREEK_MAP.get(ch, ch if ch.isspace() else "") for ch in base).strip()


HEB_POS = {
    "A":"adjective","C":"conjunction","D":"adverb","N":"noun","P":"pronoun","R":"preposition",
    "S":"suffix","T":"particle","V":"verb",
}
HEB_GENDER = {"m":"masculine","f":"feminine","b":"both-gender","c":"common"}
HEB_NUMBER = {"s":"singular","p":"plural","d":"dual"}
HEB_STATE = {"a":"absolute","c":"construct","d":"determined"}
HEB_STEM = {
    "q":"qal","N":"niphal","p":"piel","P":"pual","h":"hiphil","H":"hophal","t":"hithpael",
    "o":"polel","O":"polal","r":"hithpolel","m":"poel","M":"poal","k":"palel","K":"pulal",
}
HEB_CONJ = {"p":"perfect","q":"sequential perfect","i":"imperfect","w":"sequential imperfect","h":"cohortative","j":"jussive","v":"imperative","r":"participle active","s":"participle passive","a":"infinitive absolute","c":"infinitive construct"}


def _expand_hebrew_segment(seg: str) -> str:
    if not seg:
        return ""
    language = ""
    if seg[0] in {"H", "A"}:
        language = "Hebrew" if seg[0] == "H" else "Aramaic"
        seg = seg[1:]
    if not seg:
        return language
    pos_code = seg[0]
    pos = HEB_POS.get(pos_code, pos_code)
    rest = seg[1:]
    bits = [x for x in (language, pos) if x]

    adjective_types = {"a":"adjective","c":"cardinal number","g":"gentilic","o":"ordinal number"}
    noun_types = {"c":"common","g":"gentilic","p":"proper name"}
    pronoun_types = {"d":"demonstrative","f":"indefinite","i":"interrogative","p":"personal","r":"relative"}
    suffix_types = {"d":"directional he","h":"paragogic he","n":"paragogic nun","p":"pronominal"}
    particle_types = {"a":"affirmation","d":"definite article","e":"exhortation","i":"interrogative","j":"interjection","m":"demonstrative","n":"negative","o":"direct object marker","r":"relative"}

    def person_gender_number(value: str) -> tuple[list[str], str]:
        out: list[str] = []
        if value and value[0] in "123x":
            if value[0] != "x": out.append({"1":"first person","2":"second person","3":"third person"}[value[0]])
            value = value[1:]
        if value and value[0] in HEB_GENDER:
            out.append(HEB_GENDER[value[0]]); value = value[1:]
        if value and value[0] in HEB_NUMBER:
            out.append(HEB_NUMBER[value[0]]); value = value[1:]
        return out, value

    if pos_code in {"A", "N"}:
        types = adjective_types if pos_code == "A" else noun_types
        if rest and rest[0] in types:
            bits.append(types[rest[0]]); rest = rest[1:]
        if rest and rest[0] in HEB_GENDER:
            bits.append(HEB_GENDER[rest[0]]); rest = rest[1:]
        if rest and rest[0] in HEB_NUMBER:
            bits.append(HEB_NUMBER[rest[0]]); rest = rest[1:]
        if rest and rest[0] in HEB_STATE:
            bits.append(HEB_STATE[rest[0]]); rest = rest[1:]
    elif pos_code == "P":
        if rest and rest[0] in pronoun_types:
            bits.append(pronoun_types[rest[0]]); rest = rest[1:]
        extra, rest = person_gender_number(rest); bits.extend(extra)
    elif pos_code == "R":
        if rest and rest[0] == "d": bits.append("with definite article"); rest = rest[1:]
    elif pos_code == "S":
        if rest and rest[0] in suffix_types:
            bits.append(suffix_types[rest[0]]); rest = rest[1:]
        extra, rest = person_gender_number(rest); bits.extend(extra)
    elif pos_code == "T":
        if rest and rest[0] in particle_types:
            bits.append(particle_types[rest[0]]); rest = rest[1:]
    elif pos_code == "V":
        if rest:
            bits.append(HEB_STEM.get(rest[0], rest[0])); rest = rest[1:]
        if rest:
            bits.append(HEB_CONJ.get(rest[0], rest[0])); rest = rest[1:]
        if rest and rest[0] in "123x":
            extra, rest = person_gender_number(rest); bits.extend(extra)
        else:
            if rest and rest[0] in HEB_GENDER:
                bits.append(HEB_GENDER[rest[0]]); rest = rest[1:]
            if rest and rest[0] in HEB_NUMBER:
                bits.append(HEB_NUMBER[rest[0]]); rest = rest[1:]
        if rest and rest[0] in HEB_STATE:
            bits.append(HEB_STATE[rest[0]]); rest = rest[1:]
    if rest:
        bits.append(rest)
    return ", ".join(bits)

def expand_hebrew_morph(code: str) -> str:
    if not code:
        return ""
    return " + ".join(filter(None, (_expand_hebrew_segment(seg) for seg in code.split("/"))))


G_POS = {
    "N":"noun","A":"adjective","T":"article","P":"pronoun","R":"relative pronoun","D":"demonstrative pronoun",
    "V":"verb","ADV":"adverb","CONJ":"conjunction","PREP":"preposition","PRT":"particle","INJ":"interjection",
    "ARAM":"Aramaic expression","HEB":"Hebrew expression","N-PRI":"proper noun",
}
G_CASE = {"N":"nominative","G":"genitive","D":"dative","A":"accusative","V":"vocative"}
G_NUM = {"S":"singular","P":"plural"}
G_GENDER = {"M":"masculine","F":"feminine","N":"neuter"}
G_TENSE = {"P":"present","I":"imperfect","F":"future","A":"aorist","R":"perfect","L":"pluperfect","X":"no tense stated"}
G_VOICE = {"A":"active","M":"middle","P":"passive","E":"middle/passive","D":"middle deponent","O":"passive deponent","N":"middle or passive deponent"}
G_MOOD = {"I":"indicative","S":"subjunctive","O":"optative","M":"imperative","N":"infinitive","P":"participle"}


def expand_greek_morph(code: str) -> str:
    if not code:
        return ""
    if code in G_POS:
        return G_POS[code]
    if "-" not in code:
        return G_POS.get(code, code)
    pos_code, detail = code.split("-", 1)
    pos = G_POS.get(pos_code, pos_code)
    bits = [pos]
    if pos_code == "V" and len(detail) >= 3:
        bits.extend([G_TENSE.get(detail[0], detail[0]), G_VOICE.get(detail[1], detail[1]), G_MOOD.get(detail[2], detail[2])])
        rest = detail[3:].lstrip("-")
        if rest:
            if re.fullmatch(r"[123][SP]", rest):
                bits.append({"1":"first","2":"second","3":"third"}[rest[0]] + " person")
                bits.append(G_NUM.get(rest[1], rest[1]))
            elif len(rest) >= 3 and rest[0] in G_CASE and rest[1] in G_NUM and rest[2] in G_GENDER:
                bits.extend([G_CASE[rest[0]], G_NUM[rest[1]], G_GENDER[rest[2]]])
            else:
                bits.append(rest)
        return ", ".join(bits)
    detail = detail.replace("-", "")
    if detail and detail[0] in "123":
        bits.append({"1":"first person","2":"second person","3":"third person"}[detail[0]])
        detail = detail[1:]
    if len(detail) >= 1 and detail[0] in G_CASE:
        bits.append(G_CASE[detail[0]]); detail = detail[1:]
    if len(detail) >= 1 and detail[0] in G_NUM:
        bits.append(G_NUM[detail[0]]); detail = detail[1:]
    if len(detail) >= 1 and detail[0] in G_GENDER:
        bits.append(G_GENDER[detail[0]]); detail = detail[1:]
    if detail:
        bits.append(detail)
    return ", ".join(bits)


def strongs_from_oshb_lemma(lemma: str) -> str:
    """Return OSHB augmented-Strong identities in Bible Engine's H####A form."""
    out: list[str] = []
    for segment in (lemma or "").split("/"):
        m = re.search(r"(?<!\d)(\d{1,5})(?:\s*([a-zA-Z]))?(?!\d)", segment)
        if not m:
            continue
        out.append("H" + m.group(1) + (m.group(2) or "").upper())
    return "/".join(out)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_osis_ref(raw: str) -> tuple[str, int, int, str] | None:
    m = re.fullmatch(r"([^.]+)\.(\d+)\.(\d+)(?:!([A-Za-z]))?", raw.strip())
    if not m:
        return None
    book = OSIS_BOOKS.get(m.group(1))
    if not book:
        return None
    return book, int(m.group(2)), int(m.group(3)), (m.group(4) or "").lower()
