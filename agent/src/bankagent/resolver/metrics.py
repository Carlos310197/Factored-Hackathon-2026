"""Evaluation metrics with counts, denominators and bootstrap intervals."""
import random
from collections import Counter
from collections.abc import Callable


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def summarize(outcomes: list[str]) -> dict:
    c, n = Counter(outcomes), len(outcomes)
    acted = c["act_correct"] + c["act_wrong"]
    asked_real = c["ask_hit"] + c["ask_miss"]
    return {"n": n, **{k: c[k] for k in ("act_correct", "act_wrong", "ask_hit", "ask_miss", "ask_nil", "nil_correct",
                                         "nil_wrong")},
            "coverage": _ratio(acted, n), "selective_accuracy": _ratio(c["act_correct"], acted),
            "wrong_action_rate": _ratio(c["act_wrong"], n),
            "top3_recall_when_asking": _ratio(c["ask_hit"], asked_real),
            "resolved_one_step": _ratio(c["act_correct"] + c["nil_correct"] + c["ask_hit"], n)}


def metric(name: str) -> Callable[[list[str]], float | None]:
    return lambda outcomes: summarize(outcomes)[name]


def bootstrap_ci(outcomes: list[str], fn: Callable, n_boot: int = 1000, seed: int = 0) -> tuple[float, float] | None:
    if not outcomes:
        return None
    rng, vals = random.Random(seed), []
    for _ in range(n_boot):
        v = fn([outcomes[rng.randrange(len(outcomes))] for _ in outcomes])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]


def paired_bootstrap(a: list[str], b: list[str], fn: Callable, n_boot: int = 1000,
                     seed: int = 0) -> tuple[float, float, float] | None:
    """Difference fn(a) - fn(b) on the same cases (same order), resampling cases jointly."""
    if len(a) != len(b):
        raise ValueError("paired bootstrap needs the same cases in the same order")
    base_a, base_b = fn(a), fn(b)
    if base_a is None or base_b is None:
        return None
    rng, diffs = random.Random(seed), []
    for _ in range(n_boot):
        idx = [rng.randrange(len(a)) for _ in a]
        va, vb = fn([a[i] for i in idx]), fn([b[i] for i in idx])
        if va is not None and vb is not None:
            diffs.append(va - vb)
    diffs.sort()
    return base_a - base_b, diffs[int(0.025 * (len(diffs) - 1))], diffs[int(0.975 * (len(diffs) - 1))]


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]
