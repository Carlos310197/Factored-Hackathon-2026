import json

from tests.fakes import FakeLLM
from tests.fixtures.serving_fixture import RUN_ID, build_serving, t, write_pointer
from tests.harness import CTX_ES, CTX_PT, make_harness

DISPUTE_NETFLIX = {"intent": "dispute_charge", "target": "Netflix", "reason": "duplicate_charge"}


def test_account_inquiry_es(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info"}])
    r = h.turn("¿Cuál es el saldo de mi tarjeta?")
    assert r.pop("turn_id").startswith("TRN")
    assert r == {"reply_text": "[answer]", "language": "es", "awaiting": "none", "options": [], "refs": [],
                 "data_as_of": "2026-06-17"}
    assert [x["source"] for x in h.state()["receipts"]] == ["dim_product"]
    assert {"tool", "llm", "jev", "route"} <= set(h.log_kinds())
    assert h.jev.count("understand") == 1 and h.jev.count("verify") == 1
    sent = json.dumps(h.jev.calls[0][1])
    assert "TRX-" not in sent and "CLI-" not in sent
    _assert_jev_never_sees_customer_or_product_ids(h)


def test_compose_gets_the_customers_request(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info"}])
    h.turn("Dime el saldo de mis tarjetas")
    compose_calls = [c for c in h.llm.calls if c["model"] == "openai.gpt-oss-120b"]
    assert "<request>EN: Dime el saldo de mis tarjetas</request>" in compose_calls[0]["messages"][1]["content"]


def test_id_guard_feedback_keeps_claim_citations(ddb_store, serving_root):
    llm = FakeLLM(reply_text="Tu saldo (RCP-1791247560533CC9C92FC) es 1.250,40 USD")
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info"}], llm=llm)
    h.turn("saldo")
    compose_calls = [c for c in llm.calls if c["model"] == "openai.gpt-oss-120b"]
    feedback = compose_calls[1]["messages"][1]["content"].split("<feedback>")[1]
    assert "RCP-1791247560533CC9C92FC" in feedback and "reply_text" in feedback and "receipt_ids" in feedback
    assert "not in the receipts" not in feedback


def test_transaction_clarification_chips_are_localized(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "transaction_status", "target": "ambiguous"}])
    r = h.turn("¿Qué pasó con mi pago?")
    assert r["awaiting"] == "clarification" and r["options"]
    for label in r["options"]:
        assert not {"Purchase", "Approved", "Web", "POS"} & set(label.split(" · ")), label
    assert "Amazon · 2026-06-15 · 120.00 USD · Rechazada" in r["options"]


def test_decline_explanation_pt(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "decline_explanation", "target": "Amazon"}],
                     llm=FakeLLM(language="pt"))
    r = h.turn("Por que minha compra na Amazon foi recusada?", CTX_PT)
    assert r["language"] == "pt" and r["reply_text"] == "[answer]"
    receipts = h.state(CTX_PT)["receipts"]
    assert [x["source"] for x in receipts] == ["seed_decline_reason"]
    assert receipts[0]["data"]["reason_key"] == "insufficient_funds"


def test_dispute_confirm_file_verify(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [DISPUTE_NETFLIX, {"intent": "dispute_charge", "confirmation": "confirm"}])
    r1 = h.turn("Me cobraron dos veces Netflix, quiero disputarlo")
    assert r1["awaiting"] == "confirmation"
    assert "Resumen de la disputa" in r1["reply_text"] and "15.99 USD" in r1["reply_text"]
    assert ddb_store.disputes.get(t(101)) is None
    r2 = h.turn("sí, confirmo")
    rec = ddb_store.disputes.get(t(101))
    assert rec["status"] == "submitted" and rec["route"] == "automated"
    assert rec["customer_statement"]["original"].startswith("Me cobraron")
    assert r2["awaiting"] == "none" and rec["dispute_id"] in r2["reply_text"] and r2["refs"] == [rec["dispute_id"]]
    verify = [x for x in h.state()["receipts"] if x["source"] == "disputes.verify"]
    assert verify[0]["data"]["verified"] is True
    _assert_jev_never_sees_customer_or_product_ids(h)


