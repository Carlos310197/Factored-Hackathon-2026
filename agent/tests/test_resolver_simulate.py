from collections import Counter
from datetime import date

import pytest

from bankagent.resolver.histories import History
from bankagent.resolver.simulate import (MENTION_KEYS, load_sim_config, relative_range, round_significant, simulate)
from tests.resolver_data import txn

CFG = load_sim_config()


def histories(n: int) -> list[History]:
    base = [txn(1, day="2026-06-10"), txn(2, day="2026-06-02", merchant=None, ttype="Withdrawal", channel="ATM",
                                           amount=120.0),
            txn(3, day="2026-05-20", merchant=None, ttype="Withdrawal", channel="ATM", amount=400.0),
            txn(4, day="2026-05-01", merchant="Super Ahorro", amount=200_000.0, currency="COP", amount_usd=50.0)]
    return [History("train", "CLI-SYNTH0000001", "2026-06-17", base) for _ in range(n)]


def test_config_loads_with_hash_and_validates(tmp_path):
    assert CFG["version"] == "simulate.v1" and len(CFG["sha256"]) == 64
    bad = tmp_path / "bad.yaml"
    bad.write_text("merchant: {exact: 0.5, absent: 0.4}\namount: {exact: 1.0}\ndate: {exact: 1.0}\n")
    with pytest.raises(ValueError):
        load_sim_config(bad)


def test_same_seed_same_cases():
    assert simulate(histories(50), CFG, seed=11) == simulate(histories(50), CFG, seed=11)
    assert simulate(histories(50), CFG, seed=11) != simulate(histories(50), CFG, seed=12)


def test_nil_cases_exclude_the_target_and_others_include_it():
    for c in simulate(histories(300), CFG, seed=5):
        ids = [t["transaction_id"] for t in c["candidates"]]
        if c["slice"] == "nil":
            assert c["target_id"] is None and c["target"]["transaction_id"] not in ids
        else:
            assert c["target_id"] in ids and c["target"]["transaction_id"] == c["target_id"]
        assert set(c["mentions"]) == set(MENTION_KEYS)


def test_style_rates_match_config_within_two_points():
    cases = simulate(histories(10_000), CFG, seed=9)
    n = len(cases)
    assert abs(sum(c["style"]["nil"] for c in cases) / n - CFG["not_in_list"]) < 0.02
    assert abs(sum(c["style"]["no_detail"] for c in cases) / n - CFG["no_detail"]) < 0.02
    detailed = [c for c in cases if not c["style"]["no_detail"]]
    dates = Counter(c["style"]["date"] for c in detailed)
    for k in ("exact", "off_by_one"):
        assert abs(dates[k] / len(detailed) - CFG["date"][k]) < 0.02
    purchases = [c for c in detailed if c["style"]["merchant"] != "n/a"]
    merch = Counter(c["style"]["merchant"] for c in purchases)
    for k, p in CFG["merchant"].items():
        assert abs(merch[k] / len(purchases) - p) < 0.02
    typed = [c for c in detailed if c["style"]["type_hint"] != "n/a"]
    present = sum(c["style"]["type_hint"] in ("present", "wrong") for c in typed) / len(typed)
    assert abs(present - CFG["hints"]["type_hint"]) < 0.02


def test_hard_targets_are_oversampled_when_available():
    cases = [c for c in simulate(histories(2000), CFG, seed=4) if c["slice"] != "nil"]
    share = sum(c["slice"] == "hard" for c in cases) / len(cases)
    assert 0.45 < share < 0.55


def test_rounding_and_relative_ranges():
    assert round_significant(343.03) == 340.0 and round_significant(1_372_120) == 1_400_000.0
    assert round_significant(15.99) == 16.0
    anchor = date(2026, 6, 17)  # a Wednesday
    assert relative_range(date(2026, 6, 16), anchor) == ("this week", date(2026, 6, 15), anchor)
    assert relative_range(date(2026, 6, 10), anchor) == ("last week", date(2026, 6, 8), date(2026, 6, 14))
    assert relative_range(date(2026, 6, 2), anchor) == ("this month", date(2026, 6, 1), anchor)
    assert relative_range(date(2026, 5, 3), anchor) == ("last month", date(2026, 5, 1), date(2026, 5, 31))
    assert relative_range(date(2026, 4, 3), anchor) is None


def test_relative_date_styles_carry_their_label():
    rel = [c for c in simulate(histories(500), CFG, seed=8) if c["style"].get("date") == "relative"]
    assert rel and all(c["style"]["date_label"] in ("this week", "last week", "this month", "last month") for c in rel)
