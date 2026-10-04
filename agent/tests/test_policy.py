from datetime import date

import pytest

from bankagent.policy.dispute import DisputePolicy

AS_OF = date(2026, 6, 17)
BASE = {"transaction_status": "Approved", "transaction_type": "Purchase", "process_date": "2026-06-10",
        "amount": 15.99, "currency": "USD", "amount_usd": 15.99, "is_fraud": False, "fraud_score": 12.0}
P = DisputePolicy.load()


def ev(reason="duplicate_charge", already=False, escalation=False, **over):
    return P.evaluate({**BASE, **over}, reason, AS_OF, already_disputed=already, escalation=escalation)


def test_version_is_labeled_synthetic():
    assert P.version == "dispute-policy.v1" and P.cfg["synthetic"] is True


def test_happy_path_is_automated():
    r = ev()
    assert r.outcome == "automated" and r.redirect is None and r.triggers() == []
    assert [x.name for x in r.rules] == ["status_disputable", "type_disputable", "within_window",
                                         "not_already_disputed", "automated_eligible"]


@pytest.mark.parametrize("status,redirect", [("Declined", "explain_decline"), ("Pending", "wait_pending"),
                                             ("Reversed", "already_reversed")])
def test_non_approved_status_redirects(status, redirect):
    r = ev(transaction_status=status)
    assert r.outcome == "not_disputable" and r.redirect == redirect


@pytest.mark.parametrize("ttype", ["Deposit", "Adjustment"])
def test_non_disputable_types(ttype):
    assert ev(transaction_type=ttype).redirect == "not_disputable_type"


def test_window_boundaries():
    assert ev(process_date="2026-04-18").outcome == "automated"        # 60 days
    assert ev(process_date="2026-04-17").redirect == "out_of_window"   # 61 days
    assert ev(process_date="2026-06-18").redirect == "out_of_window"   # after as_of


def test_already_disputed():
    assert ev(already=True).redirect == "already_disputed"


@pytest.mark.parametrize("over,reason,trigger", [
    ({}, "unauthorized", "unauthorized_reason"),
    ({"is_fraud": True}, "duplicate_charge", "fraud_flag"),
    ({"fraud_score": 30.5}, "duplicate_charge", "fraud_score_high"),
    ({"amount": 800, "amount_usd": 800.0}, "wrong_amount", "amount_over_limit"),
])
def test_human_review_triggers(over, reason, trigger):
    r = ev(reason=reason, **over)
    assert r.outcome == "human_review" and trigger in r.triggers()


def test_fraud_score_30_is_still_automated():
    assert ev(fraud_score=30.0).outcome == "automated"


def test_amount_500_is_still_automated():
    assert ev(amount=500, amount_usd=500.0).outcome == "automated"


def test_escalation_signal_forces_human_review():
    assert ev(escalation=True).triggers() == ["escalation_signal"]


def test_usd_amount_used_when_amount_usd_missing():
    assert ev(amount_usd=None, amount=15.99, currency="USD").outcome == "automated"
    assert "amount_over_limit" in ev(amount_usd=None, amount=900, currency="USD").triggers()


def test_unknown_usd_amount_goes_to_human_review():
    assert ev(amount_usd=None, amount=45000, currency="COP").triggers() == ["amount_unknown"]


def test_is_fraud_string_true_counts():
    assert "fraud_flag" in ev(is_fraud="True").triggers()


def test_unknown_reason_is_error():
    with pytest.raises(ValueError):
        ev(reason="because")