EXTRACT_MODEL = "mistral.ministral-3-14b-instruct"


def test_confirm_token_files_without_extract_or_jev(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [DISPUTE_NETFLIX])
    r1 = h.turn("Me cobraron dos veces Netflix, quiero disputarlo")
    card_hash = r1["summary"]["card_hash"]
    assert card_hash == h.state()["card_hash"]
    extracts, understands = sum(c["model"] == EXTRACT_MODEL for c in h.llm.calls), h.jev.count("understand")
    r2 = h.turn(f"confirm:{card_hash}")
    rec = ddb_store.disputes.get(t(101))
    assert rec["status"] == "submitted" and r2["refs"] == [rec["dispute_id"]] and r2["awaiting"] == "none"
    assert sum(c["model"] == EXTRACT_MODEL for c in h.llm.calls) == extracts
    assert h.jev.count("understand") == understands
    guard = [r for r in ddb_store.log.list("S-es") if r["kind"] == "guard" and r["node"] == "understand"]
    assert guard[-1]["payload"] == {"check": "confirm_token", "matched": True}


def test_stale_confirm_token_does_not_file(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [DISPUTE_NETFLIX])
    r1 = h.turn("Me cobraron dos veces Netflix, quiero disputarlo")
    r2 = h.turn("confirm:" + "0" * 64)
    assert ddb_store.disputes.get(t(101)) is None
    assert r2["awaiting"] == "confirmation" and r2["summary"] == r1["summary"]
    assert h.jev.count("understand") == 1
    guard = [r for r in ddb_store.log.list("S-es") if r["kind"] == "guard" and r["node"] == "understand"]
    assert guard[-1]["payload"] == {"check": "confirm_token", "matched": False}


def _assert_jev_never_sees_customer_or_product_ids(h):
    assert h.jev.calls and any(c[0] == "verify" for c in h.jev.calls)
    for kind, state, questions in h.jev.calls:
        sent = json.dumps([state, questions])
        assert "CLI-" not in sent and "PRD-" not in sent, kind
        assert "fraud_score" not in sent and "is_fraud" not in sent, kind


def test_ambiguous_intent_clarifies_then_answers(ddb_store, serving_root):
    specs = [{"intent": "account_info", "ip": 0.5, "second": "transaction_status", "sp": 0.45}, {"intent": "account_info"}]
    h = make_harness(ddb_store, serving_root, specs)
    r1 = h.turn("tengo una duda")
    assert r1["awaiting"] == "clarification"
    assert r1["options"] == ["información de tus cuentas", "el estado de una transacción"]
    r2 = h.turn("mis cuentas")
    assert r2["awaiting"] == "none" and r2["reply_text"] == "[answer]"


def test_unsupported_request_abstains(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "unsupported"}])
    r = h.turn("Quiero un préstamo hipotecario")
    assert r["reply_text"] == "[abstain] +human" and r["awaiting"] == "none"
    assert ddb_store.handoffs.list_by_status("open") == []


def test_unrecognized_charge_drafts_dispute_and_hands_off(ddb_store, serving_root):
    spec = {"intent": "dispute_charge", "target": "Tienda X", "nouls": {"reports_unauthorized_use": 0.92}}
    h = make_harness(ddb_store, serving_root, [spec])
    r = h.turn("No reconozco el cargo de Tienda X, alguien usó mi tarjeta")
    [hnd] = ddb_store.handoffs.list_by_status("open")
    assert hnd["priority"] == "critical" and "reports_unauthorized_use" in hnd["reason_codes"]
    assert hnd["customer_request"]["en"].startswith("EN:") and hnd["open_questions"] == ["Which card was used?"]
    assert any(a["action"] == "dispute_drafted" for a in hnd["actions_taken"])
    rec = ddb_store.disputes.get(t(108))
    assert rec["route"] == "human_review" and rec["status"] == "pending_review" and rec["reason"] == "unauthorized"
    assert r["reply_text"].startswith("[handoff_notice]") and hnd["handoff_id"] in r["reply_text"]
    assert r["awaiting"] == "none" and hnd["handoff_id"] in r["refs"]


