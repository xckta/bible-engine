from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .books import BOOK_ORDER
from .original_core import OSIS_BOOKS, TISCH_BOOKS, expand_greek_morph, expand_hebrew_morph, normalize_word, strongs_from_oshb_lemma, transliterate_greek, transliterate_hebrew, _local, _parse_osis_ref

def parse_oshb_verse_map(path: Path) -> tuple[dict[tuple[str, int, int], tuple[str, int, int]], list[dict]]:
    """Read OSHB's WLC→English/KJV versification map."""
    full: dict[tuple[str, int, int], tuple[str, int, int]] = {}
    mappings: list[dict] = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if _local(elem.tag) != "verse":
            elem.clear(); continue
        source = _parse_osis_ref(elem.attrib.get("wlc", ""))
        target = _parse_osis_ref(elem.attrib.get("kjv", ""))
        mapping_type = elem.attrib.get("type", "full").lower()
        if not source or not target:
            elem.clear(); continue
        sb, sc, sv, ss = source
        tb, tc, tv, ts = target
        row = {"source_book": sb, "source_chapter": sc, "source_verse": sv, "source_segment": ss,
               "target_book": tb, "target_chapter": tc, "target_verse": tv, "target_segment": ts,
               "mapping_type": mapping_type}
        mappings.append(row)
        if mapping_type == "full" and not ss and not ts:
            full[(sb, sc, sv)] = (tb, tc, tv)
        elem.clear()
    return full, mappings


