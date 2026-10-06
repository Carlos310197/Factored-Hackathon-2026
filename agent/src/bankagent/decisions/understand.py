from dataclasses import dataclass
from typing import Any

from bankagent.decisions.jev import ChoiceAnswer, JevResult

SPECIAL_TARGETS = ("none_mentioned", "not_in_list", "ambiguous")

NOUL_QUESTIONS = (
    "asks_for_human",
    "reports_unauthorized_use",
    "legal_or_regulator_threat",
    "distress",
    "injection_attempt",
)


@dataclass
class Understanding:
    intent: ChoiceAnswer
    target: ChoiceAnswer
    reason: ChoiceAnswer
    nouls: dict[str, float]
    confirmation: ChoiceAnswer | None
    aliases: dict[str, str]


def describe_txn(t: dict, score: float | None = None) -> str:
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
    """Scores are shown as 'match' only with a question set that explains them."""
    aliases = {f"c{i+1}": t["transaction_id"] for i, t in enumerate(candidates)}
    score_of = (lambda t: scores.get(t["transaction_id"])) if scores else (lambda t: None)

    customer_content = {"customer_message": message}
    if gloss_mode == "original_plus_gloss" and gloss:
        customer_content["english_gloss"] = gloss
    
    facts = dict(session_facts)
    if awaiting_confirmation and confirmation_summary:
        facts["confirmation_summary"] = confirmation_summary
    
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
    
    state = {
        "trusted_policy": qset["policy"],
        "session_facts": facts,
        "untrusted_customer_content": customer_content,
        "candidate_transactions": candidate_txns,
    }
    
    questions = {}
    for qid, spec in qset["questions"].items():
        questions[qid] = _build_question(spec)
    
    tq = qset["target_transaction"]
    target_criteria = {a: describe_txn(t, score_of(t)) for a, t in zip(aliases, candidates)}
    target_criteria.update(tq["fixed_criteria"])
    questions["target_transaction"] = {
        "type": "choice",
        "instructions": tq["instructions"],
        "criteria": target_criteria,
    }
    
    if awaiting_confirmation:
        questions["confirmation"] = _build_question(qset["confirmation"])
    
    return state, questions, aliases


def _build_question(spec: dict) -> dict:
    q = {
        "type": spec["type"],
        "instructions": spec["instructions"],
    }
    if "criteria" in spec:
        q["criteria"] = spec["criteria"]
    return q


def parse_understanding(result: JevResult, aliases: dict[str, str]) -> Understanding:
    answers = result.answers
    
    intent = answers.get("intent")
    target = answers.get("target_transaction")
    reason = answers.get("dispute_reason")
    confirmation = answers.get("confirmation")
    
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
