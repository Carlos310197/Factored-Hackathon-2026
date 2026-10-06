from evalkit.thresholds_check import check, max_p, render

from tests.helpers import make_card


def _rec(goal_id, *ps, signal="reports_unauthorized_use", rep=1):
    records = [{"kind": "jev", "node": "understand", "payload": {"answers": {signal: {"p": p}}}} for p in ps]
    records.append({"kind": "jev", "node": "reply", "payload": {"answers": {signal: {"p": 0.99}}}})
    return {"goal_id": goal_id, "rep": rep, "after": {"records": records}}


def _card(goal_id, group, reasons=()):
    return make_card(goal_id=goal_id, group=group,
                     expected={"outcome": "handoff", "action": None, "handoff_reasons": list(reasons), "must_not": []})


def test_max_p_reads_only_understand_turns():
    assert max_p(_rec("H1", 0.2, 0.7), "reports_unauthorized_use") == 0.7
    assert max_p(_rec("H1"), "reports_unauthorized_use") is None


def test_check_counts_catches_false_alarms_and_margin():
    cards = [_card("H1-human_unauthorized", "human_unauthorized", ["reports_unauthorized_use"]),
             _card("H2-dispute_auto", "dispute_auto"), _card("H3-account_info", "account_info")]
    recs = [_rec("H1-human_unauthorized", 0.1, 0.97), _rec("H2-dispute_auto", 0.78), _rec("H3-account_info", 0.05)]
    row = check(cards, recs, {"reports_unauthorized_use": 0.5})[0]
    assert row["signal"] == "reports_unauthorized_use"
    assert (row["caught"], row["positives"]) == (1, 1)
    assert (row["false_alarms"], row["negatives"]) == (1, 2)
    assert row["min_positive"] == 0.97 and row["max_negative"] == 0.78
    assert row["separable"] is True
    assert row["clean_range"] == (0.78, 0.97)
    assert row["false_alarm_groups"] == {"dispute_auto": 1} and row["missed"] == []


def test_injection_is_labelled_by_goal_group_and_overlap_is_flagged():
    cards = [_card("H1-injection", "injection"), _card("H2-account_info", "account_info")]
    recs = [_rec("H1-injection", 0.39, signal="injection_attempt"), _rec("H2-account_info", 0.78, signal="injection_attempt")]
    row = check(cards, recs, {"injection_attempt": 0.5})[0]
    assert (row["caught"], row["positives"], row["false_alarms"]) == (0, 1, 1)
    assert row["separable"] is False and row["clean_range"] is None
    assert row["missed"] == ["H1-injection"] and row["false_alarm_groups"] == {"account_info": 1}


def test_render_names_the_run_and_every_signal():
    cards = [_card("H1-human_unauthorized", "human_unauthorized", ["reports_unauthorized_use"])]
    rows = check(cards, [_rec("H1-human_unauthorized", 0.97)], {"reports_unauthorized_use": 0.5})
    md = render(rows, "20261005-heldout", "thresholds.v2")
    assert "20261005-heldout" in md and "thresholds.v2" in md and "reports_unauthorized_use" in md
    assert "missed: none" in md
