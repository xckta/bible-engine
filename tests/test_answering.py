from types import SimpleNamespace
from app.answering import ModelAnswer,Claim,SCHEMA,answer_question,validate_answer
from app.retrieval import Evidence

CAN=Evidence('B1','canonical','ESV','Jude',1,6,6,'canonical text',10)
REF=Evidence('R1','pseudepigrapha','Charles','1 Enoch',6,1,1,'reference text',8)

class Fake:
    def status(self):return SimpleNamespace(ready=True,detail='')
    def chat_json(self,prompt,schema):
        assert 'CANONICAL' in prompt and 'REFERENCE' in prompt
        return {'answer':'Jude states X; Enoch provides context.','claims':[
            {'text':'Jude states X.','evidence_ids':['E1'],'classification':'explicit','authority':'canonical'},
            {'text':'Enoch provides context.','evidence_ids':['E2'],'classification':'explicit','authority':'reference'}],
            'insufficient_evidence':False}

def test_valid_tiered_answer():
    r=answer_question('q',[CAN,REF],Fake())
    assert r.mode=='codex_closed_corpus';assert r.claims[0]['authority']=='canonical';assert r.evidence[0]['source']=='ESV'

def test_reference_cannot_masquerade_as_canonical():
    a=ModelAnswer(answer='x',claims=[Claim(text='x',evidence_ids=['E2'],classification='explicit',authority='canonical')],insufficient_evidence=False)
    errs=validate_answer(a,{'E1':CAN,'E2':REF})
    assert any('noncanonical' in x for x in errs)


def test_codex_output_schema_requires_every_object_property():
    def walk(node):
        if isinstance(node, dict):
            props=node.get('properties')
            if isinstance(props,dict):
                assert set(node.get('required',[]))==set(props)
                assert node.get('additionalProperties') is False
            assert 'default' not in node
            for value in node.values():walk(value)
        elif isinstance(node,list):
            for value in node:walk(value)
    walk(SCHEMA)
    claim=SCHEMA['$defs']['Claim']
    assert 'evidence_ids' in claim['required']
    assert 'insufficient_evidence' in SCHEMA['required']
