from app.answering import ModelAnswer, Claim, validate_answer, answer_question
from app.retrieval import Passage

P=Passage(id=1,translation='WEB',book='Jude',chapter=1,verse=6,text='Angels ...',score=1)

def test_unknown_evidence_is_rejected():
    a=ModelAnswer(claims=[Claim(text='x',evidence_ids=['E99'],classification='explicit')])
    errors=validate_answer(a,{'E1':P})
    assert errors and 'unknown evidence' in errors[0]

def test_missing_evidence_is_rejected():
    a=ModelAnswer(claims=[Claim(text='x',evidence_ids=[],classification='explicit')])
    assert validate_answer(a,{'E1':P})

def test_no_ollama_is_extractive():
    r=answer_question('what?', [P], None)
    assert r.mode=='extractive_fallback'
    assert r.claims==[]
    assert r.evidence[0]['citation']=='WEB Jude 1:6'

class FakeGood:
    def healthy(self): return True
    def chat_json(self, system, user, schema):
        return {
            'claims':[{'text':'The angels did not keep their domain.','evidence_ids':['E1'],'classification':'explicit'}],
            'insufficient_evidence':False,
        }

class FakeBad:
    def healthy(self): return True
    def chat_json(self, system, user, schema):
        return {
            'claims':[{'text':'This cites evidence that was never supplied.','evidence_ids':['E99'],'classification':'explicit'}],
            'insufficient_evidence':False,
        }

def test_valid_model_output_renders_citation():
    r=answer_question('what?', [P], FakeGood())
    assert r.mode=='ollama_closed_corpus'
    assert r.claims[0]['citations']==['WEB Jude 1:6']

def test_invalid_model_output_is_suppressed():
    r=answer_question('what?', [P], FakeBad())
    assert r.mode=='rejected_model_output'
    assert r.claims==[]
    assert r.validation_errors