def test_over_limit_dispute_goes_to_human_review_without_confirmation(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "dispute_charge", "target": "Electrónica Max",
                                                "reason": "wrong_amount"}])
    r = h.turn("Me cobraron de más en Electrónica Max")
    assert ddb_store.disputes.get(t(105))["route"] == "human_review" and r["awaiting"] == "none"
    [hnd] = ddb_store.handoffs.list_by_status("open")
    assert hnd["priority"] == "medium" and "amount_over_limit" in hnd["reason_codes"]


def test_legal_threat_hands_off_with_high_priority(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info", "nouls": {"legal_or_regulator_threat": 0.8}}])
    h.turn("Voy a denunciarlos ante la Condusef")
    [hnd] = ddb_store.handoffs.list_by_status("open")
    assert hnd["priority"] == "high" and hnd["reason_codes"] == ["legal_or_regulator_threat"]


def test_dispute_of_declined_payment_explains_the_decline(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "dispute_charge", "target": "Amazon", "reason": "wrong_amount"}])
    h.turn("Quiero disputar el cargo de Amazon")
    assert [x["source"] for x in h.state()["receipts"]] == ["fct_transaction", "seed_decline_reason"]
    assert ddb_store.disputes.get(t(102)) is None


def test_second_request_is_queued_and_offered(ddb_store, serving_root):
    llm = FakeLLM(multi_intent=True, secondary="dispute the Netflix charge")
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info"}, DISPUTE_NETFLIX], llm=llm)
    r1 = h.turn("¿Mi saldo? Y además quiero disputar un cargo de Netflix")
    assert r1["reply_text"] == "[answer] +queued" and h.state()["queued_offer"] == "dispute the Netflix charge"
    r2 = h.turn("sí, el de Netflix, me lo cobraron doble")
    assert h.jev.calls[2][1]["session_facts"]["offered_queued_request"] == "dispute the Netflix charge"
    assert r2["awaiting"] == "confirmation"


def test_other_language_replies_in_session_language(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [{"intent": "account_info"}], llm=FakeLLM(language="other"))
    assert h.turn("What is my balance?", CTX_PT)["language"] == "pt"


def test_session_keeps_its_run_id_when_pointer_moves(ddb_store, tmp_path):
    root = build_serving(tmp_path / "serving")
    h = make_harness(ddb_store, root, [{"intent": "account_info"}, {"intent": "account_info"}])
    h.turn("saldo")
    write_pointer(root, run_id="run-that-does-not-exist")
    r = h.turn("¿y ahora?")
    assert r["reply_text"] == "[answer]" and h.state()["run_id"] == RUN_ID


def test_confirmation_is_bound_to_the_card_the_customer_saw(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [DISPUTE_NETFLIX, {"intent": "dispute_charge", "confirmation": "confirm"}])
    r1 = h.turn("Me cobraron dos veces Netflix, quiero disputarlo")
    assert r1["awaiting"] == "confirmation" and "15.99" in r1["reply_text"]
    read = h.service.deps.read
    original = read.get_transaction

    def changed(*a, **kw):  # the record behind the card changed before the customer said yes
        res = original(*a, **kw)
        return type(res)(res.source, {**res.data, "amount": 99.0}, res.as_of)

    read.get_transaction = changed
    r2 = h.turn("sí, confirmo")
    assert ddb_store.disputes.get(t(101)) is None
    assert r2["awaiting"] == "confirmation" and "99" in r2["reply_text"]


def test_llm_never_sees_customer_or_product_ids(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [DISPUTE_NETFLIX, {"intent": "dispute_charge", "confirmation": "confirm"}])
    h.turn("Me cobraron dos veces Netflix, quiero disputarlo")
    h.turn("sí, confirmo")
    composes = [c for c, r in zip(h.llm.calls, h.llm.roles) if r != "extract"]
    assert composes
    for c in composes:
        sent = json.dumps(c["messages"])
        assert "CLI-" not in sent and "PRD-" not in sent and "fraud_score" not in sent
