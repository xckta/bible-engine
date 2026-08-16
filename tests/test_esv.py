import json
from types import SimpleNamespace
from app.esv import ESVClient

class Response:
    status=200
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self):return json.dumps({'passages':['John 1:1\n\n[1] In the beginning was the Word. (ESV)','Genesis 1:1\n\n[1] In the beginning... (ESV)']}).encode()

def test_esv_batches_references(monkeypatch):
    seen={}
    def fake(req,timeout):seen['url']=req.full_url;seen['auth']=req.headers['Authorization'];return Response()
    monkeypatch.setattr('app.esv.urllib.request.urlopen',fake)
    rows=ESVClient('abc').fetch_many(['John 1:1','Genesis 1:1'])
    assert len(rows)==2 and rows[0].text.endswith('(ESV)')
    assert 'John+1%3A1%3BGenesis+1%3A1' in seen['url'] or 'John+1%3A1%3BGenesis+1%3A1' in seen['url'].replace('%3b','%3B')
    assert seen['auth']=='Token abc'
