from dataclasses import replace

from bankagent.decisions.jev import ChoiceAnswer
from bankagent.decisions.routing import Counters, decide
from bankagent.decisions.thresholds import load_thresholds
from bankagent.decisions.understand import NOUL_QUESTIONS, Understanding

TH = load_thresholds()
ALIASES = {"c1": "TRX-A", "c2": "TRX-B", "c3": "TRX-C"}
INTENTS = ["account_info", "transaction_status", "decline_explanation", "dispute_charge", "dispute_status",
           "greeting_or_thanks", "unsupported", "unclear"]
REASONS = ["duplicate_charge", "wrong_amount", "not_received", "cancelled_but_charged", "unauthorized", "unclear"]
TARGETS = ["c1", "c2", "c3", "none_mentioned", "not_in_list", "ambiguous"]
CONF = ["confirm", "reject", "modify", "unclear"]


def ch(label, labels, p=0.95, second=None, second_p=0.0):
    probs = {label: p}
    if second:
        probs[second] = second_p
    rest = [x for x in labels if x not in probs]
    left = max(0.0, 1.0 - sum(probs.values()))
    probs.update({x: left / len(rest) for x in rest})
    return ChoiceAnswer(label, probs)


def U(intent="account_info", ip=0.95, second=None, sp=0.0, target="none_mentioned", tp=0.95, tsecond=None, tsp=0.0,
      reason="unclear", rp=0.95, confirmation=None, cp=0.95, **nouls):
    base = {q: 0.02 for q in NOUL_QUESTIONS}
    base.update(nouls)
    return Understanding(ch(intent, INTENTS, ip, second, sp), ch(target, TARGETS, tp, tsecond, tsp),
                         ch(reason, REASONS, rp), base, ch(confirmation, CONF, cp) if confirmation else None, ALIASES)


def go(u, awaiting="none", counters=Counters(), pending=None):
    return decide(u, TH, awaiting, counters, pending or {})


def test_jev_failure_first_clarifies_then_hands_off():
    r = go(None)
    assert r.next == "clarify" and r.goal["topic"] == "repeat" and r.counters.jev_failures == 1
    r2 = go(None, counters=r.counters)
    assert r2.next == "handoff" and r2.reasons == ("jev_unavailable",)


def test_jev_failure_during_confirmation_reasks_without_filing():
    r = go(None, awaiting="confirmation")
    assert r.next == "confirm" and r.counters.confirm_asks == 1


def test_unauthorized_report_hands_off():
    r = go(U(reports_unauthorized_use=0.55))
    assert r.next == "handoff" and r.reasons == ("reports_unauthorized_use",)


def test_unauthorized_dispute_with_known_target_is_drafted_for_human_review():
    r = go(U("dispute_charge", target="c1", reports_unauthorized_use=0.9))
    assert r.next == "resolve_transaction" and r.escalated is True
    assert r.target_txn_id == "TRX-A" and r.dispute_reason == "unauthorized" and "reports_unauthorized_use" in r.reasons


def test_asks_for_human_threshold():
    assert go(U(asks_for_human=0.59)).next == "answer_inquiry"
    assert go(U(asks_for_human=0.61)).next == "handoff"


def test_legal_threat_hands_off():
    assert go(U(legal_or_regulator_threat=0.5)).reasons == ("legal_or_regulator_threat",)


def test_injection_refused_first_then_handoff():
    r = go(U(injection_attempt=0.6))
    assert r.next == "reply" and r.goal["kind"] == "refuse_injection" and r.counters.injections == 1
    r2 = go(U(injection_attempt=0.6), counters=r.counters)
    assert r2.next == "handoff" and r2.reasons == ("injection_repeated",)


def test_low_margin_intent_clarifies_with_top_two():
    r = go(U("account_info", ip=0.5, second="transaction_status", sp=0.45))
    assert r.next == "clarify" and r.goal == {"kind": "ask_clarification", "topic": "intent",
                                              "options": ["account_info", "transaction_status"]}


def test_third_clarification_hands_off():
    r = go(U("unclear", ip=0.9), counters=Counters(clarify=2))
    assert r.next == "handoff" and r.reasons == ("clarification_limit",)


def test_greeting_and_unsupported():
    assert go(U("greeting_or_thanks")).goal == {"kind": "greeting"}
    r = go(U("unsupported"))
    assert r.next == "reply" and r.goal == {"kind": "abstain", "offer_human": True} and r.reasons == ("unsupported",)


def test_decline_explanation_with_confident_target():
    r = go(U("decline_explanation", target="c2"))
    assert r.next == "answer_inquiry" and r.intent == "decline_explanation" and r.target_txn_id == "TRX-B"


def test_uncertain_target_clarifies_with_top_three_ids():
    r = go(U("transaction_status", target="c1", tp=0.5, tsecond="c2", tsp=0.4))
    assert r.next == "clarify" and r.goal["topic"] == "transaction"
    assert r.goal["options"][:2] == ["TRX-A", "TRX-B"] and len(r.goal["options"]) == 3


def test_dispute_without_reason_asks_reason_and_keeps_target():
    r = go(U("dispute_charge", target="c3"))
    assert r.next == "clarify" and r.goal["topic"] == "dispute_reason" and r.target_txn_id == "TRX-C"


def test_pending_intent_target_and_reason_are_carried():
    pending = {"intent": "dispute_charge", "target_txn_id": "TRX-C", "dispute_reason": None}
    r = go(U("unclear", ip=0.6, target="none_mentioned", reason="duplicate_charge"), pending=pending)
    assert r.next == "resolve_transaction" and r.target_txn_id == "TRX-C" and r.dispute_reason == "duplicate_charge"


def test_dispute_with_target_and_reason_resolves():
    r = go(U("dispute_charge", target="c1", reason="duplicate_charge"), counters=Counters(clarify=1))
    assert r.next == "resolve_transaction" and r.counters.clarify == 0


def test_confirmation_outcomes():
    assert go(U(confirmation="confirm", cp=0.95), awaiting="confirmation").next == "file_dispute"
    low = go(U(confirmation="confirm", cp=0.85), awaiting="confirmation")
    assert low.next == "confirm" and low.counters.confirm_asks == 1
    assert go(U(confirmation="reject"), awaiting="confirmation").goal == {"kind": "dispute_cancelled"}
    mod = go(U(confirmation="modify"), awaiting="confirmation")
    assert mod.next == "clarify" and mod.goal["topic"] == "dispute_change"
    gave_up = go(U(confirmation="unclear", cp=0.9), awaiting="confirmation", counters=Counters(confirm_asks=2))
    assert gave_up.next == "handoff" and gave_up.reasons == ("confirmation_unclear",)


def test_distress_offers_human_without_changing_route():
    r = go(U(distress=0.7))
    assert r.next == "answer_inquiry" and r.offer_human is True


def test_success_resets_jev_failure_counter():
    assert go(U(), counters=Counters(jev_failures=1)).counters.jev_failures == 0
