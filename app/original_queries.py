from __future__ import annotations

import sqlite3

from .books import CANONICAL_BOOKS
from .references import extract_references
from .original_core import OT_BOOKS, NT_BOOKS, normalize_word
from .original_storage import ensure_original_schema


def parse_exact_canonical_reference(text: str) -> tuple[str, int, int, int]:
    refs = [r for r in extract_references(text) if r.kind == "biblical" and r.work in set(CANONICAL_BOOKS)]
    if len(refs) != 1 or refs[0].verse_start is None:
        raise ValueError("Enter one exact canonical verse or verse range, e.g. Genesis 1:1 or John 1:1-3.")
    r = refs[0]
    end = r.verse_end or r.verse_start
    if end < r.verse_start or end - r.verse_start > 20:
        raise ValueError("Original Language Lab supports ranges of up to 21 verses at once.")
    return r.work, r.chapter, r.verse_start, end


def source_code_for_book(book: str) -> str:
    if book in OT_BOOKS:
        return "OSHB"
    if book in NT_BOOKS:
        return "TISCH"
    raise ValueError("Original Language Lab currently covers the 66-book Hebrew/Aramaic/Greek canon.")


def original_status(conn: sqlite3.Connection) -> dict:
    ensure_original_schema(conn)
    rows = conn.execute(
        "SELECT s.code,s.name,s.language,s.testament,s.license,s.source_url,s.attribution,s.version,COUNT(w.id) word_count,"
        "COUNT(DISTINCT w.book||':'||w.chapter||':'||w.verse) verse_count "
        "FROM original_lab_sources s LEFT JOIN original_lab_words w ON w.source_id=s.id GROUP BY s.id ORDER BY s.id"
    ).fetchall()
    sources = [dict(r) for r in rows]
    lexicon_entries = int(conn.execute("SELECT COUNT(*) n FROM original_lab_lexicon").fetchone()["n"])
    lexical_profiles = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_lexicon WHERE gloss<>'' OR semantic_range<>'' OR bdb_ref<>''"
    ).fetchone()["n"])
    mapping_count = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_verse_mappings WHERE source_code='OSHB'"
    ).fetchone()["n"])
    partial_mapping_count = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_verse_mappings WHERE source_code='OSHB' AND mapping_type='partial'"
    ).fetchone()["n"])
    lxx_count = int(conn.execute("SELECT COUNT(*) n FROM original_lab_lxx_lemma_occurrences").fetchone()["n"])
    hebrew_words = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id WHERE lower(COALESCE(NULLIF(w.word_language,''),s.language))='hebrew'"
    ).fetchone()["n"])
    aramaic_words = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id WHERE lower(COALESCE(NULLIF(w.word_language,''),s.language))='aramaic'"
    ).fetchone()["n"])
    greek_words = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id WHERE lower(COALESCE(NULLIF(w.word_language,''),s.language))='greek'"
    ).fetchone()["n"])
    corpus_ready = {r["code"] for r in sources if int(r["word_count"] or 0) > 0} >= {"OSHB", "TISCH"}
    enriched_ready = lexicon_entries >= 10000 and lexical_profiles >= 1000 and lxx_count >= 100000 and aramaic_words >= 100
    return {
        "ready": corpus_ready and enriched_ready,
        "corpus_ready": corpus_ready,
        "enriched_ready": enriched_ready,
        "sources": sources,
        "hebrew_words": hebrew_words,
        "aramaic_words": aramaic_words,
        "greek_words": greek_words,
        "lexicon_entries": lexicon_entries,
        "lexical_profiles": lexical_profiles,
        "lxx_lemma_occurrences": lxx_count,
        "verse_mappings": mapping_count,
        "partial_verse_mappings": partial_mapping_count,
    }


