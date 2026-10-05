import json

import pytest

from bankagent.decisions.jev import JevError, JevResult, state_hash, validate_answers
from bankagent.decisions.questions import load_question_set
from bankagent.resolver.evaluate import (adoption, evaluate, plot_curves, plot_reliability, reliability_bins,
                                         score_rows, slice_masks, summary_table, tune_systems, write_error_sheet)
from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.jev_runs import load_runs, run_system, runs_path
from bankagent.resolver.model import Resolver
from bankagent.resolver.records import save_jsonl
from bankagent.resolver.simulate import load_sim_config, simulate
from bankagent.resolver.train import search
from scripts.resolver import main
from tests.fakes import understand_answers
from tests.resolver_data import write_logreg_artifact
from tests.test_resolver_cli import dirs
from tests.test_resolver_train import ListTracker

QSETS = {"B2": load_question_set("understand.v1"), "P": load_question_set("understand.v2")}


class ScriptedJev:
    """Follows the match scores when present (P), else answers c1 (B2). Fails on every `fail_every`-th call."""

    def __init__(self, fail_every: int = 0):
        self.calls, self.fail_every = [], fail_every

    def decide(self, state, questions):
        self.calls.append(questions)
        if self.fail_every and len(self.calls) % self.fail_every == 0:
            raise JevError("scripted")
        cands = state["candidate_transactions"]
        best = max(cands, key=lambda c: c.get("match", 0.0))["alias"] if cands else None
        answers = understand_answers(questions, target=best, tp=0.9)
        return JevResult(validate_answers(questions, {"answers": answers}), {"input_tokens": 100 + len(str(state))}, 5,
                         state_hash(state), "fake-jev")


def rows_for(history_serving, split, n, seed):
    cases = simulate(sample_histories(TransactionSource(history_serving), split, n, seed=seed), load_sim_config(), seed)
    return [c | {"lang": ("es", "pt")[i % 2], "country": "México", "message": f"m{i}",
                 "extraction": {"mentions": c["mentions"], "english_gloss": "EN"}} for i, c in enumerate(cases)]


@pytest.fixture(scope="module")
def world(history_serving, tmp_path_factory):
    root = tmp_path_factory.mktemp("eval")
    write_logreg_artifact(root / "model")
    resolver = Resolver.load(root / "model")
    dev, test = rows_for(history_serving, "dev", 80, 21), rows_for(history_serving, "test", 60, 22)
    runs = {}
    for set_name, rows in (("dev", dev), ("test", test)):
        for system in ("B2", "P"):
            for rep in ((1,) if set_name == "dev" else (1, 2)):
                path = runs_path(root / "jev", set_name, system, rep)
                run_system(rows, system, ScriptedJev(), QSETS, resolver, path)
                runs.setdefault(set_name, {}).setdefault(system, []).append(load_runs(path))
    return root, resolver, dev, test, runs


def test_runs_are_cached_and_resumable(world, history_serving, tmp_path):
    _, resolver, dev, _, _ = world
    path = runs_path(tmp_path, "dev", "P", 1)
    jev = ScriptedJev(fail_every=4)
    assert run_system(dev[:10], "P", jev, QSETS, resolver, path) == 10
    assert run_system(dev[:10], "P", ScriptedJev(), QSETS, resolver, path) == 0
    recs = load_runs(path)
    assert len(recs) == 10 and sum(r["answer"] is None for r in recs.values()) == 2
    assert all(r["question_set"] == "understand.v2" for r in recs.values())
    assert all(" · match " in d for q in jev.calls for a, d in q["target_transaction"]["criteria"].items() if a.startswith("c"))
    with pytest.raises(ValueError):
        run_system(dev[:1], "B9", jev, QSETS, resolver, path)


