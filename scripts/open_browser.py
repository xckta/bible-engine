from __future__ import annotations
import time,urllib.request,webbrowser
url='http://127.0.0.1:8000'
for _ in range(40):
    try:
        with urllib.request.urlopen(url+'/api/health',timeout=.5) as r:
            if r.status==200: break
    except Exception: time.sleep(.25)
webbrowser.open(url)
