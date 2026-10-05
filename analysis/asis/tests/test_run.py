import json

from asis import metrics
from asis.artifacts import detect_all
from asis.charts import render_all
from asis.reconcile import reconcile
from asis.report import render
from asis.run import main


def test_reconcile_passes_on_exact_match_and_fails_beyond_tolerance(con):
    mt = metrics.collect(con)
    exact = {"interactions_n": 6, "complaints_n": 3, "transaccional_fcr": 0.75}
    assert reconcile(mt, exact)["status"] == "reconciled"
    off = exact | {"interactions_n": 6 * 1.002}
    r = reconcile(mt, off)
    assert r["status"] == "mismatch" and not next(x for x in r["checks"] if x["key"] == "interactions_n")["ok"]
    assert reconcile(mt, None)["status"] == "not reconciled"


def test_charts_are_written(con, tmp_path):
    names = render_all(metrics.collect(con), tmp_path)
    assert names and all((tmp_path / n).stat().st_size > 1000 for n in names)
    assert "asis-dispute-handling.png" in names  # the three dispute numbers for slide 1


def test_report_tags_artifacts_and_states_reconciliation(con):
    mt = metrics.collect(con)
    text = render(mt, detect_all(con), reconcile(mt, None), "2026-10-01", ["asis-demand-by-hour.png"])
    for h in ("## 1. Demand", "## 2. Service quality today", "## 3. Capacity", "## 4. Dispute handling today",
              "## 5. Digital channel", "## 6. Unusable sources", "## 7. Data limits and synthetic artifacts",
              "## 8. Fairness reference"):
        assert h in text
    assert "not reconciled" in text
    wait_line = next(line for line in text.splitlines() if line.startswith("- Wait time"))
    assert "synthetic artifact" in wait_line


def test_run_is_deterministic(data_dir, tmp_path):
    args = ["--data", str(data_dir), "--out", str(tmp_path / "out"), "--reports", str(tmp_path / "rep"), "--date", "2026-10-01"]
    assert main(args) == 0
    first = (tmp_path / "out" / "asis_metrics.json").read_bytes()
    assert main(args) == 0
    assert (tmp_path / "out" / "asis_metrics.json").read_bytes() == first
    doc = json.loads(first)
    assert set(doc) == {"meta", "metrics", "artifacts", "reconciliation"}
    assert doc["meta"]["window"] == ["2025-06-17", "2026-06-17"]
    assert (tmp_path / "rep" / "asis-2026-10-01.md").exists()


def test_run_fails_on_mismatch_without_writing(data_dir, tmp_path):
    counts = tmp_path / "curated.json"
    counts.write_text(json.dumps({"interactions_n": 999, "complaints_n": 3, "transaccional_fcr": 0.75}))
    out = tmp_path / "out"
    assert main(["--data", str(data_dir), "--out", str(out), "--reports", str(tmp_path / "rep"),
                 "--curated-counts", str(counts)]) == 1
    assert not (out / "asis_metrics.json").exists()


def test_report_does_not_call_generator_attributes_evidence(con):
    mt = metrics.collect(con)
    text = render(mt, detect_all(con), reconcile(mt, None), "2026-10-01", [])
    load = next(x for x in text.splitlines() if "total_monthly_interactions" in x)
    assert "synthetic artifact" in load and "evidence" not in load
    assert "logged contacts per agent per month" in text.lower()
    hourly = next(x for x in text.splitlines() if x.startswith("- Contacts per hour of day"))
    assert hourly.endswith("synthetic artifact") or "· synthetic artifact" in hourly
    assert "not evidence" in text.split("## 3. Capacity", 1)[1].split("## 4.", 1)[0]