def verse_words(conn: sqlite3.Connection, reference: str) -> dict:
    ensure_original_schema(conn)
    book, chapter, v1, v2 = parse_exact_canonical_reference(reference)
    source_code = source_code_for_book(book)
    src = conn.execute("SELECT * FROM original_lab_sources WHERE code=?", (source_code,)).fetchone()
    if not src:
        raise LookupError(f"{source_code} original-language source is not installed. Re-run START_BIBLE_ENGINE.bat.")
    rows = conn.execute(
        "SELECT w.*,s.language,s.name source_name,s.code source_code,s.source_url,s.attribution "
        "FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id "
        "WHERE s.code=? AND w.book=? AND w.chapter=? AND w.verse BETWEEN ? AND ? ORDER BY w.verse,w.position",
        (source_code, book, chapter, v1, v2),
    ).fetchall()
    if not rows:
        raise LookupError(f"No original-language words were indexed for {book} {chapter}:{v1}-{v2}.")
    words = [dict(r) for r in rows]
    for w in words:
        if not w.get("word_language"):
            w["word_language"] = "Greek" if source_code == "TISCH" else "Hebrew"
    partial_rows = []
    if source_code == "OSHB":
        partial_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM original_lab_verse_mappings WHERE source_code='OSHB' AND target_book=? AND target_chapter=? "
            "AND target_verse BETWEEN ? AND ? AND mapping_type='partial' ORDER BY target_verse,id",
            (book, chapter, v1, v2),
        ).fetchall()]
    verses: list[dict] = []
    for verse in range(v1, v2 + 1):
        vw = [w for w in words if w["verse"] == verse]
        if not vw and not any(int(m["target_verse"]) == verse for m in partial_rows):
            continue
        source_refs = []
        for w in vw:
            sb = w.get("source_book") or w["book"]
            sc = int(w.get("source_chapter") or w["chapter"])
            sv = int(w.get("source_verse") or w["verse"])
            ref = f"{sb} {sc}:{sv}"
            if ref not in source_refs:
                source_refs.append(ref)
        partial = [m for m in partial_rows if int(m["target_verse"]) == verse]
        warnings = []
        for m in partial:
            seg = f"{m['source_segment']}" if m.get("source_segment") else ""
            warnings.append(
                f"Partial WLC/English verse boundary: {m['source_book']} {m['source_chapter']}:{m['source_verse']}{seg} "
                f"maps into {m['target_book']} {m['target_chapter']}:{m['target_verse']}. "
                "The official VerseMap does not provide a word-position split, so Bible Engine does not guess at segment-level alignment."
            )
        langs = sorted({w.get("word_language") or src["language"] for w in vw})
        verses.append({
            "reference": f"{book} {chapter}:{verse}",
            "original_text": " ".join(w["surface"] for w in vw),
            "source_references": source_refs,
            "languages": langs,
            "remapped": any((w.get("source_chapter") or w["chapter"]) != w["chapter"] or (w.get("source_verse") or w["verse"]) != w["verse"] for w in vw),
            "alignment_warnings": warnings,
            "words": vw,
        })
    language_set = {w.get("word_language") or src["language"] for w in words}
    if language_set == {"Greek"}:
        language = "Greek"
    elif "Aramaic" in language_set and "Hebrew" in language_set:
        language = "Hebrew / Aramaic"
    elif "Aramaic" in language_set:
        language = "Aramaic"
    else:
        language = "Hebrew"
    return {
        "book": book, "chapter": chapter, "verse_start": v1, "verse_end": v2,
        "reference": f"{book} {chapter}:{v1}" + (f"-{v2}" if v2 != v1 else ""),
        "language": language, "source_code": source_code, "source_name": src["name"],
        "source_url": src["source_url"], "attribution": src["attribution"], "verses": verses,
    }


def _lxx_report(conn: sqlite3.Connection, lemma_normalized: str, limit: int = 80) -> dict:
    if not lemma_normalized:
        return {"occurrence_count": 0, "book_distribution": [], "occurrences": []}
    total = int(conn.execute(
        "SELECT COUNT(*) n FROM original_lab_lxx_lemma_occurrences WHERE lemma_normalized=?", (lemma_normalized,)
    ).fetchone()["n"])
    distribution = [dict(r) for r in conn.execute(
        "SELECT book,COUNT(*) n FROM original_lab_lxx_lemma_occurrences WHERE lemma_normalized=? GROUP BY book ORDER BY n DESC,book",
        (lemma_normalized,),
    ).fetchall()]
    occurrences = [dict(r) for r in conn.execute(
        "SELECT lemma,surface_key,book,chapter,verse,position,source_label,source_url "
        "FROM original_lab_lxx_lemma_occurrences WHERE lemma_normalized=? ORDER BY book_order,chapter,verse,position LIMIT ?",
        (lemma_normalized, limit),
    ).fetchall()]
    return {
        "occurrence_count": total, "book_distribution": distribution, "occurrences": occurrences,
        "note": "Lemma-index witness only. Bible Engine does not bundle or quote the separately licensed CCAT Septuagint text.",
        "source_label": "Open Scriptures Septuagint Project — LXX lemma index",
        "source_url": "https://github.com/openscriptures/GreekResources",
    }


