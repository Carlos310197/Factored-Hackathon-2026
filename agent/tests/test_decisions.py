import json

from bankagent.decisions.jev import JevResult, validate_answers
from bankagent.decisions.questions import load_question_set
from bankagent.decisions.thresholds import load_thresholds
from bankagent.decisions.understand import (SPECIAL_TARGETS, build_understand_request, describe_txn,
                                            parse_understanding, select_candidates)
from bankagent.decisions.verify import build_verify_request, parse_verify

QS = load_question_set("understand.v1")
VQS = load_question_set("verify_reply.v1")
TH = load_thresholds()


def txn(i, merchant="Netflix", amount=15.99, day="2026-06-10"):
    return {"transaction_id": f"TRX-T{i:019d}", "customer_id": "CLI-SECRET00001", "product_id": "PRD-SECRET0001",
            "process_date": day, "transaction_ts": f"{day}T20:00:00", "merchant_name": merchant, "amount": amount,
            "currency": "USD", "transaction_type": "Purchase", "transaction_status": "Approved", "channel": "Web",
            "transaction_city": "Ciudad de México"}


def build(**over):
    kw = dict(message="me cobraron doble netflix", gloss="EN: charged twice netflix", gloss_mode="original_plus_gloss",
              session_facts={"awaiting": "none"}, candidates=[txn(1), txn(2, "Amazon", 120.0)],
              awaiting_confirmation=False, confirmation_summary=None)
    return build_understand_request(QS, **{**kw, **over})


def test_versions_load():
    assert QS["version"] == "understand.v1" and VQS["version"] == "verify_reply.v1" and TH.version == "thresholds.v1"
    assert TH.intent_min_p == 0.80 and TH.handoff_noul["asks_for_human"] == 0.60 and TH.max_clarifications == 2


def test_request_uses_aliases_and_never_sends_ids():
    state, questions, aliases = build()
    assert aliases == {"c1": "TRX-T0000000000000000001", "c2": "TRX-T0000000000000000002"}
    dumped = json.dumps(state) + json.dumps(questions)
    assert "TRX-" not in dumped and "CLI-" not in dumped and "PRD-" not in dumped
    crit = questions["target_transaction"]["criteria"]
    assert crit["c1"] == describe_txn(txn(1)) and set(SPECIAL_TARGETS) <= set(crit)
    assert state["trusted_policy"] == QS["policy"]
    assert state["untrusted_customer_content"] == {"customer_message": "me cobraron doble netflix",
                                                   "english_gloss": "EN: charged twice netflix"}
    assert "confirmation" not in questions and set(questions) >= {"intent", "dispute_reason", "injection_attempt"}


def test_original_only_mode_drops_gloss():
    state, _, _ = build(gloss_mode="original_only")
    assert "english_gloss" not in state["untrusted_customer_content"]


def test_confirmation_question_only_when_awaiting():
    state, questions, _ = build(awaiting_confirmation=True, confirmation_summary="Resumen…")
    assert "confirmation" in questions and state["session_facts"]["confirmation_summary"] == "Resumen…"


def test_select_candidates_keeps_all_when_under_limit():
    txns = [txn(i) for i in range(10)]
    assert select_candidates(txns, None) == txns


def test_select_candidates_prefilters_by_mentions_when_over_limit():
    txns = [txn(i, f"Shop{i}", 10.0 + i) for i in range(50)]
    picked = select_candidates(txns, {"merchant": "shop45", "amount": None, "date_from": None, "date_to": None})
    assert [t["merchant_name"] for t in picked] == ["Shop45"]
    by_amount = select_candidates(txns, {"merchant": None, "amount": 57.0, "date_from": None, "date_to": None})
    assert [t["merchant_name"] for t in by_amount] == ["Shop47"]


def test_select_candidates_falls_back_to_most_recent_when_nothing_matches():
    txns = [txn(i, f"Shop{i}") for i in range(50)]
    assert select_candidates(txns, {"merchant": "nowhere", "amount": None, "date_from": None, "date_to": None}) == txns[:40]


def test_parse_understanding():
    _, questions, aliases = build()
    body = {"answers": {
        "intent": {"type": "choice", "choice": "dispute_charge", "probabilities": {"dispute_charge": 0.9, "unclear": 0.1}},
        "target_transaction": {"type": "choice", "choice": "c1", "probabilities": {"c1": 0.9, "c2": 0.1}},
        "dispute_reason": {"type": "choice", "choice": "duplicate_charge", "probabilities": {"duplicate_charge": 1.0}},
        **{q: {"type": "noul", "noul": 0.1} for q in ("asks_for_human", "reports_unauthorized_use",
                                                     "legal_or_regulator_threat", "distress", "injection_attempt")}}}
    u = parse_understanding(JevResult(validate_answers(questions, body), {}, 1, "h", "m"), aliases)
    assert u.intent.label == "dispute_charge" and u.aliases["c1"] == "TRX-T0000000000000000001"
    assert u.nouls["distress"] == 0.1 and u.confirmation is None


def test_verify_request_and_parse():
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17", "data": []}]
    claims = [{"claim_en": "Balance is 10 USD", "receipt_ids": ["RCP-1"]}, {"claim_en": "Refund in 3 days", "receipt_ids": []}]
    state, questions = build_verify_request(VQS, receipts, claims, "Tu saldo es 10 USD")
    assert set(questions) == {"claim_supported_0", "claim_supported_1", "promises_unverified_action"}
    assert "claim 1" in questions["claim_supported_1"]["instructions"] and state["reply_text"] == "Tu saldo es 10 USD"
    body = {"answers": {"claim_supported_0": {"type": "noul", "noul": 0.95},
                        "claim_supported_1": {"type": "noul", "noul": 0.2},
                        "promises_unverified_action": {"type": "noul", "noul": 0.7}}}
    out = parse_verify(JevResult(validate_answers(questions, body), {}, 1, "h", "m"), TH)
    assert out.ok is False and out.failed_claims == [1] and out.promises_unverified is True
