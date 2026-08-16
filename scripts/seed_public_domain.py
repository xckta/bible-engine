from __future__ import annotations
import subprocess,sys
from pathlib import Path
pairs=[
 ('WEB','World English Bible Classic + Deuterocanon/Apocrypha','data/sources/web','Public Domain','https://ebible.org/eng-web/'),
 ('ASV','American Standard Version (1901)','data/sources/asv','Public Domain','https://ebible.org/eng-asv/'),
]
for code,name,path,lic,url in pairs:
    if not Path(path).exists(): raise SystemExit(f'Missing {path}; run scripts/fetch_public_domain.py first')
    subprocess.check_call([sys.executable,'scripts/import_corpus.py','--code',code,'--name',name,'--input',path,'--license',lic,'--source-url',url])
