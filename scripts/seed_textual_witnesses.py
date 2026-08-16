from __future__ import annotations

import csv
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import init_db, session
from app.textual_witnesses import replace_edition_verses, upsert_edition, witness_stats

SBL_MAP = {
    'Matt':'Matthew','Mark':'Mark','Luke':'Luke','John':'John','Acts':'Acts','Rom':'Romans','1Cor':'1 Corinthians','2Cor':'2 Corinthians','Gal':'Galatians','Eph':'Ephesians','Phil':'Philippians','Col':'Colossians','1Thess':'1 Thessalonians','2Thess':'2 Thessalonians','1Tim':'1 Timothy','2Tim':'2 Timothy','Titus':'Titus','Phlm':'Philemon','Heb':'Hebrews','Jas':'James','1Pet':'1 Peter','2Pet':'2 Peter','1John':'1 John','2John':'2 John','3John':'3 John','Jude':'Jude','Rev':'Revelation'
}
BYZ_MAP = {
    'MAT':'Matthew','MAR':'Mark','LUK':'Luke','JOH':'John','ACT':'Acts','ROM':'Romans','1CO':'1 Corinthians','2CO':'2 Corinthians','GAL':'Galatians','EPH':'Ephesians','PHP':'Philippians','COL':'Colossians','1TH':'1 Thessalonians','2TH':'2 Thessalonians','1TI':'1 Timothy','2TI':'2 Timothy','TIT':'Titus','PHM':'Philemon','HEB':'Hebrews','JAM':'James','1PE':'1 Peter','2PE':'2 Peter','1JO':'1 John','2JO':'2 John','3JO':'3 John','JUD':'Jude','REV':'Revelation'
}

SBL_URL = 'https://github.com/Faithlife/SBLGNT/archive/refs/heads/master.zip'
BYZ_URL = 'https://github.com/byztxt/byzantine-majority-text/archive/refs/heads/master.zip'


def _markers_exist(dest: Path, markers: tuple[str, ...]) -> bool:
    return dest.exists() and all((dest / marker).is_file() for marker in markers)


def _safe_extract(payload: bytes, tmp: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        base = tmp.resolve()
        for member in zf.infolist():
            target = (tmp / member.filename).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError(f'Unsafe path in textual-witness archive: {member.filename}')
        zf.extractall(tmp)


def archive(url: str, dest: Path, markers: tuple[str, ...]) -> Path:
    """Download a source archive only when its required layout is not intact.

    A previous interrupted download/extraction must not be treated as a permanent
    cache hit. Required marker files prove the source layout needed by the parser
    is present; otherwise the directory is replaced from a fresh archive.
    """
    if _markers_exist(dest, markers):
        print(f'Textual witness source already present: {dest.name}')
        return dest

    if dest.exists():
        print(f'Removing incomplete textual witness cache: {dest}')
        shutil.rmtree(dest, ignore_errors=True)

    print(f'Downloading {url}')
    req = urllib.request.Request(url, headers={'User-Agent':'BibleEngine-TextualWitness/1.0'})
    with urllib.request.urlopen(req, timeout=120) as response:
        payload = response.read()

    tmp = dest.parent / (dest.name + '-extract')
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    _safe_extract(payload, tmp)

    roots = [p for p in tmp.iterdir() if p.is_dir()]
    src = roots[0] if len(roots) == 1 else tmp
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)

    if not _markers_exist(dest, markers):
        missing = [m for m in markers if not (dest / m).is_file()]
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError('Textual witness archive layout incomplete after extraction; missing: ' + ', '.join(missing))
    return dest


def load_sbl(root: Path) -> list[dict]:
    rows = []
    for stem, book in SBL_MAP.items():
        path = root / 'data' / 'sblgnt' / 'text' / f'{stem}.txt'
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            if '\t' not in line:
                continue
            ref, text = line.split('\t', 1)
            import re
            match = re.search(r'(\d+):(\d+)$', ref.strip())
            if match:
                rows.append({
                    'book': book,
                    'chapter': int(match.group(1)),
                    'verse': int(match.group(2)),
                    'text': text.strip(),
                })
    return rows


def load_byz(root: Path) -> list[dict]:
    rows = []
    base = root / 'csv-unicode' / 'ccat' / 'no-variants'
    for stem, book in BYZ_MAP.items():
        path = base / f'{stem}.csv'
        if not path.exists():
            continue
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                if row.get('chapter') and row.get('verse') and row.get('text'):
                    rows.append({
                        'book': book,
                        'chapter': int(row['chapter']),
                        'verse': int(row['verse']),
                        'text': row['text'].strip(),
                    })
    return rows


def main() -> int:
    init_db(settings.db_path)
    base = ROOT / 'data' / 'sources' / 'witnesses'
    sbl = archive(
        SBL_URL,
        base / 'sblgnt',
        ('data/sblgnt/text/John.txt', 'data/sblgnt/text/Rev.txt'),
    )
    byz = archive(
        BYZ_URL,
        base / 'rp2018',
        ('csv-unicode/ccat/no-variants/JOH.csv', 'csv-unicode/ccat/no-variants/REV.csv'),
    )

    sbl_rows = load_sbl(sbl)
    byz_rows = load_byz(byz)
    if len(sbl_rows) < 7900 or len(byz_rows) < 7900:
        # Do not leave an apparently valid but semantically incomplete cache that
        # would be reused forever on the next launch.
        if len(sbl_rows) < 7900:
            shutil.rmtree(sbl, ignore_errors=True)
        if len(byz_rows) < 7900:
            shutil.rmtree(byz, ignore_errors=True)
        raise RuntimeError(f'Witness source incomplete: SBLGNT={len(sbl_rows)} RP2018={len(byz_rows)}')

    with session(settings.db_path) as conn:
        upsert_edition(
            conn,
            code='SBLGNT',
            name='SBL Greek New Testament',
            language='greek',
            edition_class='critical_edition',
            date_label='2010 / public source v1.2',
            editor='Michael W. Holmes',
            license='CC BY 4.0',
            source_url='https://github.com/Faithlife/SBLGNT',
            notes='Modern critically edited Greek New Testament. Edition data, not a manuscript.',
        )
        upsert_edition(
            conn,
            code='RP2018',
            name='Robinson–Pierpont Byzantine Textform',
            language='greek',
            edition_class='byzantine_edition',
            date_label='2018',
            editor='Maurice A. Robinson / William G. Pierpont',
            license='Public Domain / Unlicense repository',
            source_url='https://github.com/byztxt/byzantine-majority-text',
            notes='Byzantine-priority Greek edition. Edition data, not a manuscript.',
        )
        sbl_count = replace_edition_verses(conn, 'SBLGNT', sbl_rows)
        byz_count = replace_edition_verses(conn, 'RP2018', byz_rows)
        stats = witness_stats(conn)

    print(
        f'Textual Witness Lab ready: SBLGNT {sbl_count:,} verses | '
        f'RP2018 {byz_count:,} verses | {stats["edition_count"]} editions'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
