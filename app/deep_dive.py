from __future__ import annotations

from pydantic import BaseModel,ConfigDict,Field,ValidationError

from .answering import _strict_output_schema
from .providers import CodexClient,ProviderError

class ResearchQuestion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str
    purpose:str
    shelf_focus:str

class ResearchPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str
    questions:list[ResearchQuestion]
    caution:str

PLAN_SCHEMA=_strict_output_schema(ResearchPlan.model_json_schema())
PLAN_PROMPT="""BIBLE ENGINE // CLOSED-CORPUS RESEARCH PLANNER
Create a compact research plan for the user's biblical research question.
You are planning searches only; you are NOT answering the question.
Rules:
1. Produce 3–6 targeted subquestions.
2. Include at least one canonical-explicit-text angle.
3. When relevant, include a canonical-parallel angle and a separately labelled ancient-reference-context angle.
4. Do not assume a theological conclusion in the questions.
5. shelf_focus must be one of: canonical, canonical_parallel, deuterocanon, reference, mixed.
6. caution must identify the main methodological risk (for example circular reasoning, chronology, lexical overreach, or conflating reference literature with canon).
Return only schema-valid JSON."""

def build_plan(codex:CodexClient,thesis:str)->ResearchPlan:
    raw=codex.chat_json(f"{PLAN_PROMPT}\n\nRESEARCH QUESTION:\n{thesis.strip()}\n",PLAN_SCHEMA)
    try:plan=ResearchPlan.model_validate(raw)
    except ValidationError as exc:raise ProviderError(f'Deep Dive planner returned invalid structured output: {exc}') from exc
    plan.questions=plan.questions[:6]
    if len(plan.questions)<3:raise ProviderError('Deep Dive planner returned fewer than three research questions.')
    return plan

def plan_dict(plan:ResearchPlan)->dict:return plan.model_dump()
