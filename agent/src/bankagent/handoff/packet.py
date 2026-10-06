"""handoff.v1: the structured packet a human agent receives. Facts come only from receipts."""
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from bankagent.ids import new_id

CRITICAL = {"reports_unauthorized_use", "unauthorized_reason", "fraud_flag", "fraud_score_high"}
HIGH = {"legal_or_regulator_threat", "injection_repeated"}


class Bilingual(BaseModel):
    original: str
    en: str


class Fact(BaseModel):
    fact: str
    receipt_id: str


class Action(BaseModel):
    action: str
    result: str
    receipt_id: str | None = None


class DecisionRef(BaseModel):
    question: str
    value: str | float
    p: float | None = None
    question_set: str
    thresholds: str


class PolicyCheck(BaseModel):
    rule: str
    passed: bool
    detail: str = ""


class HandoffPacket(BaseModel):
    schema_version: Literal["handoff.v1"] = "handoff.v1"
    handoff_id: str
    created_at: str
    status: Literal["open"] = "open"
    session_id: str
    customer_id: str
    language: Literal["es", "pt"]
    data_as_of: str
    priority: Literal["critical", "high", "medium"]
    reason_codes: list[str]
    customer_request: Bilingual
    verified_facts: list[Fact]
    actions_taken: list[Action]
    decisions: list[DecisionRef]
    policy_checks: list[PolicyCheck]
    open_questions: list[str] = Field(max_length=3)
    transcript_ref: str


def priority_for(codes) -> str:
    codes = set(codes)
    if codes & CRITICAL:
        return "critical"
    if codes & HIGH:
        return "high"
    return "medium"


def _describe(receipt: dict) -> str:
    return f"{receipt['source']}: {json.dumps(receipt['data'], ensure_ascii=False, default=str)[:400]}"


def build_packet(*, session_id: str, customer_id: str, language: str, data_as_of: str, reason_codes: list[str],
                 customer_request: dict, receipts: list[dict], actions: list[dict], decisions: list[dict],
                 policy_checks: list[dict], open_questions: list[str], now: datetime) -> HandoffPacket:
    return HandoffPacket(
        handoff_id=new_id("HND"), created_at=now.isoformat(), session_id=session_id, customer_id=customer_id,
        language=language, data_as_of=data_as_of, priority=priority_for(reason_codes), reason_codes=reason_codes,
        customer_request=Bilingual(**customer_request),
        verified_facts=[Fact(fact=_describe(r), receipt_id=r["receipt_id"]) for r in receipts],
        actions_taken=[Action(**a) for a in actions], decisions=[DecisionRef(**d) for d in decisions],
        policy_checks=[PolicyCheck(rule=c["name"], passed=c["passed"], detail=c.get("detail", "")) for c in policy_checks],
        open_questions=open_questions, transcript_ref=f"session:{session_id}")
