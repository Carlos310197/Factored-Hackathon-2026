from dataclasses import dataclass

from bankagent.decisions.jev import JevResult
from bankagent.decisions.thresholds import Thresholds


@dataclass
class VerifyOutcome:
    ok: bool
    failed_claims: list[int]
    promises_unverified: bool


# Third parties (Jev, Bedrock) never get customer or product ids, or fraud signals.
REDACTED_FIELDS = frozenset({"customer_id", "product_id", "is_fraud", "fraud_score"})


def _drop_fraud_triggers(detail: str) -> str:
    # fraud triggers stay in the bank
    return ",".join(t for t in detail.split(",") if not t.startswith("fraud"))


def redact(value):
    if isinstance(value, dict):
        return {k: (_drop_fraud_triggers(v) if k == "detail" and isinstance(v, str) else redact(v))
                for k, v in value.items() if k not in REDACTED_FIELDS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def build_verify_request(
    qset: dict,
    receipts: list[dict],
    claims: list[dict],
    reply_text: str,
) -> tuple[dict, dict]:
    state = {
        "receipts": [redact(r) for r in receipts],
        "claims": claims,
        "reply_text": reply_text,
    }
    
    questions = {}
    
    for i, claim in enumerate(claims):
        instructions = qset["claim_instructions"].format(i=i)
        questions[f"claim_supported_{i}"] = {
            "type": "noul",
            "instructions": instructions,
            "criteria": qset["claim_criteria"],
        }
    
    questions["promises_unverified_action"] = {
        "type": "noul",
        "instructions": qset["promise"]["instructions"],
        "criteria": qset["promise"]["criteria"],
    }
    
    return state, questions


def parse_verify(result: JevResult, th: Thresholds) -> VerifyOutcome:
    answers = result.answers
    
    failed_claims = []
    for key, answer in answers.items():
        if key.startswith("claim_supported_"):
            idx = int(key.split("_")[-1])
            if answer.p < th.claim_supported:
                failed_claims.append(idx)
    
    promises_unverified = False
    if "promises_unverified_action" in answers:
        promises_unverified = answers["promises_unverified_action"].p >= th.promises_unverified_action
    
    ok = len(failed_claims) == 0 and not promises_unverified
    
    return VerifyOutcome(
        ok=ok,
        failed_claims=failed_claims,
        promises_unverified=promises_unverified,
    )