def test_tune_evaluate_report_pieces(world):
    root, resolver, dev, test, runs = world
    dev_scores, _ = score_rows(dev, resolver)
    th, curves = tune_systems(dev, dev_scores, {s: runs["dev"][s][0] for s in ("B2", "P")})
    assert set(curves) == {"B1", "B2", "P"} and len(th["B1"]) == 2 and len(th["P"]) == 2
    assert th["B1_summary"]["wrong_action_rate"] <= 0.02 or th["B1_summary"]["feasible"] is False
    test_scores, latency = score_rows(test, resolver)
    results = evaluate(test, test_scores, th, runs["test"])
    assert set(results) == {"B0", "B1", "B2", "P"} and len(results["P"]) == 2 and len(results["B0"][0]) == len(test)
    table = summary_table(results, n_boot=50)
    assert table.count("\n") == 5 and "(runs " in table
    masks = slice_masks(test)
    assert "slice = hard" in masks and "lang = pt" in masks and "country = México" in masks
    assert "⚠ small sample" in summary_table(results, masks["slice = nil"], n_boot=20)
    decision = adoption(results, test)
    assert decision["decision"] in ("adopt_P", "keep_B2") and "paired_wrong_action_P_minus_B2" in decision
    errors = write_error_sheet(test, results, test_scores, {}, root / "errors.csv")
    assert all(e["cause_suggested"] in ("genuinely_ambiguous", "extract_missed", "jev_overrode_ranker", "ranker_wrong",
                                        "simulator_gap_or_other") for e in errors)
    assert plot_curves(curves, th, root / "curve.png").stat().st_size > 1000
    bins = reliability_bins(dev, dev_scores)
    assert plot_reliability(bins, bins, root / "rel.png").stat().st_size > 1000
    assert len(latency) == len(test) and max(latency) < 50


def test_adoption_not_run_without_jev(world):
    _, _, _, test, _ = world
    assert adoption({"B0": [["ask_hit"] * len(test)]}, test)["decision"] == "not_run"


def test_offline_flow_finalize_tune_report(tmp_path, history_serving):
    dev, test = rows_for(history_serving, "dev", 60, 31), rows_for(history_serving, "test", 40, 32)
    for r in test:
        r["versions"] = {"extract": ["m", "extract.v2"]}
    save_jsonl(dev, tmp_path / "data" / "dev_v1.jsonl")
    save_jsonl(test, tmp_path / "data" / "test_v1.jsonl")
    train = rows_for(history_serving, "train", 300, 33)
    finalists = search(train, dev, tmp_path / "train", ListTracker(), seed=1, metadata={"serving_run_id": "fx"},
                       logreg_grid=[{"C": 1.0}], lgbm_grid=[{"num_leaves": 7, "learning_rate": 0.1, "n_estimators": 30}])
    assert main(dirs(tmp_path) + ["finalize", "--finalists", str(tmp_path / "train" / "finalists.json"),
                                  "--promote"]) == 0
    resolver = Resolver.load(tmp_path / "artifact")
    assert (tmp_path / "artifact" / "MODEL_CARD.md").exists() and resolver.temperature != 1.0
    for set_name, rows, reps in (("dev", dev, (1,)), ("test", test, (1, 2))):
        for system in ("B2", "P"):
            for k in reps:
                run_system(rows, system, ScriptedJev(), QSETS, resolver, runs_path(tmp_path / "runs" / "jev", set_name, system, k))
    assert main(dirs(tmp_path) + ["tune"]) == 0
    th = json.loads((tmp_path / "reports" / "thresholds_dev.json").read_text())
    assert {"B1", "B2", "P"} <= set(th) and (tmp_path / "thresholds.v2.yaml").exists()
    assert (tmp_path / "reports" / "dev_reliability.png").exists()
    assert main(dirs(tmp_path) + ["report"]) == 0
    report = next((tmp_path / "reports").glob("eval-*.md")).read_text()
    for section in ("## Results (all cases)", "## Slices", "## Adoption decision", "## Calibration (dev)",
                    "## Latency and cost", "## Human ceiling", "## Error analysis", "## Limitations"):
        assert section in report
    assert "| B0 |" in report and "| P |" in report and (tmp_path / "reports" / "errors.csv").exists()
    assert finalists
