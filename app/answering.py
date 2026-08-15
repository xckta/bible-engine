from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .providers import OllamaClient, ProviderError
from .retrieval import Passage

Classification = Literal["explicit", "strong_inference", "possible_inference", "not_established"]

class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    classification: Classification

class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim]
    insufficient_evidence: bool = False

SCHEMA = ModelAnswer.model_json_schema()

SYSTEM = """You are a closed-corpus Bible research engine.
Your ONLY evidentiary source is the EVIDENCE supplied in this request. Never use pretrained knowledge, commentary, history, theology, original-language claims, cross references, or facts that are not established by EVIDENCE.
Rules:
1. Every substantive claim must cite one or more supplied evidence IDs.
2. Do not cite IDs that are not supplied.
3. Classify each claim as explicit, strong_inference, possible_inference, or not_established.
4. If the evidence cannot establish the answer, say so and set insufficient_evidence=true.
5. Do not silently infer authorship, dates, cultural background, manuscript facts, or intertextual dependence.
6. Translation differences may be described only from the supplied translations.
7. Keep quotations short; citations identify the exact verse text available to the user.
Do not return any freeform summary field; return only the structured claims and insufficient_evidence fields required by the JSON schema."""

@dataclass(frozen=True)
class AnswerResult:
    summary: str
    claims: list[dict]
    evidence: list[dict]
    mode: str
    insufficient_evidence: bool
    validation_errors: list[str]


def evidence_payload(passages: list[Passage]) -> tuple[str, dict[str, Passage]]:
    mapping = {f"E{i+1}": p for i, p in enumerate(passages)}
    text = "\n".join(f"{eid} | {p.citation} | {p.text}" for eid, p in mapping.items())
    return text, mapping


def validate_answer(answer: ModelAnswer, evidence: dict[str, Passage]) -> list[str]:
    errors: list[str] = []
    valid = set(evidence)
    for i, claim in enumerate(answer.claims, 1):
        unknown = [e for e in claim.evidence_ids if e not in valid]
        if unknown:
            errors.append(f"claim {i} cites unknown evidence IDs: {', '.join(unknown)}")
        if claim.classification != "not_established" and not claim.evidence_ids:
            errors.append(f"claim {i} has no evidence IDs")
    return errors


def render_claim(claim: Claim, mapping: dict[str, Passage]) -> dict:
    cites = [mapping[e].citation for e in claim.evidence_ids if e in mapping]
    return {"text": claim.text, "classification": claim.classification, "citations": cites, "evidence_ids": claim.evidence_ids}


def answer_question(question: str, passages: list[Passage], ollama: OllamaClient | None, generation_enabled: bool = True) -> AnswerResult:
    evidence_text, mapping = evidence_payload(passages)
    evidence_rows = [
        {"id": eid, "citation": p.citation, "text": p.text, "score": round(p.score, 5)}
        for eid, p in mapping.items()
    ]
    if not passages:
        return AnswerResult(
            summary="The loaded Bible corpus did not retrieve evidence sufficient to answer this question.",
            claims=[], evidence=[], mode="no_evidence", insufficient_evidence=True, validation_errors=[]
        )
    if not generation_enabled:
        return AnswerResult(
            summary="Evidence-only mode is enabled. No language-model synthesis was produced.",
            claims=[], evidence=evidence_rows, mode="evidence_only", insufficient_evidence=False, validation_errors=[]
        )
    if not ollama or not ollama.healthy():
        return AnswerResult(
            summary="Ollama is unavailable, so no generated interpretation was produced. Review the retrieved Scripture evidence below.",
            claims=[], evidence=evidence_rows, mode="extractive_fallback", insufficient_evidence=False, validation_errors=[]
        )
    user = f"QUESTION:\n{question}\n\nEVIDENCE:\n{evidence_text}"
    try:
        raw = ollama.chat_json(SYSTEM, user, SCHEMA)
        parsed = ModelAnswer.model_validate(raw)
    except (ProviderError, ValidationError, ValueError) as exc:
        return AnswerResult(
            summary="The language model response failed the closed-corpus response contract. No generated answer is being shown.",
            claims=[], evidence=evidence_rows, mode="rejected_model_output", insufficient_evidence=True,
            validation_errors=[str(exc)]
        )
    errors = validate_answer(parsed, mapping)
    if errors:
        return AnswerResult(
            summary="The language model response failed citation validation. No generated answer is being shown.",
            claims=[], evidence=evidence_rows, mode="rejected_model_output", insufficient_evidence=True,
            validation_errors=errors
        )
    rendered = [render_claim(c, mapping) for c in parsed.claims]
    supported_text = " ".join(c["text"] for c in rendered if c["classification"] != "not_established").strip()
    if supported_text:
        summary = supported_text
    elif parsed.insufficient_evidence:
        summary = "The supplied Scripture evidence does not establish the requested conclusion."
    else:
        summary = "No supported claim was produced from the supplied Scripture evidence."
    return AnswerResult(
        summary=summary,
        claims=rendered,
        evidence=evidence_rows,
        mode="ollama_closed_corpus",
        insufficient_evidence=parsed.insufficient_evidence,
        validation_errors=[],
    )
