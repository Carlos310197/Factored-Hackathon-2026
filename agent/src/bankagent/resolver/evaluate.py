"""Four-system evaluation: dev threshold tuning, test outcomes, slices, intervals, error sheet and the markdown report
(resolver spec §6). Offline only."""
import csv
import time
from pathlib import Path

from bankagent.resolver.features import mentions_present
from bankagent.resolver.metrics import bootstrap_ci, metric, paired_bootstrap, percentile, summarize
from bankagent.resolver.model import Resolver, Scores
from bankagent.resolver.systems import b0, b1, jev_decision, outcome
from bankagent.resolver.tune import choose, grid

SUCCESS = ("act_correct", "nil_correct", "ask_hit")
SMALL_N = 30
HEADLINE = ("coverage", "selective_accuracy", "wrong_action_rate", "top3_recall_when_asking", "resolved_one_step")


def score_rows(rows: list[dict], resolver: Resolver) -> tuple[dict[str, Scores], list[float]]:
    scores, latency = {}, []
    for r in rows:
        start = time.perf_counter()
        scores[r["case_id"]] = resolver.score(r["candidates"], r["extraction"]["mentions"])
        latency.append((time.perf_counter() - start) * 1000)
    return scores, latency


def outcomes_b0(rows):
    return [outcome(r["target_id"], b0(r["candidates"], r["extraction"]["mentions"])) for r in rows]


def outcomes_b1(rows, scores, tau, phi):
    return [outcome(r["target_id"], b1(scores[r["case_id"]], tau, phi)) for r in rows]


def outcomes_jev(rows, run: dict[str, dict], t, m):
    return [outcome(r["target_id"], jev_decision((run.get(r["case_id"]) or {}).get("answer"), t, m)) for r in rows]


def tune_systems(dev_rows: list[dict], scores: dict[str, Scores], dev_runs: dict[str, dict]) -> tuple[dict, dict]:
    """Thresholds per system on dev (§6.3) and the curves for the report."""
    th, curves = {}, {}
    pts = [(a, b) for a in grid(0.3, 0.99) for b in grid(0.3, 0.99)]
    th["B1"], best, curves["B1"] = choose(lambda p: outcomes_b1(dev_rows, scores, *p), pts)
    th["B1_summary"] = best
    pts = [(a, b) for a in grid(0.5, 0.99) for b in grid(0.0, 0.5)]
    for system in ("B2", "P"):
        if system in dev_runs:
            th[system], best, curves[system] = choose(lambda p, s=system: outcomes_jev(dev_rows, dev_runs[s], *p), pts)
            th[f"{system}_summary"] = best
    return th, curves


def evaluate(rows: list[dict], scores: dict[str, Scores], th: dict, runs: dict[str, list[dict]]) -> dict[str, list[list[str]]]:
    """system -> one outcome list per repeat (B0 and B1 are deterministic: one repeat)."""
    out = {"B0": [outcomes_b0(rows)], "B1": [outcomes_b1(rows, scores, *th["B1"])]}
    for system in ("B2", "P"):
        if runs.get(system):
            out[system] = [outcomes_jev(rows, run, *th[system]) for run in runs[system]]
    return out


def _fmt(v) -> str:
    return "not defined" if v is None else f"{v:.3f}"


def summary_table(results: dict[str, list[list[str]]], mask: list[bool] | None = None, n_boot: int = 1000) -> str:
    head = "| System | n | " + " | ".join(HEADLINE) + " |\n|" + "---|" * (len(HEADLINE) + 2) + "\n"
    lines = []
    for system, repeats in results.items():
        reps = [[o for o, keep in zip(rep, mask) if keep] if mask else rep for rep in repeats]
        n = len(reps[0])
        cells = []
        for name in HEADLINE:
            vals = [summarize(rep)[name] for rep in reps]
            ci = bootstrap_ci(reps[0], metric(name), n_boot=n_boot)
            cell = _fmt(vals[0]) if len(vals) == 1 else f"{_fmt(sum(v or 0 for v in vals) / len(vals))} (runs {_fmt(min(v or 0 for v in vals))}–{_fmt(max(v or 0 for v in vals))})"
            if ci:
                cell += f" [{ci[0]:.2f}, {ci[1]:.2f}]"
            cells.append(cell)
        flag = " ⚠ small sample" if n < SMALL_N else ""
        lines.append(f"| {system}{flag} | {n} | " + " | ".join(cells) + " |")
    return head + "\n".join(lines)


