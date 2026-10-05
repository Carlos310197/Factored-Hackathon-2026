import math


from bankagent.resolver.features import FEATURES, case_features, fold, mentions_present
from bankagent.resolver.splits import ANCHORS, case_slice, customer_split
from tests.resolver_data import mentions, txn

COL = {f: i for i, f in enumerate(FEATURES)}


def f(m, cands, name, row=0):
    return case_features(m, cands)[row, COL[name]]


def test_fold_strips_accents_case_and_spaces():
    assert fold("  Tienda  Don JOSÉ ") == "tienda don jose"


def test_accent_insensitive_merchant_match():
    assert f(mentions(merchant="tienda don jose"), [txn(1)], "merchant_sim") == 1.0
    assert f(mentions(merchant="tienda don jose"), [txn(1)], "merchant_mentioned") == 1.0


def test_merchant_named_but_candidate_has_none():
    x = case_features(mentions(merchant="Oxxo"), [txn(1, merchant=None, ttype="Withdrawal")])
    assert x[0, COL["merchant_missing_on_cand"]] == 1.0 and x[0, COL["merchant_sim"]] == 0.0


def test_amount_uses_the_closer_of_local_and_usd():
    cop = txn(1, amount=1_400_000.0, currency="COP", amount_usd=340.0)
    assert f(mentions(amount=340), [cop], "amount_log_err") == 0.0
    assert math.isclose(f(mentions(amount=340), [txn(2, amount=343.03)], "amount_log_err"), abs(math.log(340 / 343.03)))


def test_amount_error_is_capped_and_ranked():
    cands = [txn(1, amount=100.0), txn(2, amount=343.03), txn(3, amount=1e9)]
    x = case_features(mentions(amount=340), cands)
    assert x[2, COL["amount_log_err"]] == 3.0
    assert list(x[:, COL["amount_rank"]]) == [1 / 3, 0.0, 2 / 3]


def test_days_outside_the_range():
    m = mentions(date_from="2026-06-08", date_to="2026-06-14")
    assert f(m, [txn(1, day="2026-06-10")], "days_outside") == 0.0
    assert f(m, [txn(1, day="2026-06-01")], "days_outside") == math.log1p(7)
    assert f(m, [txn(1, day="2026-06-16")], "days_outside") == math.log1p(2)
    assert f(mentions(date_from="not-a-date"), [txn(1)], "date_mentioned") == 0.0


def test_hints_are_signed():
    m = mentions(type_hint="withdrawal", channel_hint="atm", city="guadalajara")
    good = txn(1, merchant=None, ttype="Withdrawal", channel="ATM")
    bad = txn(2, ttype="Purchase", channel="POS", city="Monterrey")
    x = case_features(m, [good, bad])
    assert list(x[0, [COL["type_match"], COL["channel_match"], COL["city_match"]]]) == [1.0, 1.0, 1.0]
    assert list(x[1, [COL["type_match"], COL["channel_match"], COL["city_match"]]]) == [-1.0, -1.0, -1.0]
    assert f(mentions(type_hint="loan"), [good], "type_match") == 0.0


def test_absent_mentions_are_zero_except_structure():
    x = case_features(mentions(), [txn(1), txn(2)])
    structural = {"recency_pct", "is_purchase"}
    assert all(x[:, COL[c]].sum() == 0 for c in FEATURES if c not in structural)
    assert list(x[:, COL["recency_pct"]]) == [0.0, 0.5]
    assert mentions_present(mentions()) is False and mentions_present(mentions(city="x")) is True
    assert case_features(None, []).shape == (0, len(FEATURES))


def test_customer_split_is_deterministic_and_covers_three_splits():
    ids = [f"CLI-{i:012d}" for i in range(2000)]
    splits = [customer_split(c) for c in ids]
    assert splits == [customer_split(c) for c in ids]
    share = {s: splits.count(s) / len(ids) for s in ("train", "dev", "test")}
    assert 0.75 < share["train"] < 0.85 and 0.07 < share["dev"] < 0.13 and 0.07 < share["test"] < 0.13


def test_anchor_ranges_do_not_overlap():
    spans = sorted(ANCHORS.values())
    assert all(a[1] < b[0] for a, b in zip(spans, spans[1:]))


def test_hard_slice_rule():
    target = txn(1, merchant=None, ttype="Withdrawal", amount=120.0)
    assert case_slice([target, txn(2, merchant=None, ttype="Withdrawal", amount=500.0)], target["transaction_id"]) == "hard"
    assert case_slice([txn(1), txn(2, merchant="TIENDA DON JOSE", amount=5.0)], txn(1)["transaction_id"]) == "hard"
    assert case_slice([txn(1, amount=100.0), txn(2, merchant="Oxxo", amount=109.0)], txn(1)["transaction_id"]) == "hard"
    assert case_slice([txn(1, amount=100.0), txn(2, merchant="Oxxo", amount=300.0)], txn(1)["transaction_id"]) == "easy"
    assert case_slice([txn(2)], txn(1)["transaction_id"]) == "nil"


def test_hints_tolerate_case_and_whitespace():
    atm = txn(1, merchant=None, ttype="Withdrawal", channel="ATM")
    assert f(mentions(channel_hint=" ATM ", type_hint="Withdrawal"), [atm], "channel_match") == 1.0
    assert f(mentions(type_hint=" withdrawal"), [atm], "type_match") == 1.0


def test_reversed_date_range_is_the_same_range():
    m = mentions(date_from="2026-06-14", date_to="2026-06-08")
    assert f(m, [txn(1, day="2026-06-10")], "days_outside") == 0.0
    assert f(m, [txn(1, day="2026-06-01")], "days_outside") == math.log1p(7)


def test_degenerate_amounts_are_neutral_not_errors():
    no_usd = txn(1, amount=0.0, currency="COP", amount_usd=None)
    for bad in (0, -5, True, "340"):
        assert f(mentions(amount=bad), [txn(2)], "amount_mentioned") == 0.0
    x = case_features(mentions(amount=340), [no_usd, txn(2, amount=None)])
    assert list(x[:, COL["amount_log_err"]]) == [3.0, 3.0]
