"""SYNTHETIC in-memory tables shaped like the real drop."""
import duckdb
import pytest

from asis import artifacts


def _con(interactions: list[tuple], surveys: list[tuple] = ()):
    c = duckdb.connect()
    c.sql("create table interactions (interaction_id varchar, reason_category varchar, channel varchar, "
          "was_escalated varchar, wait_time_seconds varchar, was_resolved varchar)")
    c.sql("create table surveys (interaction_id varchar, survey_type varchar, main_score varchar)")
    for r in interactions:
        c.execute("insert into interactions values (?, ?, ?, ?, ?, ?)", [str(x) for x in r])
    for r in surveys:
        c.execute("insert into surveys values (?, ?, ?)", [str(x) for x in r])
    return c


def test_wait_is_constant_when_slice_medians_agree_even_if_the_spread_is_wide():
    rows = [(i, reason, "Phone", "False", w, "True") for reason in ("A", "B")
            for i, w in enumerate([40, 120, 120, 120, 200], start=100 if reason == "A" else 200)]
    r = artifacts.wait_constant(_con(rows))
    assert r["holds"] is True and "median" in r["evidence"]


def test_wait_is_not_constant_when_slice_medians_differ():
    rows = [(i, "A", "Phone", "False", 60, "True") for i in range(5)] + \
           [(i + 10, "B", "Phone", "False", 300, "True") for i in range(5)]
    assert artifacts.wait_constant(_con(rows))["holds"] is False


def test_escalation_is_flat_across_reasons_when_only_small_buckets_wobble():
    # reason A: 10% in both channels; reason B: 10% overall but 5% / 15% by channel
    rows = [(f"a{i}", "A", ch, str(i % 10 == 0), 120, "True") for ch in ("Phone", "App") for i in range(100)]
    rows += [(f"b{i}", "B", "Phone", str(i % 20 == 0), 120, "True") for i in range(100)]
    rows += [(f"c{i}", "B", "App", str(i % 20 < 3), 120, "True") for i in range(100)]
    r = artifacts.escalation_flat(_con(rows), min_n=50)
    assert r["holds"] is True


def test_escalation_is_not_flat_when_reasons_differ():
    rows = [(f"a{i}", "A", "Phone", str(i % 10 == 0), 120, "True") for i in range(100)]
    rows += [(f"b{i}", "B", "Phone", str(i % 2 == 0), 120, "True") for i in range(100)]
    assert artifacts.escalation_flat(_con(rows), min_n=50)["holds"] is False


def _csat(resolved_scores: dict, unresolved_scores: dict):
    inter, surv, n = [], [], 0
    for resolved, scores in (("True", resolved_scores), ("False", unresolved_scores)):
        for reason, mean in scores.items():
            for k in range(10):  # a mean of x.y comes from a 90/10 mix of floor and ceil
                n += 1
                inter.append((n, reason, "Phone", "False", 120, resolved))
                surv.append((n, "CSAT", int(mean) + (1 if k < round((mean % 1) * 10) else 0)))
    return _con(inter, surv)


def test_csat_follows_resolution_when_the_gap_dwarfs_the_within_status_spread():
    c = _csat({"A": 3.0, "B": 3.0}, {"A": 2.0, "B": 2.1})
    r = artifacts.csat_by_resolution(c, min_n=10)
    assert r["holds"] is True


def test_csat_is_not_determined_by_resolution_when_the_gap_is_small():
    c = _csat({"A": 3.0, "B": 3.0}, {"A": 2.8, "B": 2.9})
    assert artifacts.csat_by_resolution(c, min_n=10)["holds"] is False


def test_csat_with_one_reason_per_status_is_insufficient():
    c = _csat({"A": 3.0}, {"A": 2.0})
    r = artifacts.csat_by_resolution(c, min_n=10)
    assert r["holds"] is False and "insufficient" in r["evidence"]
