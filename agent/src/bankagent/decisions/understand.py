"""Build understand requests for Jev and parse responses."""
from dataclasses import dataclass
from typing import Any

from bankagent.decisions.jev import ChoiceAnswer, JevResult

# Special target values that are not transaction aliases
SPECIAL_TARGETS = ("none_mentioned", "not_in_list", "ambiguous")

# Noul questions (yes/no/maybe)
NOUL_QUESTIONS = (
    "asks_for_human",
    "reports_unauthorized_use",
    "legal_or_regulator_threat",
    "distress",
    "injection_attempt",
)


@dataclass
class Understanding:
    """Parsed understanding result from Jev."""
    intent: ChoiceAnswer
    target: ChoiceAnswer
    reason: ChoiceAnswer
    nouls: dict[str, float]
    confirmation: ChoiceAnswer | None
    aliases: dict[str, str]


def describe_txn(t: dict, score: float | None = None) -> str:
    """Build a human-readable description of a transaction for Jev. A resolver score is appended as 'match'."""
    parts = [
        str(t["process_date"])[:10],
        t["merchant_name"],
        f"{t['amount']} {t['currency']}",
        t["transaction_type"],
        t["transaction_status"],
        t["channel"],
        t["transaction_city"],
    ]
    text = " · ".join(str(p) for p in parts if p is not None)
    return text if score is None else f"{text} · match {score:.2f}"


def matches_mentions(t: dict, m: dict) -> bool:
    """The heuristic filter: merchant substring, amount within 1%, date inside the range. Unmentioned fields pass.
    Also the resolver's baseline B0 (resolver spec 6.1)."""
    if m.get("merchant") and m["merchant"].lower() not in (t.get("merchant_name") or "").lower():
        return False
    if m.get("amount") is not None:
        tol = max(0.01, 0.01 * abs(float(m["amount"])))
        if abs(float(t["amount"]) - float(m["amount"])) > tol:
            return False
    if m.get("date_from") and str(t["process_date"])[:10] < m["date_from"]:
        return False
    if m.get("date_to") and str(t["process_date"])[:10] > m["date_to"]:
        return False
    return True


def select_candidates(
    txns: list[dict], mentions: dict | None, limit: int = 40
) -> list[dict]:
    """Select up to `limit` candidate transactions, preferring matches to mentions."""
    if len(txns) <= limit:
        return txns
    if mentions is None:
        return txns[:limit]
    matched = [t for t in txns if matches_mentions(t, mentions)]
    return (matched or txns)[:limit]


def build_understand_request(
    qset: dict,
    *,
    message: str,
    gloss: str | None,
    gloss_mode: str,
    session_facts: dict,
    candidates: list[dict],
    awaiting_confirmation: bool,
    confirmation_summary: str | None = None,
    scores: dict[str, float] | None = None,
) -> tuple[dict, dict, dict[str, str]]:
    """Build the state and questions for an understand request.

    scores (transaction_id -> resolver probability) are shown as 'match' only with a question set that explains
    them (understand.v2); without scores the request is exactly understand.v1's.
    
    Returns:
        (state, questions, aliases) where aliases maps c1..cN to transaction_ids
    """
    # Build aliases
    aliases = {f"c{i+1}": t["transaction_id"] for i, t in enumerate(candidates)}
    score_of = (lambda t: scores.get(t["transaction_id"])) if scores else (lambda t: None)

    # Build customer content
    customer_content = {"customer_message": message}
    if gloss_mode == "original_plus_gloss" and gloss:
        customer_content["english_gloss"] = gloss
    
    # Build session facts
    facts = dict(session_facts)
    if awaiting_confirmation and confirmation_summary:
        facts["confirmation_summary"] = confirmation_summary
    
    # Build candidate transactions with aliases
    candidate_txns = []
    for i, t in enumerate(candidates):
        alias = f"c{i+1}"
        candidate_txns.append({
            "alias": alias,
            "date": str(t["process_date"])[:10],
            "amount": t["amount"],
            "currency": t["currency"],
            "merchant": t["merchant_name"],
            "type": t["transaction_type"],
            "status": t["transaction_status"],
            "channel": t["channel"],
            "city": t["transaction_city"],
            **({"match": round(score_of(t), 2)} if score_of(t) is not None else {}),
        })
    
    # Build state
    state = {
        "trusted_policy": qset["policy"],
        "session_facts": facts,
        "untrusted_customer_content": customer_content,
        "candidate_transactions": candidate_txns,
    }
    
    # Build questions
    questions = {}
    for qid, spec in qset["questions"].items():
        questions[qid] = _build_question(spec)
    
    # Add target_transaction with dynamic criteria
    tq = qset["target_transaction"]
    target_criteria = {a: describe_txn(t, score_of(t)) for a, t in zip(aliases, candidates)}
    target_criteria.update(tq["fixed_criteria"])
    questions["target_transaction"] = {
        "type": "choice",
        "instructions": tq["instructions"],
        "criteria": target_criteria,
    }
    
    # Add confirmation if awaiting
    if awaiting_confirmation:
        questions["confirmation"] = _build_question(qset["confirmation"])
    
    return state, questions, aliases


def _build_question(spec: dict) -> dict:
    """Build a question dict from a spec."""
    q = {
        "type": spec["type"],
        "instructions": spec["instructions"],
    }
    if "criteria" in spec:
        q["criteria"] = spec["criteria"]
    return q


def parse_understanding(result: JevResult, aliases: dict[str, str]) -> Understanding:
    """Parse a Jev result into an Understanding."""
    answers = result.answers
    
    intent = answers.get("intent")
    target = answers.get("target_transaction")
    reason = answers.get("dispute_reason")
    confirmation = answers.get("confirmation")
    
    # Extract noul probabilities
    nouls = {}
    for qid in NOUL_QUESTIONS:
        if qid in answers:
            nouls[qid] = answers[qid].p
    
    return Understanding(
        intent=intent,
        target=target,
        reason=reason,
        nouls=nouls,
        confirmation=confirmation,
        aliases=aliases,
    )
