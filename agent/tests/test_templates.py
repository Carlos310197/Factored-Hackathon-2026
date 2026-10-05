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
    assert "HND-1" in handoff_notice("HND-1", "es") and "especialista" in handoff_notice("HND-1", "pt")
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