def parse_oshb_xml(path: Path, verse_map: dict[tuple[str, int, int], tuple[str, int, int]] | None = None) -> list[dict]:
    rows: list[dict] = []
    current_ref: tuple[str, int, int] | None = None
    pos = 0
    for event, elem in ET.iterparse(path, events=("start", "end")):
        local = _local(elem.tag)
        if event == "start" and local == "verse":
            osis = elem.attrib.get("osisID", "")
            bits = osis.split(".")
            if len(bits) >= 3 and bits[0] in OSIS_BOOKS:
                current_ref = (OSIS_BOOKS[bits[0]], int(bits[1]), int(bits[2])); pos = 0
        elif event == "end" and local == "w" and current_ref:
            if elem.attrib.get("type") == "x-ketiv":
                elem.clear(); continue
            surface = "".join(elem.itertext()).strip()
            if surface:
                pos += 1
                source_book, source_chapter, source_verse = current_ref
                book, chapter, verse = (verse_map or {}).get(current_ref, current_ref)
                lemma = elem.attrib.get("lemma", ""); morph = elem.attrib.get("morph", "")
                rows.append({
                    "book": book, "book_order": BOOK_ORDER[book], "chapter": chapter, "verse": verse,
                    "source_book": source_book, "source_chapter": source_chapter, "source_verse": source_verse,
                    "verse_mapping_type": "full" if (book, chapter, verse) != current_ref else "same",
                    "position": pos, "source_word_id": elem.attrib.get("id", elem.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")),
                    "surface": surface, "surface_normalized": normalize_word(surface), "lemma": lemma,
                    "lemma_normalized": normalize_word(lemma), "alt_lemma": "", "strongs": strongs_from_oshb_lemma(lemma),
                    "morph": morph, "morph_expanded": expand_hebrew_morph(morph), "transliteration": transliterate_hebrew(surface),
                    "word_language": "Aramaic" if any(seg[:1].upper() == "A" for seg in morph.split("/") if seg) else "Hebrew",
                })
            elem.clear()
        elif event == "end" and local == "verse":
            current_ref = None; elem.clear()
    return rows


def parse_tischendorf_file(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split()
        if len(parts) < 6: continue
        code, ref_token, surface, morph, strong = parts[:5]
        book = TISCH_BOOKS.get(code.upper())
        m = re.fullmatch(r"(\d+):(\d+)\.(\d+)", ref_token)
        if not book or not m: continue
        chapter, verse, position = map(int, m.groups()); lemma = parts[5]; alt = ""
        if "!" in parts:
            idx = parts.index("!")
            if idx + 1 < len(parts): alt = parts[idx + 1]
        rows.append({
            "book": book, "book_order": BOOK_ORDER[book], "chapter": chapter, "verse": verse, "position": position,
            "source_book": book, "source_chapter": chapter, "source_verse": verse, "verse_mapping_type": "same",
            "source_word_id": f"{code.upper()}-{chapter}-{verse}-{position}", "surface": surface,
            "surface_normalized": normalize_word(surface), "lemma": lemma, "lemma_normalized": normalize_word(lemma),
            "alt_lemma": alt, "strongs": "G" + strong if strong.isdigit() else strong,
            "morph": morph, "morph_expanded": expand_greek_morph(morph), "transliteration": transliterate_greek(surface),
            "word_language": "Greek",
        })
    return rows


def parse_strongs_dat(path: Path, prefix: str) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines(); out: list[dict] = []; i = 0
    while i < len(lines):
        if not lines[i].startswith("$$T"):
            i += 1; continue
        i += 1; number = ""
        while i < len(lines) and not number:
            m = re.match(r"\\0*(\d+)\\", lines[i].strip())
            if m: number = str(int(m.group(1)))
            i += 1
        head = ""
        while i < len(lines) and not lines[i].startswith("$$T"):
            if lines[i].strip(): head = lines[i].strip(); i += 1; break
            i += 1
        definition_lines: list[str] = []
        while i < len(lines) and not lines[i].startswith("$$T"):
            definition_lines.append(lines[i].rstrip()); i += 1
        if not number: continue
        headword = re.sub(r"^\s*\d+\s+", "", head).strip()
        definition = re.sub(r"\n{3,}", "\n\n", "\n".join(definition_lines).strip())
        out.append({"strongs": prefix.upper() + number, "headword": headword, "definition": definition,
                    "source_label": "Strong's Dictionaries (1890), OpenScriptures corrected e-text",
                    "source_url": "https://github.com/openscriptures/strongs",
                    "license": "Strong's 1890 dictionary public domain; corrected OpenScriptures edition terms apply"})
    return out


LXX_OSIS_BOOKS = {
    **OSIS_BOOKS,
    "Tob": "Tobit", "Jdt": "Judith", "Wis": "Wisdom", "Sir": "Sirach", "Bar": "Baruch",
    "EpJer": "Letter of Jeremiah", "PrAzar": "Prayer of Azariah", "Sus": "Susanna", "Bel": "Bel and the Dragon",
    "1Macc": "1 Maccabees", "2Macc": "2 Maccabees", "3Macc": "3 Maccabees", "4Macc": "4 Maccabees",
    "1Esd": "1 Esdras", "PrMan": "Prayer of Manasseh", "Ps151": "Psalm 151",
}


def _clean_inline_text(elem: ET.Element | None) -> str:
    if elem is None: return ""
    return re.sub(r"\s+", " ", " ".join("".join(elem.itertext()).split())).strip()


def parse_hebrew_lexicon(lexical_index_path: Path, bdb_path: Path, aug_index_path: Path | None = None) -> list[dict]:
    bdb_ranges: dict[str, str] = {}
    tree = ET.parse(bdb_path)
    for entry in tree.getroot().iter():
        if entry.tag.rsplit('}', 1)[-1] != 'entry': continue
        eid = entry.attrib.get('id', '').strip()
        if not eid: continue
        defs: list[str] = []
        for child in entry.iter():
            local = child.tag.rsplit('}', 1)[-1]
            if local in {'def', 'sense'}:
                txt = _clean_inline_text(child)
                if txt and txt not in defs: defs.append(txt)
        if not defs:
            txt = _clean_inline_text(entry)
            if txt: defs.append(txt)
        bdb_ranges[eid] = '; '.join(defs[:18])[:2400]

    lexical_by_id: dict[str, dict] = {}
    root = ET.parse(lexical_index_path).getroot()
    for entry in root.iter():
        if entry.tag.rsplit('}', 1)[-1] != 'entry': continue
        entry_id = entry.attrib.get('id', '').strip()
        if not entry_id: continue
        word = next((x for x in entry if x.tag.rsplit('}', 1)[-1] == 'w'), None)
        xref = next((x for x in entry if x.tag.rsplit('}', 1)[-1] == 'xref'), None)
        if xref is None: continue
        bdb_ref = (xref.attrib.get('bdb') or '').strip()
        lexical_by_id[entry_id] = {
            'language': 'Hebrew', 'headword': _clean_inline_text(word),
            'gloss': _clean_inline_text(next((x for x in entry if x.tag.rsplit('}', 1)[-1] == 'def'), None)),
            'pos': _clean_inline_text(next((x for x in entry if x.tag.rsplit('}', 1)[-1] == 'pos'), None)),
            'transliteration': (word.attrib.get('xlit') if word is not None else '') or '',
            'bdb_ref': bdb_ref, 'twot_ref': (xref.attrib.get('twot') or '').strip(),
            'etymology': _clean_inline_text(next((x for x in entry if x.tag.rsplit('}', 1)[-1] == 'etym'), None)),
            'semantic_range': bdb_ranges.get(bdb_ref, ''), 'raw_strong': (xref.attrib.get('strong') or '').strip(),
            'raw_aug_suffix': (xref.attrib.get('aug') or '').strip(),
            'lexical_source_label': 'Brown–Driver–Briggs / OpenScriptures Hebrew Lexicon',
            'lexical_source_url': 'https://github.com/openscriptures/HebrewLexicon',
            'lexical_license': 'BDB text public domain; OpenScriptures markup CC BY 4.0',
        }

    keyed: dict[str, dict] = {}
    for entry_id, profile in lexical_by_id.items():
        raw = profile.get('raw_strong', ''); m = re.search(r'\d+', raw)
        if not m: continue
        key = 'H' + str(int(m.group())) + str(profile.get('raw_aug_suffix') or '').upper()
        keyed[key] = {k: v for k, v in profile.items() if not k.startswith('raw_')}
    if aug_index_path and aug_index_path.exists():
        aug_root = ET.parse(aug_index_path).getroot()
        for w in aug_root.iter():
            if w.tag.rsplit('}', 1)[-1] != 'w': continue
            aug = (w.attrib.get('aug') or '').strip(); entry_id = _clean_inline_text(w); profile = lexical_by_id.get(entry_id)
            if not aug or not profile: continue
            keyed['H' + aug.upper()] = {k: v for k, v in profile.items() if not k.startswith('raw_')}
    return [dict(profile, strongs=strongs) for strongs, profile in sorted(keyed.items())]


def parse_lxx_lemma_file(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(payload, dict): raise ValueError(f'LXX lemma file {path.name} is not a JSON object.')
    out: list[dict] = []
    for osis_ref, words in payload.items():
        bits = str(osis_ref).split('.')
        if len(bits) < 3: continue
        try: chapter, verse = int(bits[-2]), int(bits[-1])
        except ValueError: continue
        osis_book = '.'.join(bits[:-2]); book = LXX_OSIS_BOOKS.get(osis_book)
        if not book or book not in BOOK_ORDER or not isinstance(words, list): continue
        for pos, word in enumerate(words, 1):
            if not isinstance(word, dict): continue
            lemma = str(word.get('lemma') or '').strip()
            if not lemma: continue
            out.append({'surface_key': str(word.get('key') or '').strip(), 'lemma': lemma,
                        'lemma_normalized': normalize_word(lemma), 'book': book, 'book_order': BOOK_ORDER[book],
                        'chapter': chapter, 'verse': verse, 'position': pos,
                        'source_label': 'Open Scriptures Septuagint Project — lemma index',
                        'source_url': 'https://github.com/openscriptures/GreekResources'})
    return out
