import pytest

from app.answering import ModelAnswer, Claim, validate_answer, answer_question
from app.providers import ProviderError
from app.retrieval import Passage

P = Passage(id=1, translation="WEB", book="Jude", chapter=1, verse=6, text="Angels ...", score=1)


def test_unknown_evidence_is_rejected():
    a = ModelAnswer(claims=[Claim(text="x", evidence_ids=["E99"], classification="explicit")])
    errors = validate_answer(a, {"E1": P})
    assert errors and "unknown evidence" in errors[0]


def test_missing_evidence_is_rejected():
    a = ModelAnswer(claims=[Claim(text="x", evidence_ids=[], classification="explicit")])
    assert validate_answer(a, {"E1": P})


class FakeUnavailable:
    def chat_json(self, prompt, schema):
        raise ProviderError("Codex unavailable")


def test_codex_is_required_no_fallback():
    with pytest.raises(ProviderError):
        answer_question("what?", [P], FakeUnavailable())


class FakeGood:
    def chat_json(self, prompt, schema):
        assert "EVIDENCE:" in prompt
        return {
            "claims": [
                {
                    "text": "The supplied verse describes angels in relation to a failure to keep their place.",
                    "evidence_ids": ["E1"],
                    "classification": "explicit",
                }
            ],
            "insufficient_evidence": False,
        }


class FakeBad:
    def chat_json(self, prompt, schema):
        return {
            "claims": [
                {
                    "text": "This cites evidence that was never supplied.",
                    "evidence_ids": ["E99"],
                    "classification": "explicit",
                }
            ],
            "insufficient_evidence": False,
        }


def test_valid_codex_output_renders_citation():
    r = answer_question("what?", [P], FakeGood())
    assert r.mode == "codex_closed_corpus"
    assert r.claims[0]["citations"] == ["WEB Jude 1:6"]


def test_invalid_codex_output_is_suppressed():
    r = answer_question("what?", [P], FakeBad())
    assert r.mode == "rejected_codex_output"
    assert r.claims == []
    assert r.validation_errors
