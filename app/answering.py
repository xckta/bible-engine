from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .providers import CodexClient, ProviderError
from .retrieval import Evidence

Classification = Literal["explicit", "strong_inference", "possible_inference", "not_established"]
Authority = Literal["canonical", "deuterocanon", "reference", "supplemental", "mixed"]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_ids: list[str]
    classification: Classification
    authority: Authority


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    claims: list[Claim]
    insufficient_evidence: bool


def _strict_output_schema(schema: dict) -> dict:
    def walk(node):
        if isinstance(node, dict):
            out = {k: walk(v) for k, v in node.items() if k != "default"}
            props = out.get("properties")
            if isinstance(props, dict):
                out["required"] = list(props.keys())
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


SCHEMA = _strict_output_schema(ModelAnswer.model_json_schema())

SYSTEM = """BIBLE ENGINE // CLOSED-CORPUS RESEARCH PROTOCOL

You are the synthesis layer for a Bible research instrument. The prompt may supply four explicitly separated evidence tiers.

AUTHORITY RULES
A. CANONICAL SCRIPTURE: 66-book Protestant canon, displayed in ESV. This is the highest evidentiary tier.
B. DEUTEROCANON/APOCRYPHA: separately labelled historical/religious texts whose canonical status varies by Christian tradition.
C. REFERENCE LITERATURE: Second Temple / pseudepigraphal / related ancient literature. It may illuminate concepts, vocabulary, traditions, and intertextual background, but it is never to be called canonical Scripture.
D. SUPPLEMENTAL USER CORPUS: material the user imported into the Vault, such as scholarship, lexicons, ancient-source editions, or personal notes. It may be cited only as supplemental evidence and can never establish what canonical Scripture itself says.

HARD CONSTRAINTS
1. Use ONLY the supplied EVIDENCE as evidence. No web, commentary, memory, original-language knowledge, chronology, authorship claims, or theological facts unless explicitly present in EVIDENCE.
2. Every substantive claim must cite one or more supplied evidence IDs.
3. Never invent evidence IDs or citations.
4. A claim labelled authority=canonical must be supported exclusively by CANONICAL evidence IDs.
5. Do not use deuterocanon/reference/supplemental evidence to prove that canonical Scripture says something it does not say. Instead describe parallels, developments, interpretations, or contextual claims only when the supplied evidence supports that wording.
6. When evidence tiers differ, name the distinction explicitly.
7. Classify each claim: explicit, strong_inference, possible_inference, or not_established.
8. If the evidence does not establish a conclusion, say so and set insufficient_evidence=true.
9. Keep direct quotation modest; the UI separately displays the exact evidence text and citation.
10. The answer field should be a concise integrated synthesis, not a sermon and not a list of uncited outside facts.
11. PROJECT CONTEXT, when supplied, is continuity/navigation only. It is NOT evidence, cannot support a claim, and must never be cited as though it were Scripture or an ancient source. Fresh EVIDENCE IDs remain mandatory.
12. Return ONLY the JSON object required by the output schema.
"""


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    claims: list[dict]
    evidence: list[dict]
    mode: str
    insufficient_evidence: bool
    validation_errors: list[str]


def _tier_label(e: Evidence) -> str:
    return {
        "canonical": "CANONICAL",
        "deuterocanon": "DEUTEROCANON",
        "pseudepigrapha": "REFERENCE",
        "vault": "SUPPLEMENTAL",
    }.get(e.tier, e.tier.upper())


def evidence_payload(evidence: list[Evidence]) -> tuple[str, dict[str, Evidence]]:
    mapping = {f"E{i + 1}": e for i, e in enumerate(evidence)}
    lines = [f"{eid} | {_tier_label(e)} | {e.citation} | {e.text}" for eid, e in mapping.items()]
    return "\n".join(lines), mapping