def slice_masks(rows: list[dict]) -> dict[str, list[bool]]:
    masks = {}
    for key in ("slice", "lang", "country"):
        for value in sorted({str(r.get(key)) for r in rows}):
            masks[f"{key} = {value}"] = [str(r.get(key)) == value for r in rows]
    return masks


def suggest_cause(row: dict, p_outcome: str, score: Scores, ceiling: dict[str, str | None]) -> str:
    if row["case_id"] in ceiling and ceiling[row["case_id"]] != row["target_id"]:
        return "genuinely_ambiguous"
    ex = row["extraction"]
    if "error" in ex or (not mentions_present(ex["mentions"]) and not row["style"].get("no_detail")):
        return "extract_missed"
    top = score.ranked[0] if score.ranked else None
    if row["target_id"] is not None and top == row["target_id"] and p_outcome not in SUCCESS:
        return "jev_overrode_ranker"
    if row["target_id"] is not None and top != row["target_id"]:
        return "ranker_wrong"
    return "simulator_gap_or_other"


def write_error_sheet(rows, results, scores, ceiling, path: Path) -> list[dict]:
    """Every failed P case (B1 when P was not run) with a suggested cause; cause_confirmed is filled by hand and kept
    when the sheet is regenerated."""
    system = "P" if "P" in results else "B1"
    confirmed = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            confirmed = {r["case_id"]: r.get("cause_confirmed", "") for r in csv.DictReader(f)}
    out = []
    for r, o in zip(rows, results[system][0]):
        if o in SUCCESS:
            continue
        out.append({"case_id": r["case_id"], "system": system, "outcome": o, "slice": r["slice"], "lang": r["lang"],
                    "message": r["message"], "mentions": r["extraction"]["mentions"],
                    "ranker_top": (scores[r["case_id"]].ranked or [None])[0], "target_id": r["target_id"],
                    "cause_suggested": suggest_cause(r, o, scores[r["case_id"]], ceiling),
                    "cause_confirmed": confirmed.get(r["case_id"], "")})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]) if out else ["case_id"])
        w.writeheader()
        w.writerows(out)
    return out


