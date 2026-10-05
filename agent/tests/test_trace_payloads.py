from bankagent.decisions.thresholds import load_thresholds
from bankagent.decisions.trace_payload import alias_view, confirmation_payload, thresholds_map


def test_thresholds_map_is_flat_and_complete():
    m = thresholds_map(load_thresholds())
    assert m["intent"] == 0.80 and m["intent.margin"] == 0.15
    assert m["target_transaction"] == 0.85 and m["target_transaction.margin"] == 0.20
    assert m["confirmation"] == 0.90 and m["injection_attempt"] == 0.50
    assert m["reports_unauthorized_use"] == 0.50 and m["asks_for_human"] == 0.60 and m["distress"] == 0.60
    assert all(isinstance(v, float) for v in m.values())


def test_alias_view_keeps_only_known_candidates():
    cands = [{"transaction_id": "TRX-1", "merchant_name": "Amazon", "amount": 420.0, "currency": "USD",
              "process_date": "2026-06-02"}]
    v = alias_view({"c1": "TRX-1", "c2": "TRX-GONE"}, cands)
    assert v == {"c1": {"transaction_id": "TRX-1", "merchant": "Amazon", "amount": 420.0, "currency": "USD",
                        "date": "2026-06-02"}}


def test_confirmation_payload_uses_the_same_draft_fields():
    txn = {"transaction_id": "TRX-9", "merchant_name": "\u00c9xito Laureles", "amount": 184900, "currency": "COP",
           "process_date": "2026-06-03"}
    assert confirmation_payload(txn, "duplicate_charge") == {
        "merchant": "\u00c9xito Laureles", "date": "2026-06-03", "amount": 184900, "currency": "COP",
        "reason_code": "duplicate_charge"}


def test_confirmation_payload_falls_back_to_timestamp_date():
    p = confirmation_payload({"merchant_name": None, "amount": 1, "currency": "USD",
                              "transaction_ts": "2026-06-01T10:00:00"}, None)
    assert p["merchant"] == "" and p["date"] == "2026-06-01" and p["reason_code"] is None