def validate_answer(answer: ModelAnswer, evidence: dict[str, Evidence]) -> list[str]:
    errors: list[str] = []
    valid = set(evidence)
    for i, claim in enumerate(answer.claims, 1):
        unknown = [eid for eid in claim.evidence_ids if eid not in valid]
        if unknown:
            errors.append(f"claim {i} cites unknown evidence IDs: {', '.join(unknown)}")
            continue
        if claim.classification != "not_established" and not claim.evidence_ids:
            errors.append(f"claim {i} has no evidence IDs")
        tiers = {evidence[eid].tier for eid in claim.evidence_ids if eid in evidence}
        if claim.authority == "canonical" and tiers - {"canonical"}:
            errors.append(f"claim {i} labels noncanonical evidence as canonical authority")
        if claim.authority == "deuterocanon" and tiers and not tiers <= {"deuterocanon"}:
            errors.append(f"claim {i} has mismatched deuterocanon authority")
        if claim.authority == "reference" and tiers and not tiers <= {"pseudepigrapha"}:
            errors.append(f"claim {i} has mismatched reference authority")
        if claim.authority == "supplemental" and tiers and not tiers <= {"vault"}:
            errors.append(f"claim {i} has mismatched supplemental authority")
    return errors


def _render_claim(claim: Claim, mapping: dict[str, Evidence]) -> dict:
    rows = [mapping[eid] for eid in claim.evidence_ids if eid in mapping]
    return {
        "text": claim.text,
        "classification": claim.classification,
        "authority": claim.authority,
        "evidence_ids": claim.evidence_ids,
        "citations": [e.citation for e in rows],
    }


def answer_question(
    question: str,
    evidence: list[Evidence],
    codex: CodexClient,
    project_context: str = "",
) -> AnswerResult:
    evidence_rows = []
    payload, mapping = evidence_payload(evidence)
    for eid, e in mapping.items():
        evidence_rows.append({
            "id": eid,
            "tier": e.tier,
            "source": e.source,
            "citation": e.citation,
            "work": e.work,
            "text": e.text,
            "source_label": e.source_label,
            "source_url": e.source_url,
            "score": round(e.score, 5),
        })
    if not evidence:
        return AnswerResult(
            answer="The installed corpus did not retrieve enough evidence for that question.", claims=[], evidence=[],
            mode="no_evidence", insufficient_evidence=True, validation_errors=[]
        )
    status = codex.status()
    if not status.ready:
        raise ProviderError(status.detail or "Codex CLI is required and could not be started.")

    context_block = ""
    if project_context.strip():
        context_block = (
            "\n\nPROJECT CONTEXT — NON-EVIDENTIARY CONTINUITY ONLY:\n"
            + project_context.strip()
            + "\n\nEND PROJECT CONTEXT\n"
        )
    prompt = f"{SYSTEM}{context_block}\n\nUSER QUESTION:\n{question}\n\nEVIDENCE:\n{payload}\n"
    try:
        raw = codex.chat_json(prompt, SCHEMA)
        parsed = ModelAnswer.model_validate(raw)
    except ValidationError as exc:
        return AnswerResult(
            answer="Codex returned output that violated the Bible Engine schema, so it was suppressed.", claims=[],
            evidence=evidence_rows, mode="rejected_codex_output", insufficient_evidence=True,
            validation_errors=[str(exc)],
        )
    errors = validate_answer(parsed, mapping)
    if errors:
        return AnswerResult(
            answer="Codex failed Bible Engine's citation/authority validation, so the generated synthesis was suppressed.",
            claims=[], evidence=evidence_rows, mode="rejected_codex_output", insufficient_evidence=True,
            validation_errors=errors,
        )
    return AnswerResult(
        answer=parsed.answer.strip(), claims=[_render_claim(c, mapping) for c in parsed.claims],
        evidence=evidence_rows, mode="codex_closed_corpus", insufficient_evidence=parsed.insufficient_evidence,
        validation_errors=[],
    )