def plot_curves(curves: dict[str, list[dict]], chosen: dict, path: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    for system, curve in curves.items():
        pts = sorted({(c["coverage"] or 0.0, c["wrong_action_rate"] or 0.0) for c in curve})
        ax.plot([p[0] for p in pts], [p[1] for p in pts], ".", ms=2, label=system, alpha=0.6)
        best = chosen.get(f"{system}_summary")
        if best:
            ax.plot(best["coverage"], best["wrong_action_rate"], "k*", ms=10)
    ax.axhline(0.02, color="grey", lw=0.8, ls="--")
    ax.set_xlabel("coverage (acted / all)")
    ax.set_ylabel("wrong-action rate")
    ax.set_title("Dev: coverage vs wrong actions (★ chosen)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_reliability(bins_before: list[tuple], bins_after: list[tuple], path: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls="--")
    for label, bins in (("T = 1", bins_before), ("calibrated", bins_after)):
        ax.plot([b[0] for b in bins], [b[1] for b in bins], "o-", label=label)
    ax.set_xlabel("predicted probability of top candidate")
    ax.set_ylabel("observed accuracy")
    ax.set_title("Dev reliability")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def reliability_bins(rows: list[dict], scores: dict[str, Scores], bins: int = 10) -> list[tuple[float, float, int]]:
    pairs = [(scores[r["case_id"]].probs[scores[r["case_id"]].ranked[0]], scores[r["case_id"]].ranked[0] == r["target_id"])
             for r in rows if r["target_id"] is not None and scores[r["case_id"]].ranked]
    out = []
    for b in range(bins):
        sel = [(p, h) for p, h in pairs if min(int(p * bins), bins - 1) == b]
        if sel:
            out.append((sum(p for p, _ in sel) / len(sel), sum(h for _, h in sel) / len(sel), len(sel)))
    return out


def adoption(results: dict[str, list[list[str]]], rows: list[dict]) -> dict:
    """Resolver spec §6.4: P replaces B2 iff wrong-action(P) <= wrong-action(B2) and hard resolved(P) > hard(B2)."""
    if "P" not in results or "B2" not in results:
        return {"decision": "not_run", "reason": "Jev runs missing for B2 or P"}
    hard = [r["slice"] == "hard" for r in rows]

    def mean(system, name, mask=None):
        vals = [summarize([o for o, k in zip(rep, mask) if k] if mask else rep)[name] or 0.0 for rep in results[system]]
        return sum(vals) / len(vals)

    w_p, w_b = mean("P", "wrong_action_rate"), mean("B2", "wrong_action_rate")
    h_p, h_b = mean("P", "resolved_one_step", hard), mean("B2", "resolved_one_step", hard)
    adopt = w_p <= w_b and h_p > h_b
    return {"decision": "adopt_P" if adopt else "keep_B2", "wrong_action": {"P": w_p, "B2": w_b},
            "hard_resolved_one_step": {"P": h_p, "B2": h_b},
            "paired_wrong_action_P_minus_B2": paired_bootstrap(results["P"][0], results["B2"][0], metric("wrong_action_rate")),
            "paired_hard_resolved_P_minus_B2": paired_bootstrap(
                [o for o, k in zip(results["P"][0], hard) if k], [o for o, k in zip(results["B2"][0], hard) if k],
                metric("resolved_one_step"))}


def latency_line(name: str, values: list[float]) -> str:
    return f"- {name}: p50 {_fmt(percentile(values, 0.5))} ms, p95 {_fmt(percentile(values, 0.95))} ms (n={len(values)})"


def cause_counts(errors: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in errors:
        key = e["cause_confirmed"] or f"{e['cause_suggested']} (unconfirmed)"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def render_report(*, day: str, versions: dict, rows: list[dict], dev_n: int, thresholds: dict,
                  results: dict[str, list[list[str]]], decision: dict, latency: list[str], tokens: str,
                  calibration: dict, ceiling: dict | None, errors: list[dict], n_boot: int = 1000) -> str:
    masks = slice_masks(rows)
    slices = "\n\n".join(f"### {name}\n\n{summary_table(results, mask, n_boot)}" for name, mask in masks.items())
    th = {k: v for k, v in thresholds.items() if not k.endswith("_summary")}
    counts = cause_counts(errors)
    examples = "\n".join(f"- `{e['case_id']}` ({e['lang']}, {e['slice']}, {e['outcome']}): \"{e['message']}\" → "
                          f"{e['cause_confirmed'] or e['cause_suggested'] + ' (unconfirmed)'}" for e in errors[:5])
    ceil = ("not run" if not ceiling else
            f"{ceiling['correct']}/{ceiling['n']} = {ceiling['correct'] / ceiling['n']:.3f} (blind, after the test run)")
    return f"""# Transaction resolver evaluation, {day}

Spec: the resolver design spec (`docs/design/`, §6). Offline evaluation on a held-out,
team-written test set. This is not a production measurement.

## Setup
- Test set: {len(rows)} cases written blind by Andrés (`resolver/data/test_v1.jsonl`); dev: {dev_n} cases.
- Versions: {", ".join(f"{k} `{v}`" for k, v in versions.items())}.
- Thresholds (chosen on dev, frozen before the test run): `{th}`.
- Jev systems (B2, P) were run {len(results.get("P", results.get("B2", [[]])))} time(s) per case; cells show the mean,
  the range over runs, and a 95% bootstrap interval on run 1. Intervals of about ±7 points are expected at n = 150.

## Results (all cases)

{summary_table(results, None, n_boot)}

## Slices

{slices}

## Adoption decision (rule fixed in spec §6.4 before the test run)
- Decision: **{decision["decision"]}**
- Details: `{ {k: v for k, v in decision.items() if k != "decision"} }`

## Calibration (dev)
- Temperature {calibration["temperature"]:.3f}; ECE {_fmt(calibration["ece_before"])} → {_fmt(calibration["ece_after"])}.
- Figures: `dev_reliability.png`, `dev_coverage_curve.png`.

## Latency and cost
{chr(10).join(latency)}
- {tokens}

## Human ceiling
{ceil}

## Error analysis ({len(errors)} failed cases of the {"P" if "P" in results else "B1"} system)
{chr(10).join(f"- {k}: {v}" for k, v in counts.items()) or "- none"}

Examples:
{examples or "- none"}

## Limitations
- Training mentions are simulated; the style rates are assumptions (`simulate.yaml`).
- Portuguese messages describe the histories of Spanish-speaking customers; country is the customer's most frequent
  transaction country (histories carry no customer attributes).
- Slices marked ⚠ have fewer than {SMALL_N} cases and are not conclusive. Zero observed errors does not mean zero risk.
"""
