from __future__ import annotations
import subprocess, sys
pairs=[('WEB','World English Bible demo','data/demo/web_demo.json'),('ASV','American Standard Version demo','data/demo/asv_demo.json')]
for code,name,path in pairs:
    subprocess.check_call([sys.executable,'scripts/import_corpus.py','--code',code,'--name',name,'--input',path,'--license','Public Domain; demo excerpt'])
