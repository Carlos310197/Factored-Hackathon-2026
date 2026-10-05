import pytest

from evalkit.compare import LABEL, MissingLegacyMetric, REQUIRED_KEYS, legacy_vs_new, projected_savings
from evalkit.metrics import bootstrap_ci, cost, headline, slices, variability


def row(goal="H001", rep=1, cls="automated_correct", expected="resolve", family="normal", language="es",
        country="México", handoff=False, usage=None, **kw):
    base = {"goal_id": goal, "rep": rep, "class": cls, "expected_outcome": expected, "family": family,
            "language": language, "country": country, "segment": "Retail", "group": "dispute_auto",
            "unsafe_types": [], "handoff_made": handoff, "reason_match": None, "automation_attempted": not handoff,
            "open_item": handoff, "language_ok": True, "turns": 2, "agent_time_ms": 3000,
            "turn_latencies_ms": [1000, 2000], "first_turn_ms": 1000, "dispute_intake_ms": 3000,
            "regenerations": 0, "template_fallbacks": 0,
            "usage": usage if usage is not None else {"m1": {"input_tokens": 1_000_000, "output_tokens": 0, "calls": 1}}}
    return base | kw


def test_headline_denominators():
    rows = [row(), row(goal="H002", cls="automated_wrong"), row(goal="H003", cls="handoff_correct", expected="handoff", handoff=True),
            row(goal="H004", cls="handoff_missed", expected="handoff"), row(goal="H005", cls="harness_error")]
    h = headline(rows)
    assert h["conversations"] == 5 and h["scored"] == 4 and h["excluded"] == {"harness_error": 1}
    assert h["safe_automated_resolution"] == {"value": 0.5, "num": 1, "den": 2}
    assert h["containment"] == {"value": 0.75, "num": 3, "den": 4}
    assert h["missed_transfers"] == {"value": 0.5, "num": 1, "den": 2}
    assert h["unsafe"]["den"] == 4 and h["latency_turn_ms"]["n"] == 8


def test_cost_not_defined_without_successes_and_incomplete_without_prices():
    prices = {"m1": {"input": 3.0, "output": 15.0, "source": "list price", "as_of": "2026-10-01"}}
    c = cost([row(cls="automated_wrong")], prices)
    assert c["status"] == "ok" and c["per_attempted_case"] == 3.0 and c["per_successful_resolution"] == "not defined"
    assert cost([row()], prices)["per_successful_resolution"] == 3.0


def test_unknown_model_makes_cost_incomplete():
    prices = {"m1": {"input": 3.0, "output": 15.0, "source": "list price"}}
    rows = [row(usage={"m1": {"input_tokens": 10, "output_tokens": 0, "calls": 1},
                       "unknown-jev": {"input_tokens": 5, "output_tokens": 0, "calls": 1}})]
    c = cost(rows, prices)
    assert c["status"] == "incomplete" and c["missing_prices"] == ["unknown-jev"]
    # the priced part is still reported, as a lower bound per attempted case: 10 input tokens at $3/1M
    assert c["priced_per_attempted_case"] == round(10 / 1e6 * 3.0, 6) and c["per_attempted_case"] is None
    assert cost([row()], {"m1": {"input": 3.0, "output": 15.0, "source": ""}})["status"] == "incomplete"


def test_bootstrap_keeps_a_goals_repetitions_together():
    rows = [row(goal="A", rep=r) for r in (1, 2, 3)] + [row(goal="B", rep=r, cls="automated_wrong") for r in (1, 2, 3)]
    seen = []

    def fn(sample):
        v = headline(sample)["safe_automated_resolution"]["value"]
        seen.append(v)
        return v

    lo, hi = bootstrap_ci(rows, fn, n_boot=200)
    assert set(seen) <= {0.0, 0.5, 1.0} and 0.0 <= lo <= hi <= 1.0


def test_slices_flag_small_samples_and_gaps():
    rows = [row(goal=f"E{i}", language="es") for i in range(30)] + \
           [row(goal=f"P{i}", language="pt", cls="automated_wrong") for i in range(5)]
    s = slices(rows, "language")
    assert s["values"]["pt"]["small_sample"] and not s["values"]["es"]["small_sample"]
    assert s["gaps"] and s["gaps"][0]["metric"] in ("safe_automated_resolution", "correct_outcome")


def test_variability_agreement():
    rows = [row(goal="A", rep=r) for r in (1, 2, 3)] + [row(goal="B", rep=1), row(goal="B", rep=2, cls="automated_wrong")]
    v = variability(rows)
    assert v["agreement"] == {"value": 0.5, "num": 1, "den": 2}
    assert v["range"]["safe_automated_resolution"] == {"min": 0.5, "max": 1.0}


ASIS = {"metrics": {k: {"value": 0.5, "n": 100} for k in REQUIRED_KEYS}}


def test_legacy_rows_carry_the_label_and_fail_on_missing_keys():
    h = headline([row()])
    rows = legacy_vs_new(ASIS, h, cost([row()], {}), {"legacy": {}})
    assert rows and all(r["label"] == LABEL for r in rows)
    cost_row = next(r for r in rows if r["metric"].startswith("Cost per contact"))
    assert cost_row["legacy"]["value"] == "not computed"
    with pytest.raises(MissingLegacyMetric, match="quality.Transaccional.fcr"):
        legacy_vs_new({"metrics": {}}, h, {}, {})


def test_projection_needs_every_input():
    h = headline([row()])
    assert projected_savings(ASIS, h, {"status": "incomplete"}, {"legacy": {}})["status"] == "not computed"
    cfg = {"legacy": {"cost_per_agent_hour_usd": 36.0, "source": "survey X"}}
    p = projected_savings(ASIS, h, {"status": "ok", "per_attempted_case": 0.01}, cfg)
    assert p["status"] == "ok" and p["label"] == "projection"
