"""Measures the thresholds in use; never tunes them (a held-out run must not pick thresholds).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import yaml

from evalkit.goals import read_goals

SIGNALS = ("reports_unauthorized_use", "legal_or_regulator_threat", "asks_for_human", "injection_attempt")


def max_p(rec: dict, signal: str) -> float | None:
    ps = [r["payload"]["answers"][signal]["p"] for r in (rec.get("after") or {}).get("records") or []
          if r.get("kind") == "jev" and r.get("node") == "understand"
          and signal in ((r.get("payload") or {}).get("answers") or {})]
    return max(ps) if ps else None


def _is_case(card, signal: str) -> bool:
    if signal == "injection_attempt":
        return card.group == "injection"
    return signal in card.expected.get("handoff_reasons", [])


def check(cards, records: list[dict], thresholds: dict[str, float]) -> list[dict]:
    by_id = {c.goal_id: c for c in cards}
    rows = []
    for signal, t in thresholds.items():
        pos, neg, alarm_groups, missed = [], [], Counter(), []
        for rec in records:
            p = max_p(rec, signal)
            if p is None:
                continue
            card = by_id[rec["goal_id"]]
            if _is_case(card, signal):
                pos.append(p)
                if p < t:
                    missed.append(rec["goal_id"])
            else:
                neg.append(p)
                if p >= t:
                    alarm_groups[card.group] += 1
        lo, hi = (max(neg) if neg else None), (min(pos) if pos else None)
        separable = lo is not None and hi is not None and hi > lo
        rows.append({"signal": signal, "threshold": t, "positives": len(pos), "caught": sum(p >= t for p in pos),
                     "negatives": len(neg), "false_alarms": sum(p >= t for p in neg), "min_positive": hi,
                     "max_negative": lo, "separable": separable, "clean_range": (lo, hi) if separable else None,
                     "false_alarm_groups": dict(alarm_groups.most_common()), "missed": sorted(set(missed))})
    return rows


def thresholds_from_yaml(path: Path) -> tuple[str, dict[str, float]]:
    y = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    flat = {**y.get("handoff_noul", {}), "injection_attempt": y["injection_attempt"]}
    return y["version"], {s: float(flat[s]) for s in SIGNALS}


def _f(x) -> str:
    return "–" if x is None else f"{x:.2f}"


def render(rows: list[dict], run: str, version: str) -> str:
    out = [f"## Threshold check: `{version}` on run `{run}`", "",
           "Highest Jev `understand` score per conversation. Real case = the goal expects this handoff reason "
           "(injection: an injection goal). Measured, not tuned: this run is held out.", "",
           "| Signal | Threshold | Real cases caught | False alarms | Lowest score, real case | Highest score, other | "
           "Any threshold in between is error-free |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        clean = f"yes ({_f(r['clean_range'][0])}–{_f(r['clean_range'][1])})" if r["separable"] else "no, scores overlap"
        out.append(f"| `{r['signal']}` | {r['threshold']:.2f} | {r['caught']}/{r['positives']} | "
                   f"{r['false_alarms']}/{r['negatives']} | {_f(r['min_positive'])} | {_f(r['max_negative'])} | {clean} |")
    out += ["", "Where the errors come from (goal group of each false alarm; goals with a missed real case):", ""]
    for r in rows:
        groups = ", ".join(f"{g} {n}" for g, n in r["false_alarm_groups"].items()) or "none"
        out.append(f"- `{r['signal']}`: false alarms by goal group: {groups}; missed: {', '.join(r['missed']) or 'none'}")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--goals", type=Path, required=True)
    p.add_argument("--thresholds", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    version, thresholds = thresholds_from_yaml(a.thresholds)
    records = [json.loads(x) for x in (a.run / "conversations.jsonl").read_text(encoding="utf-8").splitlines() if x]
    a.out.write_text(render(check(read_goals(a.goals), records, thresholds), a.run.name, version), encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
