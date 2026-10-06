from collections.abc import Callable
from pathlib import Path

from bankagent.resolver.metrics import summarize

MAX_WRONG = 0.02
THRESHOLDS_DIR = Path(__file__).resolve().parents[1] / "decisions"


def grid(lo: float, hi: float, step: float = 0.01) -> list[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 4) for i in range(n + 1)]


def choose(evaluate: Callable[[tuple], list[str]], points: list[tuple],
           max_wrong: float = MAX_WRONG) -> tuple[tuple, dict, list[dict]]:
    """Ties: better resolved_one_step, then stricter thresholds. None meets max_wrong: lowest wrong-action wins."""
    curve = []
    for p in points:
        s = summarize(evaluate(p))
        curve.append({"point": p, **s})
    feasible = [c for c in curve if (c["wrong_action_rate"] or 0.0) <= max_wrong]
    if feasible:
        best = max(feasible, key=lambda c: (c["coverage"] or 0.0, c["resolved_one_step"] or 0.0, sum(c["point"])))
        best = best | {"feasible": True}
    else:
        best = min(curve, key=lambda c: (c["wrong_action_rate"], -(c["coverage"] or 0.0))) | {"feasible": False}
    return best["point"], best, curve


def write_thresholds_v2(t: float, m: float, src: Path = THRESHOLDS_DIR / "thresholds.v1.yaml",
                        dst: Path = THRESHOLDS_DIR / "thresholds.v2.yaml") -> Path:
    lines, in_target = [], False
    for line in src.read_text(encoding="utf-8").splitlines():
        if in_target and line.startswith((" ", "\t")):
            continue
        in_target = False
        if line.startswith("version:"):
            line = "version: thresholds.v2"
        elif line.startswith("target_transaction:"):
            line, in_target = f"target_transaction: {{min_p: {t}, min_margin: {m}}}", True
        elif line.startswith("# Labeled synthetic"):
            line = ("# Labeled synthetic: target_transaction tuned on the resolver dev set for Jev + ranker; "
                    "rest as v1.")
        lines.append(line)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dst
