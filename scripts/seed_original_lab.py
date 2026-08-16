from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import init_db, session
from app.original_parsers import (
    parse_hebrew_lexicon, parse_lxx_lemma_file, parse_oshb_verse_map, parse_oshb_xml, parse_strongs_dat, parse_tischendorf_file,
)
from app.original_storage import (
    merge_original_lexicon_profiles,
    replace_lxx_lemma_occurrences,
    replace_original_lexicon,
    replace_original_verse_mappings,
    replace_original_words,
    upsert_original_source,
)
ROOT = Path('data/sources/original')
OSHB_DIR = ROOT / 'morphhb-master'
TISCH_DIR = ROOT / 'tischendorf-data-master'
STRONGS_DIR = ROOT / 'strongs-master'
HEBREW_LEXICON_DIR = ROOT / 'HebrewLexicon-master'
GREEK_RESOURCES_DIR = ROOT / 'GreekResources-master'
OSHB_URL = 'https://github.com/openscriptures/morphhb/archive/refs/heads/master.zip'
TISCH_URL = 'https://github.com/morphgnt/tischendorf-data/archive/refs/heads/master.zip'
STRONGS_URL = 'https://github.com/openscriptures/strongs/archive/refs/heads/master.zip'
HEBREW_LEXICON_URL = 'https://github.com/openscriptures/HebrewLexicon/archive/refs/heads/master.zip'
GREEK_RESOURCES_URL = 'https://github.com/openscriptures/GreekResources/archive/refs/heads/master.zip'


def download_extract(url: str, expected_dir: Path, label: str) -> None:
    if expected_dir.exists():
        print(f'{label} source already downloaded.')
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    archive = ROOT / (expected_dir.name + '.zip')
    print(f'Downloading {label}...')
    req = urllib.request.Request(url, headers={'User-Agent': 'BibleEngine-OriginalLanguageLab/0.6.1'})
    with urllib.request.urlopen(req, timeout=120) as response, archive.open('wb') as out:
        shutil.copyfileobj(response, out)
    print(f'Extracting {label}...')
    with zipfile.ZipFile(archive) as z:
        base = ROOT.resolve()
        for member in z.infolist():
            dest = (ROOT / member.filename).resolve()
            if base not in dest.parents and dest != base:
                raise RuntimeError('Unsafe path in downloaded ZIP archive.')
        z.extractall(ROOT)
    archive.unlink(missing_ok=True)
    if not expected_dir.exists():
        raise RuntimeError(f'{label} archive did not contain expected folder {expected_dir}.')


def oshb_rows(verse_map):
    files = sorted(p for p in (OSHB_DIR / 'wlc').glob('*.xml') if p.name != 'VerseMap.xml')
    if not files:
        raise RuntimeError('OSHB WLC XML files were not found after download.')
    for i, path in enumerate(files, 1):
        rows = parse_oshb_xml(path, verse_map)
        if rows:
            print(f'  Hebrew/Aramaic {i:02d}/{len(files):02d} {rows[0]["book"]}: {len(rows):,} words')
            yield from rows


def tisch_rows():
    files = sorted((TISCH_DIR / 'word-per-line' / '1.1' / 'Unicode').glob('*.TUP'))
    if not files:
        raise RuntimeError('Tischendorf Unicode morphology files were not found after download.')
    for i, path in enumerate(files, 1):
        rows = parse_tischendorf_file(path)
        if rows:
            print(f'  Greek  {i:02d}/{len(files):02d} {rows[0]["book"]}: {len(rows):,} words')
            yield from rows


def lxx_rows():
    dirs = [p for p in GREEK_RESOURCES_DIR.rglob('LxxLemmas') if p.is_dir()]
    if not dirs:
        raise RuntimeError('GreekResources LxxLemmas directory was not found after download.')
    files = sorted(dirs[0].glob('*.js'))
    if not files:
        raise RuntimeError('No LXX lemma index files were found.')
    for i, path in enumerate(files, 1):
        rows = parse_lxx_lemma_file(path)
        if rows:
            if i == 1 or i % 10 == 0 or i == len(files):
                print(f'  LXX lemma index {i:02d}/{len(files):02d}: {path.stem}')
            yield from rows


