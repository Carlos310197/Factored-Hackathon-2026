from evalkit.compare import LABEL, REQUIRED_KEYS
from evalkit.report import build, charts, render, suggest_cause
from tests.helpers import make_card

ASIS = {"metrics": {k: {"value": 0.5, "n": 100} for k in REQUIRED_KEYS}}
CFG = {"prices": {}, "legacy": {}, "persona": {"model": "p"}, "judge": {"model": "j"}}


def conv(goal, rep, replies, end="done"):
    return {"goal_id": goal, "rep": rep, "session_id": "S", "end_reason": end,
            "turns": [{"i": i, "customer": "m", "reply": r, "latency_ms": 1000, "token_expired": False}
                      for i, r in enumerate(replies)],
            "after": {"disputes": [], "handoffs": [], "records": [], "customer_case_ids": []}}


def test_report_has_every_section_and_labels():
    goals = [make_card(goal_id="H001-dispute_auto"), make_card(goal_id="H002-dispute_auto", language="pt")]
    records = [conv(g.goal_id, r, [{"reply_text": "ok", "language": g.language}]) for g in goals for r in (1, 2, 3)]
    data = build(goals, records, ASIS, CFG)
    text = render(data, "2026-10-04", ["eval-headline.png"])
    for h in ("## 1. Setup", "## 2. Headline results", "## 3. Legacy vs new (shared metrics)", "## 4. Slices",
              "## 5. Results by failure type", "## 6. Error analysis", "## 7. Judge validation and label review",
              "## 8. Limitations", "## 9. Projected savings (projection, not a measurement)"):
        assert h in text
    assert LABEL in text and "not defined" in text and "not computed" in text
    assert data["headline"]["safe_automated_resolution"]["value"] == 0.0


def test_charts_render(tmp_path):
    goals = [make_card()]
    data = build(goals, [conv("H001-dispute_auto", 1, [{"reply_text": "ok", "language": "es"}])], ASIS, CFG)
    names = charts(data, tmp_path)
    assert names and all((tmp_path / n).exists() for n in names)


def test_suggest_cause():
    jev_err = {"after": {"records": [{"kind": "error", "payload": {"role": "jev"}}]}}
    assert suggest_cause(jev_err, {"class": "automated_wrong", "unsafe_types": []}) == "Jev"
    assert suggest_cause({}, {"class": "harness_error", "unsafe_types": []}) == "harness"
    assert suggest_cause({}, {"class": "handoff_missed", "unsafe_types": []}) == "threshold"
    assert suggest_cause({}, {"class": "unsafe", "unsafe_types": ["false_claim"]}) == "compose"
