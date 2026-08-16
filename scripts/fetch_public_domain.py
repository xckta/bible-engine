from __future__ import annotations
import io, urllib.request, zipfile
from pathlib import Path
SOURCES={
 'WEB':'https://ebible.org/Scriptures/eng-web_usfm.zip',
 'ASV':'https://ebible.org/Scriptures/eng-asv_usfm.zip',
}
out=Path('data/sources');out.mkdir(parents=True,exist_ok=True)
for code,url in SOURCES.items():
    target=out/code.lower(); target.mkdir(parents=True,exist_ok=True)
    if any(target.rglob('*.usfm')) or any(target.rglob('*.sfm')):
        print(f'{code} source already present: {target}');continue
    print(f'Downloading {code} from {url}')
    req=urllib.request.Request(url,headers={'User-Agent':'BibleEngine/0.3'})
    with urllib.request.urlopen(req,timeout=90) as r: payload=r.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        root=target.resolve()
        for member in z.infolist():
            dest=(target/member.filename).resolve()
            if root != dest and root not in dest.parents: raise RuntimeError(f'Unsafe archive path: {member.filename}')
            z.extract(member,target)
    print(f'Extracted {code} to {target}')
