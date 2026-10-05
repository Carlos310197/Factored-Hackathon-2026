"""python -m evalkit.report: classifications, metrics, comparison and reports/eval-<date>.md (spec §6)."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from evalkit.classify import CORRECT, classify  # noqa: E402
from evalkit.compare import LABEL, fairness_rows, legacy_vs_new, projected_savings  # noqa: E402
from evalkit.goals import read_goals  # noqa: E402
from evalkit.judge import validate  # noqa: E402
from evalkit.metrics import bootstrap_ci, by_family, cost, headline, slices, variability  # noqa: E402

SERIES, ACCENT, INK, MUTED, LINE = "#2A78D6", "#EB6834", "#1E2A38", "#5B6878", "#DCE2EA"
CI_METRICS = ("safe_automated_resolution", "containment", "unsafe", "correct_outcome")
FAILURE_FAMILIES = ("injection", "other_customer", "expired", "tool_failure", "bad_data", "multilingual")
LIMITATIONS = (
    "The data is synthetic; several outcomes are assigned at fixed rates (see the as-is report, section 7).",
    "No Portuguese-speaking customers exist in the data; Portuguese goals describe Spanish-speaking customers' "
    "histories.",
    "Customers are simulated by a language model; the discard count shows how often it went off-script.",
    "120 goals give wide intervals on rare classes; zero observed unsafe outcomes does not establish zero risk.",
    "Every number is an offline measurement on a simulated workload, not a production result.",
    "There is no system-level same-workload baseline; the learned component's baseline is the resolver's B0-vs-P "
    "comparison (resolver report).",
)


def suggest_cause(rec: dict, row: dict) -> str:
    if row["class"] == "harness_error":
        return "harness"
    if row["class"] == "persona_discarded":
        return "persona"
    roles = {(r.get("payload") or {}).get("role") for r in (rec.get("after") or {}).get("records") or []
             if r.get("kind") == "error"}
    if "extract" in roles:
        return "extract"
    if "jev" in roles:
        return "Jev"
    if row["class"] in ("handoff_missed", "handoff_unnecessary"):
        return "threshold"
    if "false_claim" in row["unsafe_types"]:
        return "compose"
    if "wrong_outcome" in row["unsafe_types"]:
        return "policy"
    return ""


def _versions(records: list[dict]) -> dict:
    out: dict[str, set] = {}
    for rec in records:
        for r in (rec.get("after") or {}).get("records") or []:
            for k, v in (r.get("versions") or {}).items():
                out.setdefault(k, set()).add(str(v))
    return {k: sorted(v) for k, v in sorted(out.items())}


def build(goals, records, asis, cfg, judgments=None, labeled=None, review=None, causes=None, manifest=None) -> dict:
    cards = {g.goal_id: g for g in goals}
    pairs = [(rec, classify(cards[rec["goal_id"]], rec)) for rec in records]
    rows = [row for _, row in pairs]
    head = headline(rows)
    ci = {k: bootstrap_ci(rows, lambda s, k=k: headline(s)[k]["value"]) for k in CI_METRICS}
    c = cost(rows, cfg.get("prices") or {})
    failed = [(rec, row) for rec, row in pairs if row["class"] not in CORRECT]
    causes = causes or {}
    errors = [{"goal_id": row["goal_id"], "rep": row["rep"], "class": row["class"],
               "unsafe_types": ";".join(row["unsafe_types"]),
               "cause": causes.get((row["goal_id"], row["rep"])) or suggest_cause(rec, row)} for rec, row in failed]
    return {"manifest": manifest or {}, "mix": dict(Counter(g.group for g in goals)), "rows": rows,
            "headline": head, "ci": ci, "cost": c, "by_family": by_family(rows),
            "slices": {d: slices(rows, d) for d in ("language", "country", "segment")},
            "variability": variability(rows), "legacy": legacy_vs_new(asis, head, c, cfg),
            "fairness": fairness_rows(asis, rows), "savings": projected_savings(asis, head, c, cfg),
            "errors": errors, "error_causes": dict(Counter(e["cause"] or "unassigned" for e in errors)),
            "judge": validate(judgments, labeled) if judgments and labeled else None,
            "review": review, "versions": _versions(records), "prices": cfg.get("prices") or {},
            "legacy_cost_cfg": cfg.get("legacy") or {}}


def _r(x: dict | None, ci=None) -> str:
    if not x or x.get("value") is None:
        return f"not defined (0/{x['den'] if x else 0})"
    s = f"{x['value']:.1%} ({x['num']}/{x['den']})"
    return s + (f" [95% CI {ci[0]:.1%}–{ci[1]:.1%}]" if ci else "")


def _cell(v) -> str:
    if isinstance(v, dict) and "num" in v:
        return _r(v)
    if isinstance(v, dict) and "value" in v and "n" in v:
        return f"{v['value']} (n={v['n']:,})" if isinstance(v["value"], (int, float)) else str(v["value"])
    if isinstance(v, dict):
        return ", ".join(f"{k} {val}" for k, val in v.items() if k not in ("reason", "label"))
    return str(v)


def render(d: dict, date: str, figures: list[str]) -> str:
    h, c, man = d["headline"], d["cost"], d["manifest"]
    L = ["# Evaluation of the LATAM Bank agent", "",
         f"Generated {date}. Offline simulation with simulated customers; not a production measurement.", "",
         "## 1. Setup", "",
         f"- Goals: {sum(d['mix'].values())} ({', '.join(f'{g} {n}' for g, n in d['mix'].items())})",
         f"- Held-out goal set SHA-256: `{man.get('goals_sha256', 'n/a')}`; run `{man.get('run_id', 'n/a')}`; "
         f"agent git SHA `{man.get('git_sha', 'n/a')}`; repetitions {man.get('reps', 'n/a')}",
         f"- Models: agent {man.get('agent_models', {})}, prompts {man.get('prompt_versions', {})}, "
         f"Jev {man.get('jev_model', 'n/a')}, persona {man.get('persona_model', 'n/a')}, judge {man.get('judge_model', 'n/a')}",
         f"- Versions seen in decision records: {d['versions']}",
         f"- Prices (USD per 1M tokens): " + "; ".join(f"{m}: in {p.get('input')}, out {p.get('output')}, source "
                                                      f"'{p.get('source')}'" for m, p in d["prices"].items()),
         "", "## 2. Headline results", "",
         f"Conversations {h['conversations']}, scored {h['scored']}, excluded {h['excluded']}.", "",
         "| Metric | Result |", "|---|---|",
         f"| Safe automated resolution (in-scope goals) | {_r(h['safe_automated_resolution'], d['ci']['safe_automated_resolution'])} |",
         f"| Automation attempted (in-scope goals) | {_r(h['automation_attempted'])} |",
         f"| Containment (not a success measure on its own) | {_r(h['containment'], d['ci']['containment'])} |",
         f"| Correct outcome (all goals) | {_r(h['correct_outcome'], d['ci']['correct_outcome'])} |",
         f"| Missed transfers | {_r(h['missed_transfers'])} |",
         f"| Unnecessary transfers | {_r(h['unnecessary_transfers'])} |",
         f"| Handoff reason match | {_r(h['handoff_reason_match'])} |",
         f"| Unsafe outcomes | {_r(h['unsafe'], d['ci']['unsafe'])} |"]
    L += [f"| Unsafe: {t} | {_r(x)} |" for t, x in h["unsafe_by_type"].items()]
    L += [f"| Turns to resolution after clarifying (p50) | {h['turns_to_resolution']['p50']} (n={h['turns_to_resolution']['n']}) |",
          f"| Latency per turn p50 / p95 (ms) | {h['latency_turn_ms']['p50']} / {h['latency_turn_ms']['p95']} (n={h['latency_turn_ms']['n']}) |",
          f"| Latency per conversation p50 / p95 (ms) | {h['latency_conversation_ms']['p50']} / {h['latency_conversation_ms']['p95']} |",
          f"| Reply regenerations / template fallbacks (turns) | {h['regeneration_turns']} / {h['template_fallback_turns']} |",
          f"| Cost status | {c['status']}{' (missing: ' + ', '.join(c.get('missing_prices', [])) + ')' if c['status'] != 'ok' else ''} |",
          f"| Cost per attempted case (USD) | {c.get('per_attempted_case')} |",
          *([f"| Priced models only, per attempted case (USD, lower bound) | {c['priced_per_attempted_case']} |"]
            if c.get("priced_per_attempted_case") is not None else []),
          f"| Cost per successful automated resolution (USD) | {c.get('per_successful_resolution') if c.get('per_successful_resolution') is not None else 'not defined'} |",
          "", f"Variability across repetitions: outcome agreement {_r(d['variability']['agreement'])}; ranges {d['variability']['range']}."]
    L += ["", "## 3. Legacy vs new (shared metrics)", "", f"Every row: *{LABEL}*.", "",
          "| Metric | Legacy (historical) | New (offline simulation) | Note |", "|---|---|---|---|"]
    L += [f"| {r['metric']} | {_cell(r['legacy'])} | {_cell(r['new'])} | {r['note']} |" for r in d["legacy"]]
    L += ["", "CSAT, CES, NPS and sentiment are not compared: the new system has no surveys and an LLM proxy for "
              "satisfaction is not valid.", "", "| Dimension | Value | Legacy FCR | New safe resolution | n | |",
          "|---|---|---|---|---|---|"]
    L += [f"| {r['dimension']} | {r['value']} | {_cell(r['legacy_fcr']) if r['legacy_fcr'] else 'n/a'} | "
          f"{_r(r['new_safe_resolution'])} | {r['n']} | {'small sample, not conclusive' if r['small_sample'] else ''} |"
          for r in d["fairness"]]
    L += ["", "## 4. Slices", ""]
    for dim, s in d["slices"].items():
        L += [f"### By {dim}", "", "| Value | n | Safe resolution | Correct outcome | Unsafe | |", "|---|---|---|---|---|---|"]
        L += [f"| {k} | {x['n']} | {_r(x['safe_automated_resolution'])} | {_r(x['correct_outcome'])} | {_r(x['unsafe'])} | "
              f"{'small sample, not conclusive' if x['small_sample'] else ''} |" for k, x in s["values"].items()]
        L += [f"- Gap to investigate: {g['metric']} {g['high']} vs {g['low']}, {g['gap']:.1%}" for g in s["gaps"]] + [""]
    L += ["## 5. Results by failure type", "", "| Family | Correct | Unsafe | Classes |", "|---|---|---|---|"]
    L += [f"| {f} | {_r(x['correct'])} | {_r(x['unsafe'])} | {x['classes']} |" for f, x in d["by_family"].items()
          if f in FAILURE_FAMILIES]
    L += ["", "## 6. Error analysis", "", f"Failed or unsafe conversations: {len(d['errors'])}. "
          f"Causes: {d['error_causes']}. Worked examples are added by hand from `error_analysis.csv`.", ""]
    L += ["## 7. Judge validation and label review", ""]
    if d["judge"]:
        L += [f"- Cohen's kappa for `{f}`: {x['kappa']} (n={x['n']})" for f, x in d["judge"].items()]
    else:
        L.append("- Judge not validated yet (no labeled human sheet).")
    rv = d["review"]
    L.append(f"- Goal-card review: {rv['reviewed']} cards reviewed, {rv['corrected']} corrected." if rv
             else "- Goal-card review: not recorded.")
    L += ["", "## 8. Limitations", ""] + [f"- {x}" for x in LIMITATIONS]
    s = d["savings"]
    L += ["", "## 9. Projected savings (projection, not a measurement)", ""]
    if s["status"] == "ok":
        L += [f"- Projected monthly savings: {s['monthly_usd']:,} USD", f"- Inputs: {s['inputs']}",
              f"- Legacy cost source: {d['legacy_cost_cfg'].get('source')}"]
    else:
        L.append("- not computed: it needs a sourced legacy cost per agent hour, complete prices, and at least one "
                 "safe automated resolution.")
    L += ["", "## Figures", ""] + [f"![{f}](figures/{f})" for f in figures]
    return "\n".join(L) + "\n"


def charts(d: dict, out_dir: Path) -> list[str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h = d["headline"]
    labels = ["Safe automated resolution", "Containment", "Correct outcome", "Unsafe outcomes"]
    vals = [h[k]["value"] or 0 for k in ("safe_automated_resolution", "containment", "correct_outcome", "unsafe")]
    fig, ax = plt.subplots(figsize=(8, 2.8), dpi=150)
    ax.barh(labels[::-1], vals[::-1], color=[ACCENT, SERIES, SERIES, SERIES])
    for i, v in enumerate(vals[::-1]):
        ax.text(v + 0.01, i, f"{v:.0%}", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, 1.12)
    ax.set_title("New system on the held-out simulated workload", loc="left", color=INK, fontsize=12, fontweight="bold")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    fig.tight_layout()
    fig.savefig(out_dir / "eval-headline.png")
    plt.close(fig)
    return ["eval-headline.png"]


def _read_csv(path: Path | None) -> list[dict] | None:
    if not path or not Path(path).exists():
        return None
    with Path(path).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--goals", type=Path, required=True)
    p.add_argument("--asis", type=Path, required=True)
    p.add_argument("--review", type=Path)
    p.add_argument("--labeled", type=Path)
    p.add_argument("--out", type=Path, default=Path("../reports"))
    p.add_argument("--date", required=True)
    a = p.parse_args(argv)
    from evalkit.config import load_config
    cfg = load_config()
    goals = read_goals(a.goals)
    records = [json.loads(x) for x in (a.run / "conversations.jsonl").read_text(encoding="utf-8").splitlines() if x]
    judg_path = a.run / "judgments.jsonl"
    judgments = [json.loads(x) for x in judg_path.read_text(encoding="utf-8").splitlines() if x] if judg_path.exists() else None
    review_rows = _read_csv(a.review)
    review = ({"reviewed": sum(bool(r["reviewer_ok"].strip()) for r in review_rows),
               "corrected": sum(r["reviewer_ok"].strip().lower() == "n" for r in review_rows)} if review_rows else None)
    err_path = a.run / "error_analysis.csv"
    causes = {(r["goal_id"], int(r["rep"])): r["cause"] for r in (_read_csv(err_path) or []) if r.get("cause")}
    manifest = json.loads((a.run / "run.json").read_text(encoding="utf-8")) if (a.run / "run.json").exists() else {}
    d = build(goals, records, json.loads(a.asis.read_text(encoding="utf-8")), cfg, judgments, _read_csv(a.labeled),
              review, causes, manifest)
    (a.run / "classifications.jsonl").write_text("".join(json.dumps(r) + "\n" for r in d["rows"]), encoding="utf-8")
    if not err_path.exists() and d["errors"]:
        with err_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(d["errors"][0]))
            w.writeheader()
            w.writerows(d["errors"])
    figures = charts(d, a.out / "figures")
    (a.out / f"eval-{a.date}.md").write_text(render(d, a.date, figures), encoding="utf-8")
    print(f"wrote {a.out / f'eval-{a.date}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
