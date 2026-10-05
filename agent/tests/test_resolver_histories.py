from datetime import date

from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.splits import ANCHORS, customer_split
from bankagent.tools.read import TXN_FIELDS


def test_histories_respect_split_window_and_order(history_serving):
    src = TransactionSource(history_serving)
    hs = sample_histories(src, "dev", 15, seed=1)
    assert len(hs) == 15
    lo, hi = ANCHORS["dev"]
    for h in hs:
        anchor = date.fromisoformat(h.anchor)
        assert customer_split(h.customer_id) == "dev" and lo <= anchor <= hi
        assert len(h.candidates) >= 2 and list(h.candidates[0]) == list(TXN_FIELDS)
        days = [date.fromisoformat(t["process_date"]) for t in h.candidates]
        assert all(0 <= (anchor - d).days <= 60 for d in days)
        ts = [t["transaction_ts"] for t in h.candidates]
        assert ts == sorted(ts, reverse=True)
        assert all(t["customer_id"] == h.customer_id for t in h.candidates)


def test_histories_are_deterministic_and_splits_disjoint(history_serving):
    src = TransactionSource(history_serving)
    a = sample_histories(src, "train", 20, seed=3)
    assert [(h.customer_id, h.anchor) for h in a] == [(h.customer_id, h.anchor) for h in sample_histories(src, "train", 20, seed=3)]
    test_customers = {h.customer_id for h in sample_histories(src, "test", 10, seed=3)}
    assert test_customers and not test_customers & {h.customer_id for h in a}
    assert isinstance(a[0].candidates[0]["amount"], float)
