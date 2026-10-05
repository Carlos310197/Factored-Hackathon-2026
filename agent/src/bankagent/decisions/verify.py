"""Build verify_reply requests for Jev and parse responses."""
from dataclasses import dataclass

from bankagent.decisions.jev import JevResult
from bankagent.decisions.thresholds import Thresholds


@dataclass
class VerifyOutcome:
    """Result of verify_reply check."""
    ok: bool
    failed_claims: list[int]
    promises_unverified: bool


# Third parties (Jev, and Bedrock in a second AWS account) never get customer or product ids, or fraud signals.
# Claims are about transactions, amounts, statuses and dispute/complaint/handoff ids, which stay.
REDACTED_FIELDS = frozenset({"customer_id", "product_id", "is_fraud", "fraud_score"})


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k not in REDACTED_FIELDS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def build_verify_request(
    qset: dict,
    receipts: list[dict],
    claims: list[dict],
    reply_text: str,
) -> tuple[dict, dict]:
    """Build the state and questions for a verify_reply request.
    
    Args:
        qset: verify_reply.v1 question set
        receipts: list of receipt dicts
        claims: list of claim dicts with claim_en and receipt_ids
        reply_text: the reply text to verify
    
    Returns:
        (state, questions) tuple
    """
    # Build state
    state = {
        "receipts": [redact(r) for r in receipts],
        "claims": claims,
        "reply_text": reply_text,
    }
    
    # Build questions
    questions = {}
    
    # Add claim_supported_<i> questions
    for i, claim in enumerate(claims):
        instructions = qset["claim_instructions"].format(i=i)
        questions[f"claim_supported_{i}"] = {
            "type": "noul",
            "instructions": instructions,
            "criteria": qset["claim_criteria"],
        }
    
    # Add promises_unverified_action question
    questions["promises_unverified_action"] = {
        "type": "noul",
        "instructions": qset["promise"]["instructions"],
        "criteria": qset["promise"]["criteria"],
    }
    
    return state, questions


def parse_verify(result: JevResult, th: Thresholds) -> VerifyOutcome:
    """Parse a Jev verify result into a VerifyOutcome."""
    answers = result.answers
    
    # Check which claims failed
    failed_claims = []
    for key, answer in answers.items():
        if key.startswith("claim_supported_"):
            idx = int(key.split("_")[-1])
            if answer.p < th.claim_supported:
                failed_claims.append(idx)
    
    # Check if promises are unverified
    promises_unverified = False
    if "promises_unverified_action" in answers:
        promises_unverified = answers["promises_unverified_action"].p >= th.promises_unverified_action
    
    ok = len(failed_claims) == 0 and not promises_unverified
    
    return VerifyOutcome(
        ok=ok,
        failed_claims=failed_claims,
        promises_unverified=promises_unverified,
    )