def _required_file(root: Path, filename: str) -> Path:
    hits = list(root.rglob(filename))
    if not hits:
        raise RuntimeError(f'{filename} was not found under {root}.')
    return hits[0]


def main() -> None:
    download_extract(OSHB_URL, OSHB_DIR, 'Open Scriptures Hebrew Bible')
    download_extract(TISCH_URL, TISCH_DIR, 'Tischendorf Greek New Testament morphology')
    download_extract(STRONGS_URL, STRONGS_DIR, "Strong's Hebrew and Greek dictionaries")
    download_extract(HEBREW_LEXICON_URL, HEBREW_LEXICON_DIR, 'OpenScriptures Hebrew Lexicon / BDB bridge')
    download_extract(GREEK_RESOURCES_URL, GREEK_RESOURCES_DIR, 'OpenScriptures Septuagint lemma resources')
    init_db(settings.db_path)
    with session(settings.db_path) as conn:
        oshb_id = upsert_original_source(
            conn, code='OSHB', name='Open Scriptures Hebrew Bible / Westminster Leningrad Codex',
            language='Hebrew', testament='Old Testament',
            license_text='WLC text Public Domain; OSHB lemma and morphology CC BY 4.0',
            source_url='https://github.com/openscriptures/morphhb',
            attribution='Open Scriptures Hebrew Bible Project; Westminster Leningrad Codex', version='master',
        )
        verse_map_path = OSHB_DIR / 'wlc' / 'VerseMap.xml'
        if not verse_map_path.exists():
            raise RuntimeError('OSHB VerseMap.xml was not found; refusing to index Hebrew without versification safeguards.')
        full_verse_map, verse_mappings = parse_oshb_verse_map(verse_map_path)
        mapping_count = replace_original_verse_mappings(conn, 'OSHB', verse_mappings)
        print(f'Loaded {mapping_count:,} official WLC/English versification mappings.')
        print('Indexing Hebrew + Biblical Aramaic words with English-reference alignment...')
        hebrew = replace_original_words(conn, oshb_id, oshb_rows(full_verse_map))
        print(f'Indexed {hebrew:,} Hebrew/Aramaic word records.')

        tisch_id = upsert_original_source(
            conn, code='TISCH', name="Tischendorf's 8th Greek New Testament with Morphology",
            language='Greek', testament='New Testament',
            license_text='Public Domain — text and analysis; copy freely',
            source_url='https://github.com/morphgnt/tischendorf-data',
            attribution='Ulrik Petersen; G. Clint Yale; Maurice A. Robinson', version='1.1',
        )
        print('Indexing Greek New Testament words...')
        greek = replace_original_words(conn, tisch_id, tisch_rows())
        print(f'Indexed {greek:,} Greek word records.')

        print("Indexing Strong's historical orientation layer...")
        heb_lex = parse_strongs_dat(STRONGS_DIR / 'hebrew' / 'strongshebrew.dat', 'H')
        grk_lex = parse_strongs_dat(STRONGS_DIR / 'greek' / 'strongsgreek.dat', 'G')
        hcount = replace_original_lexicon(conn, 'Hebrew', heb_lex)
        gcount = replace_original_lexicon(conn, 'Greek', grk_lex)
        print(f"Indexed {hcount:,} Hebrew + {gcount:,} Greek Strong's dictionary entries.")

        print('Merging Brown–Driver–Briggs / OpenScriptures Hebrew lexical profiles...')
        lexical_index = _required_file(HEBREW_LEXICON_DIR, 'LexicalIndex.xml')
        bdb = _required_file(HEBREW_LEXICON_DIR, 'BrownDriverBriggs.xml')
        aug_index = _required_file(HEBREW_LEXICON_DIR, 'AugIndex.xml')
        profiles = parse_hebrew_lexicon(lexical_index, bdb, aug_index)
        profile_count = merge_original_lexicon_profiles(conn, profiles)
        print(f'Merged {profile_count:,} Hebrew lexical profiles.')

        print('Indexing Septuagint lemma witnesses (metadata only; no restricted LXX text)...')
        lxx_count = replace_lxx_lemma_occurrences(conn, lxx_rows())
        print(f'Indexed {lxx_count:,} LXX lemma-occurrence records.')
    print('Original Language Lab corpus ready.')


if __name__ == '__main__':
    main()
