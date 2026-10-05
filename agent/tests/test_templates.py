from bankagent.llm.templates import (auth_message, confirmation_summary, dispute_filed, fallback_reply, fmt_money,
                                     handoff_notice)

TXN = {"merchant_name": "Netflix", "process_date": "2026-06-10", "amount": 15.99, "currency": "USD",
       "transaction_type": "Purchase"}


def test_fmt_money():
    assert fmt_money(15.99, "USD") == "15.99 USD"
    assert fmt_money(45000, "COP") == "45,000 COP"
    assert fmt_money(1250.4, "ARS") == "1,250.40 ARS"


def test_confirmation_summary_es_and_pt():
    es = confirmation_summary(TXN, "duplicate_charge", "es")
    assert "Netflix" in es and "2026-06-10" in es and "15.99 USD" in es and "cobro duplicado" in es and "sí, confirmo" in es
    pt = confirmation_summary(TXN, "duplicate_charge", "pt")
    assert "cobrança duplicada" in pt and "sim, confirmo" in pt


def test_fixed_blocks():
    es, pt = handoff_notice("HND-1", "es"), handoff_notice("HND-1", "pt")
    assert "HND-1" in es and "HND-1" in pt
    # complements the model's own "a specialist will review" sentence: next step + safety step, no repeat
    assert "este chat" in es and "bloquea tu tarjeta" in es and "especialista" not in es
    assert "este chat" in pt and "bloqueie seu cartão" in pt and "especialista" not in pt
    assert "DSP-1" in dispute_filed("DSP-1", "pt")
    assert auth_message("session_expired", "pt") != auth_message("session_expired", "es")


def test_fallback_answer_renders_receipts():
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17",
                 "data": [{"product_type": "Tarjeta de Crédito", "product_last4": "4242", "current_balance": 1250.4,
                           "currency": "USD", "product_status": "Active"}]},
                {"receipt_id": "RCP-2", "source": "seed_decline_reason", "as_of": "2026-06-17",
                 "data": {"customer_text_es": "No había saldo.", "customer_text_pt": "Não havia saldo."}}]
    es = fallback_reply({"kind": "answer"}, receipts, "es")
    assert "****4242" in es and "1,250.40 USD" in es and "No había saldo." in es
    assert "Não havia saldo." in fallback_reply({"kind": "answer"}, receipts, "pt")


def test_fallback_offers_human_and_lists_options():
    text = fallback_reply({"kind": "ask_clarification", "display_options": ["opción A", "opción B"], "offer_human": True},
                          [], "es")
    assert "• opción A" in text and "especialista" in text


def test_fallback_unknown_language_defaults_to_es():
    assert fallback_reply({"kind": "greeting"}, [], "fr") == fallback_reply({"kind": "greeting"}, [], "es")


def test_fallback_translates_product_and_transaction_status():
    products = {"receipt_id": "R1", "source": "dim_product", "data": [
        {"product_type": "Tarjeta Débito", "product_last4": "5827", "current_balance": 309666.73, "currency": "ARS",
         "product_status": "Active"}]}
    txn = {"receipt_id": "R2", "source": "fct_transaction", "data": {**TXN, "transaction_status": "Declined"}}
    es = fallback_reply({"kind": "answer"}, [products, txn], "es")
    assert "(Activa)" in es and "Rechazada" in es and "Active" not in es and "Declined" not in es
    pt = fallback_reply({"kind": "answer"}, [products, txn], "pt")
    assert "(Ativa)" in pt and "Recusada" in pt
    unknown = {**products, "data": [{**products["data"][0], "product_status": "Frozen"}]}
    assert "(Frozen)" in fallback_reply({"kind": "answer"}, [unknown], "es")  # unknown values pass through


def test_portuguese_copy_has_no_spanish():
    from bankagent.llm.templates import FALLBACK, INTENT_LABELS
    assert "con sus" not in FALLBACK["pt"]["greeting"]
    assert " fue " not in INTENT_LABELS["pt"]["decline_explanation"]
    import inspect

    from bankagent.llm import templates
    pt_block = inspect.getsource(templates).split('"pt": {"not_declined"', 1)[1].split("}", 1)[0]
    assert " fue " not in pt_block


def test_compose_prompt_sets_one_register():
    from bankagent.llm.compose import COMPOSE_SYSTEM
    assert "tú" in COMPOSE_SYSTEM and "você" in COMPOSE_SYSTEM