def lemma_report(conn: sqlite3.Connection, word_id: int, limit: int = 80, offset: int = 0) -> dict:
    ensure_original_schema(conn)
    selected = conn.execute(
        "SELECT w.*,s.code source_code,s.name source_name,s.language,s.source_url,s.attribution FROM original_lab_words w "
        "JOIN original_lab_sources s ON s.id=w.source_id WHERE w.id=?", (word_id,),
    ).fetchone()
    if not selected:
        raise LookupError("Original-language word not found.")
    s = dict(selected)
    if not s.get("word_language"):
        s["word_language"] = "Greek" if s["source_code"] == "TISCH" else "Hebrew"
    if s["strongs"]:
        where = "w.source_id=? AND w.strongs=?"; args: list[object] = [s["source_id"], s["strongs"]]
    else:
        where = "w.source_id=? AND w.lemma_normalized=?"; args = [s["source_id"], s["lemma_normalized"]]
    total = int(conn.execute(f"SELECT COUNT(*) n FROM original_lab_words w WHERE {where}", args).fetchone()["n"])
    dist_rows = conn.execute(f"SELECT w.book,COUNT(*) n FROM original_lab_words w WHERE {where} GROUP BY w.book ORDER BY n DESC,w.book", args).fetchall()
    occ = conn.execute(
        f"SELECT w.id,w.book,w.chapter,w.verse,w.position,w.surface,w.transliteration,w.morph,w.morph_expanded,w.word_language,"
        f"w.source_book,w.source_chapter,w.source_verse,w.verse_mapping_type FROM original_lab_words w WHERE {where} "
        f"ORDER BY w.book_order,w.chapter,w.verse,w.position LIMIT ? OFFSET ?", args + [limit, offset],
    ).fetchall()
    strong_codes = [x for x in str(s.get("strongs") or "").split("/") if x]
    lexicon = []
    if strong_codes:
        marks = ",".join("?" for _ in strong_codes)
        lexicon = [dict(r) for r in conn.execute(f"SELECT * FROM original_lab_lexicon WHERE strongs IN ({marks}) ORDER BY strongs", strong_codes).fetchall()]
    lxx = _lxx_report(conn, s.get("lemma_normalized", ""), min(limit, 100)) if s["source_code"] == "TISCH" else None
    return {"word": s, "occurrence_count": total, "book_distribution": [dict(r) for r in dist_rows], "occurrences": [dict(r) for r in occ], "lexicon": lexicon, "lxx": lxx, "limit": limit, "offset": offset}


def search_words(conn: sqlite3.Connection, query: str, language: str = "all", field: str = "all", limit: int = 60) -> list[dict]:
    ensure_original_schema(conn)
    q = query.strip()
    if not q:
        return []
    clauses = []; args: list[object] = []
    lang = language.lower()
    if lang in {"hebrew", "aramaic", "greek"}:
        clauses.append("lower(COALESCE(NULLIF(w.word_language,''),s.language))=?"); args.append(lang)
    normalized = normalize_word(q)
    if field == "strongs":
        clauses.append("upper(w.strongs)=upper(?)"); args.append(q)
    elif field == "morph":
        clauses.append("(w.morph LIKE ? OR lower(w.morph_expanded) LIKE ?)"); args.extend([f"%{q}%", f"%{q.lower()}%"])
    elif field == "lemma":
        clauses.append("(w.lemma_normalized=? OR w.alt_lemma LIKE ?)"); args.extend([normalized, f"%{q}%"])
    elif field == "surface":
        clauses.append("w.surface_normalized=?"); args.append(normalized)
    else:
        clauses.append("(w.surface_normalized=? OR w.lemma_normalized=? OR upper(w.strongs)=upper(?) OR lower(w.transliteration) LIKE ?)")
        args.extend([normalized, normalized, q, f"%{q.lower()}%"])
    sql = (
        "SELECT w.id,w.book,w.chapter,w.verse,w.position,w.surface,w.transliteration,w.lemma,w.alt_lemma,w.strongs,w.morph,w.morph_expanded,"
        "w.word_language,w.source_book,w.source_chapter,w.source_verse,w.verse_mapping_type,s.language,s.code source_code "
        "FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id WHERE " + " AND ".join(clauses) +
        " ORDER BY w.book_order,w.chapter,w.verse,w.position LIMIT ?"
    )
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def morphology_summary(conn: sqlite3.Connection, language: str, limit: int = 100) -> list[dict]:
    ensure_original_schema(conn)
    rows = conn.execute(
        "SELECT w.morph,w.morph_expanded,COUNT(*) n FROM original_lab_words w JOIN original_lab_sources s ON s.id=w.source_id "
        "WHERE lower(COALESCE(NULLIF(w.word_language,''),s.language))=? AND w.morph<>'' GROUP BY w.morph,w.morph_expanded ORDER BY n DESC LIMIT ?",
        (language.lower(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def translation_parallels(conn: sqlite3.Connection, reference: str) -> list[dict]:
    book, chapter, v1, v2 = parse_exact_canonical_reference(reference)
    rows = conn.execute(
        "SELECT t.code,t.name,v.verse,v.text FROM verses v JOIN translations t ON t.id=v.translation_id "
        "WHERE t.code IN ('WEB','ASV') AND v.book=? AND v.chapter=? AND v.verse BETWEEN ? AND ? "
        "ORDER BY CASE t.code WHEN 'WEB' THEN 1 ELSE 2 END,v.verse", (book, chapter, v1, v2),
    ).fetchall()
    grouped: dict[str, dict] = {}
    for row in rows:
        code = row["code"]
        g = grouped.setdefault(code, {"translation": code, "name": row["name"], "reference": reference, "verses": []})
        g["verses"].append({"verse": int(row["verse"]), "text": row["text"]})
    out = []
    for code in ("WEB", "ASV"):
        if code not in grouped: continue
        g = grouped[code]; g["text"] = " ".join(f"[{x['verse']}] {x['text']}" for x in g["verses"]); out.append(g)
    return out
