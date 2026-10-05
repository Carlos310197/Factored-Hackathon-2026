from collections import namedtuple

from bankagent.decisions.thresholds import load_thresholds
from bankagent.resolver.metrics import bootstrap_ci, metric, paired_bootstrap, percentile, summarize
from bankagent.resolver.systems import Decision, b0, b1, jev_decision, outcome
from bankagent.resolver.tune import choose, grid, write_thresholds_v2
from tests.resolver_data import mentions, txn

# Stand-in with the fields of bankagent.resolver.model.Scores (unit 31), so this suite does not depend on it.
Scores = namedtuple("Scores", "probs p_none ranked best_raw_fit contributions version")

A, B, C = txn(1)["transaction_id"], txn(2)["transaction_id"], txn(3)["transaction_id"]
CANDS = [txn(1, merchant="Netflix", amount=15.99), txn(2, merchant="Netflix", amount=15.99),
         txn(3, merchant="Amazon", amount=120.0, day="2026-06-01")]


def test_outcomes():
    assert outcome(A, Decision("act", A)) == "act_correct" and outcome(A, Decision("act", B)) == "act_wrong"
    assert outcome(None, Decision("act", B)) == "act_wrong"
    assert outcome(A, Decision("ask", options=(B, A))) == "ask_hit" and outcome(A, Decision("ask")) == "ask_miss"
    assert outcome(None, Decision("ask", options=(A,))) == "ask_nil"
    assert outcome(None, Decision("nil")) == "nil_correct" and outcome(A, Decision("nil")) == "nil_wrong"


def test_b0_acts_only_on_a_unique_filter_match():
    assert b0(CANDS, mentions(merchant="amazon")) == Decision("act", C)
    assert b0(CANDS, mentions(merchant="netflix")) == Decision("ask", options=(A, B))
    assert b0(CANDS, mentions(type_hint="purchase")) == Decision("ask", options=(A, B, C))
    assert b0(CANDS, mentions(merchant="oxxo")).options == (A, B, C)


def test_b1_thresholds():
    s = Scores({A: 0.9, B: 0.05, C: 0.03}, 0.02, [A, B, C], 0.8, {}, "v")
    assert b1(s, 0.85, 0.5) == Decision("act", A)
    assert b1(s, 0.95, 0.5) == Decision("ask", options=(A, B, C))
    assert b1(s, 0.85, 0.9) == Decision("nil")
    assert b1(Scores({}, 1.0, [], 0.0, {}, "v"), 0.5, 0.1) == Decision("nil")


def test_jev_decision():
    ans = {"label": A, "probs": {A: 0.9, B: 0.05, "not_in_list": 0.03, "ambiguous": 0.02}}
    assert jev_decision(ans, 0.85, 0.2) == Decision("act", A)
    assert jev_decision(ans, 0.95, 0.2) == Decision("ask", options=(A, B))
    nil = {"label": "not_in_list", "probs": {"not_in_list": 0.9, A: 0.1}}
    assert jev_decision(nil, 0.8, 0.2) == Decision("nil")
    amb = {"label": "ambiguous", "probs": {"ambiguous": 0.6, A: 0.3, B: 0.1}}
    assert jev_decision(amb, 0.5, 0.0) == Decision("ask", options=(A, B))
    assert jev_decision(None, 0.5, 0.0) == Decision("ask")


def test_summary_rates_and_denominators():
    s = summarize(["act_correct"] * 6 + ["act_wrong"] + ["ask_hit"] * 2 + ["ask_miss", "ask_nil", "nil_correct"])
    assert s["n"] == 12 and s["coverage"] == 7 / 12 and s["selective_accuracy"] == 6 / 7
    assert s["wrong_action_rate"] == 1 / 12 and s["top3_recall_when_asking"] == 2 / 3
    assert s["resolved_one_step"] == 9 / 12
    assert summarize(["ask_miss"])["selective_accuracy"] is None


def test_bootstrap_intervals():
    out = ["act_correct"] * 80 + ["act_wrong"] * 20
    lo, hi = bootstrap_ci(out, metric("selective_accuracy"), n_boot=300)
    assert lo < 0.8 < hi and hi - lo < 0.2
    diff, dlo, dhi = paired_bootstrap(["act_correct"] * 100, out, metric("selective_accuracy"), n_boot=300)
    assert abs(diff - 0.2) < 1e-9 and dlo > 0
    assert percentile([5, 1, 3, 2, 4], 0.5) == 3 and percentile([], 0.5) is None


def test_choose_prefers_coverage_within_the_wrong_action_limit():
    table = {(0.5,): ["act_correct"] * 90 + ["act_wrong"] * 10, (0.8,): ["act_correct"] * 70 + ["ask_hit"] * 29 +
             ["act_wrong"], (0.9,): ["act_correct"] * 50 + ["ask_hit"] * 50}
    point, best, curve = choose(lambda p: table[p], list(table))
    assert point == (0.8,) and best["feasible"] and len(curve) == 3
    point, best, _ = choose(lambda p: ["act_wrong"] * (1 if p == (0.9,) else 5) + ["act_correct"] * 5,
                            [(0.5,), (0.9,)])
    assert point == (0.9,) and best["feasible"] is False
    assert grid(0.5, 0.52) == [0.5, 0.51, 0.52]


def test_thresholds_v2_changes_only_the_target(tmp_path):
    dst = write_thresholds_v2(0.77, 0.12, dst=tmp_path / "thresholds.v2.yaml")
    v1, v2 = load_thresholds(), load_thresholds(dst)
    assert v2.version == "thresholds.v2" and (v2.target_min_p, v2.target_min_margin) == (0.77, 0.12)
    assert v2.intent_min_p == v1.intent_min_p and v2.handoff_noul == v1.handoff_noul
