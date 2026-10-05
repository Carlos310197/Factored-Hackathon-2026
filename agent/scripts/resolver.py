"""Transaction-resolver pipeline (the resolver design spec (docs/design/)).
Offline tooling; subcommands marked LIVE call Bedrock or Jev and need --live, used only with the owner's approval.

  train          simulated cases → hyperparameter search → MLflow → resolver_runs/<stamp>/finalists.json
  test-sheet     the blind test sheet for Andrés (resolver/data/test_sheet_v1.csv + .json)
  dev-set        LIVE (Bedrock): 300 dev messages → resolver/data/dev_v1.jsonl
  finalize       choose the finalist on dev, fit the temperature; --promote writes artifacts/v1 + MODEL_CARD.md
  jev            LIVE (Jev): B2 / P runs on dev or test → resolver/runs/jev/<set>/<system>_r<k>.jsonl
  tune           dev thresholds → resolver/reports/thresholds_dev.json, thresholds.v2.yaml, figures
  ingest-test    LIVE (Bedrock): Andrés's completed sheet → resolver/data/test_v1.jsonl; prints the SHA-256
  ceiling-sheet  the blind human-ceiling sheet (after the test run)
  report         resolver/reports/eval-<date>.md + errors.csv
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
LIVE = {"dev-set", "ingest-test", "jev"}


def _paths(a):
    return Path(a.data_dir), Path(a.reports_dir), Path(a.runs_dir)


def _resolver(a, temperature: float | None = None):
    from bankagent.resolver.model import Resolver

    r = Resolver.load(Path(a.artifact))
    return r if temperature is None else Resolver(r.spec | {"temperature": temperature}, Path(a.artifact))


def cmd_train(a):
    from bankagent.resolver.histories import TransactionSource, sample_histories
    from bankagent.resolver.simulate import load_sim_config, simulate
    from bankagent.resolver.tracking import MlflowTracker
    from bankagent.resolver.train import search

    src, cfg = TransactionSource(a.serving), load_sim_config()
    train = simulate(sample_histories(src, "train", a.n_train, a.seed), cfg, a.seed)
    val = simulate(sample_histories(src, "dev", a.n_val, a.seed + 1), cfg, a.seed + 1)
    out = AGENT / "resolver_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {"serving_run_id": src.run_id, "seed": a.seed, "n_train": len(train), "n_val": len(val),
            "simulate_version": cfg["version"], "simulate_sha256": cfg["sha256"]}
    finalists = search(train, val, out, MlflowTracker(AGENT / "mlruns"), a.seed, meta)
    print(json.dumps({k: v.__dict__ for k, v in finalists.items()}, indent=1))
    print(f"finalists: {out / 'finalists.json'}")


def cmd_test_sheet(a):
    from bankagent.resolver.histories import TransactionSource, sample_histories
    from bankagent.resolver.simulate import load_sim_config
    from bankagent.resolver.testset import make_test_sheet, write_sheet

    data, _, _ = _paths(a)
    hs = sample_histories(TransactionSource(a.serving), "test", 800, a.seed)
    cases = make_test_sheet(hs, load_sim_config(), a.seed)
    write_sheet(cases, data / "test_sheet_v1")
    print(f"{len(cases)} cases → {data / 'test_sheet_v1.csv'}")


def cmd_dev_set(a):
    from bankagent.llm.client import make_bedrock_client
    from bankagent.llm.config import load_models
    from bankagent.resolver.devset import build_dev_set
    from bankagent.resolver.records import save_jsonl
    from bankagent.resolver.histories import TransactionSource, sample_histories
    from bankagent.resolver.simulate import load_sim_config

    data, _, _ = _paths(a)
    hs = sample_histories(TransactionSource(a.serving), "dev", a.n * 2, a.seed)
    rows, skipped = build_dev_set(hs, load_sim_config(), a.seed, a.n, make_bedrock_client(a.region), load_models())
    save_jsonl(rows, data / "dev_v1.jsonl")
    print(f"{len(rows)} dev rows ({skipped} skipped after LLM errors) → {data / 'dev_v1.jsonl'}")


def cmd_finalize(a):
    from bankagent.resolver.records import load_jsonl
    from bankagent.resolver.finalize import choose_finalist, fit_temperature, promote, write_model_card
    from bankagent.resolver.model import Resolver
    from bankagent.resolver.train import case_metrics

    data, _, _ = _paths(a)
    finalists, dev = json.loads(Path(a.finalists).read_text()), load_jsonl(data / "dev_v1.jsonl")
    family, metrics = choose_finalist(finalists, dev)
    t = fit_temperature(Resolver.load(Path(finalists[family]["path"])), dev)
    print(json.dumps({"chosen": family, "temperature": t, "dev_metrics": metrics}, indent=1))
    if a.promote:
        r = promote(Path(finalists[family]["path"]), t, {"dev_choice": metrics, "promoted_at": date.today().isoformat()},
                    dst=Path(a.artifact))
        print(write_model_card(Path(a.artifact), r, metrics, case_metrics(r, dev, "extraction")))


def cmd_jev(a):
    from bankagent.decisions.jev import JevClient
    from bankagent.decisions.questions import load_question_set
    from bankagent.resolver.records import load_jsonl
    from bankagent.resolver.jev_runs import run_system, runs_path
    from bankagent.settings import Settings

    data, _, runs = _paths(a)
    s = Settings.from_env({"SERVING_URI": "unused"} | dict(os.environ))
    jev = JevClient(s.jev_api_key, s.jev_url, s.jev_model)
    qsets = {"B2": load_question_set("understand.v1"), "P": load_question_set("understand.v2")}
    rows, resolver = load_jsonl(data / f"{a.set}_v1.jsonl"), _resolver(a)
    for rep in range(1, a.repeats + 1):
        n = run_system(rows, a.system, jev, qsets, resolver, runs_path(runs / "jev", a.set, a.system, rep))
        print(f"{a.set} {a.system} run {rep}: {n} new Jev calls")


def _thresholds(reports: Path) -> dict:
    raw = json.loads((reports / "thresholds_dev.json").read_text())
    return {k: (tuple(v) if not k.endswith("_summary") else v) for k, v in raw.items()}


def cmd_tune(a):
    from bankagent.resolver.records import load_jsonl
    from bankagent.resolver.evaluate import plot_curves, plot_reliability, reliability_bins, score_rows, tune_systems
    from bankagent.resolver.jev_runs import load_runs, runs_path
    from bankagent.resolver.tune import write_thresholds_v2

    data, reports, runs = _paths(a)
    reports.mkdir(parents=True, exist_ok=True)
    dev, resolver = load_jsonl(data / "dev_v1.jsonl"), _resolver(a)
    scores, _ = score_rows(dev, resolver)
    dev_runs = {s: load_runs(runs_path(runs / "jev", "dev", s, 1)) for s in ("B2", "P")}
    th, curves = tune_systems(dev, scores, {s: r for s, r in dev_runs.items() if r})
    (reports / "thresholds_dev.json").write_text(json.dumps(th, indent=1, default=list))
    plot_curves(curves, th, reports / "dev_coverage_curve.png")
    plot_reliability(reliability_bins(dev, score_rows(dev, _resolver(a, 1.0))[0]), reliability_bins(dev, scores),
                     reports / "dev_reliability.png")
    if "P" in th:
        print(write_thresholds_v2(*th["P"], dst=Path(a.thresholds_out)))
    print(json.dumps({k: v for k, v in th.items() if not k.endswith("_summary")}))


def cmd_ingest_test(a):
    from bankagent.llm.client import make_bedrock_client
    from bankagent.llm.config import load_models
    from bankagent.resolver.records import save_jsonl
    from bankagent.resolver.testset import ingest_test_set

    data, _, _ = _paths(a)
    rows, digest = ingest_test_set(data / "test_sheet_v1", Path(a.completed), make_bedrock_client(a.region), load_models())
    save_jsonl(rows, data / "test_v1.jsonl")
    print(f"{len(rows)} test rows → {data / 'test_v1.jsonl'}\nSHA-256 of the completed sheet: {digest}")


def cmd_ceiling_sheet(a):
    from bankagent.resolver.records import load_jsonl
    from bankagent.resolver.testset import make_ceiling_sheet

    data, _, _ = _paths(a)
    ids = make_ceiling_sheet(load_jsonl(data / "test_v1.jsonl"), a.n, a.seed, data / "ceiling_v1.csv")
    print(f"{len(ids)} cases → {data / 'ceiling_v1.csv'}")


def cmd_report(a):
    from bankagent.resolver.records import load_jsonl
    from bankagent.resolver.evaluate import (adoption, evaluate, latency_line, render_report, score_rows,
                                             write_error_sheet)
    from bankagent.resolver.jev_runs import load_runs, runs_path
    from bankagent.resolver.metrics import percentile
    from bankagent.resolver.testset import read_ceiling
    from bankagent.resolver.train import case_metrics

    data, reports, runs = _paths(a)
    test, dev, resolver = load_jsonl(data / "test_v1.jsonl"), load_jsonl(data / "dev_v1.jsonl"), _resolver(a)
    th = _thresholds(reports)
    scores, ranker_ms = score_rows(test, resolver)
    test_runs = {s: [r for r in (load_runs(runs_path(runs / "jev", "test", s, k)) for k in (1, 2, 3)) if r]
                 for s in ("B2", "P")}
    results = evaluate(test, scores, th, test_runs)
    ceiling_path = data / "ceiling_v1.csv"
    picks = read_ceiling(ceiling_path, test) if ceiling_path.exists() else {}
    by_id = {r["case_id"]: r for r in test}
    ceiling = {"n": len(picks), "correct": sum(by_id[c]["target_id"] == p for c, p in picks.items())} if picks else None
    errors = write_error_sheet(test, results, scores, picks, reports / "errors.csv")
    lat = [latency_line("ranker scoring (B1)", ranker_ms)]
    tok = {}
    for s, reps in test_runs.items():
        if reps:
            lat.append(latency_line(f"Jev {s}", [r["latency_ms"] for r in reps[0].values() if r.get("latency_ms")]))
            tok[s] = percentile([r["usage"].get("input_tokens", 0) for r in reps[0].values() if r.get("usage")], 0.5)
    tokens = f"Jev median input tokens per call: {tok}" if tok else "Jev not run"
    cal = case_metrics(_resolver(a, 1.0), dev, "extraction")
    text = render_report(day=date.today().isoformat(),
                         versions={"resolver": resolver.version, "family": resolver.spec["metadata"].get("family"),
                                   "question sets": "understand.v1 (B2) / understand.v2 (P)",
                                   "extract": test[0]["versions"]["extract"][1] if test else "n/a"},
                         rows=test, dev_n=len(dev), thresholds=th, results=results, decision=adoption(results, test),
                         latency=lat, tokens=tokens,
                         calibration={"temperature": resolver.temperature, "ece_before": cal["ece"],
                                      "ece_after": case_metrics(resolver, dev, "extraction")["ece"]},
                         ceiling=ceiling, errors=errors)
    out = reports / f"eval-{date.today().isoformat()}.md"
    out.write_text(text, encoding="utf-8")
    print(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(AGENT / "resolver" / "data"))
    ap.add_argument("--reports-dir", default=str(AGENT / "resolver" / "reports"))
    ap.add_argument("--runs-dir", default=str(AGENT / "resolver" / "runs"))
    ap.add_argument("--artifact", default=str(AGENT / "src" / "bankagent" / "resolver" / "artifacts" / "v1"))
    ap.add_argument("--thresholds-out",
                    default=str(AGENT / "src" / "bankagent" / "decisions" / "thresholds.v2.yaml"))
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--live", action="store_true", help="allow Bedrock/Jev calls (owner-approved runs only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("train")
    p.add_argument("--serving", default=str(AGENT / ".serving"))
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-train", type=int, default=30000)
    p.add_argument("--n-val", type=int, default=3000)
    p = sub.add_parser("test-sheet")
    p.add_argument("--serving", default=str(AGENT / ".serving"))
    p.add_argument("--seed", type=int, default=3)
    p = sub.add_parser("dev-set")
    p.add_argument("--serving", default=str(AGENT / ".serving"))
    p.add_argument("--seed", type=int, default=2)
    p.add_argument("--n", type=int, default=300)
    p = sub.add_parser("finalize")
    p.add_argument("--finalists", required=True)
    p.add_argument("--promote", action="store_true")
    p = sub.add_parser("jev")
    p.add_argument("--set", choices=("dev", "test"), required=True)
    p.add_argument("--system", choices=("B2", "P"), required=True)
    p.add_argument("--repeats", type=int, default=1)
    sub.add_parser("tune")
    p = sub.add_parser("ingest-test")
    p.add_argument("--completed", required=True)
    p = sub.add_parser("ceiling-sheet")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=4)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd in LIVE and not a.live:
        print(f"'{a.cmd}' calls Bedrock or Jev: rerun with --live after the owner approves this run.", file=sys.stderr)
        return 2
    {"train": cmd_train, "test-sheet": cmd_test_sheet, "dev-set": cmd_dev_set, "finalize": cmd_finalize,
     "jev": cmd_jev, "tune": cmd_tune, "ingest-test": cmd_ingest_test, "ceiling-sheet": cmd_ceiling_sheet,
     "report": cmd_report}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
