from types import SimpleNamespace

from app.answering import answer_question
from app.retrieval import Evidence


class FakeCodex:
    def status(self):
        return SimpleNamespace(ready=True, detail="")

    def chat_json(self, prompt, schema):
        assert "PROJECT CONTEXT — NON-EVIDENTIARY" in prompt
        assert "Pinned finding" in prompt
        assert "EVIDENCE:" in prompt
        return {
            "answer": "ok",
            "claims": [{
                "text": "claim",
                "evidence_ids": ["E1"],
                "classification": "explicit",
                "authority": "canonical",
            }],
            "insufficient_evidence": False,
        }


def test_project_context_is_in_prompt_but_evidence_contract_remains():
    evidence = Evidence("B1", "canonical", "ESV", "Jude", 1, 6, 6, "canonical evidence", 1)
    result = answer_question("question", [evidence], FakeCodex(), project_context="# Context\n- Pinned finding")
    assert result.answer == "ok"
    assert result.claims[0]["citations"] == ["ESV Jude 1:6"]
