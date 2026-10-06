"""The fakes refuse a leaking payload, so every graph test doubles as an egress test (Jev and Bedrock)."""
import pytest

from tests.fakes import FakeJev, FakeLLM, assert_no_egress


def test_guard_flags_customer_product_ids_and_fraud_fields():
    for leak in ["CLI-00P4VN7YGMT5", "PRD-ABC12345", '{"fraud_score": 92}', '{"is_fraud": true}']:
        with pytest.raises(AssertionError):
            assert_no_egress(leak, "x")
    assert_no_egress({"transaction_id": "TRX-JV8M1O76FTNG6CZYNLLD", "amount": 15.99, "alias": "c1"}, "x")


def test_fake_jev_and_fake_bedrock_refuse_a_leak():
    with pytest.raises(AssertionError, match="Jev"):
        FakeJev([{}]).decide({"customer_id": "CLI-00P4VN7YGMT5"}, {"intent": {}})
    from bankagent.llm.compose import compose
    from bankagent.llm.config import load_models
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17",
                 "data": [{"note": "owner CLI-00P4VN7YGMT5"}]}]  # an id in a value, past the key-based redaction
    with pytest.raises(AssertionError, match="Bedrock"):
        compose(FakeLLM(), load_models(env={})["compose"], {"kind": "answer"}, receipts, "es")


def test_redact_drops_fraud_triggers_from_policy_rule_details():
    """Live packets carry the policy rules; `automated_eligible` lists triggers like fraud_score_high (a fraud signal)."""
    from bankagent.decisions.verify import redact
    rules = [{"name": "automated_eligible", "passed": False,
              "detail": "unauthorized_reason,fraud_flag,fraud_score_high,escalation_signal"}]
    assert redact(rules) == [{"name": "automated_eligible", "passed": False,
                              "detail": "unauthorized_reason,escalation_signal"}]
    assert redact({"detail": "7 days"}) == {"detail": "7 days"}
